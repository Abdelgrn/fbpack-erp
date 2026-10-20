from django.db import models
from django.contrib.auth.models import User


class UserModulePermission(models.Model):
    """Permissions par module pour chaque utilisateur"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='module_permissions')

    can_access_dashboard = models.BooleanField("Dashboard", default=True)
    can_access_planning = models.BooleanField("Planning Gantt", default=False)
    can_access_reporting = models.BooleanField("Reporting", default=False)
    can_access_kpi = models.BooleanField("KPI & Data Analyse", default=False)
    can_access_crm = models.BooleanField("CRM & Devis", default=False)
    can_access_prepress = models.BooleanField("Prépresse & Outils", default=False)
    can_access_planification = models.BooleanField("Planification Atelier", default=False)
    can_access_production = models.BooleanField("Production Spécial", default=False)
    can_access_stock = models.BooleanField("Stocks & Achats", default=False)
    can_access_suivi_postes = models.BooleanField("Suivi par poste (Stock)", default=False)
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
        if self.can_access_kpi: modules.append('kpi')
        if self.can_access_crm: modules.append('crm')
        if self.can_access_prepress: modules.append('prepress')
        if self.can_access_planification: modules.append('planification')
        if self.can_access_production: modules.append('production')
        if self.can_access_stock: modules.append('stock')
        if self.can_access_suivi_postes: modules.append('suivi_postes')
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


class ModuleAdministrator(models.Model):
    """Délégation d'administration strictement limitée à un module ERP."""
    MODULE_CHOICES = [
        ('dashboard','Dashboard'), ('planning','Planning Gantt'), ('reporting','Reporting'),
        ('kpi','KPI & Data Analyse'), ('crm','CRM & Devis'), ('prepress','Prépresse & Outils'),
        ('planification','Planification Atelier'), ('production','Production'), ('stock','Stocks & Achats'),
        ('maintenance','Maintenance'), ('drh','Ressources Humaines'), ('chat','Chat'), ('import','Import Excel'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='administered_modules')
    module = models.CharField(max_length=30, choices=MODULE_CHOICES)
    granted_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='module_admin_grants')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    class Meta:
        app_label = 'core'
        constraints = [models.UniqueConstraint(fields=['user','module'], name='unique_module_administrator')]
        ordering = ['module','user__username']
    def __str__(self):
        return f'{self.user.username} — {self.get_module_display()}'


class AdministrationAuditLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name='erp_admin_actions')
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='erp_admin_history')
    action = models.CharField(max_length=40)
    module = models.CharField(max_length=30, blank=True)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = 'core'
        ordering = ['-created_at']


# Import cumulatif : core.models.__init__ charge déjà ce module dans le projet
# existant. Cet import enregistre donc les modèles 0047 sans remplacer ni
# deviner le contenu actuel de core/models/__init__.py.
from .security_audit import (  # noqa: E402,F401
    AccountSecurityState,
    KnownAccessSignature,
    SecurityEvent,
    SecurityEventType,
    SecurityRiskLevel,
    SecuritySession,
)
