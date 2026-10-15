def density_default(process, ink_type):
    # LOT BAT AUTOFILL V1.3 : densités FB PACK — blanc TiO2 1,5 ; autres encres 1,3.
    # Valeur pré-remplie modifiable côté formulaire ; utilisée aussi si champ vidé.
    if ink_type=='WHITE': return 1.5
    return 1.3

def validate_coverage(area_cm2, coverage, repeat_mm, width_mm):
    # LOT BAT AUTOFILL V1.3 : cohérence cm2 <-> couverture exprimée en POURCENT
    # (l'ancienne formule rendait un ratio 0-1 : tout pré-remplissage BAT échouait)
    if area_cm2 and repeat_mm and width_mm:
        calculated=100.0*area_cm2/((repeat_mm*width_mm)/100.0)
        return abs(calculated-coverage)<=1.0, calculated
    return True, coverage
