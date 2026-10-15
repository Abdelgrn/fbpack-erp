"""Fournisseurs de clichés et consommation par fournisseur (V1.10). Pur Python, sans Django.

SUPPLIER_CHOICES doit rester identique à CLICHE_SUPPLIER_CHOICES du modèle InkCalculationJob.
"""

SUPPLIER_CHOICES = ['Studio Flexo', 'Poly Slim', 'Yahiaoui Photogravure', 'Autre']
NON_RENSEIGNE = 'Non renseigné'


def supplier_or_blank(value):
    """Valeur postée acceptée seulement si elle figure dans la liste ; sinon vide."""
    value = (value or '').strip()
    return value if value in SUPPLIER_CHOICES else ''


def summarize(triples):
    """triples : (fournisseur ou vide, kg à préparer, surface m²).

    Retourne une ligne par fournisseur, triée par consommation totale décroissante.
    g/m² = total kg × 1000 ÷ total surface : compare des jobs de tailles différentes.
    """
    groups = {}
    for supplier, kg, area in triples:
        key = supplier or NON_RENSEIGNE
        g = groups.setdefault(key, {'supplier': key, 'jobs': 0, 'total_kg': 0.0, 'total_m2': 0.0})
        g['jobs'] += 1
        g['total_kg'] += float(kg or 0)
        g['total_m2'] += float(area or 0)
    out = []
    for g in groups.values():
        g['avg_kg'] = g['total_kg'] / g['jobs'] if g['jobs'] else 0.0
        g['g_per_m2'] = g['total_kg'] * 1000.0 / g['total_m2'] if g['total_m2'] else 0.0
        out.append(g)
    return sorted(out, key=lambda g: -g['total_kg'])
