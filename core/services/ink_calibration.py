"""Estimation calée de la consommation d'encre (LOT INK_CALIBRATION V1.3).

Réglages de référence : transfert anilox 32 %, densité 0,87 (couleurs ET blanc),
données du fournisseur d'encre. Le moteur théorique (ink_calculator) n'est PAS modifié ici.

Facteur = consommation réelle nette / théorique net (mêmes réglages), PAR m².
Calé sur 5 jobs de production : CHOR KHALED, SULTANA 1, Chips RIFKUS ZVITI HOT,
DulcesoIPANDORINO, MAMAMIA VERT 50 g (facteurs recalculés depuis la V1.2 pour 32 % / 0,87).

- CALIBRATION : famille vue sur 2 jobs ou plus (médiane, min, max, nombre de jobs).
- INDICATIVE  : encre vue sur 1 seul job : facteur seul, sans fourchette.
- Autres encres : facteur 1,0, « non calé ».
"""

# famille -> (médiane, min, max, nombre de jobs)
CALIBRATION = {
    'Blanc':        (0.84, 0.73, 1.23, 4),
    'PANTONE 485':  (1.14, 0.90, 2.50, 3),
    'Cyan':         (5.16, 3.77, 5.44, 4),
    'Magenta':      (1.44, 1.08, 4.86, 5),
    'Yellow':       (1.36, 0.93, 2.50, 5),
    'Black':        (1.14, 0.56, 4.54, 5),
}

# encres vues sur un seul job : facteur indicatif, pas de fourchette
INDICATIVE = {
    'PANTONE 7442C': 1.34,
    'PANTONE 7385': 2.26,
    'PANTONE 3272 C': 1.51,
    'PANTONE 254 C': 1.03,
    'Gold': 1.91,
}

_ALIASES = {
    'blanc': 'Blanc', 'white': 'Blanc',
    'pantone 485': 'PANTONE 485', 'pantone 485 c': 'PANTONE 485', 'pantone 485c': 'PANTONE 485',
    'cyan': 'Cyan', 'magenta': 'Magenta', 'yellow': 'Yellow', 'jaune': 'Yellow',
    'black': 'Black', 'pantone black c': 'Black',
    'pantone 7442c': 'PANTONE 7442C', 'pantone 7442': 'PANTONE 7442C',
    'pantone 7385': 'PANTONE 7385', 'pantone 7385 c': 'PANTONE 7385',
    'pantone 3272 c': 'PANTONE 3272 C', 'pantone 3272': 'PANTONE 3272 C',
    'pantone 254 c': 'PANTONE 254 C', 'pantone 254': 'PANTONE 254 C',
    'gold': 'Gold',
}


def family_for(name):
    """Famille d'un nom d'encre, ou None si l'encre n'est pas calée."""
    key = ' '.join((name or '').lower().split())
    return _ALIASES.get(key)


def calibrated_estimate(name, theoretical_net_kg):
    """Estimation nette d'une encre (kg). Retourne un dict."""
    fam = family_for(name)
    base = {'famille': fam, 'theorique_kg': round(theoretical_net_kg, 3)}
    if fam in CALIBRATION:
        med, lo, hi, n = CALIBRATION[fam]
        return dict(base, statut=f'calé sur {n} jobs', facteur=med,
                    estime_kg=round(theoretical_net_kg * med, 3),
                    bas_kg=round(theoretical_net_kg * lo, 3),
                    haut_kg=round(theoretical_net_kg * hi, 3))
    if fam in INDICATIVE:
        med = INDICATIVE[fam]
        return dict(base, statut='indicatif (1 job)', facteur=med,
                    estime_kg=round(theoretical_net_kg * med, 3), bas_kg=None, haut_kg=None)
    return dict(base, statut='non calé', facteur=1.0,
                estime_kg=round(theoretical_net_kg, 3), bas_kg=None, haut_kg=None)


def estimate_job(lines):
    """lines : liste de (nom, net_theorique_kg). Retourne (lignes, totaux)."""
    rows = [dict(nom=n, **calibrated_estimate(n, kg)) for n, kg in lines]
    tot = {
        'theorique_kg': round(sum(r['theorique_kg'] for r in rows), 3),
        'estime_kg': round(sum(r['estime_kg'] for r in rows), 3),
        'bas_kg': round(sum(r['bas_kg'] if r['bas_kg'] is not None else r['estime_kg'] for r in rows), 3),
        'haut_kg': round(sum(r['haut_kg'] if r['haut_kg'] is not None else r['estime_kg'] for r in rows), 3),
    }
    return rows, tot


def calibrated_g_m2(name, theoretical_g_m2):
    """Estimation par m² (g/m²) : même logique, unité g/m²."""
    r = calibrated_estimate(name, theoretical_g_m2)
    return {'statut': r['statut'], 'facteur': r['facteur'],
            'estime_g_m2': round(r['estime_kg'], 3),
            'bas_g_m2': None if r['bas_kg'] is None else round(r['bas_kg'], 3),
            'haut_g_m2': None if r['haut_kg'] is None else round(r['haut_kg'], 3)}
