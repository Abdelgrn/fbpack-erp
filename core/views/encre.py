# core/views/encre.py
import json
from collections import defaultdict
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.contrib import messages

from ..models import (
    ConsommationEncre,
    # 🆕 Fusion avec les fiches de production Flexo/Hélio
    FicheProductionJournaliere, FicheImpressionEncreGroupe,
)
from ..forms import ConsommationEncreForm


# ===========================================================================
# ADAPTATEUR : Fiche moderne (Groupe d'encre) → interface ConsommationEncre
# ===========================================================================

# Mapping automatique : mots-clés couleur → attribut du dashboard
_COLOR_MAPPING = {
    'noir': 'encre_noir', 'black': 'encre_noir', 'k': 'encre_noir',
    'magenta': 'encre_magenta', 'rose': 'encre_magenta', 'pink': 'encre_magenta', 'm': 'encre_magenta',
    'jaune': 'encre_jaune', 'yellow': 'encre_jaune', 'y': 'encre_jaune',
    'cyan': 'encre_cyan', 'bleu': 'encre_cyan', 'blue': 'encre_cyan', 'c': 'encre_cyan',
    'dor': 'encre_dore', 'gold': 'encre_dore', 'or': 'encre_dore',
    'silver': 'encre_silver', 'argent': 'encre_silver',
    'orange': 'encre_orange',
    'blanc': 'encre_blanc', 'white': 'encre_blanc',
    'vernis': 'encre_vernis', 'varnish': 'encre_vernis',
}


def _detect_color_field(designation):
    """Retourne le champ encre_* correspondant à la désignation."""
    if not designation:
        return None
    d = designation.lower().strip()
    for kw, field in _COLOR_MAPPING.items():
        if kw in d:
            return field
    return None


class FicheEncreAsConso:
    """
    Adapte une FicheProductionJournaliere (Flexo/Hélio) pour qu'elle expose
    la même interface qu'une ConsommationEncre → utilisée par le dashboard.
    """

    PROCESS_MAP = {'FLEXO': 'FLEXO', 'HELIO': 'HELIO'}

    def __init__(self, fiche):
        self.id = f"fiche_{fiche.id}"          # ID préfixé pour éviter collision
        self._fiche = fiche
        self.date = fiche.date_fabrication
        self.job_name = fiche.designation_produit or fiche.numero_doc or "—"
        self.support = fiche.support or "—"
        self.process_type = self.PROCESS_MAP.get(fiche.type_fiche, 'FLEXO')

        # Init couleurs à 0
        self.encre_noir = 0.0
        self.encre_magenta = 0.0
        self.encre_jaune = 0.0
        self.encre_cyan = 0.0
        self.encre_dore = 0.0
        self.encre_silver = 0.0
        self.encre_orange = 0.0
        self.encre_blanc = 0.0
        self.encre_vernis = 0.0

        # Totaux calculés depuis les 8 groupes
        self.total_encre = 0.0
        self.total_solvant = 0.0

        for g in fiche.encres_groupes.all():
            encre_kg = float(g.conso_encre_kg or 0)
            solvant_kg = float(g.conso_solvant_kg or 0)
            self.total_encre += encre_kg
            self.total_solvant += solvant_kg

            # Ventilation par couleur (auto-détection sur le nom saisi)
            field = _detect_color_field(g.designation_encre)
            if field:
                setattr(self, field, getattr(self, field) + encre_kg)

        # Métrage (venant des bobines imprimées)
        self.metrage = 0.0
        for b in fiche.bobines_imprimees.all():
            self.metrage += float(b.metrage_m or 0)

        # Grammage moyen : si laize et poids dispos → g/m²
        self.grammage = 0.0
        try:
            laize_m = float(fiche.laize_mm or 0) / 1000.0
            poids_prod = float(fiche.total_poids_produit_kg or 0)
            if self.metrage > 0 and laize_m > 0 and poids_prod > 0:
                # g/m² = (poids kg * 1000) / (metrage * laize)
                self.grammage = round((poids_prod * 1000) / (self.metrage * laize_m), 2)
        except Exception:
            self.grammage = 0.0

        # Bilan matière — on considère qu'il n'y a pas d'évaporé mesuré
        # (à activer si tu ajoutes ces champs dans la fiche)
        self.matiere_evaporee_kg = 0.0
        self.gain_de_masse_kg = 0.0

    def get_process_type_display(self):
        return dict(ConsommationEncre.PROCESS_CHOICES).get(self.process_type, self.process_type)


def _get_all_encre_items(request):
    """Fusionne anciennes ConsommationEncre + Fiches Flexo/Hélio → 1 seule liste."""
    consos = list(_get_filtered_encre(request))
    fiches = _get_filtered_fiches_encre(request)
    adapted = [FicheEncreAsConso(f) for f in fiches if f.encres_groupes.exists()]
    return consos + adapted


# ===========================================================================
# FILTRES
# ===========================================================================

def _get_filtered_encre(request):
    consos = ConsommationEncre.objects.all().order_by('-date')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    process = request.GET.get('process_type', '')
    support = request.GET.get('support', '')
    job = request.GET.get('job', '')

    if date_from:
        consos = consos.filter(date__gte=date_from)
    if date_to:
        consos = consos.filter(date__lte=date_to)
    if process:
        consos = consos.filter(process_type=process)
    if support:
        consos = consos.filter(support__icontains=support)
    if job:
        consos = consos.filter(job_name=job)
    return consos


def _get_filtered_fiches_encre(request):
    """Fiches Flexo/Hélio filtrées (les seules qui ont des groupes d'encre)."""
    fiches = FicheProductionJournaliere.objects.filter(
        type_fiche__in=['FLEXO', 'HELIO']
    ).prefetch_related('encres_groupes', 'bobines_imprimees').order_by('-date_fabrication')

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    process = request.GET.get('process_type', '')
    support = request.GET.get('support', '')
    job = request.GET.get('job', '')

    if date_from:
        fiches = fiches.filter(date_fabrication__gte=date_from)
    if date_to:
        fiches = fiches.filter(date_fabrication__lte=date_to)
    if process:
        fiches = fiches.filter(type_fiche=process)
    if support:
        fiches = fiches.filter(support__icontains=support)
    if job:
        fiches = fiches.filter(designation_produit__icontains=job)
    return fiches


def _get_encre_filter_context(request):
    # Supports : ancien + nouveau
    old_supports = ConsommationEncre.objects.values_list('support', flat=True).distinct()
    new_supports = FicheProductionJournaliere.objects.filter(
        type_fiche__in=['FLEXO', 'HELIO']
    ).exclude(support='').values_list('support', flat=True).distinct()
    all_supports = sorted(set(list(old_supports) + list(new_supports)))

    # Jobs : ancien + nouveau
    old_jobs = ConsommationEncre.objects.values_list('job_name', flat=True).distinct()
    new_jobs = FicheProductionJournaliere.objects.filter(
        type_fiche__in=['FLEXO', 'HELIO']
    ).exclude(designation_produit='').values_list('designation_produit', flat=True).distinct()
    all_jobs = sorted(set(list(old_jobs) + list(new_jobs)))

    return {
        'all_supports_encre': all_supports,
        'all_jobs_encre': all_jobs,
        'process_choices': ConsommationEncre.PROCESS_CHOICES,
        'sel_date_from': request.GET.get('date_from', ''),
        'sel_date_to': request.GET.get('date_to', ''),
        'sel_process': request.GET.get('process_type', ''),
        'sel_support': request.GET.get('support', ''),
        'sel_job': request.GET.get('job', ''),
    }


# ===========================================================================
# DASHBOARD ENCRE — FUSION AUTOMATIQUE
# ===========================================================================

@login_required
def encre_dashboard(request):
    # 🔥 Fusion anciennes saisies + fiches Flexo/Hélio
    all_items = _get_all_encre_items(request)
    count = len(all_items)

    total_encre = sum(c.total_encre for c in all_items)
    total_solvant = sum(c.total_solvant for c in all_items)
    total_injecte = total_encre + total_solvant

    total_gain_masse = sum(c.gain_de_masse_kg for c in all_items)
    total_evaporee = sum(c.matiere_evaporee_kg for c in all_items)

    taux_gain_global = round((total_gain_masse / total_injecte * 100), 2) if total_injecte else 0
    taux_evap_global = round((total_evaporee / total_injecte * 100), 2) if total_injecte else 0

    total_metrage = sum(c.metrage for c in all_items)

    grammages = [c.grammage for c in all_items if c.grammage > 0]
    grammage_moyen = round(sum(grammages) / len(grammages), 2) if grammages else 0

    couleurs_noms = ['Noir', 'Magenta', 'Jaune', 'Cyan', 'Doré', 'Silver', 'Orange', 'Blanc', 'Vernis']
    couleur_attrs = [
        'encre_noir', 'encre_magenta', 'encre_jaune', 'encre_cyan',
        'encre_dore', 'encre_silver', 'encre_orange', 'encre_blanc', 'encre_vernis',
    ]
    couleurs_vals = [
        round(sum(getattr(c, attr, 0) or 0 for c in all_items), 2)
        for attr in couleur_attrs
    ]
    couleurs_colors = [
        '#1a1a1a', '#e91e8c', '#ffd600', '#00b8d9',
        '#ffc107', '#9e9e9e', '#ff6d00', '#f5f5f5', '#4caf50'
    ]

    data_dates = defaultdict(lambda: {'encre': 0, 'solvant': 0, 'gain': 0, 'evap': 0, 'metrage': 0})
    for c in all_items:
        d = str(c.date)
        data_dates[d]['encre'] += c.total_encre
        data_dates[d]['solvant'] += c.total_solvant
        data_dates[d]['gain'] += c.gain_de_masse_kg
        data_dates[d]['evap'] += c.matiere_evaporee_kg
        data_dates[d]['metrage'] += c.metrage

    dates_sorted = sorted(data_dates.keys())

    pie_labels = ['Encres', 'Solvants']
    pie_vals = [round(total_encre, 2), round(total_solvant, 2)]
    pie_colors = ['#f3b83a', '#38bdf8']

    pie2_labels = ['Gain de masse', 'Matière évaporée']
    pie2_vals = [round(total_gain_masse, 2), round(total_evaporee, 2)]
    pie2_colors = ['#22c55e', '#ef4444']

    job_data = defaultdict(float)
    for c in all_items:
        job_data[c.job_name[:30]] += c.total_encre + c.total_solvant
    top_jobs = sorted(job_data.items(), key=lambda x: x[1], reverse=True)[:8]

    flexo_count = sum(1 for c in all_items if c.process_type == 'FLEXO')
    helio_count = sum(1 for c in all_items if c.process_type == 'HELIO')

    couleurs_table = [
        {'nom': n, 'val': v, 'color': c}
        for n, v, c in zip(couleurs_noms, couleurs_vals, couleurs_colors) if v > 0
    ]

    # Tri des saisies récentes (fiches + anciennes) par date desc
    consos_recentes = sorted(
        all_items,
        key=lambda x: x.date or __import__('datetime').date.min,
        reverse=True
    )[:15]

    context = {
        'count': count,
        'total_encre': round(total_encre, 2),
        'total_solvant': round(total_solvant, 2),
        'total_injecte': round(total_injecte, 2),
        'total_gain_masse': round(total_gain_masse, 2),
        'total_evaporee': round(total_evaporee, 2),
        'taux_gain_global': taux_gain_global,
        'taux_evap_global': taux_evap_global,
        'total_metrage': round(total_metrage, 2),
        'grammage_moyen': grammage_moyen,
        'flexo_count': flexo_count,
        'helio_count': helio_count,
        'couleurs_table': couleurs_table,
        'consos_recentes': consos_recentes,
        'chart_couleurs_labels': json.dumps(couleurs_noms),
        'chart_couleurs_vals': json.dumps(couleurs_vals),
        'chart_couleurs_colors': json.dumps(couleurs_colors),
        'chart_dates': json.dumps(dates_sorted),
        'chart_encre_vals': json.dumps([round(data_dates[d]['encre'], 2) for d in dates_sorted]),
        'chart_solvant_vals': json.dumps([round(data_dates[d]['solvant'], 2) for d in dates_sorted]),
        'chart_gain_vals': json.dumps([round(data_dates[d]['gain'], 2) for d in dates_sorted]),
        'chart_evap_vals': json.dumps([round(data_dates[d]['evap'], 2) for d in dates_sorted]),
        'chart_metrage_vals': json.dumps([round(data_dates[d]['metrage'], 1) for d in dates_sorted]),
        'pie_labels': json.dumps(pie_labels),
        'pie_vals': json.dumps(pie_vals),
        'pie_colors': json.dumps(pie_colors),
        'pie2_labels': json.dumps(pie2_labels),
        'pie2_vals': json.dumps(pie2_vals),
        'pie2_colors': json.dumps(pie2_colors),
        'chart_jobs_labels': json.dumps([j[0] for j in top_jobs]),
        'chart_jobs_vals': json.dumps([round(j[1], 2) for j in top_jobs]),
        'chart_process_labels': json.dumps(['Flexo', 'Hélio']),
        'chart_process_vals': json.dumps([flexo_count, helio_count]),
    }
    context.update(_get_encre_filter_context(request))
    return render(request, 'production_special/encre_dashboard.html', context)


# ===========================================================================
# ANCIENNES VUES (Saisie manuelle) — conservées telles quelles
# ===========================================================================

@login_required
def encre_saisie(request):
    if request.method == 'POST':
        form = ConsommationEncreForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Consommation encre enregistrée avec succès.")
            return redirect('encre_dashboard')
        else:
            messages.error(request, "❌ Erreur dans le formulaire. Vérifiez les champs.")
    else:
        form = ConsommationEncreForm()

    recent = ConsommationEncre.objects.all().order_by('-date')[:10]
    context = {
        'form': form, 'titre': 'Nouvelle Saisie — Encre & Solvants',
        'recent': recent, 'edit_mode': False,
    }
    return render(request, 'production_special/encre_saisie.html', context)


@login_required
def encre_edit(request, id):
    conso = get_object_or_404(ConsommationEncre, id=id)
    if request.method == 'POST':
        form = ConsommationEncreForm(request.POST, instance=conso)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Saisie mise à jour.")
            return redirect('encre_dashboard')
        else:
            messages.error(request, "❌ Erreur dans le formulaire.")
    else:
        form = ConsommationEncreForm(instance=conso)

    recent = ConsommationEncre.objects.all().order_by('-date')[:10]
    context = {
        'form': form, 'titre': f'Modifier — {conso.job_name} ({conso.date})',
        'recent': recent, 'edit_mode': True, 'conso': conso,
    }
    return render(request, 'production_special/encre_saisie.html', context)


@login_required
def encre_delete(request, id):
    conso = get_object_or_404(ConsommationEncre, id=id)
    if request.method == 'POST':
        conso.delete()
        messages.success(request, "🗑️ Saisie supprimée.")
        return redirect('encre_dashboard')
    return render(request, 'production_special/encre_confirm_delete.html', {'conso': conso})


@login_required
def encre_detail(request, id):
    conso = get_object_or_404(ConsommationEncre, id=id)

    couleurs_detail = [
        {'nom': 'Noir', 'val': conso.encre_noir, 'color': '#1a1a1a', 'bg': 'bg-gray-800'},
        {'nom': 'Magenta', 'val': conso.encre_magenta, 'color': '#e91e8c', 'bg': 'bg-pink-900'},
        {'nom': 'Jaune', 'val': conso.encre_jaune, 'color': '#ffd600', 'bg': 'bg-yellow-800'},
        {'nom': 'Cyan', 'val': conso.encre_cyan, 'color': '#00b8d9', 'bg': 'bg-cyan-900'},
        {'nom': 'Doré', 'val': conso.encre_dore, 'color': '#ffc107', 'bg': 'bg-amber-800'},
        {'nom': 'Silver', 'val': conso.encre_silver, 'color': '#9e9e9e', 'bg': 'bg-slate-600'},
        {'nom': 'Orange', 'val': conso.encre_orange, 'color': '#ff6d00', 'bg': 'bg-orange-900'},
        {'nom': 'Blanc', 'val': conso.encre_blanc, 'color': '#f5f5f5', 'bg': 'bg-slate-500'},
        {'nom': 'Vernis', 'val': conso.encre_vernis, 'color': '#4caf50', 'bg': 'bg-green-900'},
    ]
    couleurs_detail = [c for c in couleurs_detail if c['val'] > 0]

    pie_noms = [c['nom'] for c in couleurs_detail]
    pie_vals_d = [c['val'] for c in couleurs_detail]
    pie_cols_d = [c['color'] for c in couleurs_detail]

    context = {
        'conso': conso, 'couleurs_detail': couleurs_detail,
        'pie_noms_json': json.dumps(pie_noms),
        'pie_vals_json': json.dumps(pie_vals_d),
        'pie_cols_json': json.dumps(pie_cols_d),
    }
    return render(request, 'production_special/encre_detail.html', context)


# ===========================================================================
# ANALYSE AVANCÉE — Fusion aussi
# ===========================================================================

@login_required
def encre_analyse(request):
    # 🔥 Fusion aussi ici
    all_items = _get_all_encre_items(request)
    count = len(all_items)

    dechet_dates = defaultdict(float)
    dechet_flexo = defaultdict(float)
    dechet_helio = defaultdict(float)
    grammage_dates = defaultdict(list)

    for c in all_items:
        d = str(c.date)
        dechet_dates[d] += c.matiere_evaporee_kg
        if c.grammage > 0:
            grammage_dates[d].append(c.grammage)
        if c.process_type == 'FLEXO':
            dechet_flexo[d] += c.matiere_evaporee_kg
        else:
            dechet_helio[d] += c.matiere_evaporee_kg

    dates_sorted = sorted(dechet_dates.keys())

    flexo_items = [c for c in all_items if c.process_type == 'FLEXO']
    helio_items = [c for c in all_items if c.process_type == 'HELIO']

    def _stats(items):
        total_inj = sum(c.total_encre + c.total_solvant for c in items)
        total_evp = sum(c.matiere_evaporee_kg for c in items)
        total_gai = sum(c.gain_de_masse_kg for c in items)
        gram_list = [c.grammage for c in items if c.grammage > 0]
        return {
            'count': len(items),
            'total_inj': round(total_inj, 2),
            'total_evp': round(total_evp, 2),
            'total_gai': round(total_gai, 2),
            'taux_evp': round(total_evp / total_inj * 100, 2) if total_inj else 0,
            'gram_moy': round(sum(gram_list) / len(gram_list), 2) if gram_list else 0,
        }

    stats_flexo = _stats(flexo_items)
    stats_helio = _stats(helio_items)

    radar_labels = ['Total Injecté', 'Total Évaporé', 'Gain Masse', 'Taux Évap %', 'Grammage moy.']
    radar_flexo = [
        stats_flexo['total_inj'], stats_flexo['total_evp'],
        stats_flexo['total_gai'], stats_flexo['taux_evp'],
        stats_flexo['gram_moy'],
    ]
    radar_helio = [
        stats_helio['total_inj'], stats_helio['total_evp'],
        stats_helio['total_gai'], stats_helio['taux_evp'],
        stats_helio['gram_moy'],
    ]

    support_data = defaultdict(float)
    for c in all_items:
        support_data[(c.support or '—')[:25]] += c.total_encre

    top_support = sorted(support_data.items(), key=lambda x: x[1], reverse=True)[:10]

    job_seen = {}
    for c in all_items:
        key = (c.job_name or '—')[:30]
        if key not in job_seen:
            job_seen[key] = {'evap': 0, 'inj': 0}
        job_seen[key]['evap'] += c.matiere_evaporee_kg
        job_seen[key]['inj'] += c.total_encre + c.total_solvant

    job_evap = []
    for job, vals in sorted(job_seen.items(), key=lambda x: x[1]['evap'], reverse=True)[:8]:
        taux = round(vals['evap'] / vals['inj'] * 100, 1) if vals['inj'] else 0
        job_evap.append({'job': job, 'evap': round(vals['evap'], 2), 'taux': taux})

    context = {
        'count': count,
        'stats_flexo': stats_flexo,
        'stats_helio': stats_helio,
        'job_evap': job_evap,
        'chart_dec_dates': json.dumps(dates_sorted),
        'chart_dec_total': json.dumps([round(dechet_dates[d], 2) for d in dates_sorted]),
        'chart_dec_flexo': json.dumps([round(dechet_flexo.get(d, 0), 2) for d in dates_sorted]),
        'chart_dec_helio': json.dumps([round(dechet_helio.get(d, 0), 2) for d in dates_sorted]),
        'chart_gram_dates': json.dumps(dates_sorted),
        'chart_gram_vals': json.dumps([
            round(sum(grammage_dates[d]) / len(grammage_dates[d]), 2) if grammage_dates[d] else 0
            for d in dates_sorted
        ]),
        'radar_labels': json.dumps(radar_labels),
        'radar_flexo': json.dumps(radar_flexo),
        'radar_helio': json.dumps(radar_helio),
        'chart_sup_labels': json.dumps([s[0] for s in top_support]),
        'chart_sup_vals': json.dumps([round(s[1], 2) for s in top_support]),
        'chart_job_labels': json.dumps([j['job'] for j in job_evap]),
        'chart_job_evap': json.dumps([j['evap'] for j in job_evap]),
        'chart_job_taux': json.dumps([j['taux'] for j in job_evap]),
    }
    context.update(_get_encre_filter_context(request))
    return render(request, 'production_special/encre_analyse.html', context)