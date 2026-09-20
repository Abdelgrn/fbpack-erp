from .models import AlerteMaintenance
from .models.permissions import UserModulePermission


def maintenance_alerts(request):
    """Ajoute le compteur d'alertes maintenance à tous les templates"""
    if request.user.is_authenticated:
        try:
            count = AlerteMaintenance.objects.filter(est_traitee=False).count()
        except Exception:
            count = 0
        return {'alertes_maintenance_count': count}
    return {'alertes_maintenance_count': 0}


def user_permissions(request):
    """Injecte les permissions par module dans tous les templates"""
    if not request.user.is_authenticated:
        return {'user_modules': [], 'is_super_admin': False}

    if request.user.is_superuser:
        return {
            'user_modules': [
                'dashboard', 'planning', 'reporting', 'crm', 'prepress',
                'planification', 'production', 'stock', 'maintenance',
                'drh', 'chat', 'import', 'admin'
            ],
            'is_super_admin': True,
        }

    try:
        perms = request.user.module_permissions
        return {
            'user_modules': perms.get_allowed_modules(),
            'is_super_admin': False,
        }
    except UserModulePermission.DoesNotExist:
        return {'user_modules': ['dashboard'], 'is_super_admin': False}