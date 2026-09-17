import json
import datetime
from datetime import timedelta
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
from django.http import JsonResponse, HttpResponse
from django.utils import timezone

from ..models import (
    Client, ProductionOrder, OrdreFabrication, EtapeProduction, SemiProduit,
    SuiviProduction, ProcessType, Machine, Atelier, ProductionEntry,
)
from ..forms import (
    ProductionOrderForm, OrdreFabricationForm, EtapeProductionFormSet,
    SuiviProductionForm, ProcessTypeForm, OFLancementRapideForm,
    PlanificationEtapeFormSet,
)


# ===========================================================================
# --- CONFIGURATION DES ONGLETS PLANNING (STYLE EXCEL fb.pack) ---
# ===========================================================================

PLANNING_ATELIERS = [
    {
        'code': 'EXTRUSION', 'nom': 'Extrusion', 'icone': '🔥',
        'machine_types': ['EXT'], 'atelier_types': ['EXTRUSION'],
        'keywords': ['EXT', 'EXTRU'],
    },
    {
        'code': 'FLEXO', 'nom': 'Flexo / Impression', 'icone': '🎨',
        'machine_types': ['IMP'], 'atelier_types': ['IMPRESSION'],
        'keywords': ['IMP', 'FLEXO', 'PRINT'],
    },
    {
        'code': 'HELIO', 'nom': 'Hélio / Impression', 'icone': '🔄',
        'machine_types': ['HELIO'], 'atelier_types': ['IMPRESSION'],
        'keywords': ['HELIO', 'HELI'],
    },
    {
        'code': 'COMPLEXAGE', 'nom': 'Complexage', 'icone': '🧩',
        'machine_types': ['COMP'], 'atelier_types': ['COMPLEXAGE'],
        'keywords': ['COMP', 'COMPLEX'],
    },
    {
        'code': 'DECOUPE', 'nom': 'Découpe', 'icone': '✂️',
        'machine_types': ['DEC', 'DEC2', 'DCM'], 'atelier_types': ['DECOUPE'],
        'keywords': ['DEC', 'DECOUP', 'CUT', 'DCM', 'PANTHER'],
    },
    {
        'code': 'FOND_CARRE', 'nom': 'Fond Carré', 'icone': '🛍️',
        'machine_types': ['SAC_FC', 'SAC_SO'], 'atelier_types': ['SACS'],
        'keywords': ['SAC', 'FOND', 'FC', 'SOUD'],
    },
]

ENTRY_PROCESS_TAB = {
    'FLEXO': 'FLEXO',
    'HELIO': 'HELIO',
    'DECOUPE': 'DECOUPE',
    'DECOUPE2': 'DECOUPE',
}

JOURS_FR = ['LUNDI', 'MARDI', 'MERCREDI', 'JEUDI', 'VENDREDI', 'SAMEDI', 'DIMANCHE']


# ===========================================================================
# --- HELPERS DE PLANIFICATION ---
# ===========================================================================

def _jour_fr(d):
    if not d:
        return ""
    return JOURS_FR[d.weekday()]


def _dt(date, hour, minute=0):
    naive = datetime.datetime.combine(date, datetime.time(hour, minute))
    return timezone.make_aware(naive) if settings.USE_TZ else naive


def _parse_week(request):
    week_filter = request.GET.get('week', '')
    if not week_filter:
        now = datetime.date.today()
        y, w, _ = now.isocalendar()
        week_filter = f"{y}-W{w:02d}"
    try:
        ys, ws = week_filter.split('-W')
        iso_year, iso_week = int(ys), int(ws)
    except (ValueError, AttributeError):
        now = datetime.date.today()
        iso_year, iso_week, _ = now.isocalendar()
        week_filter = f"{iso_year}-W{iso_week:02d}"
    return week_filter, iso_year, iso_week


def _week_date_range(iso_year, iso_week):
    """
    Semaine fb.pack = Dimanche → Samedi (ISO week Mon-Sun décalée).
    Retourne (dimanche_debut, dimanche_fin) pour couvrir TOUTE la semaine.
    """
    jan4 = datetime.date(iso_year, 1, 4)
    iso_monday = jan4 + datetime.timedelta(days=-jan4.isoweekday() + 1, weeks=iso_week - 1)
    sunday_start = iso_monday - datetime.timedelta(days=1)
    sunday_end = iso_monday + datetime.timedelta(days=6)
    return sunday_start, sunday_end


def _qte_finale_str(etape):
    kg = etape.quantite_sortie or etape.quantite_entree or 0
    ml = etape.quantite_ml or 0
    nb = etape.nb_bobines or 0
    if ml:
        detail = []
        if kg:
            detail.append(f"{kg:.1f}KG")
        if nb:
            detail.append(f"{nb} BOBINES")
        if detail:
            return f"{ml:.0f}ML({','.join(detail)})"
        return f"{ml:.0f}ML"
    if kg:
        return f"{kg:.1f}KG"
    return "—"


def _etape_match_tab(etape, tab):
    mtype = (etape.machine.type if etape.machine else None) or ''
    mname = (etape.machine.name if etape.machine else '') or ''
    atype = None
    if etape.atelier:
        atype = etape.atelier.type_atelier
    elif etape.machine and etape.machine.atelier:
        atype = etape.machine.atelier.type_atelier
    pcode = etape.process_type.code.upper() if etape.process_type else ''
    mtype_u = mtype.upper() if mtype else ''
    mname_u = mname.upper()
    atype_u = (atype or '').upper()

    if mtype in tab['machine_types'] or mtype_u in [t.upper() for t in tab['machine_types']]:
        return True

    if tab['code'] == 'HELIO':
        if mtype_u == 'HELIO' or 'HELIO' in pcode or 'HELI' in pcode:
            return True
        return False

    if tab['code'] == 'FLEXO':
        if mtype_u == 'HELIO' or 'HELIO' in pcode or 'HELI' in pcode:
            return False
        if mtype in tab['machine_types']:
            return True
        if atype in tab['atelier_types']:
            return True
        for kw in tab['keywords']:
            if kw in pcode or kw in mname_u or kw in mtype_u:
                return True
        return False

    if atype in tab['atelier_types'] or atype_u in [a.upper() for a in tab.get('atelier_types', [])]:
        return True

    for kw in tab['keywords']:
        kw_u = kw.upper()
        if kw_u in pcode or kw_u in mname_u or kw_u in mtype_u or kw_u in atype_u:
            return True
    return False


def _entry_match_tab(entry, tab):
    mtype = entry.machine.type if entry.machine else None
    mname = (entry.machine.name if entry.machine else '') or ''
    if mtype in tab['machine_types']:
        return True
    mname_u = mname.upper()
    for kw in tab.get('keywords', []):
        if kw.upper() in mname_u:
            return True
    return ENTRY_PROCESS_TAB.get(entry.type_process) == tab['code']


def auto_planifier_etapes(of):
    if not of.date_lancement:
        return
    current_date = of.date_lancement
    for etape in of.etapes.order_by('numero_etape'):
        changed = False
        if not etape.date_planifiee:
            etape.date_planifiee = current_date
            changed = True
        if not etape.heure_debut_planifiee:
            etape.heure_debut_planifiee = datetime.time(8, 0)
            changed = True
        if not etape.heure_fin_planifiee:
            etape.heure_fin_planifiee = datetime.time(17, 0)
            changed = True
        if changed:
            etape.save(update_fields=['date_planifiee', 'heure_debut_planifiee', 'heure_fin_planifiee'])
        current_date = current_date + timedelta(days=1)


# ===========================================================================
# --- ANCIENS OF (COMPATIBILITÉ) ---
# ===========================================================================

@login_required
def production_view(request):
    ofs = ProductionOrder.objects.all().order_by('-start_time')
    return render(request, 'production_list.html', {'ofs': ofs})


@login_required
def add_production(request):
    if request.method == 'POST':
        form = ProductionOrderForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('production_view')
    else:
        form = ProductionOrderForm()
    return render(request, 'production_form.html', {
        'form': form, 'titre': 'Créer un Ordre de Fabrication'
    })


@login_required
def edit_production(request, id):
    of = get_object_or_404(ProductionOrder, id=id)
    if request.method == 'POST':
        form = ProductionOrderForm(request.POST, request.FILES, instance=of)
        if form.is_valid():
            form.save()
            return redirect('production_view')
    else:
        form = ProductionOrderForm(instance=of)
    return render(request, 'production_form.html', {
        'form': form, 'titre': f'Modifier OF {of.of_number}'
    })


# ===========================================================================
# --- LISTE DES OF (BACKLOG PLANIFICATEUR) ---
# ===========================================================================

@login_required
def of_list_view(request):
    statut = request.GET.get('statut', '')
    priorite = request.GET.get('priorite', '')
    client_id = request.GET.get('client', '')
    atelier_id = request.GET.get('atelier', '')
    machine_id = request.GET.get('machine', '')
    search = request.GET.get('q', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    ofs = OrdreFabrication.objects.select_related(
        'client', 'produit', 'cree_par'
    ).prefetch_related('etapes', 'etapes__machine', 'etapes__atelier').order_by('-date_creation')

    if statut:
        ofs = ofs.filter(statut=statut)
    if priorite:
        ofs = ofs.filter(priorite=priorite)
    if client_id:
        ofs = ofs.filter(client_id=client_id)
    if atelier_id:
        ofs = ofs.filter(etapes__atelier_id=atelier_id).distinct()
    if machine_id:
        ofs = ofs.filter(etapes__machine_id=machine_id).distinct()
    if search:
        ofs = ofs.filter(
            Q(numero_of__icontains=search) |
            Q(numero_lot__icontains=search) |
            Q(support__icontains=search) |
            Q(produit__name__icontains=search) |
            Q(client__name__icontains=search)
        )
    if date_from:
        ofs = ofs.filter(date_lancement__gte=date_from)
    if date_to:
        ofs = ofs.filter(date_lancement__lte=date_to)

    stats = {
        'total': ofs.count(),
        'brouillon': ofs.filter(statut='BROUILLON').count(),
        'en_cours': ofs.filter(statut='EN_COURS').count(),
        'termine': ofs.filter(statut='TERMINE').count(),
        'en_retard': sum(1 for of in ofs if of.est_en_retard),
    }

    context = {
        'ofs': ofs[:100],
        'stats': stats,
        'statut_choices': OrdreFabrication.STATUT_CHOICES,
        'priorite_choices': OrdreFabrication.PRIORITE_CHOICES,
        'clients': Client.objects.filter(status='ACTIVE'),
        'ateliers': Atelier.objects.filter(est_actif=True).order_by('ordre_affichage', 'nom'),
        'machines': Machine.objects.filter(est_active=True).order_by('name'),
        'selected_statut': statut,
        'selected_priorite': priorite,
        'selected_client': client_id,
        'selected_atelier': atelier_id,
        'selected_machine': machine_id,
        'search': search,
        'selected_date_from': date_from,
        'selected_date_to': date_to,
    }
    return render(request, 'of/of_list.html', context)


# ===========================================================================
# --- CRÉATION / ÉDITION OF (TECHNIQUE / ANCIENNE VUE) ---
# ===========================================================================

@login_required
def of_create_view(request):
    machine_warning = None
    machine_blocked = None
    machine_id = request.GET.get('machine')

    if machine_id:
        try:
            machine_check = Machine.objects.get(id=machine_id)
            peut_creer, msg = machine_check.peut_creer_of
            if not peut_creer:
                machine_blocked = msg
            elif msg:
                machine_warning = msg
        except Machine.DoesNotExist:
            pass

    if request.method == 'POST':
        form = OrdreFabricationForm(request.POST, request.FILES)
        formset = EtapeProductionFormSet(request.POST, prefix='etapes')

        blocked_messages = []
        warning_messages = []

        if form.is_valid():
            for etape_form in formset.forms:
                machine_val = etape_form.data.get(f"{etape_form.prefix}-machine")
                if machine_val:
                    try:
                        m = Machine.objects.get(id=machine_val)
                        peut, msg = m.peut_creer_of
                        if not peut:
                            blocked_messages.append(
                                f"Étape {etape_form.data.get(f'{etape_form.prefix}-numero_etape', '?')} — {m.name}: {msg}"
                            )
                        elif msg:
                            warning_messages.append(f"{m.name}: {msg}")
                    except Machine.DoesNotExist:
                        pass

            if blocked_messages:
                for msg in blocked_messages:
                    messages.error(request, msg)
            else:
                of = form.save(commit=False)
                of.cree_par = request.user
                of.save()

                if formset.is_valid():
                    etapes = formset.save(commit=False)
                    for etape in etapes:
                        etape.of = of
                        etape.save()
                    for obj in formset.deleted_objects:
                        obj.delete()

                auto_planifier_etapes(of)

                for msg in warning_messages:
                    messages.warning(request, msg)

                messages.success(request, f"OF {of.numero_of} créé avec succès !")
                return redirect('of_detail', of_id=of.id)
        else:
            messages.error(request, "Erreur dans le formulaire. Vérifiez les champs.")
    else:
        form = OrdreFabricationForm()
        formset = EtapeProductionFormSet(prefix='etapes', queryset=EtapeProduction.objects.none())

    context = {
        'form': form,
        'formset': formset,
        'process_types': ProcessType.objects.filter(est_actif=True),
        'machines': Machine.objects.filter(est_active=True).order_by('atelier__nom', 'name'),
        'titre': 'Nouvel Ordre de Fabrication',
        'machine_warning': machine_warning,
        'machine_blocked': machine_blocked,
        'machines_statuts': {
            str(m.id): {
                'status': m.status,
                'peut_creer': m.peut_creer_of[0],
                'message': m.peut_creer_of[1],
                'om_actif': str(m.om_actif) if m.om_actif else None,
            }
            for m in Machine.objects.filter(est_active=True)
        },
    }
    return render(request, 'of/of_form.html', context)


@login_required
def of_edit_view(request, of_id):
    of = get_object_or_404(OrdreFabrication, id=of_id)

    if request.method == 'POST':
        form = OrdreFabricationForm(request.POST, request.FILES, instance=of)
        formset = EtapeProductionFormSet(request.POST, instance=of, prefix='etapes')

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            auto_planifier_etapes(of)
            messages.success(request, f"OF {of.numero_of} mis à jour !")
            return redirect('of_detail', of_id=of.id)
        else:
            messages.error(request, "Erreur dans le formulaire.")
    else:
        form = OrdreFabricationForm(instance=of)
        formset = EtapeProductionFormSet(instance=of, prefix='etapes')

    context = {
        'form': form,
        'formset': formset,
        'of': of,
        'process_types': ProcessType.objects.filter(est_actif=True),
        'machines': Machine.objects.filter(est_active=True).order_by('atelier__nom', 'name'),
        'titre': f'Modifier OF {of.numero_of}',
    }
    return render(request, 'of/of_form.html', context)


@login_required
def of_detail_view(request, of_id):
    of = get_object_or_404(
        OrdreFabrication.objects.select_related('client', 'produit', 'cree_par'),
        id=of_id
    )

    etapes = of.etapes.select_related(
        'process_type', 'machine', 'operateur', 'atelier'
    ).prefetch_related('suivis', 'consommations').order_by('numero_etape')

    semi_produits = SemiProduit.objects.filter(of_origine=of).order_by('-date_creation')

    suivis = SuiviProduction.objects.filter(
        etape__of=of
    ).select_related('etape', 'operateur').order_by('-date_heure')[:50]

    etapes_data = []
    for etape in etapes:
        etapes_data.append({
            'nom': etape.get_nom_display(),
            'progression': etape.progression,
            'statut': etape.statut,
            'couleur': etape.get_statut_color(),
        })

    context = {
        'of': of,
        'etapes': etapes,
        'semi_produits': semi_produits,
        'suivis': suivis,
        'etapes_data_json': json.dumps(etapes_data),
    }
    return render(request, 'of/of_detail.html', context)


@login_required
def of_delete_view(request, of_id):
    of = get_object_or_404(OrdreFabrication, id=of_id)
    if request.method == 'POST':
        numero = of.numero_of
        of.delete()
        messages.success(request, f"OF {numero} supprimé.")
        return redirect('of_list')
    return render(request, 'of/of_confirm_delete.html', {'of': of})


@login_required
def of_changer_statut(request, of_id, nouveau_statut):
    of = get_object_or_404(OrdreFabrication, id=of_id)
    ancien_statut = of.statut

    if nouveau_statut in dict(OrdreFabrication.STATUT_CHOICES):
        of.statut = nouveau_statut
        if nouveau_statut == 'LANCE' and not of.date_lancement:
            of.date_lancement = timezone.now().date()
        elif nouveau_statut == 'TERMINE':
            of.date_fin_reelle = timezone.now().date()
        of.save()

        if nouveau_statut == 'LANCE':
            auto_planifier_etapes(of)

        messages.success(request, f"OF {of.numero_of} : {ancien_statut} → {nouveau_statut}")
    else:
        messages.error(request, "Statut invalide.")
    return redirect('of_detail', of_id=of_id)


# ===========================================================================
# --- LANCEMENT RAPIDE ---
# ===========================================================================

@login_required
def of_lancement_rapide(request):
    if request.method == 'POST':
        form = OFLancementRapideForm(request.POST)

        if form.is_valid():
            of = OrdreFabrication.objects.create(
                client=form.cleaned_data['client'],
                produit=form.cleaned_data['produit'],
                quantite_prevue=form.cleaned_data['quantite'],
                support=form.cleaned_data.get('support', ''),
                priorite=form.cleaned_data['priorite'],
                date_lancement=form.cleaned_data['date_lancement'],
                statut='LANCE',
                cree_par=request.user,
            )

            numero = 1
            date_courante = form.cleaned_data['date_lancement']

            def creer_etape(code_process, machine, qte, support='', dev=None):
                nonlocal numero, date_courante
                process = ProcessType.objects.filter(code=code_process).first()
                if not process:
                    process = ProcessType.objects.filter(
                        code__icontains=code_process[:4]
                    ).first()
                EtapeProduction.objects.create(
                    of=of,
                    numero_etape=numero,
                    process_type=process,
                    machine=machine,
                    quantite_entree=qte or form.cleaned_data['quantite'],
                    support=support or form.cleaned_data.get('support', ''),
                    developpement=dev or 0,
                    statut='PRET' if numero == 1 else 'EN_ATTENTE',
                    date_planifiee=date_courante,
                    heure_debut_planifiee=datetime.time(8, 0),
                    heure_fin_planifiee=datetime.time(17, 0),
                    date_prevue_debut=_dt(date_courante, 8, 0),
                    date_prevue_fin=_dt(date_courante, 17, 0),
                )
                numero += 1
                date_courante = date_courante + timedelta(days=1)

            if form.cleaned_data.get('etape_extrusion'):
                creer_etape(
                    'EXTRUSION',
                    form.cleaned_data.get('machine_extrusion'),
                    form.cleaned_data.get('qte_extrusion'),
                    support=form.cleaned_data.get('support_extrusion', ''),
                )

            if form.cleaned_data.get('etape_impression'):
                creer_etape(
                    'IMPRESSION',
                    form.cleaned_data.get('machine_impression'),
                    form.cleaned_data.get('qte_impression'),
                    support=form.cleaned_data.get('support_impression', ''),
                    dev=form.cleaned_data.get('developpement_impression'),
                )

            if form.cleaned_data.get('etape_complexage'):
                creer_etape(
                    'COMPLEXAGE',
                    form.cleaned_data.get('machine_complexage'),
                    form.cleaned_data.get('qte_complexage'),
                )

            if form.cleaned_data.get('etape_decoupe'):
                creer_etape(
                    'DECOUPE',
                    form.cleaned_data.get('machine_decoupe'),
                    form.cleaned_data.get('qte_decoupe'),
                )

            if form.cleaned_data.get('etape_fond_carre'):
                creer_etape(
                    'FOND_CARRE',
                    form.cleaned_data.get('machine_fond_carre'),
                    form.cleaned_data.get('qte_fond_carre'),
                )

            messages.success(request, f"OF {of.numero_of} lancé avec {of.nb_etapes} étapes !")
            return redirect('of_detail', of_id=of.id)
    else:
        form = OFLancementRapideForm()

    context = {'form': form, 'titre': 'Lancement Rapide OF'}
    return render(request, 'of/of_lancement_rapide.html', context)


# ===========================================================================
# --- ÉTAPES DE PRODUCTION ---
# ===========================================================================

@login_required
def etape_detail_view(request, etape_id):
    etape = get_object_or_404(
        EtapeProduction.objects.select_related('of', 'process_type', 'machine', 'operateur', 'atelier'),
        id=etape_id
    )

    suivis = etape.suivis.select_related('operateur').order_by('-date_heure')
    consommations = etape.consommations.select_related('material', 'lot')
    semi_produits = SemiProduit.objects.filter(etape_origine=etape)

    if request.method == 'POST':
        form = SuiviProductionForm(request.POST)
        if form.is_valid():
            suivi = form.save(commit=False)
            suivi.etape = etape
            suivi.operateur = request.user
            suivi.save()

            etape.quantite_sortie += suivi.quantite_produite
            etape.quantite_rebut += suivi.quantite_rebut

            if suivi.type_evenement == 'DEMARRAGE':
                etape.statut = 'EN_COURS'
                if not etape.date_debut_reel:
                    etape.date_debut_reel = timezone.now()
            elif suivi.type_evenement == 'FIN':
                etape.statut = 'TERMINE'
                etape.date_fin_reel = timezone.now()
            elif suivi.type_evenement == 'ARRET':
                etape.statut = 'PAUSE'

            etape.save()

            of = etape.of
            of.quantite_produite = sum(e.quantite_sortie for e in of.etapes.filter(statut='TERMINE'))
            of.quantite_rebut = sum(e.quantite_rebut for e in of.etapes.all())
            of.save()

            messages.success(request, "Suivi enregistré !")
            return redirect('etape_detail', etape_id=etape_id)
    else:
        form = SuiviProductionForm()

    context = {
        'etape': etape, 'of': etape.of, 'suivis': suivis,
        'consommations': consommations, 'semi_produits': semi_produits,
        'form': form,
    }
    return render(request, 'of/etape_detail.html', context)


@login_required
def etape_demarrer(request, etape_id):
    etape = get_object_or_404(EtapeProduction, id=etape_id)
    if etape.statut in ['EN_ATTENTE', 'PRET', 'PAUSE']:
        etape.statut = 'EN_COURS'
        if not etape.date_debut_reel:
            etape.date_debut_reel = timezone.now()
        etape.save()

        SuiviProduction.objects.create(
            etape=etape, operateur=request.user,
            type_evenement='DEMARRAGE', commentaire="Étape démarrée"
        )

        if etape.of.statut == 'LANCE':
            etape.of.statut = 'EN_COURS'
            etape.of.save()

        messages.success(request, f"Étape {etape.numero_etape} démarrée !")

    return redirect('etape_detail', etape_id=etape_id)


@login_required
def etape_terminer(request, etape_id):
    etape = get_object_or_404(EtapeProduction, id=etape_id)

    if request.method == 'POST':
        quantite_sortie = float(request.POST.get('quantite_sortie', 0))
        quantite_rebut = float(request.POST.get('quantite_rebut', 0))

        etape.quantite_sortie = quantite_sortie
        etape.quantite_rebut = quantite_rebut
        etape.statut = 'TERMINE'
        etape.date_fin_reel = timezone.now()
        etape.save()

        if etape.genere_semi_produit and quantite_sortie > 0:
            type_sp = 'FILM_EXTRUDE'
            if etape.process_type:
                if 'IMP' in etape.process_type.code.upper() or 'HELIO' in etape.process_type.code.upper():
                    type_sp = 'FILM_IMPRIME'
                elif 'COMP' in etape.process_type.code.upper():
                    type_sp = 'FILM_COMPLEXE'

            SemiProduit.objects.create(
                designation=f"SP - {etape.of.produit.name} - Étape {etape.numero_etape}",
                type_semi_produit=type_sp,
                of_origine=etape.of, etape_origine=etape,
                quantite=quantite_sortie, laize=etape.of.laize, conforme=True,
            )

        SuiviProduction.objects.create(
            etape=etape, operateur=request.user, type_evenement='FIN',
            quantite_produite=quantite_sortie, quantite_rebut=quantite_rebut,
            commentaire="Étape terminée"
        )

        of = etape.of
        if all(e.statut == 'TERMINE' for e in of.etapes.all()):
            of.statut = 'TERMINE'
            of.date_fin_reelle = timezone.now().date()
            of.quantite_produite = quantite_sortie

        of.quantite_rebut = sum(e.quantite_rebut for e in of.etapes.all())
        of.save()

        etape_suivante = EtapeProduction.objects.filter(
            of=of, numero_etape=etape.numero_etape + 1
        ).first()

        if etape_suivante:
            etape_suivante.statut = 'PRET'
            etape_suivante.quantite_entree = quantite_sortie
            etape_suivante.save()

        messages.success(request, f"Étape {etape.numero_etape} terminée !")
        return redirect('of_detail', of_id=etape.of.id)

    return render(request, 'of/etape_terminer.html', {'etape': etape})


# ===========================================================================
# --- SEMI-PRODUITS ---
# ===========================================================================

@login_required
def semi_produit_list(request):
    statut = request.GET.get('statut', '')
    type_sp = request.GET.get('type', '')

    semi_produits = SemiProduit.objects.select_related(
        'of_origine', 'etape_origine', 'emplacement'
    ).order_by('-date_creation')

    if statut:
        semi_produits = semi_produits.filter(statut=statut)
    if type_sp:
        semi_produits = semi_produits.filter(type_semi_produit=type_sp)

    stats = {
        'total': semi_produits.count(),
        'disponible': semi_produits.filter(statut='DISPONIBLE').count(),
        'reserve': semi_produits.filter(statut='RESERVE').count(),
        'total_kg': semi_produits.filter(statut='DISPONIBLE').aggregate(t=Sum('quantite'))['t'] or 0,
    }

    context = {
        'semi_produits': semi_produits[:100], 'stats': stats,
        'statut_choices': SemiProduit.STATUT_CHOICES,
        'type_choices': SemiProduit.TYPE_CHOICES,
        'selected_statut': statut, 'selected_type': type_sp,
    }
    return render(request, 'of/semi_produit_list.html', context)


@login_required
def semi_produit_detail(request, sp_id):
    sp = get_object_or_404(
        SemiProduit.objects.select_related(
            'of_origine', 'etape_origine', 'etape_destination', 'emplacement'
        ), id=sp_id
    )
    return render(request, 'of/semi_produit_detail.html', {'semi_produit': sp})


# ===========================================================================
# --- PROCESS TYPES ---
# ===========================================================================

@login_required
def process_type_list(request):
    process_types = ProcessType.objects.all().order_by('ordre_defaut')
    if request.method == 'POST':
        form = ProcessTypeForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Type de processus créé !")
            return redirect('process_type_list')
    else:
        form = ProcessTypeForm()

    return render(request, 'of/process_type_list.html', {'process_types': process_types, 'form': form})


@login_required
def process_type_delete(request, pt_id):
    pt = get_object_or_404(ProcessType, id=pt_id)
    if request.method == 'POST':
        pt.delete()
        messages.success(request, "Type de processus supprimé.")
    return redirect('process_type_list')


# ===========================================================================
# --- API JSON STATS OF ---
# ===========================================================================

@login_required
def of_stats_api(request):
    statuts = {code: OrdreFabrication.objects.filter(statut=code).count() for code, _ in OrdreFabrication.STATUT_CHOICES}
    date_30j = timezone.now().date() - timedelta(days=30)
    ofs_recents = OrdreFabrication.objects.filter(
        date_lancement__gte=date_30j
    ).values('date_lancement').annotate(
        qte=Sum('quantite_produite')
    ).order_by('date_lancement')

    prod_par_jour = {str(of['date_lancement']): of['qte'] or 0 for of in ofs_recents}
    top_clients = OrdreFabrication.objects.values(
        'client__name'
    ).annotate(
        total=Sum('quantite_prevue')
    ).order_by('-total')[:5]

    return JsonResponse({
        'statuts': statuts,
        'production_par_jour': prod_par_jour,
        'top_clients': list(top_clients),
    })


# ===========================================================================
# --- PLANNING GANTT PAR MACHINE ---
# ===========================================================================

@login_required
def production_gantt(request):
    machines = Machine.objects.exclude(name__icontains="Nettoyage").order_by('atelier', 'name')

    week_filter, iso_year, iso_week = _parse_week(request)

    entries_qs = ProductionEntry.objects.filter(
        date__iso_year=iso_year,
        date__week=iso_week
    ).select_related('machine', 'client', 'of_lie')

    etapes_qs = EtapeProduction.objects.filter(
        Q(date_planifiee__iso_year=iso_year, date_planifiee__week=iso_week) |
        Q(date_debut_reel__iso_year=iso_year, date_debut_reel__week=iso_week) |
        Q(
            of__date_creation__iso_year=iso_year,
            of__date_creation__week=iso_week,
            date_debut_reel__isnull=True,
            date_planifiee__isnull=True
        )
    ).select_related('machine', 'of', 'of__client', 'of__produit', 'process_type')

    machine_gantt = []
    total_jobs_count = 0
    total_en_cours_count = 0

    for m in machines:
        m_items = []

        m_entries = entries_qs.filter(machine=m).order_by('date', 'heure_debut')
        for e in m_entries:
            total_jobs_count += 1
            is_today = (e.date == datetime.date.today())
            if is_today:
                total_en_cours_count += 1

            m_items.append({
                'id': f"entry_{e.id}",
                'title': e.produit,
                'client_name': e.client.name if e.client else "Client non spécifié",
                'lot_or_of': f"Lot : {e.lot}" if e.lot else (f"OF : {e.of_lie.numero_of}" if e.of_lie else f"JOB-{e.id}"),
                'type_process': e.get_type_process_display(),
                'date': e.date,
                'heure_debut': e.heure_debut,
                'heure_fin': e.heure_fin,
                'quantite_str': f"{e.prod_kg or e.quantite_lancee} kg / {e.prod_ml} ML",
                'support': e.support,
                'source_type': 'SAISIE_DIRECTE',
                'status': 'IN_PROGRESS' if is_today else 'DONE',
                'status_label': 'Production Directe' if is_today else 'Terminé',
                'badge_color': 'emerald' if is_today else 'blue',
                'duree_str': e.temps_ouverture,
                'is_of': False,
            })

        m_etapes = etapes_qs.filter(machine=m)
        m_etapes = sorted(m_etapes, key=lambda x: x.date_debut_reel or x.date_planifiee or x.of.date_creation)

        for et in m_etapes:
            total_jobs_count += 1
            if et.statut == 'EN_COURS':
                total_en_cours_count += 1

            dt_start_date = et.date_planifiee or (et.date_debut_reel.date() if et.date_debut_reel else et.of.date_creation.date())
            dt_start_time = et.heure_debut_planifiee or (et.date_debut_reel.time() if et.date_debut_reel else None)
            dt_end_time = et.heure_fin_planifiee or (et.date_fin_reel.time() if et.date_fin_reel else None)

            m_items.append({
                'id': f"etape_{et.id}",
                'title': f"OF #{et.of.numero_of} - {et.get_nom_display()}",
                'client_name': et.of.client.name if et.of.client else "",
                'lot_or_of': et.numero_lot_etape or et.of.numero_lot or f"OF #{et.of.numero_of}",
                'type_process': et.process_type.nom if et.process_type else "Process",
                'date': dt_start_date,
                'heure_debut': dt_start_time,
                'heure_fin': dt_end_time,
                'quantite_str': _qte_finale_str(et),
                'support': et.support or et.of.support,
                'source_type': 'OF_ETAPE',
                'status': et.statut,
                'status_label': et.get_statut_display(),
                'badge_color': 'amber' if et.statut == 'EN_COURS' else ('purple' if et.statut == 'TERMINE' else 'cyan'),
                'duree_str': f"{et.temps_arret_minutes} min",
                'is_of': True,
                'shift': et.get_shift_display(),
                'equipe': et.get_equipe_display(),
            })

        m_items = sorted(m_items, key=lambda x: (x['date'], x['heure_debut'] or datetime.time.min))

        machine_gantt.append({
            'machine': m,
            'items': m_items,
            'count': len(m_items)
        })

    context = {
        'machine_gantt': machine_gantt,
        'selected_week': week_filter,
        'week_display': f"Semaine {iso_week} ({iso_year})",
        'total_jobs_count': total_jobs_count,
        'total_en_cours_count': total_en_cours_count,
        'total_machines_count': len(machines),
    }
    return render(request, 'production/planning_gantt.html', context)


# ===========================================================================
# --- PLANNING PAR ATELIER (TABLEAU EXCEL FB.PACK) ---
# ===========================================================================

@login_required
def planning_atelier_view(request):
    week_filter, iso_year, iso_week = _parse_week(request)
    date_start, date_end = _week_date_range(iso_year, iso_week)

    selected_atelier = request.GET.get('atelier', 'EXTRUSION')
    if selected_atelier not in [a['code'] for a in PLANNING_ATELIERS]:
        selected_atelier = 'EXTRUSION'

    etapes_qs = EtapeProduction.objects.filter(
        Q(date_planifiee__iso_year=iso_year, date_planifiee__week=iso_week) |
        Q(date_debut_reel__iso_year=iso_year, date_debut_reel__week=iso_week) |
        Q(date_planifiee__gte=date_start, date_planifiee__lte=date_end) |
        Q(date_debut_reel__date__gte=date_start, date_debut_reel__date__lte=date_end) |
        Q(
            date_planifiee__isnull=True,
            date_debut_reel__isnull=True,
            statut__in=['EN_ATTENTE', 'PRET', 'EN_COURS']
        )
    ).select_related(
        'of', 'of__client', 'of__produit', 'machine', 'machine__atelier',
        'process_type', 'atelier'
    ).exclude(of__statut='ANNULE').distinct()

    entries_qs = ProductionEntry.objects.filter(
        Q(date__iso_year=iso_year, date__week=iso_week) |
        Q(date__gte=date_start, date__lte=date_end)
    ).select_related('machine', 'machine__atelier', 'client', 'of_lie').distinct()

    tabs = []
    selected_rows = []
    selected_machines = []

    for tab in PLANNING_ATELIERS:
        rows = []

        for et in etapes_qs:
            if not _etape_match_tab(et, tab):
                continue
            
            dt = et.date_planifiee or (et.date_debut_reel.date() if et.date_debut_reel else et.of.date_creation.date())
            
            rows.append({
                'source': 'OF',
                'etape_id': et.id,
                'jour': _jour_fr(dt),
                'date': dt,
                'heure_debut': et.heure_debut_planifiee,
                'heure_fin': et.heure_fin_planifiee,
                'shift': et.get_shift_display() or '—',
                'equipe': et.get_equipe_display() or '—',
                'ordre': et.ordre_passage,
                'client': et.of.client.name if et.of.client else '—',
                'produit': et.of.produit.name if et.of.produit else '—',
                'support': et.support or et.of.support or '',
                'qte_finale': _qte_finale_str(et),
                'developpement': et.developpement or '',
                'lot': et.numero_lot_etape or et.of.numero_lot or '',
                'observation': et.observation or et.of.observation or '',
                'machine': et.machine.name if et.machine else '—',
                'of_id': et.of.id,
                'of_numero': et.of.numero_of,
                'statut': et.statut,
                'statut_label': et.get_statut_display(),
                'color': et.get_statut_color(),
            })

        for e in entries_qs:
            if not _entry_match_tab(e, tab):
                continue
            kg = e.prod_kg or e.quantite_lancee or 0
            ml = e.prod_ml or 0
            qte = f"{ml:.0f}ML({kg:.1f}KG)" if ml else f"{kg:.1f}KG"
            rows.append({
                'source': 'SAISIE',
                'etape_id': None,
                'jour': _jour_fr(e.date),
                'date': e.date,
                'heure_debut': e.heure_debut,
                'heure_fin': e.heure_fin,
                'shift': '—',
                'equipe': '—',
                'ordre': 0,
                'client': e.client.name if e.client else '—',
                'produit': e.produit,
                'support': e.support or '',
                'qte_finale': qte,
                'developpement': '',
                'lot': e.lot or '',
                'observation': '',
                'machine': e.machine.name if e.machine else '—',
                'of_id': e.of_lie.id if e.of_lie else None,
                'of_numero': e.of_lie.numero_of if e.of_lie else '',
                'statut': 'TERMINE',
                'statut_label': 'Saisie directe',
                'color': 'blue',
            })

        rows = sorted(rows, key=lambda r: (r['date'], r['machine'], r['ordre'] or 0, r['heure_debut'] or datetime.time.min))

        tab_data = {
            'code': tab['code'],
            'nom': tab['nom'],
            'icone': tab['icone'],
            'count': len(rows),
        }
        tabs.append(tab_data)

        if tab['code'] == selected_atelier:
            selected_rows = rows
            selected_machines = Machine.objects.filter(
                est_active=True, type__in=tab['machine_types']
            ).order_by('name')

    stats = {
        'nb_lignes': len(selected_rows),
        'nb_of': len(set(r['of_numero'] for r in selected_rows if r['of_numero'])),
        'nb_clients': len(set(r['client'] for r in selected_rows)),
    }

    context = {
        'tabs': tabs,
        'selected_atelier': selected_atelier,
        'rows': selected_rows,
        'machines_atelier': selected_machines,
        'stats': stats,
        'selected_week': week_filter,
        'week_display': f"Semaine {iso_week} ({iso_year})",
    }
    return render(request, 'of/planning_atelier.html', context)


# ===========================================================================
# --- L'ÉCRAN DÉDIÉ AU PLANIFICATEUR (ORDONNANCEMENT) ---
# ===========================================================================

@login_required
def planification_ordonnancer(request, of_id):
    of = get_object_or_404(OrdreFabrication.objects.select_related('client', 'produit'), id=of_id)

    if request.GET.get('generer_etapes'):
        codes_defaut = ['EXTRUSION', 'IMPRESSION', 'COMPLEXAGE', 'DECOUPE']
        num = 1
        for code in codes_defaut:
            pt = ProcessType.objects.filter(code__icontains=code[:4]).first()
            EtapeProduction.objects.create(
                of=of,
                numero_etape=num,
                process_type=pt,
                quantite_entree=of.quantite_prevue or 0,
                support=of.support or '',
                statut='PRET' if num == 1 else 'EN_ATTENTE',
                date_planifiee=of.date_lancement or timezone.now().date(),
                heure_debut_planifiee=datetime.time(8, 0),
                heure_fin_planifiee=datetime.time(16, 0),
                shift='MATIN',
                equipe='A'
            )
            num += 1
        messages.success(request, f"4 étapes de production créées automatiquement pour l'OF {of.numero_of} ✓")
        return redirect('planification_ordonnancer', of_id=of.id)

    if request.method == 'POST':
        nouveau_lot = (request.POST.get('numero_lot') or '').strip()
        formset = PlanificationEtapeFormSet(request.POST, instance=of, prefix='etapes')

        if formset.is_valid():
            if nouveau_lot:
                of.numero_lot = nouveau_lot

            instances = formset.save(commit=False)

            for obj in formset.deleted_objects:
                obj.delete()

            existing_nums = list(of.etapes.values_list('numero_etape', flat=True))
            next_num = (max(existing_nums) if existing_nums else 0) + 1

            for instance in instances:
                instance.of = of
                if not instance.numero_etape:
                    instance.numero_etape = next_num
                    next_num += 1
                if not instance.statut:
                    instance.statut = 'EN_ATTENTE'
                instance.save()

            if of.numero_lot:
                of.etapes.filter(
                    Q(numero_lot_etape__isnull=True) | Q(numero_lot_etape='')
                ).update(numero_lot_etape=of.numero_lot)

            if of.statut == 'BROUILLON':
                of.statut = 'LANCE'
                if not of.date_lancement:
                    of.date_lancement = timezone.now().date()

            of.save()
            messages.success(request, f"OF {of.numero_of} planifié avec succès ✓ — Lot : {of.numero_lot or '—'}")
            return redirect('planning_atelier')
        else:
            messages.error(request, "Erreur dans les champs de planification. Détails ci-dessous.")
    else:
        formset = PlanificationEtapeFormSet(instance=of, prefix='etapes')

    today = datetime.date.today()
    iso_year, iso_week, _ = today.isocalendar()
    current_week_str = f"{iso_year}-W{iso_week:02d}"

    return render(request, 'of/planification_ordonnancer.html', {
        'of': of,
        'formset': formset,
        'current_week_str': current_week_str,
    })


# ===========================================================================
# --- EXPORT EXCEL DU PLANNING (STYLE FB.PACK — Découpe 2 machines) ---
# ===========================================================================

def _is_grande_decoupe(machine_name):
    """DCM Panther 1350 = Grande ; le reste = Petite."""
    if not machine_name:
        return False
    name = machine_name.upper()
    return '1350' in name


@login_required
def export_planning_excel(request):
    week_filter, iso_year, iso_week = _parse_week(request)
    date_start, date_end = _week_date_range(iso_year, iso_week)

    etapes_qs = EtapeProduction.objects.filter(
        Q(date_planifiee__iso_year=iso_year, date_planifiee__week=iso_week) |
        Q(date_debut_reel__iso_year=iso_year, date_debut_reel__week=iso_week) |
        Q(date_planifiee__gte=date_start, date_planifiee__lte=date_end) |
        Q(date_debut_reel__date__gte=date_start, date_debut_reel__date__lte=date_end)
    ).select_related(
        'of', 'of__client', 'of__produit', 'machine', 'machine__atelier',
        'process_type', 'atelier'
    ).exclude(of__statut='ANNULE').distinct()

    entries_qs = ProductionEntry.objects.filter(
        Q(date__iso_year=iso_year, date__week=iso_week) |
        Q(date__gte=date_start, date__lte=date_end)
    ).select_related('machine', 'machine__atelier', 'client', 'of_lie').distinct()

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # Styles
    DARK_BLUE_FILL = PatternFill(start_color='143C5E', end_color='143C5E', fill_type='solid')
    WHITE_BOLD_FONT = Font(color='FFFFFF', bold=True, name='Calibri', size=11)
    BIG_TITLE_FONT = Font(color='FFFFFF', bold=True, name='Calibri', size=16)
    HEADER_FONT = Font(color='FFFFFF', bold=True, name='Calibri', size=11)
    CENTER_ALIGN = Alignment(horizontal='center', vertical='center', wrap_text=True)
    LEFT_ALIGN = Alignment(horizontal='left', vertical='center', wrap_text=True)
    THIN_BORDER = Border(
        left=Side(style='thin', color='000000'),
        right=Side(style='thin', color='000000'),
        top=Side(style='thin', color='000000'),
        bottom=Side(style='thin', color='000000')
    )
    GREEN_FILL = PatternFill(start_color='E2EFDA', end_color='E2EFDA', fill_type='solid')
    PURPLE_FILL = PatternFill(start_color='E4DFEC', end_color='E4DFEC', fill_type='solid')
    WHITE_FILL = PatternFill(start_color='FFFFFF', end_color='FFFFFF', fill_type='solid')

    for tab in PLANNING_ATELIERS:
        rows_data = []

        for et in etapes_qs:
            if not _etape_match_tab(et, tab):
                continue
            dt = et.date_planifiee or (et.date_debut_reel.date() if et.date_debut_reel else None)
            if not dt:
                continue
            rows_data.append({
                'date_obj': dt,
                'machine_name': et.machine.name if et.machine else '—',
                'ordre': et.ordre_passage or 0,
                'heure_debut_obj': et.heure_debut_planifiee or datetime.time.min,
                'jour': _jour_fr(dt),
                'date_str': dt.strftime('%d/%m/%Y'),
                'client': et.of.client.name if et.of.client else '',
                'produit': et.of.produit.name if et.of.produit else '',
                'support': et.support or et.of.support or '',
                'qte': _qte_finale_str(et),
                'dev': et.developpement or '',
                'lot': et.numero_lot_etape or et.of.numero_lot or '',
                'obs': et.observation or et.of.observation or '',
            })

        for e in entries_qs:
            if not _entry_match_tab(e, tab):
                continue
            if not e.date:
                continue
            kg = e.prod_kg or e.quantite_lancee or 0
            ml = e.prod_ml or 0
            qte = f"{ml:.0f}ML({kg:.1f}KG)" if ml else f"{kg:.1f}KG"
            rows_data.append({
                'date_obj': e.date,
                'machine_name': e.machine.name if e.machine else '—',
                'ordre': 0,
                'heure_debut_obj': e.heure_debut or datetime.time.min,
                'jour': _jour_fr(e.date),
                'date_str': e.date.strftime('%d/%m/%Y'),
                'client': e.client.name if e.client else '',
                'produit': e.produit,
                'support': e.support or '',
                'qte': qte,
                'dev': '',
                'lot': e.lot or '',
                'obs': '',
            })

        if not rows_data:
            continue

        rows_data = sorted(rows_data, key=lambda r: (r['date_obj'], r['machine_name'], r['ordre'], r['heure_debut_obj']))
        sheet_title = tab['nom'][:31].replace('/', '-')
        ws = wb.create_sheet(title=sheet_title)

        # =====================================================================
        # 🔥 CAS SPÉCIAL : DÉCOUPE = 2 colonnes (Grande 1350 | Petite)
        # =====================================================================
        if tab['code'] == 'DECOUPE':
            # --- Ligne 1 : Titre ---
            ws.merge_cells('A1:I1')
            title_cell = ws['A1']
            title_cell.value = f"  fb.pack          PLANNING PRÉVENTIF — DECOUPE | SEMAINE {iso_week}"
            title_cell.fill = DARK_BLUE_FILL
            title_cell.font = BIG_TITLE_FONT
            title_cell.alignment = Alignment(horizontal='left', vertical='center', indent=1)
            ws.row_dimensions[1].height = 36

            # --- Ligne 2 : Groupes Grande / Petite / Remarque ---
            ws.merge_cells('A2:B2')  # zone jour
            ws.merge_cells('C2:E2')  # Grande découpeuse
            ws.merge_cells('F2:H2')  # Petite découpeuse
            # I2 = REMARQUE

            for col in range(1, 10):
                cell = ws.cell(row=2, column=col)
                cell.fill = DARK_BLUE_FILL
                cell.font = HEADER_FONT
                cell.alignment = CENTER_ALIGN
                cell.border = THIN_BORDER

            ws['C2'].value = "Grande découpeuse"
            ws['F2'].value = "Petite découpeuse"
            ws['I2'].value = "REMARQUE"
            ws.row_dimensions[2].height = 22

            # --- Ligne 3 : Sous-en-têtes ---
            sub_headers = ['Jour', '', 'Client', 'Produit', 'N°LOT', 'Client', 'Produit', 'N°LOT', '']
            for col_num, h in enumerate(sub_headers, 1):
                cell = ws.cell(row=3, column=col_num, value=h)
                cell.fill = DARK_BLUE_FILL
                cell.font = WHITE_BOLD_FONT
                cell.alignment = CENTER_ALIGN
                cell.border = THIN_BORDER
            ws['A3'].value = "Jour"
            ws.merge_cells('A3:B3')
            ws.row_dimensions[3].height = 20

            # --- Grouper par date ---
            from collections import defaultdict
            by_date = defaultdict(lambda: {'grande': [], 'petite': [], 'jour': '', 'date_str': ''})

            for item in rows_data:
                key = item['date_obj']
                by_date[key]['jour'] = item['jour']
                by_date[key]['date_str'] = item['date_str']
                if _is_grande_decoupe(item['machine_name']):
                    by_date[key]['grande'].append(item)
                else:
                    by_date[key]['petite'].append(item)

            # Trier les dates
            sorted_dates = sorted(by_date.keys())

            current_row = 4
            color_toggle = True

            for dt in sorted_dates:
                day_data = by_date[dt]
                grandes = day_data['grande']
                petites = day_data['petite']
                n_rows = max(len(grandes), len(petites), 1)
                color_toggle = not color_toggle
                row_fill = GREEN_FILL if color_toggle else PURPLE_FILL

                for i in range(n_rows):
                    g = grandes[i] if i < len(grandes) else None
                    p = petites[i] if i < len(petites) else None

                    if i == 0:
                        ws.cell(row=current_row, column=1, value=day_data['jour'])
                        ws.cell(row=current_row, column=2, value=day_data['date_str'])
                    else:
                        ws.cell(row=current_row, column=1, value='')
                        ws.cell(row=current_row, column=2, value='')

                    if g:
                        ws.cell(row=current_row, column=3, value=g['client'])
                        ws.cell(row=current_row, column=4, value=g['produit'])
                        ws.cell(row=current_row, column=5, value=g['lot'])
                    else:
                        ws.cell(row=current_row, column=3, value='')
                        ws.cell(row=current_row, column=4, value='')
                        ws.cell(row=current_row, column=5, value='')

                    if p:
                        ws.cell(row=current_row, column=6, value=p['client'])
                        ws.cell(row=current_row, column=7, value=p['produit'])
                        ws.cell(row=current_row, column=8, value=p['lot'])
                    else:
                        ws.cell(row=current_row, column=6, value='')
                        ws.cell(row=current_row, column=7, value='')
                        ws.cell(row=current_row, column=8, value='')

                    obs = ''
                    if g and g.get('obs'):
                        obs = g['obs']
                    elif p and p.get('obs'):
                        obs = p['obs']
                    ws.cell(row=current_row, column=9, value=obs)

                    for col in range(1, 10):
                        cell = ws.cell(row=current_row, column=col)
                        cell.fill = row_fill
                        cell.border = THIN_BORDER
                        cell.alignment = CENTER_ALIGN if col in (1, 2, 5, 8) else LEFT_ALIGN
                        if col == 1:
                            cell.font = Font(bold=True, name='Calibri', size=10)

                    ws.row_dimensions[current_row].height = 18
                    current_row += 1

            widths = {
                'A': 12, 'B': 12,
                'C': 22, 'D': 28, 'E': 12,
                'F': 22, 'G': 28, 'H': 12,
                'I': 20,
            }
            for col, w in widths.items():
                ws.column_dimensions[col].width = w

            continue  # Fin Découpe, on passe à l'onglet suivant

        # =====================================================================
        # AUTRES ATELIERS (layout standard)
        # =====================================================================
        if tab['code'] == 'EXTRUSION':
            headers = ['date', 'client', 'produit', 'support', 'quantité finale', 'N° LOT', 'observation']
        elif tab['code'] in ['FLEXO', 'HELIO']:
            headers = ['date', 'client', 'produit', 'support', 'quantité finale (QTE imprime)', 'developpement', 'N° LOT', 'observation']
        elif tab['code'] == 'COMPLEXAGE':
            headers = ['Jour', 'Client', 'Produit', 'Quantité finie', 'N° lot', 'observation']
        elif tab['code'] == 'FOND_CARRE':
            headers = ['Jour', 'Client', 'Produit', 'Quantité', 'OBS']
        else:
            headers = ['Jour', 'Date', 'Client', 'Produit', 'Support', 'Qté', 'Lot', 'Obs']

        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
        title_cell = ws.cell(row=1, column=1)
        title_cell.value = f"  fb.pack          PLANNING PRÉVENTIF — {tab['code']} | SEMAINE {iso_week}"
        title_cell.fill = DARK_BLUE_FILL
        title_cell.font = BIG_TITLE_FONT
        title_cell.alignment = Alignment(horizontal='left', vertical='center', indent=1)
        ws.row_dimensions[1].height = 36

        ws.append(headers)
        ws.row_dimensions[2].height = 22
        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=2, column=col_num)
            cell.fill = DARK_BLUE_FILL
            cell.font = WHITE_BOLD_FONT
            cell.alignment = CENTER_ALIGN
            cell.border = THIN_BORDER

        current_day = None
        color_toggle = True

        for item in rows_data:
            if item['jour'] != current_day:
                current_day = item['jour']
                color_toggle = not color_toggle

            row_fill = GREEN_FILL if color_toggle else WHITE_FILL
            jour_date = f"{item['jour']}\n{item['date_str']}"

            if tab['code'] == 'EXTRUSION':
                row_to_append = [jour_date, item['client'], item['produit'], item['support'], item['qte'], item['lot'], item['obs']]
            elif tab['code'] in ['FLEXO', 'HELIO']:
                row_to_append = [jour_date, item['client'], item['produit'], item['support'], item['qte'], item['dev'], item['lot'], item['obs']]
            elif tab['code'] == 'COMPLEXAGE':
                row_to_append = [jour_date, item['client'], item['produit'], item['qte'], item['lot'], item['obs']]
            elif tab['code'] == 'FOND_CARRE':
                row_to_append = [jour_date, item['client'], item['produit'], item['qte'], item['obs']]
            else:
                row_to_append = [item['jour'], item['date_str'], item['client'], item['produit'], item['support'], item['qte'], item['lot'], item['obs']]

            ws.append(row_to_append)
            current_row = ws.max_row

            for col_num in range(1, len(headers) + 1):
                cell = ws.cell(row=current_row, column=col_num)
                cell.fill = row_fill
                cell.border = THIN_BORDER
                if col_num == 1 or headers[col_num - 1].lower() in [
                    'quantité finale', 'quantité', 'quantité finie',
                    'quantité finale (qte imprime)', 'n° lot', 'n°lot', 'developpement'
                ]:
                    cell.alignment = CENTER_ALIGN
                else:
                    cell.alignment = LEFT_ALIGN

        for col_num in range(1, len(headers) + 1):
            column_letter = openpyxl.utils.get_column_letter(col_num)
            header_text = headers[col_num - 1].lower()
            if header_text in ['date', 'jour']:
                ws.column_dimensions[column_letter].width = 14
            elif header_text in ['client', 'produit', 'observation', 'obs']:
                ws.column_dimensions[column_letter].width = 28
            elif 'quantit' in header_text or header_text == 'support':
                ws.column_dimensions[column_letter].width = 26
            else:
                ws.column_dimensions[column_letter].width = 14

    if not wb.sheetnames:
        ws_vide = wb.create_sheet("Vide")
        ws_vide['A1'] = f"Aucune planification trouvée pour la Semaine {iso_week} de l'année {iso_year}."

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="fbpack_Planning_Semaine_{iso_week}_{iso_year}.xlsx"'
    
    wb.save(response)
    return response