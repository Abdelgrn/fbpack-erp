import json
import datetime
from collections import defaultdict
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.contrib import messages

from ..models import (
    Machine, ProductionEntry, CalculTempsProduction, OrdreFabrication,
    # --- NOUVEAUX MODELES ---
    FicheProductionJournaliere, FicheExtrusionMatiere, FicheExtrusionArret,
    FicheImpressionBobineEntree, FicheImpressionBobineImprimee, FicheImpressionEncreGroupe,
    FicheComplexageDerouleur1, FicheComplexageDerouleur2, FicheComplexageEnrouleur,
    FicheFondCarreEquipe, FicheDecoupeBobineMere, FicheDecoupeBobineFille
)
from ..forms import (
    ProductionEntryForm, CalculTempsProductionForm,
    # --- NOUVEAUX FORMULAIRES ET FORMSETS ---
    FicheProductionJournaliereForm, FicheExtrusionMatiereFormSet,
    FicheExtrusionArretFormSet, FicheFlexoBobineEntreeFormSet,
    FicheFlexoBobineImprimeeFormSet, FicheFlexoEncreGroupeFormSet,
    FicheComplexageDerouleur1FormSet, FicheComplexageDerouleur2FormSet,
    FicheComplexageEnrouleurFormSet, FicheFondCarreEquipeFormSet,
    FicheDecoupeBobineMereFormSet, FicheDecoupeBobineFilleFormSet
)

# ===========================================================================
# FILTRES GLOBAUX
# ===========================================================================

def _get_filtered_entries(request):
    entries = ProductionEntry.objects.exclude(
        machine__name__icontains="Nettoyage"
    ).order_by('-date', '-heure_debut')
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    machine_id = request.GET.get('machine', '')
    support = request.GET.get('support', '')
    equipe = request.GET.get('equipe', '')
    produit = request.GET.get('produit', '')
    unite = request.GET.get('unite_commande', '')

    if date_from:
        entries = entries.filter(date__gte=date_from)
    if date_to:
        entries = entries.filter(date__lte=date_to)
    if machine_id:
        entries = entries.filter(machine_id=machine_id)
    if support:
        entries = entries.filter(support=support)
    if equipe:
        entries = entries.filter(equipe=equipe)
    if produit:
        entries = entries.filter(produit=produit)
    if unite:
        entries = entries.filter(unite_commande=unite)
    return entries


def _get_filter_context(request):
    all_produits = ProductionEntry.objects.values_list('produit', flat=True).distinct().order_by('produit')
    machines_sans_nettoyage = Machine.objects.exclude(name__icontains="Nettoyage").order_by('name')
    return {
        'all_machines': machines_sans_nettoyage,
        'all_supports': ProductionEntry.objects.values_list('support', flat=True).distinct().order_by('support'),
        'all_produits': all_produits,
        'all_unites': [('PCS', 'Pièces (Étiquettes/Sacs)'), ('KG', 'Tonnage (KG)'), ('ML', 'Mètres Linéaires (ML)')],
        'selected_date_from': request.GET.get('date_from', ''),
        'selected_date_to': request.GET.get('date_to', ''),
        'selected_machine': request.GET.get('machine', ''),
        'selected_support': request.GET.get('support', ''),
        'selected_equipe': request.GET.get('equipe', ''),
        'selected_produit': request.GET.get('produit', ''),
        'selected_unite': request.GET.get('unite_commande', ''),
    }


# ===========================================================================
# 🚀 NOUVELLE VUE DE SAISIE MULTI-FICHES (MODERNISÉE)
# ===========================================================================

@login_required
def prod_saisie(request):
    """Nouvelle vue de saisie qui gère la fiche unifiée et ses sous-tableaux (FormSets)"""
    if request.method == 'POST':
        form = FicheProductionJournaliereForm(request.POST)
        if form.is_valid():
            fiche = form.save(commit=False)
            fiche.cree_par = request.user
            fiche.save()

            type_f = fiche.type_fiche
            
            # --- Enregistrement dynamique des FormSets selon le type de fiche ---
            if type_f == 'EXTRUSION':
                fs_mat = FicheExtrusionMatiereFormSet(request.POST, instance=fiche)
                fs_arr = FicheExtrusionArretFormSet(request.POST, instance=fiche)
                if fs_mat.is_valid(): fs_mat.save()
                if fs_arr.is_valid(): fs_arr.save()

            elif type_f in ['FLEXO', 'HELIO']:
                fs_ent = FicheFlexoBobineEntreeFormSet(request.POST, instance=fiche)
                fs_imp = FicheFlexoBobineImprimeeFormSet(request.POST, instance=fiche)
                fs_enc = FicheFlexoEncreGroupeFormSet(request.POST, instance=fiche)
                if fs_ent.is_valid(): fs_ent.save()
                if fs_imp.is_valid(): fs_imp.save()
                if fs_enc.is_valid(): fs_enc.save()

            elif type_f == 'COMPLEXAGE':
                fs_dr1 = FicheComplexageDerouleur1FormSet(request.POST, instance=fiche)
                fs_dr2 = FicheComplexageDerouleur2FormSet(request.POST, instance=fiche)
                fs_enr = FicheComplexageEnrouleurFormSet(request.POST, instance=fiche)
                if fs_dr1.is_valid(): fs_dr1.save()
                if fs_dr2.is_valid(): fs_dr2.save()
                if fs_enr.is_valid(): fs_enr.save()

            elif type_f == 'FONDS_CARRES':
                fs_fc = FicheFondCarreEquipeFormSet(request.POST, instance=fiche)
                if fs_fc.is_valid(): fs_fc.save()

            elif type_f in ['DECOUPE', 'DECOUPE2']:
                fs_bm = FicheDecoupeBobineMereFormSet(request.POST, instance=fiche)
                fs_bf = FicheDecoupeBobineFilleFormSet(request.POST, instance=fiche)
                if fs_bm.is_valid(): fs_bm.save()
                if fs_bf.is_valid(): fs_bf.save()

            messages.success(request, f"✅ Fiche {fiche.get_type_fiche_display()} enregistrée avec succès !")
            
            # Si un lot était renseigné, on redirige vers sa traçabilité !
            if fiche.numero_lot or fiche.of_lie:
                lot = fiche.numero_lot or (fiche.of_lie.numero_lot if fiche.of_lie else None)
                if lot:
                    return redirect('prod_tracabilite_lot', numero_lot=lot)
                    
            return redirect('prod_dashboard')
        else:
            messages.error(request, "❌ Erreur dans la saisie principale de la fiche. Vérifiez les champs.")
    else:
        form = FicheProductionJournaliereForm(initial={'type_fiche': 'FLEXO'})

    recent_fiches = FicheProductionJournaliere.objects.all().order_by('-date_fabrication', '-heure_debut')[:10]

    context = {
        'form': form,
        'titre': 'Nouvelle Fiche de Production Journalière',
        'recent_fiches': recent_fiches,
        
        # Initialisation de tous les FormSets vides pour le frontend
        'fs_ext_mat': FicheExtrusionMatiereFormSet(),
        'fs_ext_arr': FicheExtrusionArretFormSet(),
        
        'fs_flx_ent': FicheFlexoBobineEntreeFormSet(),
        'fs_flx_imp': FicheFlexoBobineImprimeeFormSet(),
        'fs_flx_enc': FicheFlexoEncreGroupeFormSet(initial=[{'groupe_numero': i} for i in range(1, 9)]),
        
        'fs_cpx_dr1': FicheComplexageDerouleur1FormSet(),
        'fs_cpx_dr2': FicheComplexageDerouleur2FormSet(),
        'fs_cpx_enr': FicheComplexageEnrouleurFormSet(),
        
        'fs_fc': FicheFondCarreEquipeFormSet(initial=[
            {'equipe_num': 1, 'shift_code': '08_16'}, 
            {'equipe_num': 2, 'shift_code': '16_00'}, 
            {'equipe_num': 3, 'shift_code': '00_08'}
        ]),
        
        'fs_dec_bm': FicheDecoupeBobineMereFormSet(),
        'fs_dec_bf': FicheDecoupeBobineFilleFormSet(),
    }
    return render(request, 'production_special/saisie.html', context)


@login_required
def prod_print_fiche(request, id):
    """Vue dédiée à l'impression d'une fiche de production"""
    fiche = get_object_or_404(FicheProductionJournaliere, id=id)
    return render(request, 'production_special/fiche_print.html', {'fiche': fiche})


# ===========================================================================
# 🚀 VUE TRAÇABILITÉ PAR LOT (LE COEUR DU SYSTÈME)
# ===========================================================================

@login_required
def prod_tracabilite_lot(request, numero_lot=None):
    """Affiche la timeline complète d'un lot, de la création à la dernière fiche de production."""
    # Si recherche via la barre globale (paramètre GET ?q=LOT...)
    q = request.GET.get('q')
    if q:
        return redirect('prod_tracabilite_lot', numero_lot=q)

    context = {'numero_lot': numero_lot, 'search_query': numero_lot}
    
    if numero_lot:
        # On utilise notre méthode de classe intelligente !
        of = OrdreFabrication.chercher_par_lot(numero_lot)
        
        if of:
            context['of'] = of
            context['totaux'] = of.get_totaux_lot()
            context['fiches_par_type'] = of.get_fiches_par_type()
            context['workflow'] = of.workflow_visualisation
            context['encres'] = of.get_consommations_encres()
            context['messages_chat'] = of.get_chat_messages_lot()
            messages.success(request, f"Traçabilité complète trouvée pour l'OF {of.numero_of} (Lot: {of.numero_lot})")
        else:
            # Si l'OF n'existe pas, on cherche les fiches "orphelines"
            fiches = FicheProductionJournaliere.objects.filter(
                Q(numero_lot__iexact=numero_lot) | Q(numero_doc__iexact=numero_lot)
            ).order_by('-date_fabrication', '-heure_debut')
            anciennes = ProductionEntry.objects.filter(lot__iexact=numero_lot).order_by('-date')
            
            if fiches.exists() or anciennes.exists():
                context['fiches_orphelines'] = fiches
                context['anciennes_orphelines'] = anciennes
                messages.warning(request, f"Des fiches ont été trouvées pour le Lot '{numero_lot}', mais aucun OF parent n'a été créé.")
            else:
                messages.error(request, f"Aucun Lot ou OF correspondant à '{numero_lot}' n'existe dans le système.")
    
    return render(request, 'production_special/tracabilite_lot.html', context)


# ===========================================================================
# --- ANCIENNE VUE DE SAISIE (CONSERVÉE SOUS UN NOUVEAU NOM) ---
# ===========================================================================

@login_required
def prod_saisie_legacy(request):
    """Ancienne vue de saisie (ProductionEntry) conservée intacte"""
    if request.method == 'POST':
        form = ProductionEntryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Saisie de production enregistrée avec succès.")
            return redirect('prod_dashboard')
        else:
            messages.error(request, "Erreur dans le formulaire. Vérifiez les données saisies.")
    else:
        form = ProductionEntryForm()
    
    form.fields['machine'].queryset = Machine.objects.exclude(name__icontains="Nettoyage")
    recent = ProductionEntry.objects.all().order_by('-date', '-heure_debut')[:10]
    context = {
        'form': form, 'titre': 'Nouvelle Saisie Production',
        'recent': recent, 'edit_mode': False,
    }
    return render(request, 'production_special/saisie_legacy.html', context)


# ===========================================================================
# VUES EXISTANTES (AVEC AJOUT DES NOUVELLES FICHES DANS LE CONTEXTE)
# ===========================================================================

@login_required
def prod_dashboard(request):
    # --- LOGIQUE EXISTANTE (ProductionEntry) ---
    entries = _get_filtered_entries(request)
    total_prod_ml = entries.aggregate(t=Sum('prod_ml'))['t'] or 0
    total_prod_kg = entries.aggregate(t=Sum('prod_kg'))['t'] or 0
    total_dechets_kg = round(sum(e.total_dechets_kg for e in entries), 2)
    taux_dechets = round((total_dechets_kg / float(total_prod_kg) * 100), 2) if total_prod_kg else 0

    stats_modes = {
        'PCS': {'count': 0, 'volume': 0},
        'KG': {'count': 0, 'volume': 0},
        'ML': {'count': 0, 'volume': 0}
    }
    for e in entries:
        mode = getattr(e, 'unite_commande', 'PCS') or 'PCS'
        if mode in stats_modes:
            stats_modes[mode]['count'] += 1
            stats_modes[mode]['volume'] += float(e.quantite_lancee or 0)

    data_par_date = defaultdict(lambda: {'ml': 0, 'kg': 0, 'dem': 0, 'lis': 0, 'jon': 0, 'tra': 0, 'taux': []})
    for e in entries:
        d = str(e.date)
        data_par_date[d]['ml'] += e.prod_ml
        data_par_date[d]['kg'] += e.prod_kg
        data_par_date[d]['dem'] += e.dechets_demarrage
        data_par_date[d]['lis'] += e.dechets_lisiere
        data_par_date[d]['jon'] += e.dechets_jonction
        data_par_date[d]['tra'] += e.dechets_transport
        if e.prod_kg > 0:
            data_par_date[d]['taux'].append(e.taux_dechets)

    dates_sorted = sorted(data_par_date.keys())
    support_data = defaultdict(float)
    for e in entries:
        support_data[e.support] += e.prod_kg

    # --- AJOUT NOUVELLE LOGIQUE (Fiches Modernisées) ---
    fiches_modernes = FicheProductionJournaliere.objects.all().order_by('-date_fabrication', '-heure_debut')
    
    context = {
        'entries': entries[:20],
        'fiches_modernes': fiches_modernes[:20], # Injecté pour le dashboard unifié
        'total_prod_ml': round(float(total_prod_ml), 2),
        'total_prod_kg': round(float(total_prod_kg), 2),
        'total_dechets_kg': total_dechets_kg,
        'taux_dechets': taux_dechets,
        'count': entries.count(),
        'stats_modes': stats_modes,
        'prod_ml_dates': json.dumps(dates_sorted),
        'prod_ml_values': json.dumps([round(data_par_date[d]['ml'], 1) for d in dates_sorted]),
        'prod_kg_dates': json.dumps(dates_sorted),
        'prod_kg_values': json.dumps([round(data_par_date[d]['kg'], 2) for d in dates_sorted]),
        'prod_kg_support_labels': json.dumps(list(support_data.keys())),
        'prod_kg_support_values': json.dumps([round(v, 2) for v in support_data.values()]),
        'taux_dechets_dates': json.dumps(dates_sorted),
        'taux_dechets_values': json.dumps([
            round(sum(data_par_date[d]['taux']) / len(data_par_date[d]['taux']), 2) if data_par_date[d]['taux'] else 0
            for d in dates_sorted
        ]),
        'dechets_dates': json.dumps(dates_sorted),
        'dechets_dem_values': json.dumps([round(data_par_date[d]['dem'], 2) for d in dates_sorted]),
        'dechets_lis_values': json.dumps([round(data_par_date[d]['lis'], 2) for d in dates_sorted]),
        'dechets_jon_values': json.dumps([round(data_par_date[d]['jon'], 2) for d in dates_sorted]),
        'dechets_tra_values': json.dumps([round(data_par_date[d]['tra'], 2) for d in dates_sorted]),
    }
    context.update(_get_filter_context(request))
    return render(request, 'production_special/dashboard.html', context)


@login_required
def prod_edit_entry(request, id):
    entry = get_object_or_404(ProductionEntry, id=id)
    if request.method == 'POST':
        form = ProductionEntryForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, "Saisie mise à jour avec succès.")
            return redirect('prod_base')
        else:
            messages.error(request, "Erreur dans le formulaire lors de la modification.")
    else:
        form = ProductionEntryForm(instance=entry)
    
    form.fields['machine'].queryset = Machine.objects.exclude(name__icontains="Nettoyage")
    recent = ProductionEntry.objects.all().order_by('-date', '-heure_debut')[:10]
    context = {
        'form': form, 'titre': f'Modifier Saisie — {entry.produit} ({entry.date})',
        'recent': recent, 'edit_mode': True, 'entry': entry,
    }
    return render(request, 'production_special/saisie_legacy.html', context)


@login_required
def prod_delete_entry(request, id):
    entry = get_object_or_404(ProductionEntry, id=id)
    if request.method == 'POST':
        entry.delete()
        messages.success(request, "Saisie supprimée.")
        return redirect('prod_base')
    return render(request, 'production_special/confirm_delete.html', {'entry': entry})


@login_required
def prod_base(request):
    entries = _get_filtered_entries(request)
    fiches_modernes = FicheProductionJournaliere.objects.all().order_by('-date_fabrication', '-heure_debut')
    context = {'entries': entries, 'fiches_modernes': fiches_modernes}
    context.update(_get_filter_context(request))
    return render(request, 'production_special/base.html', context)


@login_required
def prod_detail_qualite(request):
    entries = _get_filtered_entries(request)
    fiches_modernes = FicheProductionJournaliere.objects.all().order_by('-date_fabrication', '-heure_debut')
    
    total_dechets_kg = round(sum(e.total_dechets_kg for e in entries), 2)
    total_dechets_demarrage = round(sum(e.dechets_demarrage for e in entries), 2)
    total_dechets_lisiere = round(sum(e.dechets_lisiere for e in entries), 2)
    total_dechets_jonction = round(sum(e.dechets_jonction for e in entries), 2)
    total_dechets_transport = round(sum(e.dechets_transport for e in entries), 2)

    dechets_par_machine = defaultdict(lambda: {'total': 0, 'prod': 0, 'dem': 0, 'lis': 0, 'jon': 0, 'tra': 0})
    dechets_par_equipe = defaultdict(lambda: {'total': 0, 'prod': 0, 'dem': 0, 'lis': 0, 'jon': 0, 'tra': 0})

    for e in entries:
        m_name = e.machine.name if e.machine else "Inconnue"
        eq = e.equipe or 'Inconnue'
        
        dechets_par_machine[m_name]['total'] += e.total_dechets_kg
        dechets_par_machine[m_name]['prod'] += e.prod_kg
        dechets_par_machine[m_name]['dem'] += e.dechets_demarrage
        dechets_par_machine[m_name]['lis'] += e.dechets_lisiere
        dechets_par_machine[m_name]['jon'] += e.dechets_jonction
        dechets_par_machine[m_name]['tra'] += e.dechets_transport

        dechets_par_equipe[eq]['total'] += e.total_dechets_kg
        dechets_par_equipe[eq]['prod'] += e.prod_kg
        dechets_par_equipe[eq]['dem'] += e.dechets_demarrage
        dechets_par_equipe[eq]['lis'] += e.dechets_lisiere
        dechets_par_equipe[eq]['jon'] += e.dechets_jonction
        dechets_par_equipe[eq]['tra'] += e.dechets_transport

    for val in list(dechets_par_machine.values()) + list(dechets_par_equipe.values()):
        val['taux'] = round((val['total'] / val['prod'] * 100), 2) if val['prod'] > 0 else 0
        val['total'] = round(val['total'], 2)

    lots_dict = defaultdict(list)
    for e in entries:
        if e.lot:
            lots_dict[e.lot].append(e)

    workflows_qualite = []
    for lot_no, lot_entries in lots_dict.items():
        sorted_steps = sorted(
            lot_entries,
            key=lambda x: datetime.datetime.combine(x.date or datetime.date.today(), x.heure_debut or datetime.time.min)
        )
        
        steps_data = []
        lot_total_dechets = 0
        lot_total_prod_kg = 0

        for step in sorted_steps:
            lot_total_dechets += step.total_dechets_kg
            lot_total_prod_kg += step.prod_kg
            
            steps_data.append({
                'machine': step.machine.name if step.machine else "—",
                'type_process': step.get_type_process_display() if hasattr(step, 'get_type_process_display') else str(step.type_process),
                'date': step.date,
                'dechets_demarrage': step.dechets_demarrage,
                'dechets_lisiere': step.dechets_lisiere,
                'dechets_jonction': step.dechets_jonction,
                'dechets_transport': step.dechets_transport,
                'total_dechets_kg': step.total_dechets_kg,
                'taux_dechets': step.taux_dechets,
                'prod_kg': step.prod_kg,
            })

        workflows_qualite.append({
            'lot': lot_no,
            'produit': sorted_steps[0].produit,
            'client': sorted_steps[0].client.name if sorted_steps[0].client else "Non défini",
            'steps': steps_data,
            'total_dechets': round(lot_total_dechets, 2),
            'total_prod_kg': round(lot_total_prod_kg, 2),
            'taux_global': round((lot_total_dechets / lot_total_prod_kg * 100), 1) if lot_total_prod_kg > 0 else 0.0
        })

    data_dates = defaultdict(lambda: {
        'dem_a': 0, 'dem_b': 0, 'dem_c': 0,
        'lis_a': 0, 'lis_b': 0, 'lis_c': 0,
        'jon_a': 0, 'jon_b': 0, 'jon_c': 0,
        'tra_a': 0, 'tra_b': 0, 'tra_c': 0, 'total': 0
    })
    for e in entries:
        d = str(e.date)
        eq = e.equipe or 'A'
        eq_key = eq.lower()
        data_dates[d]['dem_' + eq_key] += e.dechets_demarrage
        data_dates[d]['lis_' + eq_key] += e.dechets_lisiere
        data_dates[d]['jon_' + eq_key] += e.dechets_jonction
        data_dates[d]['tra_' + eq_key] += e.dechets_transport
        data_dates[d]['total'] += e.total_dechets_kg

    dates_sorted = sorted(data_dates.keys())
    context = {
        'entries': entries,
        'fiches_modernes': fiches_modernes,
        'workflows_qualite': workflows_qualite,
        'total_dechets_kg': total_dechets_kg,
        'total_dechets_demarrage': total_dechets_demarrage,
        'total_dechets_lisiere': total_dechets_lisiere,
        'total_dechets_jonction': total_dechets_jonction,
        'total_dechets_transport': total_dechets_transport,
        'dechets_par_machine': dict(dechets_par_machine),
        'dechets_par_equipe': dict(dechets_par_equipe),
        'dates_labels': json.dumps(dates_sorted),
        'dem_a': json.dumps([round(data_dates[d]['dem_a'], 2) for d in dates_sorted]),
        'dem_b': json.dumps([round(data_dates[d]['dem_b'], 2) for d in dates_sorted]),
        'dem_c': json.dumps([round(data_dates[d]['dem_c'], 2) for d in dates_sorted]),
        'lis_a': json.dumps([round(data_dates[d]['lis_a'], 2) for d in dates_sorted]),
        'lis_b': json.dumps([round(data_dates[d]['lis_b'], 2) for d in dates_sorted]),
        'lis_c': json.dumps([round(data_dates[d]['lis_c'], 2) for d in dates_sorted]),
        'jon_a': json.dumps([round(data_dates[d]['jon_a'], 2) for d in dates_sorted]),
        'jon_b': json.dumps([round(data_dates[d]['jon_b'], 2) for d in dates_sorted]),
        'jon_c': json.dumps([round(data_dates[d]['jon_c'], 2) for d in dates_sorted]),
        'tra_a': json.dumps([round(data_dates[d]['tra_a'], 2) for d in dates_sorted]),
        'tra_b': json.dumps([round(data_dates[d]['tra_b'], 2) for d in dates_sorted]),
        'tra_c': json.dumps([round(data_dates[d]['tra_c'], 2) for d in dates_sorted]),
        'h_dates': json.dumps(dates_sorted),
        'h_dem': json.dumps([round(data_dates[d]['dem_a'] + data_dates[d]['dem_b'] + data_dates[d]['dem_c'], 2) for d in dates_sorted]),
        'h_lis': json.dumps([round(data_dates[d]['lis_a'] + data_dates[d]['lis_b'] + data_dates[d]['lis_c'], 2) for d in dates_sorted]),
        'h_jon': json.dumps([round(data_dates[d]['jon_a'] + data_dates[d]['jon_b'] + data_dates[d]['jon_c'], 2) for d in dates_sorted]),
        'h_tra': json.dumps([round(data_dates[d]['tra_a'] + data_dates[d]['tra_b'] + data_dates[d]['tra_c'], 2) for d in dates_sorted]),
    }
    context.update(_get_filter_context(request))
    return render(request, 'production_special/detail_qualite.html', context)


@login_required
def prod_synthese_temps(request):
    entries = _get_filtered_entries(request)
    fiches_modernes = FicheProductionJournaliere.objects.all().order_by('-date_fabrication', '-heure_debut')

    decalage_total = round(sum(e.decalage for e in entries), 2)
    temps_ouverture_total_min = sum(e.temps_ouverture_minutes for e in entries)
    heures = int(temps_ouverture_total_min // 60)
    minutes = int(temps_ouverture_total_min % 60)
    temps_ouverture_total = f"{heures}:{minutes:02d}"
    total_rebobinage = round(sum(e.rebobinage_kg for e in entries), 2)

    total_calage_min = sum(getattr(e, 'temps_calage_min', 30) or 30 for e in entries)
    total_roulage_min = max(0, temps_ouverture_total_min - total_calage_min)
    
    calage_heures = round(total_calage_min / 60, 1)
    roulage_heures = round(total_roulage_min / 60, 1)

    machine_vitesses = defaultdict(list)
    for e in entries:
        if e.machine and getattr(e, 'vitesse_machine_trmin', None):
            machine_vitesses[e.machine.name].append(e.vitesse_machine_trmin)
    
    avg_machine_vitesses = {
        m_name: round(sum(vits) / len(vits), 1) if vits else 0
        for m_name, vits in machine_vitesses.items()
    }

    unite_stats = defaultdict(lambda: {'count': 0, 'total': 0})
    for e in entries:
        mode = getattr(e, 'unite_commande', 'PCS') or 'PCS'
        unite_stats[mode]['count'] += 1
        unite_stats[mode]['total'] += float(e.quantite_lancee or 0)

    lots_dict = defaultdict(list)
    for e in entries:
        if e.lot:
            lots_dict[e.lot].append(e)

    workflows_list = []
    for lot_no, lot_entries in lots_dict.items():
        sorted_steps = sorted(
            lot_entries,
            key=lambda x: datetime.datetime.combine(x.date or datetime.date.today(), x.heure_debut or datetime.time.min)
        )
        
        steps_data = []
        cumul_temps_ouverture_min = 0
        cumul_temps_calage_min = 0
        cumul_dechets_kg = 0
        bottleneck_machine = None
        max_duration_min = -1

        for i, step in enumerate(sorted_steps):
            dur_min = step.temps_ouverture_minutes or 0
            cal_min = getattr(step, 'temps_calage_min', 30) or 30
            rou_min = max(0, dur_min - cal_min)

            cumul_temps_ouverture_min += dur_min
            cumul_temps_calage_min += cal_min
            cumul_dechets_kg += step.total_dechets_kg

            if dur_min > max_duration_min:
                max_duration_min = dur_min
                bottleneck_machine = step.machine.name if step.machine else "Machine non définie"

            temps_attente_next = None
            if i < len(sorted_steps) - 1:
                next_step = sorted_steps[i+1]
                t_fin_curr = datetime.datetime.combine(step.date or datetime.date.today(), step.heure_fin or datetime.time.max)
                t_deb_next = datetime.datetime.combine(next_step.date or datetime.date.today(), next_step.heure_debut or datetime.time.min)
                if t_deb_next > t_fin_curr:
                    diff_dt = t_deb_next - t_fin_curr
                    diff_h = diff_dt.seconds // 3600
                    diff_m = (diff_dt.seconds % 3600) // 60
                    temps_attente_next = f"{diff_h}h {diff_m}min" if diff_h > 0 else f"{diff_m}min"

            steps_data.append({
                'id': step.id,
                'machine': step.machine.name if step.machine else "Non assignée",
                'type_process': step.get_type_process_display() if hasattr(step, 'get_type_process_display') else str(step.type_process),
                'date': step.date,
                'heure_debut': step.heure_debut,
                'heure_fin': step.heure_fin,
                'temps_ouverture_min': dur_min,
                'temps_calage_min': cal_min,
                'temps_roulage_min': rou_min,
                'vitesse': getattr(step, 'vitesse_machine_trmin', 200),
                'dechets_kg': step.total_dechets_kg,
                'taux_dechets': step.taux_dechets,
                'prod_kg': step.prod_kg,
                'prod_ml': step.prod_ml,
                'rendement_etape': round((step.prod_kg / step.quantite_lancee * 100), 1) if step.quantite_lancee > 0 else 100.0,
                'transition_next': temps_attente_next
            })

        first_step = sorted_steps[0]
        last_step = sorted_steps[-1]
        
        dt_start = datetime.datetime.combine(first_step.date or datetime.date.today(), first_step.heure_debut or datetime.time.min)
        dt_end = datetime.datetime.combine(last_step.date or datetime.date.today(), last_step.heure_fin or datetime.time.max)
        
        total_lead_time_diff = dt_end - dt_start
        lead_time_h = total_lead_time_diff.days * 24 + total_lead_time_diff.seconds // 3600
        lead_time_m = (total_lead_time_diff.seconds % 3600) // 60
        lead_time_str = f"{lead_time_h}h {lead_time_m:02d}min"

        poids_lance_global = first_step.quantite_lancee or 0
        poids_fini_global = last_step.prod_kg or 0
        rendement_matiere_global = round((poids_fini_global / poids_lance_global * 100), 2) if poids_lance_global > 0 else 0

        workflows_list.append({
            'lot': lot_no,
            'produit': first_step.produit,
            'client': first_step.client.name if first_step.client else "Inconnu",
            'steps': steps_data,
            'steps_count': len(steps_data),
            'total_dechets': round(cumul_dechets_kg, 2),
            'total_ouverture_str': f"{int(cumul_temps_ouverture_min // 60)}h {int(cumul_temps_ouverture_min % 60):02d}min",
            'total_calage_str': f"{int(cumul_temps_calage_min // 60)}h {int(cumul_temps_calage_min % 60):02d}min",
            'lead_time_str': lead_time_str,
            'poids_lance': round(poids_lance_global, 1),
            'poids_fini': round(poids_fini_global, 1),
            'rendement_global': rendement_matiere_global,
            'bottleneck_machine': bottleneck_machine,
        })

    data_dec = defaultdict(float)
    data_temps_a = defaultdict(float)
    data_temps_b = defaultdict(float)
    data_temps_c = defaultdict(float)
    produits_set = set()

    for e in entries:
        d = str(e.date)
        data_dec[d] += e.decalage
        produits_set.add(e.produit[:20])
        eq = e.equipe or 'A'
        if eq == 'A':
            data_temps_a[e.produit[:20]] += e.temps_ouverture_minutes / 60
        elif eq == 'B':
            data_temps_b[e.produit[:20]] += e.temps_ouverture_minutes / 60
        elif eq == 'C':
            data_temps_c[e.produit[:20]] += e.temps_ouverture_minutes / 60

    dates_sorted = sorted(data_dec.keys())
    produits_sorted = sorted(produits_set)

    calculs_recents = CalculTempsProduction.objects.all().select_related(
        'client', 'machine_impression', 'machine_decoupe', 'cree_par'
    ).order_by('-date_calcul')[:30]

    form_calcul = CalculTempsProductionForm()

    context = {
        'entries': entries,
        'fiches_modernes': fiches_modernes,
        'workflows': workflows_list,
        'decalage_total': decalage_total,
        'temps_ouverture_total': temps_ouverture_total,
        'total_rebobinage': total_rebobinage,
        'calage_heures': calage_heures,
        'roulage_heures': roulage_heures,
        'avg_machine_vitesses': avg_machine_vitesses,
        'unite_stats': dict(unite_stats),
        'decalage_dates': json.dumps(dates_sorted),
        'decalage_values': json.dumps([round(data_dec[d], 2) for d in dates_sorted]),
        'temps_produit_labels': json.dumps(produits_sorted),
        'temps_produit_a': json.dumps([round(data_temps_a.get(p, 0), 2) for p in produits_sorted]),
        'temps_produit_b': json.dumps([round(data_temps_b.get(p, 0), 2) for p in produits_sorted]),
        'temps_produit_c': json.dumps([round(data_temps_c.get(p, 0), 2) for p in produits_sorted]),
        'calculs_recents': calculs_recents,
        'form_calcul': form_calcul,
    }
    context.update(_get_filter_context(request))
    return render(request, 'production_special/synthese_temps.html', context)


# ===========================================================================
# --- CALCULATEUR DE TEMPS ---
# ===========================================================================

@login_required
def prod_calculer_temps(request):
    if request.method == 'POST':
        form = CalculTempsProductionForm(request.POST)
        if form.is_valid():
            calcul = form.save(commit=False)
            calcul.cree_par = request.user
            calcul.save()
            messages.success(request, f"✅ Calcul prévisionnel pour '{calcul.nom_job}' enregistré avec succès !")
            return redirect('prod_synthese_temps')
        else:
            messages.error(request, "❌ Erreur dans le formulaire de calcul. Vérifiez les champs.")
    return redirect('prod_synthese_temps')

@login_required
def prod_calculer_temps_save(request):
    return redirect('prod_synthese_temps')

@login_required
def prod_calculer_temps_delete(request, id):
    calcul = get_object_or_404(CalculTempsProduction, id=id)
    if request.method == 'POST':
        calcul.delete()
        messages.success(request, "🗑️ Calcul prévisionnel supprimé.")
    return redirect('prod_synthese_temps')