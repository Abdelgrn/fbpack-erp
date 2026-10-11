def density_default(process, ink_type):
    if ink_type=='WHITE': return 1.35
    return 1.00

def validate_coverage(area_cm2, coverage, repeat_mm, width_mm):
    if area_cm2 and repeat_mm and width_mm:
        calculated=area_cm2/((repeat_mm*width_mm)/100)
        return abs(calculated-coverage)<=1.0, calculated
    return True, coverage
