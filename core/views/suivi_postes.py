"""Vue « Suivi par poste » : production par machine, comme la liste de coulissage de la pesée.

Lecture seule, sauf l'action « Entrer en stock produit fini » (manuelle, sur un job clôturé).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from core.models.stock_produit_fini import ProduitFiniLot
from core.services.produit_fini import entrer_en_stock
from core.services.suivi_postes import (
    MACHINES, construire_arbre, liste_postes, lots_par_numero, palettes_a_plat, totaux, totaux_par_machine,
    url_avec,
)
from core.views.produit_fini import _acces_suivi_postes, _refuse

VUES = ('clients', 'palettes', 'lots')


@login_required
def suivi_postes(request):
    if not _acces_suivi_postes(request.user):
        return _refuse(request)

    poste = (request.GET.get('poste') or '').strip()
    recherche = (request.GET.get('q') or '').strip()
    date_debut_txt = request.GET.get('date_debut') or ''
    date_fin_txt = request.GET.get('date_fin') or ''
    date_debut = parse_date(date_debut_txt)
    date_fin = parse_date(date_fin_txt)
    vue = request.GET.get('vue') if request.GET.get('vue') in VUES else 'clients'

    # Paramètres courants, pour que les tuiles et onglets gardent les filtres
    courants = {'q': recherche, 'date_debut': date_debut_txt, 'date_fin': date_fin_txt}

    tuiles = [{
        'nom': 'Toutes les machines',
        'url': url_avec(courants, vue=vue),
        'actif': not poste,
        'res': None,
    }]
    machines = totaux_par_machine(recherche or None, date_debut, date_fin)
    for t in machines:
        tuiles.append({
            'nom': t['nom'],
            'url': url_avec(courants, vue=vue, poste=t['nom']),
            'actif': poste == t['nom'],
            'res': t['res'],
        })
    tuiles[0]['res'] = {
        'nb_bobines': sum(t['res']['nb_bobines'] for t in machines),
        'kg': sum(t['res']['kg'] for t in machines),
    }

    contexte = {
        'tuiles': tuiles,
        'vue': vue,
        'url_vue_clients': url_avec(courants, poste=poste, vue='clients'),
        'url_vue_palettes': url_avec(courants, poste=poste, vue='palettes'),
        'url_vue_lots': url_avec(courants, poste=poste, vue='lots'),
        'liste_postes': liste_postes(),
        'filtre_poste': poste,
        'filtre_q': recherche,
        'filtre_date_debut': date_debut_txt,
        'filtre_date_fin': date_fin_txt,
        'machine_selectionnee': poste if poste in MACHINES else '',
    }

    if vue == 'lots':
        groupes = lots_par_numero(poste or None, recherche or None, date_debut, date_fin)
        contexte['lots'] = groupes
        contexte['total'] = {
            'nb_bobines': sum(g['res']['nb_bobines'] for g in groupes),
            'kg': sum(g['res']['kg'] for g in groupes),
        }
    elif vue == 'palettes':
        lignes = palettes_a_plat(poste or None, recherche or None, date_debut, date_fin)
        contexte['palettes'] = lignes
        contexte['total'] = {
            'nb_bobines': sum(l['nb_bobines'] for l in lignes),
            'kg': sum(l['kg'] for l in lignes),
        }
    else:
        postes = construire_arbre(poste or None, recherche or None, date_debut, date_fin)
        contexte['postes'] = postes
        contexte['total'] = totaux(postes)

    return render(request, 'produit_fini/suivi_postes.html', contexte)


@login_required
@require_POST
def entrer_en_stock_produit_fini(request, lot_id):
    if not _acces_suivi_postes(request.user):
        return _refuse(request)
    lot = get_object_or_404(ProduitFiniLot, pk=lot_id)
    try:
        entrer_en_stock(lot, utilisateur=request.user)
        messages.success(request, f'Lot {lot.numero_lot} entré en stock produit fini.')
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect('suivi_postes')
