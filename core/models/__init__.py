import os
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.db.models import Q

# CRM
from .crm import (
    Client, ClientContact, InteractionLog, Opportunite,
    CommandeClient, LigneCommandeClient, DemandePrix,
)

# Prepress
from .prepress import TechnicalProduct, Tooling

# Stock
from .stock import (
    Supplier, Material, StockLocation, StockLot, StockMovement,
    DemandeAchat, BonCommande, LigneBonCommande, StockSeuil
)

# Machines
from .machines import Atelier, Machine, CompteurMachine

# Maintenance
from .maintenance import (
    CategoriePiece, PieceRechange, MouvementPiece,
    PlanMaintenancePreventive, OrdreMaintenance,
    ConsommationPiece, AlerteMaintenance
)

# Production OF
from .production_of import (
    ProcessType, OrdreFabrication, EtapeProduction,
    SemiProduit, SuiviProduction, ConsommationMatiere
)

# Production Spéciale & Quote
from .production_speciale import (
    ProductionOrder, ConsumptionLog, PurchaseOrder, Quote,
    ProductionEntry, CalculTempsProduction
)

# Encre
from .encre import ConsommationEncre

# Fiches
from .fiches import (
    FicheProductionJournaliere, FicheExtrusionMatiere, FicheExtrusionArret,
    FicheImpressionBobineEntree, FicheImpressionBobineImprimee,
    FicheImpressionEncreGroupe, FicheComplexageDerouleur1,
    FicheComplexageDerouleur2, FicheComplexageEnrouleur,
    FicheFondCarreEquipe, FicheDecoupeBobineMere, FicheDecoupeBobineFille,
    FicheDecoupeArret, FicheDecoupeControle,
)

# DRH
from .drh import (
    Department, Position, Employee, EmployeeDocument, Skill,
    EmployeeSkill, MachineAuthorization, Shift, Attendance,
    LeaveType, LeaveRequest, SalaryGrid, Payslip, WorkSchedule,
    ShiftAssignment, MedicalVisit, WorkIncident, ProtectiveEquipment
)

# Chat
from .chat import ChatRoom, ChatMessage, UserPresence

# Permissions
from .permissions import UserModulePermission, user_has_module_access


# --- CORRECTION AUTOMATIQUE DES MACHINES APRES MIGRATE ---
@receiver(post_migrate)
def corriger_base_machines_post_migrate(sender, **kwargs):
    if sender.name == 'core':
        try:
            Machine.objects.filter(Q(name__icontains='1.3M') | Q(name__icontains='1M')).exclude(
                Q(name__icontains='1350') | Q(name__icontains='Panther')
            ).delete()

            Machine.objects.filter(name__icontains='1350').update(
                type='DEC',
                name='DCM Panther 1350'
            )

            Machine.objects.filter(Q(name__icontains='DCM panther 1') | Q(name__icontains='DCM Panther 1')).exclude(
                name__icontains='1350'
            ).update(
                type='DEC2',
                name='DCM Panther 1'
            )
        except Exception:
            pass


# --- INITIALISATION SÉCURISÉE DES PERMISSIONS & ADMIN ---
@receiver(post_migrate)
def auto_init_super_admin_et_permissions(sender, **kwargs):
    if sender.name == 'core':
        try:
            from django.contrib.auth.models import User

            # 1. Créer l'admin uniquement s'il n'existe AUCUN superutilisateur
            if not User.objects.filter(is_superuser=True).exists():
                username = os.environ.get('ADMIN_USERNAME', 'admin')
                password = os.environ.get('ADMIN_PASSWORD', 'admin1234')
                email = os.environ.get('ADMIN_EMAIL', 'admin@fbpack.com')

                admin_user, created = User.objects.get_or_create(username=username)
                if created:
                    admin_user.set_password(password)
                    admin_user.email = email
                    admin_user.is_superuser = True
                    admin_user.is_staff = True
                    admin_user.save()

            # 2. S'assurer que tous les utilisateurs existants ont leur fiche de permissions
            all_fields = [
                'can_access_dashboard', 'can_access_planning', 'can_access_reporting',
                'can_access_crm', 'can_access_prepress', 'can_access_planification',
                'can_access_production', 'can_access_stock', 'can_access_maintenance',
                'can_access_drh', 'can_access_chat', 'can_access_import', 'can_access_admin'
            ]

            for u in User.objects.all():
                p, _ = UserModulePermission.objects.get_or_create(user=u)
                if u.is_superuser:
                    for field in all_fields:
                        setattr(p, field, True)
                    p.save()
        except Exception:
            pass


# --- EXPORT DE TOUS LES MODÈLES ---
__all__ = [
    # CRM
    'Client', 'ClientContact', 'InteractionLog', 'Opportunite',
    'CommandeClient', 'LigneCommandeClient', 'DemandePrix',
    # Prepress
    'TechnicalProduct', 'Tooling',
    # Stock
    'Supplier', 'Material', 'StockLocation', 'StockLot', 'StockMovement',
    'DemandeAchat', 'BonCommande', 'LigneBonCommande', 'StockSeuil',
    # Machines
    'Atelier', 'Machine', 'CompteurMachine',
    # Maintenance
    'CategoriePiece', 'PieceRechange', 'MouvementPiece',
    'PlanMaintenancePreventive', 'OrdreMaintenance', 'ConsommationPiece', 'AlerteMaintenance',
    # Production OF
    'ProcessType', 'OrdreFabrication', 'EtapeProduction', 'SemiProduit',
    'SuiviProduction', 'ConsommationMatiere',
    # Production Spéciale
    'ProductionOrder', 'ConsumptionLog', 'PurchaseOrder', 'Quote',
    'ProductionEntry', 'CalculTempsProduction',
    # Encre
    'ConsommationEncre',
    # Fiches
    'FicheProductionJournaliere', 'FicheExtrusionMatiere', 'FicheExtrusionArret',
    'FicheImpressionBobineEntree', 'FicheImpressionBobineImprimee', 'FicheImpressionEncreGroupe',
    'FicheComplexageDerouleur1', 'FicheComplexageDerouleur2', 'FicheComplexageEnrouleur',
    'FicheFondCarreEquipe', 'FicheDecoupeBobineMere', 'FicheDecoupeBobineFille',
    'FicheDecoupeArret', 'FicheDecoupeControle',
    # DRH
    'Department', 'Position', 'Employee', 'EmployeeDocument', 'Skill', 'EmployeeSkill',
    'MachineAuthorization', 'Shift', 'Attendance', 'LeaveType', 'LeaveRequest', 'SalaryGrid',
    'Payslip', 'WorkSchedule', 'ShiftAssignment', 'MedicalVisit', 'WorkIncident', 'ProtectiveEquipment',
    # Chat
    'ChatRoom', 'ChatMessage', 'UserPresence',
    # Permissions
    'UserModulePermission', 'user_has_module_access',
]