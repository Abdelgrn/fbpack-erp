from django.db import models
from django.contrib.auth.models import User


class UserModulePermission(models.Model):
    """Permissions par module pour chaque utilisateur"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='module_permissions')

    can_access_dashboard = models.BooleanField("Dashboard", default=True)
    can_access_planning = models.BooleanField("Planning Gantt", default=False)
    can_access_reporting = models.BooleanField("Reporting", default=False)
    can_access_crm = models.BooleanField("CRM & Devis", default=False)
    can_access_prepress = models.BooleanField("Prépresse & Outils", default=False)
    can_access_planification = models.BooleanField("Planification Atelier", default=False)
    can_access_production = models.BooleanField("Production Spécial", default=False)
    can_access_stock = models.BooleanField("Stocks & Achats", default=False)
    can_access_maintenance = models.BooleanField("Maintenance", default=False)
    can_access_drh = models.BooleanField("Ressources Humaines", default=False)
    can_access_chat = models.BooleanField("Chat d'Équipe", default=True)
    can_access_import = models.BooleanField("Import Excel", default=False)
    can_access_admin = models.BooleanField("Administration", default=False)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'core'
        verbose_name = "Permission Module Utilisateur"
        verbose_name_plural = "Permissions Modules Utilisateurs"

    def __str__(self):
        return f"Permissions de {self.user.username}"

    def get_allowed_modules(self):
        """Retourne la liste des modules autorisés"""
        modules = []
        if self.can_access_dashboard: modules.append('dashboard')
        if self.can_access_planning: modules.append('planning')
        if self.can_access_reporting: modules.append('reporting')
        if self.can_access_crm: modules.append('crm')
        if self.can_access_prepress: modules.append('prepress')
        if self.can_access_planification: modules.append('planification')
        if self.can_access_production: modules.append('production')
        if self.can_access_stock: modules.append('stock')
        if self.can_access_maintenance: modules.append('maintenance')
        if self.can_access_drh: modules.append('drh')
        if self.can_access_chat: modules.append('chat')
        if self.can_access_import: modules.append('import')
        if self.can_access_admin: modules.append('admin')
        return modules

    def has_module_access(self, module_name):
        """Vérifie si l'utilisateur a accès à un module"""
        return getattr(self, f'can_access_{module_name}', False)


def user_has_module_access(user, module_name):
    """Fonction utilitaire globale pour vérifier l'accès"""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    try:
        perms = user.module_permissions
        return perms.has_module_access(module_name)
    except UserModulePermission.DoesNotExist:
        return False