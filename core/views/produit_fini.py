"""Vues du stock produit fini (arbre, déstockage, annulation) et API de réception pesée."""
import hmac
import json
from collections import OrderedDict, defaultdict

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models.stock_produit_fini import (
    ProduitFiniBobine, ProduitFiniLot, ProduitFiniMouvement, ProduitFiniPalette,
)
from core.services.produit_fini import (
    annuler_mouvement, destocker, resume_bobines, traiter_evenement,
)

MAX_EVENEMENTS = 500


def _acces_stock(user):
    """Superutilisateur, ou permission « stock » de l'utilisateur.

    À adapter si le champ de permission a un autre nom dans UserModulePermission.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    from core.models import UserModulePermission
    perm = UserModulePermission.objects.filter(user=user).first()
    return bool(perm and getattr(perm, 'can_access_stock', False))


def _acces_suivi_postes(user):
    """Superutilisateur, ou permission « suivi par poste » (sous-module du Stock) de l'utilisateur."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    from core.models import UserModulePermission
    perm = UserModulePermission.objects.filter(user=user).first()
    return bool(perm and getattr(perm, 'can_access_suivi_postes', False))


def _refuse(request):
    messages.error(request, 'Accès au stock refusé.')
    return redirect('/')


@login_required
def stock_produit_fini_arbre(request):
    if not _acces_stock(request.user):
        return _refuse(request)

    # Seuls les lots entrés en stock produit fini apparaissent ici.
    lots = list(ProduitFiniLot.objects.select_related('client', 'produit')
                .filter(entree_stock_le__isnull=False))
    ids = [l.id for l in lots]
    palettes = list(ProduitFiniPalette.objects.filter(lot_id__in=ids).order_by('numero_palette'))
    bobines = list(ProduitFiniBobine.objects.filter(palette__lot_id__in=ids)
                   .select_related('palette').order_by('date_heure', 'id'))
    mouvements = list(ProduitFiniMouvement.objects.filter(lot_id__in=ids)
                      .select_related('utilisateur').order_by('-date', '-id'))

    pal_par_lot = defaultdict(list)
    for p in palettes:
        pal_par_lot[p.lot_id].append(p)
    bob_par_pal = defaultdict(list)
    bob_par_lot = defaultdict(list)
    for b in bobines:
        bob_par_pal[b.palette_id].append(b)
        bob_par_lot[b.palette.lot_id].append(b)
    mv_par_lot = defaultdict(list)
    for m in mouvements:
        mv_par_lot[m.lot_id].append(m)

    # arbre : client -> produit -> lot -> palette -> bobine
    arbre = OrderedDict()
    for lot in lots:
        cle_client = lot.client_nom or '—'
        cle_produit = lot.produit_nom or '—'
        pals = []
        for pal in pal_par_lot[lot.id]:
            bob = bob_par_pal[pal.id]
            pals.append({'obj': pal, 'res': resume_bobines(bob), 'bobines': bob})
        res_lot = resume_bobines(bob_par_lot[lot.id])
        node_client = arbre.setdefault(cle_client, {'lots_res': [], 'produits': OrderedDict()})
        node_prod = node_client['produits'].setdefault(cle_produit, {'lots': []})
        node_prod['lots'].append({'obj': lot, 'res': res_lot, 'palettes': pals,
                                  'mouvements': mv_par_lot[lot.id]})
        node_client['lots_res'].append(res_lot)

    # totaux client et produit
    resume_clients = []
    for nom, node in arbre.items():
        r = node['lots_res']
        total = {
            'nb_bobines': sum(x['nb_bobines'] for x in r),
            'kg_total': round(sum(x['kg_total'] for x in r), 3),
            'nb_restantes': sum(x['nb_restantes'] for x in r),
            'kg_restants': round(sum(x['kg_restants'] for x in r), 3),
            'nb_palettes': sum(len(pl['palettes']) for prod in node['produits'].values() for pl in prod['lots']),
        }
        produits = []
        for pnom, pnode in node['produits'].items():
            produits.append({'nom': pnom, 'lots': pnode['lots']})
        resume_clients.append({'nom': nom, 'res': total, 'produits': produits})

    return render(request, 'produit_fini/stock_arbre.html', {
        'clients': resume_clients,
        'nb_a_relier': sum(1 for l in lots if l.a_relier),
    })


@login_required
@require_POST
def destocker_produit_fini(request, lot_id):
    if not _acces_stock(request.user):
        return _refuse(request)
    lot = get_object_or_404(ProduitFiniLot, pk=lot_id)
    motif = request.POST.get('motif', '')
    action = request.POST.get('action', '')
    palette_ids = None
    if action == 'selection':
        palette_ids = [int(x) for x in request.POST.getlist('palette') if x.isdigit()]
        if not palette_ids:
            messages.error(request, 'Coche au moins une palette.')
            return redirect('stock_produit_fini')
    try:
        mv = destocker(lot, palette_ids=palette_ids, motif=motif, utilisateur=request.user)
        messages.success(request, f'{mv.nb_bobines} bobine(s) déstockée(s) — {mv.poids_kg} kg — {mv.palettes_libelle}')
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect('stock_produit_fini')


@login_required
@require_POST
def annuler_mouvement_produit_fini(request, mv_id):
    if not _acces_stock(request.user):
        return _refuse(request)
    mv = get_object_or_404(ProduitFiniMouvement, pk=mv_id)
    try:
        annuler_mouvement(mv, motif=request.POST.get('motif', ''), utilisateur=request.user)
        messages.success(request, 'Sortie annulée : les bobines sont de nouveau en stock.')
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect('stock_produit_fini')


@csrf_exempt
@require_POST
def api_pesee_sync(request):
    """Reçoit les événements de la pesée. Authentification : en-tête Authorization: Bearer <jeton>."""
    token = getattr(settings, 'PESEE_SYNC_TOKEN', '') or ''
    if not token:
        return JsonResponse({'erreur': 'Synchronisation non configurée sur le serveur.'}, status=503)
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer ') or not hmac.compare_digest(auth[7:].encode(), token.encode()):
        return JsonResponse({'erreur': 'Non autorisé.'}, status=401)
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({'erreur': 'JSON invalide.'}, status=400)
    evts = data.get('evenements') if isinstance(data, dict) else None
    if not isinstance(evts, list) or len(evts) > MAX_EVENEMENTS:
        return JsonResponse({'erreur': f'Attendu : liste "evenements" (max {MAX_EVENEMENTS}).'}, status=400)
    return JsonResponse({'resultats': [traiter_evenement(e) for e in evts]})
