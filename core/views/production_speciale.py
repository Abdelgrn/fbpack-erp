import json
import datetime
from collections import defaultdict
from datetime import timedelta
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
    FicheFondCarreEquipe, FicheDecoupeBobineMere, FicheDecoupeBobineFille,
    FicheDecoupeArret, FicheDecoupeControle,
)
from ..forms import (
    ProductionEntryForm, CalculTempsProductionForm,
    # --- NOUVEAUX FORMULAIRES ET FORMSETS ---
    FicheProductionJournaliereForm, FicheExtrusionMatiereFormSet,
    FicheExtrusionArretFormSet, FicheFlexoBobineEntreeFormSet,
    FicheFlexoBobineImprimeeFormSet, FicheFlexoEncreGroupeFormSet,
    FicheComplexageDerouleur1FormSet, FicheComplexageDerouleur2FormSet,
    FicheComplexageEnrouleurFormSet, FicheFondCarreEquipeFormSet,
    FicheDecoupeBobineMereFormSet, FicheDecoupeBobineFilleFormSet,
    FicheDecoupeArretFormSet, FicheDecoupeControleForm,
)

# ===========================================================================
# ADAPTATEUR : Fiche moderne → interface compatible ProductionEntry
# ===========================================================================

class FicheAsEntry:
    """
    Adapte une FicheProductionJournaliere pour qu'elle expose
    la même interface que ProductionEntry (templates synthèse / qualité).
    """

    def __init__(self, fiche):
        self.id = fiche.id
        self._f = fiche
        self.date = fiche.date_fabrication
        self.produit = fiche.designation_produit or "—"
        self.support = fiche.support or "—"
        self.lot = fiche.numero_lot or fiche.numero_doc or ""
        self.client = fiche.client
        self.equipe = fiche.equipe or 'A'
        self.machine = fiche.machine
        self.heure_debut = fiche.heure_debut
        self.heure_fin = fiche.heure_fin
        self.laize = fiche.laize_mm or 0
        self.type_process = self._map_type(fiche.type_fiche)
        self.unite_commande = 'KG'
        self.quantite_commandee_unites = fiche.qte_programmee or 0
        self.grammage_g_m2 = 0
        self.pas_mm = 275.0
        self.laize_produit_mm = 65.0
        self.laize_bobine_mere_mm = fiche.laize_mm or 825.0
        self.longueur_bobine_mere_m = 10000.0
        self.vitesse_machine_trmin = fiche.vitesse_machine or 200.0
        self.temps_calage_min = int(fiche.t_preparation_min or 30)
        self.rebobinage_kg = 0.0
        self._compute_metrics()

    def _map_type(self, t):
        return {
            'FLEXO': 'FLEXO', 'HELIO': 'HELIO',
            'DECOUPE': 'DECOUPE', 'DECOUPE2': 'DECOUPE2',
            'EXTRUSION': 'AUTRE', 'COMPLEXAGE': 'AUTRE', 'FONDS_CARRES': 'AUTRE',
        }.get(t, 'AUTRE')

    def _compute_metrics(self):
        f = self._f
        self.dechets_demarrage = 0.0
        self.dechets_lisiere = 0.0
        self.dechets_jonction = 0.0
        self.dechets_transport = 0.0
        self.prod_kg = 0.0
        self.prod_ml = 0.0
        self.quantite_lancee = 0.0

        if f.type_fiche in ['DECOUPE', 'DECOUPE2']:
            # Bobines Mères = matière lancée
            for bm in f.bobines_meres_decoupe.all():
                self.quantite_lancee += float(bm.poids_kg or 0)
                self.prod_ml += float(bm.metrage_ml or 0)
            # Bobines Filles = produit fini + rebuts
            for bf in f.bobines_filles_decoupe.all():
                self.prod_kg += float(bf.poids_filles_kg or 0)
                self.dechets_demarrage += float(bf.dechets_demarrage_kg or 0)
                # "Rebut" de l'UI = dechets_lisiere_kg
                self.dechets_lisiere += float(bf.dechets_lisiere_kg or 0)
                self.dechets_jonction += float(bf.dechets_jonction_kg or 0)
                self.dechets_transport += float(bf.dechets_transport_kg or 0)
                self.dechets_lisiere += float(bf.rouleaux_non_conforme_kg or 0)

        elif f.type_fiche in ['FLEXO', 'HELIO']:
            for b in f.bobines_entrees.all():
                self.quantite_lancee += float(b.poids_kg or 0)
                self.dechets_demarrage += float(b.dechets_neutre_kg or 0)
            for b in f.bobines_imprimees.all():
                self.prod_kg += float(b.poids_kg or 0)
                self.prod_ml += float(b.metrage_m or 0)
                self.dechets_lisiere += float(b.dechet_imprime_kg or 0)

        elif f.type_fiche == 'COMPLEXAGE':
            for d in f.derouleur1_items.all():
                self.quantite_lancee += float(d.poids_kg or 0)
                self.dechets_lisiere += float(d.dechets_kg or 0)
            for d in f.derouleur2_items.all():
                self.quantite_lancee += float(d.poids_kg or 0)
                self.dechets_lisiere += float(d.dechets_kg or 0)
            for e in f.enrouleur_items.all():
                self.prod_kg += float(e.poids_kg or 0)
                self.prod_ml += float(e.ml or 0)
                self.dechets_jonction += float(e.dechets_kg or 0)

        elif f.type_fiche == 'EXTRUSION':
            for m in f.matieres_extrusion.all():
                self.quantite_lancee += float(m.poids_mp_kg or 0)
                self.prod_kg += float(m.qte_realisee_net_kg or 0)
                self.prod_ml += float(m.metrage_m or 0)
            self.dechets_demarrage = float(f.dechet_bloc_b or 0) + float(f.dechet_b_demarrage_r or 0)
            self.dechets_lisiere = float(f.dechet_lisiere or 0) + float(f.dechet_film or 0)
            self.dechets_jonction = float(f.dechet_purge or 0)

        elif f.type_fiche == 'FONDS_CARRES':
            for e in f.fonds_carres_equipes.all():
                self.prod_kg += float(e.poids_sacs_kg or 0)
                self.quantite_lancee += float(e.poids_initial_kg or 0)
                self.dechets_lisiere += float(e.dechets_sacs_kg or 0) + float(e.dechets_bob_kg or 0)

        # Fallback sur totaux stockés si sous-tables vides
        if self.prod_kg == 0 and f.total_poids_produit_kg:
            self.prod_kg = float(f.total_poids_produit_kg)
        if self.quantite_lancee == 0 and f.total_qte_lancee:
            self.quantite_lancee = float(f.total_qte_lancee)
        if (self.dechets_demarrage + self.dechets_lisiere + self.dechets_jonction + self.dechets_transport) == 0:
            if f.total_dechets_kg:
                self.dechets_lisiere = float(f.total_dechets_kg)

    @property
    def total_dechets_kg(self):
        return round(
            self.dechets_demarrage + self.dechets_lisiere +
            self.dechets_jonction + self.dechets_transport, 2
        )

    @property
    def taux_dechets(self):
        if self.prod_kg == 0:
            return 0
        return round((self.total_dechets_kg / self.prod_kg) * 100, 2)

    @property
    def decalage(self):
        return round(self.prod_kg - self.quantite_lancee, 2)

    @property
    def temps_ouverture_minutes(self):
        return self._f.temps_ouverture_minutes

    @property
    def temps_ouverture(self):
        m = int(self.temps_ouverture_minutes or 0)
        return f"{m // 60}:{m % 60:02d}"

    def get_type_process_display(self):
        return self._f.get_type_fiche_display()

    def get_unite_commande_display(self):
        return "Tonnage (KG)"

    @property
    def nb_poses_largeur(self):
        return 1

    @property
    def metrage_total_necessaire_m(self):
        return round(self.prod_ml or 0, 2)

    @property
    def nb_bobines_meres_necessaires(self):
        if self._f.type_fiche in ['DECOUPE', 'DECOUPE2']:
            return max(1, self._f.bobines_meres_decoupe.count())
        return 1

    @property
    def nb_bobines_filles_totales(self):
        if self._f.type_fiche in ['DECOUPE', 'DECOUPE2']:
            return sum(int(b.nombre_filles or 0) for b in self._f.bobines_filles_decoupe.all())
        return 0

    @property
    def temps_estime_min(self):
        return self.temps_ouverture_minutes or 0

    @property
    def temps_estime_formatted(self):
        m = int(self.temps_estime_min or 0)
        return f"{m // 60}h {m % 60:02d}min"

    @property
    def fin_estimee_24h(self):
        if not self.date:
            return None
        h_start = self.heure_debut if self.heure_debut else datetime.time(8, 0)
        return datetime.datetime.combine(self.date, h_start) + timedelta(minutes=int(self.temps_estime_min or 0))


def _consolider_fiche(fiche):
    """Calcule et persiste les totaux (poids, déchets, métrage) sur la fiche mère."""
    adapter = FicheAsEntry(fiche)
    fiche.total_dechets_kg = adapter.total_dechets_kg
    fiche.total_poids_produit_kg = adapter.prod_kg
    fiche.total_qte_lancee = adapter.quantite_lancee
    fiche.total_metrage_ml = adapter.prod_ml
    fiche.dechet_lisiere = adapter.dechets_lisiere
    if fiche.type_fiche in ['DECOUPE', 'DECOUPE2']:
        fiche.total_bobines_filles = adapter.nb_bobines_filles_totales
    fiche.save(update_fields=[
        'total_dechets_kg', 'total_poids_produit_kg', 'total_qte_lancee',
        'total_metrage_ml', 'dechet_lisiere', 'total_bobines_filles',
    ])


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


def _get_filtered_fiches(request):
    """Filtre les fiches modernes avec les mêmes critères GET que les anciennes saisies."""
    fiches = FicheProductionJournaliere.objects.all().order_by(
        '-date_fabrication', '-heure_debut'
    ).select_related('machine', 'client').prefetch_related(
        'bobines_meres_decoupe', 'bobines_filles_decoupe',
        'bobines_entrees', 'bobines_imprimees',
        'derouleur1_items', 'derouleur2_items', 'enrouleur_items',
        'matieres_extrusion', 'fonds_carres_equipes', 'encres_groupes',
    )

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    machine_id = request.GET.get('machine', '')
    support = request.GET.get('support', '')
    equipe = request.GET.get('equipe', '')
    produit = request.GET.get('produit', '')

    if date_from:
        fiches = fiches.filter(date_fabrication__gte=date_from)
    if date_to:
        fiches = fiches.filter(date_fabrication__lte=date_to)
    if machine_id:
        fiches = fiches.filter(machine_id=machine_id)
    if support:
        fiches = fiches.filter(support__icontains=support)
    if equipe:
        fiches = fiches.filter(equipe=equipe)
    if produit:
        fiches = fiches.filter(designation_produit__icontains=produit)
    return fiches


def _get_all_production_items(request):
    """
    Fusionne anciennes ProductionEntry + nouvelles FicheProductionJournaliere
    pour que Synthèse Temps et Détail Qualité affichent TOUT.
    """
    entries = list(_get_filtered_entries(request))
    fiches = _get_filtered_fiches(request)
    adapted = [FicheAsEntry(f) for f in fiches]
    return entries + adapted


def _get_filter_context(request):
    all_produits = ProductionEntry.objects.values_list('produit', flat=True).distinct().order_by('produit')
    # Ajouter aussi les produits des fiches modernes
    fiches_produits = FicheProductionJournaliere.objects.exclude(
        designation_produit=''
    ).values_list('designation_produit', flat=True).distinct()
    all_produits = sorted(set(list(all_produits) + list(fiches_produits)))

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
    causes_decoupe_init = [{'cause': c} for c in [
        'CHANGEMENT DE FORMAT', 'DEMARAGE', 'ESSAI', 'PREPARATION BOBINES MERE',
        'PREPARATION BOBINES FILLES', 'NETTOYAGE MACHINE', 'PREVENTIF',
        'MANQUE MATIERE PREMIERE', 'JONCTION NON CONFORME', 'PROBLEMES REGLAGE',
        'PROBLEMES MANDRIN', 'PANNE MAINTENANCE', 'COUPURE ELECTRIQUE', 'AUTRES (OBSERVATION)'
    ]]

    if request.method == 'POST':
        form = FicheProductionJournaliereForm(request.POST)
        if form.is_valid():
            fiche = form.save(commit=False)
            fiche.cree_par = request.user
            # Si numero_doc rempli mais pas numero_lot → copier pour la traçabilité
            if fiche.numero_doc and not fiche.numero_lot:
                fiche.numero_lot = fiche.numero_doc
            fiche.save()

            type_f = fiche.type_fiche
            formsets_ok = True
            erreurs_fs = []

            # --- Enregistrement dynamique des FormSets (préfixes = related_name) ---
            if type_f == 'EXTRUSION':
                fs_mat = FicheExtrusionMatiereFormSet(
                    request.POST, instance=fiche, prefix='matieres_extrusion'
                )
                fs_arr = FicheExtrusionArretFormSet(
                    request.POST, instance=fiche, prefix='arrets_extrusion'
                )
                if fs_mat.is_valid():
                    fs_mat.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Matières Extrusion')
                if fs_arr.is_valid():
                    fs_arr.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Arrêts Extrusion')

            elif type_f in ['FLEXO', 'HELIO']:
                fs_ent = FicheFlexoBobineEntreeFormSet(
                    request.POST, instance=fiche, prefix='bobines_entrees'
                )
                fs_imp = FicheFlexoBobineImprimeeFormSet(
                    request.POST, instance=fiche, prefix='bobines_imprimees'
                )
                fs_enc = FicheFlexoEncreGroupeFormSet(
                    request.POST, instance=fiche, prefix='encres_groupes'
                )
                if fs_ent.is_valid():
                    fs_ent.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Bobines Entrées')
                if fs_imp.is_valid():
                    fs_imp.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Bobines Imprimées')
                if fs_enc.is_valid():
                    fs_enc.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Groupes Encres')

            elif type_f == 'COMPLEXAGE':
                fs_dr1 = FicheComplexageDerouleur1FormSet(
                    request.POST, instance=fiche, prefix='derouleur1_items'
                )
                fs_dr2 = FicheComplexageDerouleur2FormSet(
                    request.POST, instance=fiche, prefix='derouleur2_items'
                )
                fs_enr = FicheComplexageEnrouleurFormSet(
                    request.POST, instance=fiche, prefix='enrouleur_items'
                )
                if fs_dr1.is_valid():
                    fs_dr1.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Dérouleur 1')
                if fs_dr2.is_valid():
                    fs_dr2.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Dérouleur 2')
                if fs_enr.is_valid():
                    fs_enr.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Enrouleur')

            elif type_f == 'FONDS_CARRES':
                fs_fc = FicheFondCarreEquipeFormSet(
                    request.POST, instance=fiche, prefix='fonds_carres_equipes'
                )
                if fs_fc.is_valid():
                    fs_fc.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Équipes Fonds Carrés')

            elif type_f in ['DECOUPE', 'DECOUPE2']:
                fs_bm = FicheDecoupeBobineMereFormSet(
                    request.POST, instance=fiche, prefix='bobines_meres_decoupe'
                )
                fs_bf = FicheDecoupeBobineFilleFormSet(
                    request.POST, instance=fiche, prefix='bobines_filles_decoupe'
                )
                fs_arr = FicheDecoupeArretFormSet(
                    request.POST, instance=fiche, prefix='arrets_decoupe'
                )
                form_ctrl = FicheDecoupeControleForm(
                    request.POST, prefix='controle_decoupe'
                )

                if fs_bm.is_valid():
                    fs_bm.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Bobines Mères')
                if fs_bf.is_valid():
                    fs_bf.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Bobines Filles')
                if fs_arr.is_valid():
                    fs_arr.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Arrêts Découpe')
                if form_ctrl.is_valid():
                    ctrl = form_ctrl.save(commit=False)
                    ctrl.fiche = fiche
                    ctrl.save()

            # Consolider les totaux (poids, rebuts, métrage) sur la fiche
            _consolider_fiche(fiche)

            if formsets_ok:
                messages.success(
                    request,
                    f"✅ Fiche {fiche.get_type_fiche_display()} enregistrée "
                    f"(Prod: {fiche.total_poids_produit_kg or 0:.1f} kg — "
                    f"Rebuts: {fiche.total_dechets_kg or 0:.1f} kg) !"
                )
            else:
                messages.warning(
                    request,
                    f"⚠️ Fiche enregistrée mais erreurs dans : {', '.join(erreurs_fs)}. "
                    f"Vérifiez les sous-tableaux."
                )

            if fiche.numero_lot or fiche.of_lie:
                lot = fiche.numero_lot or (fiche.of_lie.numero_lot if fiche.of_lie else None)
                if lot:
                    return redirect('prod_tracabilite_lot', numero_lot=lot)

            return redirect('prod_dashboard')
        else:
            messages.error(request, "❌ Erreur dans la saisie principale de la fiche. Vérifiez les champs.")
    else:
        form = FicheProductionJournaliereForm(initial={'type_fiche': 'FLEXO'})

    recent_fiches = FicheProductionJournaliere.objects.all().order_by(
        '-date_fabrication', '-heure_debut'
    )[:10]

    context = {
        'form': form,
        'titre': 'Nouvelle Fiche de Production Journalière',
        'recent_fiches': recent_fiches,

        # ⚠️ prefix = related_name (doit matcher le JS addFormsetRow)
        'fs_ext_mat': FicheExtrusionMatiereFormSet(prefix='matieres_extrusion'),
        'fs_ext_arr': FicheExtrusionArretFormSet(prefix='arrets_extrusion'),
        'fs_flx_ent': FicheFlexoBobineEntreeFormSet(prefix='bobines_entrees'),
        'fs_flx_imp': FicheFlexoBobineImprimeeFormSet(prefix='bobines_imprimees'),
        'fs_flx_enc': FicheFlexoEncreGroupeFormSet(
            prefix='encres_groupes',
            initial=[{'groupe_numero': i} for i in range(1, 9)]
        ),
        'fs_cpx_dr1': FicheComplexageDerouleur1FormSet(prefix='derouleur1_items'),
        'fs_cpx_dr2': FicheComplexageDerouleur2FormSet(prefix='derouleur2_items'),
        'fs_cpx_enr': FicheComplexageEnrouleurFormSet(prefix='enrouleur_items'),
        'fs_fc': FicheFondCarreEquipeFormSet(
            prefix='fonds_carres_equipes',
            initial=[
                {'equipe_num': 1, 'shift_code': '08_16'},
                {'equipe_num': 2, 'shift_code': '16_00'},
                {'equipe_num': 3, 'shift_code': '00_08'},
            ]
        ),
        'fs_dec_bm': FicheDecoupeBobineMereFormSet(prefix='bobines_meres_decoupe'),
        'fs_dec_bf': FicheDecoupeBobineFilleFormSet(prefix='bobines_filles_decoupe'),
        'fs_dec_arr': FicheDecoupeArretFormSet(prefix='arrets_decoupe', initial=causes_decoupe_init),
        'form_dec_ctrl': FicheDecoupeControleForm(prefix='controle_decoupe'),
    }
    return render(request, 'production_special/saisie.html', context)


@login_required
def prod_print_fiche(request, id):
    """Vue dédiée à l'impression d'une fiche de production"""
    fiche = get_object_or_404(FicheProductionJournaliere, id=id)
    return render(request, 'production_special/fiche_print.html', {'fiche': fiche})


@login_required
def prod_delete_fiche(request, id):
    """Suppression d'une FicheProductionJournaliere"""
    fiche = get_object_or_404(FicheProductionJournaliere, id=id)
    if request.method == 'POST':
        numero = fiche.numero_fiche or str(fiche.id)
        fiche.delete()
        messages.success(request, f"🗑️ Fiche {numero} supprimée avec succès.")
        return redirect('prod_base')
    return redirect('prod_base')


@login_required
def prod_edit_fiche(request, id):
    """Édition d'une FicheProductionJournaliere existante + ses sous-tableaux"""
    fiche = get_object_or_404(FicheProductionJournaliere, id=id)
    type_f = fiche.type_fiche

    causes_decoupe_init = [{'cause': c} for c in [
        'CHANGEMENT DE FORMAT', 'DEMARAGE', 'ESSAI', 'PREPARATION BOBINES MERE',
        'PREPARATION BOBINES FILLES', 'NETTOYAGE MACHINE', 'PREVENTIF',
        'MANQUE MATIERE PREMIERE', 'JONCTION NON CONFORME', 'PROBLEMES REGLAGE',
        'PROBLEMES MANDRIN', 'PANNE MAINTENANCE', 'COUPURE ELECTRIQUE', 'AUTRES (OBSERVATION)'
    ]]

    if request.method == 'POST':
        form = FicheProductionJournaliereForm(request.POST, instance=fiche)
        if form.is_valid():
            fiche = form.save(commit=False)
            if fiche.numero_doc and not fiche.numero_lot:
                fiche.numero_lot = fiche.numero_doc
            fiche.save()

            formsets_ok = True
            erreurs_fs = []

            if type_f == 'EXTRUSION':
                fs_mat = FicheExtrusionMatiereFormSet(request.POST, instance=fiche, prefix='matieres_extrusion')
                fs_arr = FicheExtrusionArretFormSet(request.POST, instance=fiche, prefix='arrets_extrusion')
                if fs_mat.is_valid():
                    fs_mat.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Matières Extrusion')
                if fs_arr.is_valid():
                    fs_arr.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Arrêts Extrusion')

            elif type_f in ['FLEXO', 'HELIO']:
                fs_ent = FicheFlexoBobineEntreeFormSet(request.POST, instance=fiche, prefix='bobines_entrees')
                fs_imp = FicheFlexoBobineImprimeeFormSet(request.POST, instance=fiche, prefix='bobines_imprimees')
                fs_enc = FicheFlexoEncreGroupeFormSet(request.POST, instance=fiche, prefix='encres_groupes')
                if fs_ent.is_valid():
                    fs_ent.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Bobines Entrées')
                if fs_imp.is_valid():
                    fs_imp.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Bobines Imprimées')
                if fs_enc.is_valid():
                    fs_enc.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Groupes Encres')

            elif type_f == 'COMPLEXAGE':
                fs_dr1 = FicheComplexageDerouleur1FormSet(request.POST, instance=fiche, prefix='derouleur1_items')
                fs_dr2 = FicheComplexageDerouleur2FormSet(request.POST, instance=fiche, prefix='derouleur2_items')
                fs_enr = FicheComplexageEnrouleurFormSet(request.POST, instance=fiche, prefix='enrouleur_items')
                if fs_dr1.is_valid():
                    fs_dr1.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Dérouleur 1')
                if fs_dr2.is_valid():
                    fs_dr2.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Dérouleur 2')
                if fs_enr.is_valid():
                    fs_enr.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Enrouleur')

            elif type_f == 'FONDS_CARRES':
                fs_fc = FicheFondCarreEquipeFormSet(request.POST, instance=fiche, prefix='fonds_carres_equipes')
                if fs_fc.is_valid():
                    fs_fc.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Équipes Fonds Carrés')

            elif type_f in ['DECOUPE', 'DECOUPE2']:
                fs_bm = FicheDecoupeBobineMereFormSet(request.POST, instance=fiche, prefix='bobines_meres_decoupe')
                fs_bf = FicheDecoupeBobineFilleFormSet(request.POST, instance=fiche, prefix='bobines_filles_decoupe')
                fs_arr = FicheDecoupeArretFormSet(request.POST, instance=fiche, prefix='arrets_decoupe')
                if fs_bm.is_valid():
                    fs_bm.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Bobines Mères')
                if fs_bf.is_valid():
                    fs_bf.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Bobines Filles')
                if fs_arr.is_valid():
                    fs_arr.save()
                else:
                    formsets_ok = False
                    erreurs_fs.append('Arrêts Découpe')

            _consolider_fiche(fiche)

            if formsets_ok:
                messages.success(
                    request,
                    f"✅ Fiche {fiche.numero_fiche} mise à jour "
                    f"(Prod: {fiche.total_poids_produit_kg or 0:.1f} kg — "
                    f"Rebuts: {fiche.total_dechets_kg or 0:.1f} kg) !"
                )
            else:
                messages.warning(
                    request,
                    f"⚠️ Fiche mise à jour mais erreurs dans : {', '.join(erreurs_fs)}."
                )
            return redirect('prod_base')
        else:
            messages.error(request, "❌ Erreur dans le formulaire principal. Vérifiez les champs.")
    else:
        form = FicheProductionJournaliereForm(instance=fiche)

    # Formsets pré-remplis avec les données existantes
    context = {
        'form': form,
        'titre': f'Modifier Fiche — {fiche.numero_fiche or fiche.id}',
        'edit_mode': True,
        'fiche': fiche,
        'recent_fiches': FicheProductionJournaliere.objects.all().order_by(
            '-date_fabrication', '-heure_debut'
        )[:10],

        'fs_ext_mat': FicheExtrusionMatiereFormSet(instance=fiche, prefix='matieres_extrusion'),
        'fs_ext_arr': FicheExtrusionArretFormSet(instance=fiche, prefix='arrets_extrusion'),
        'fs_flx_ent': FicheFlexoBobineEntreeFormSet(instance=fiche, prefix='bobines_entrees'),
        'fs_flx_imp': FicheFlexoBobineImprimeeFormSet(instance=fiche, prefix='bobines_imprimees'),
        'fs_flx_enc': FicheFlexoEncreGroupeFormSet(instance=fiche, prefix='encres_groupes'),
        'fs_cpx_dr1': FicheComplexageDerouleur1FormSet(instance=fiche, prefix='derouleur1_items'),
        'fs_cpx_dr2': FicheComplexageDerouleur2FormSet(instance=fiche, prefix='derouleur2_items'),
        'fs_cpx_enr': FicheComplexageEnrouleurFormSet(instance=fiche, prefix='enrouleur_items'),
        'fs_fc': FicheFondCarreEquipeFormSet(instance=fiche, prefix='fonds_carres_equipes'),
        'fs_dec_bm': FicheDecoupeBobineMereFormSet(instance=fiche, prefix='bobines_meres_decoupe'),
        'fs_dec_bf': FicheDecoupeBobineFilleFormSet(instance=fiche, prefix='bobines_filles_decoupe'),
        'fs_dec_arr': FicheDecoupeArretFormSet(instance=fiche, prefix='arrets_decoupe'),
        'form_dec_ctrl': FicheDecoupeControleForm(prefix='controle_decoupe'),
    }
    return render(request, 'production_special/saisie.html', context)


# ===========================================================================
# 🚀 VUE TRAÇABILITÉ PAR LOT
# ===========================================================================

@login_required
def prod_tracabilite_lot(request, numero_lot=None):
    """Affiche la timeline complète d'un lot, de la création à la dernière fiche de production."""
    q = request.GET.get('q')
    if q:
        return redirect('prod_tracabilite_lot', numero_lot=q)

    context = {'numero_lot': numero_lot, 'search_query': numero_lot}

    if numero_lot:
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
# --- ANCIENNE VUE DE SAISIE ---
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
# VUES EXISTANTES
# ===========================================================================

@login_required
def prod_dashboard(request):
    entries = _get_filtered_entries(request)
    total_prod_ml = entries.aggregate(t=Sum('prod_ml'))['t'] or 0
    total_prod_kg = entries.aggregate(t=Sum('prod_kg'))['t'] or 0
    total_dechets_kg = round(sum(e.total_dechets_kg for e in entries), 2)

    # Ajouter les totaux des fiches modernes
    fiches = _get_filtered_fiches(request)
    fiches_adapted = [FicheAsEntry(f) for f in fiches]
    total_prod_kg += sum(a.prod_kg for a in fiches_adapted)
    total_prod_ml += sum(a.prod_ml for a in fiches_adapted)
    total_dechets_kg += sum(a.total_dechets_kg for a in fiches_adapted)
    total_dechets_kg = round(total_dechets_kg, 2)

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
    # Fiches modernes comptées en KG
    stats_modes['KG']['count'] += len(fiches_adapted)
    stats_modes['KG']['volume'] += sum(a.quantite_lancee for a in fiches_adapted)

    data_par_date = defaultdict(lambda: {'ml': 0, 'kg': 0, 'dem': 0, 'lis': 0, 'jon': 0, 'tra': 0, 'taux': []})
    for e in list(entries) + fiches_adapted:
        d = str(e.date)
        data_par_date[d]['ml'] += float(getattr(e, 'prod_ml', 0) or 0)
        data_par_date[d]['kg'] += float(getattr(e, 'prod_kg', 0) or 0)
        data_par_date[d]['dem'] += float(getattr(e, 'dechets_demarrage', 0) or 0)
        data_par_date[d]['lis'] += float(getattr(e, 'dechets_lisiere', 0) or 0)
        data_par_date[d]['jon'] += float(getattr(e, 'dechets_jonction', 0) or 0)
        data_par_date[d]['tra'] += float(getattr(e, 'dechets_transport', 0) or 0)
        if getattr(e, 'prod_kg', 0) and e.prod_kg > 0:
            data_par_date[d]['taux'].append(e.taux_dechets)

    dates_sorted = sorted(data_par_date.keys())
    support_data = defaultdict(float)
    for e in list(entries) + fiches_adapted:
        support_data[e.support or '—'] += float(getattr(e, 'prod_kg', 0) or 0)

    fiches_modernes = FicheProductionJournaliere.objects.all().order_by('-date_fabrication', '-heure_debut')

    context = {
        'entries': list(entries)[:20],
        'fiches_modernes': fiches_modernes[:20],
        'total_prod_ml': round(float(total_prod_ml), 2),
        'total_prod_kg': round(float(total_prod_kg), 2),
        'total_dechets_kg': total_dechets_kg,
        'taux_dechets': taux_dechets,
        'count': entries.count() + len(fiches_adapted),
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
        messages.success(request, "🗑️ Saisie supprimée avec succès.")
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
    # 🔥 Fusion anciennes saisies + nouvelles fiches
    entries = _get_all_production_items(request)
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
            key=lambda x: datetime.datetime.combine(
                x.date or datetime.date.today(),
                x.heure_debut or datetime.time.min
            )
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

        client_name = "Non défini"
        if sorted_steps[0].client:
            client_name = sorted_steps[0].client.name if hasattr(sorted_steps[0].client, 'name') else str(sorted_steps[0].client)

        workflows_qualite.append({
            'lot': lot_no,
            'produit': sorted_steps[0].produit,
            'client': client_name,
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
        eq = (e.equipe or 'A').upper()
        if eq not in ('A', 'B', 'C'):
            eq = 'A'
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
    # 🔥 Fusion anciennes saisies + nouvelles fiches
    entries = _get_all_production_items(request)
    fiches_modernes = FicheProductionJournaliere.objects.all().order_by('-date_fabrication', '-heure_debut')

    decalage_total = round(sum(e.decalage for e in entries), 2)
    temps_ouverture_total_min = sum(e.temps_ouverture_minutes for e in entries)
    heures = int(temps_ouverture_total_min // 60)
    minutes = int(temps_ouverture_total_min % 60)
    temps_ouverture_total = f"{heures}:{minutes:02d}"
    total_rebobinage = round(sum(getattr(e, 'rebobinage_kg', 0) or 0 for e in entries), 2)

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
        unite_stats[mode]['total'] += float(getattr(e, 'quantite_lancee', 0) or 0)

    lots_dict = defaultdict(list)
    for e in entries:
        if e.lot:
            lots_dict[e.lot].append(e)

    workflows_list = []
    for lot_no, lot_entries in lots_dict.items():
        sorted_steps = sorted(
            lot_entries,
            key=lambda x: datetime.datetime.combine(
                x.date or datetime.date.today(),
                x.heure_debut or datetime.time.min
            )
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
                next_step = sorted_steps[i + 1]
                t_fin_curr = datetime.datetime.combine(
                    step.date or datetime.date.today(),
                    step.heure_fin or datetime.time.max
                )
                t_deb_next = datetime.datetime.combine(
                    next_step.date or datetime.date.today(),
                    next_step.heure_debut or datetime.time.min
                )
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

        dt_start = datetime.datetime.combine(
            first_step.date or datetime.date.today(),
            first_step.heure_debut or datetime.time.min
        )
        dt_end = datetime.datetime.combine(
            last_step.date or datetime.date.today(),
            last_step.heure_fin or datetime.time.max
        )

        total_lead_time_diff = dt_end - dt_start
        lead_time_h = total_lead_time_diff.days * 24 + total_lead_time_diff.seconds // 3600
        lead_time_m = (total_lead_time_diff.seconds % 3600) // 60
        lead_time_str = f"{lead_time_h}h {lead_time_m:02d}min"

        poids_lance_global = first_step.quantite_lancee or 0
        poids_fini_global = last_step.prod_kg or 0
        rendement_matiere_global = round(
            (poids_fini_global / poids_lance_global * 100), 2
        ) if poids_lance_global > 0 else 0

        client_name = "Inconnu"
        if first_step.client:
            client_name = first_step.client.name if hasattr(first_step.client, 'name') else str(first_step.client)

        workflows_list.append({
            'lot': lot_no,
            'produit': first_step.produit,
            'client': client_name,
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
        prod_label = (e.produit or "—")[:20]
        produits_set.add(prod_label)
        eq = e.equipe or 'A'
        mins = (e.temps_ouverture_minutes or 0) / 60
        if eq == 'A':
            data_temps_a[prod_label] += mins
        elif eq == 'B':
            data_temps_b[prod_label] += mins
        elif eq == 'C':
            data_temps_c[prod_label] += mins

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