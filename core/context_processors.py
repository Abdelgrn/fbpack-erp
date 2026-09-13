from .models import AlerteMaintenance


def maintenance_alerts(request):
    """Ajoute le compteur d'alertes maintenance à tous les templates"""
    if request.user.is_authenticated:
        try:
            count = AlerteMaintenance.objects.filter(est_traitee=False).count()
        except Exception:
            count = 0
        return {'alertes_maintenance_count': count}
    return {'alertes_maintenance_count': 0}