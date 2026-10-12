from datetime import datetime, timedelta
from django.db.models import Sum
from django.utils import timezone


def _number(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _metric(label, planned, actual, unit, lower_is_better=False, available=True):
    planned, actual = _number(planned), _number(actual)
    difference = actual - planned
    percent = (difference / planned * 100) if planned else None
    if not available:
        status = 'neutral'
    elif lower_is_better:
        status = 'good' if actual <= planned else ('warning' if percent is not None and percent <= 10 else 'bad')
    else:
        attainment = (actual / planned * 100) if planned else 0
        status = 'good' if attainment >= 100 else ('warning' if attainment >= 90 else 'bad')
    return {'label': label, 'planned': planned, 'actual': actual, 'difference': difference,
            'percent': round(percent, 2) if percent is not None else None, 'unit': unit,
            'status': status, 'available': available}


def _planned_minutes(step):
    start, end = step.date_prevue_debut, step.date_prevue_fin
    if start and end and end >= start:
        return (end - start).total_seconds() / 60
    if step.date_planifiee and step.heure_debut_planifiee and step.heure_fin_planifiee:
        start = datetime.combine(step.date_planifiee, step.heure_debut_planifiee)
        end = datetime.combine(step.date_planifiee, step.heure_fin_planifiee)
        if end <= start:
            end += timedelta(days=1)
        return (end - start).total_seconds() / 60
    return 0


def _actual_minutes(step):
    if not step.date_debut_reel:
        return 0
    end = step.date_fin_reel or (timezone.now() if step.statut == 'EN_COURS' else None)
    if not end or end < step.date_debut_reel:
        return 0
    # Durée productive : durée écoulée moins arrêts déclarés.
    return max(0, (end - step.date_debut_reel).total_seconds() / 60 - _number(step.temps_arret_minutes))


def build_of_planned_actual(of):
    """Construit le comparatif sans écrire ni dupliquer aucune donnée métier."""
    steps = list(of.etapes.all())
    totals = of.get_totaux_lot()
    has_real_sheets = bool(totals.get('nb_fiches') or totals.get('nb_saisies_anciennes'))
    actual_production = totals['total_prod_kg'] if has_real_sheets else _number(of.quantite_produite)
    actual_waste = totals['total_dechets_kg'] if has_real_sheets else _number(of.quantite_rebut)

    planned_minutes = sum(_planned_minutes(step) for step in steps)
    actual_minutes = sum(_actual_minutes(step) for step in steps)
    time_available = planned_minutes > 0 or actual_minutes > 0

    consumption_rows = []
    for row in of.etapes.values('consommations__material__name', 'consommations__material__unit').annotate(
        planned=Sum('consommations__quantite_prevue'), actual=Sum('consommations__quantite_reelle')):
        if row['consommations__material__name']:
            consumption_rows.append(_metric(row['consommations__material__name'], row['planned'], row['actual'],
                                            row['consommations__material__unit'] or '', lower_is_better=True))

    ink = None
    ink_job = of.ink_calculations.prefetch_related('colors__anilox').first()
    if ink_job:
        colors = list(ink_job.colors.all())
        theoretical = sum(color.prepare_kg for color in colors)
        entered_actual = [color for color in colors if color.actual_consumed_kg is not None]
        if entered_actual:
            real = sum(max(0, _number(color.actual_consumed_kg) - _number(color.recovered_kg)) for color in entered_actual)
        else:
            real = _number(totals.get('total_encre_kg'))
        ink = _metric('Consommation d’encre', theoretical, real, 'kg', lower_is_better=True,
                      available=bool(theoretical or real))
        ink['job_id'] = ink_job.pk

    delivery = None
    if of.date_prevue_fin:
        actual_date = of.date_fin_reelle or (timezone.localdate() if of.statut not in ('TERMINE', 'ANNULE') else None)
        if actual_date:
            days = (actual_date - of.date_prevue_fin).days
            delivery = {'planned': of.date_prevue_fin, 'actual': of.date_fin_reelle,
                        'difference_days': days, 'ongoing': of.date_fin_reelle is None,
                        'status': 'good' if days <= 0 else ('warning' if days <= 2 else 'bad')}

    return {
        'production': _metric('Production', of.quantite_prevue, actual_production, 'kg'),
        'waste': {'actual': actual_waste, 'rate': round(actual_waste / actual_production * 100, 2) if actual_production else 0},
        'time': _metric('Temps productif', planned_minutes, actual_minutes, 'min', lower_is_better=True,
                        available=time_available),
        'materials': consumption_rows,
        'ink': ink,
        'delivery': delivery,
        'real_source': 'Fiches de production' if has_real_sheets else 'Suivi de l’OF',
    }
