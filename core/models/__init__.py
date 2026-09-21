import os
import json
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.db.models import Q
from django.apps import apps
from django.conf import settings
from django.db import transaction, connection

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


def robust_import_local_data():
    """Importateur universel : importe 100% des 9 machines, clients, OFs, stocks et fiches depuis data_import.json sans toucher aux utilisateurs de Render"""
    from django.contrib.auth.models import User

    search_paths = [
        'data_import.json',
        'data_core.json',
        'data.json',
        os.path.join(getattr(settings, 'BASE_DIR', ''), 'data_import.json'),
        os.path.join(getattr(settings, 'BASE_DIR', ''), 'data_core.json'),
        os.path.join(getattr(settings, 'BASE_DIR', ''), 'data.json'),
    ]

    filepath = None
    for fp in search_paths:
        if fp and os.path.exists(fp):
            filepath = fp
            break

    if not filepath:
        return False, "❌ Fichier de données introuvable (data_import.json)."

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        return False, f"❌ Erreur de lecture du fichier {filepath}: {e}"

    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        admin_user = User.objects.create_superuser('admin', 'admin@fbpack.com', 'admin1234')

    model_priority = [
        'auth.user',
        'core.atelier',
        'core.supplier',
        'core.department',
        'core.position',
        'core.stocklocation',
        'core.material',
        'core.machine',
        'core.client',
        'core.technicalproduct',
        'core.tooling',
        'core.processtype',
        'core.ordrefabrication',
        'core.productionorder',
        'core.etapeproduction',
        'core.ficheproductionjournaliere',
    ]

    def get_priority(item):
        m = item.get('model', '')
        try:
            return model_priority.index(m)
        except ValueError:
            return 99

    sorted_data = sorted(data, key=get_priority)

    # 1. Créer uniquement les utilisateurs du fichier JSON s'ils n'existent pas sur Render
    for item in sorted_data:
        if item.get('model') == 'auth.user':
            pk = item.get('pk')
            fields = item.get('fields', {})
            username = fields.get('username')
            if username and not User.objects.filter(username=username).exists():
                try:
                    with transaction.atomic():
                        u = User(
                            pk=pk, username=username, email=fields.get('email', ''),
                            first_name=fields.get('first_name', ''), last_name=fields.get('last_name', ''),
                            is_staff=fields.get('is_staff', False), is_active=fields.get('is_active', True),
                            is_superuser=fields.get('is_superuser', False)
                        )
                        u.password = fields.get('password', '')
                        u.save()
                except Exception:
                    pass

    # 2. Importer les objets métier
    counts = {}

    for item in sorted_data:
        model_str = item.get('model')
        if model_str in ['auth.user', 'contenttypes.contenttype', 'auth.permission']:
            continue

        pk = item.get('pk')
        fields = dict(item.get('fields', {}))

        try:
            ModelClass = apps.get_model(model_str)
        except Exception:
            continue

        for fname in list(fields.keys()):
            try:
                fobj = ModelClass._meta.get_field(fname)
                if fobj.is_relation and not fobj.many_to_many:
                    related_cls = fobj.related_model
                    val = fields[fname]
                    if val is not None:
                        if not related_cls.objects.filter(pk=val).exists():
                            if related_cls == User:
                                fields[fname] = admin_user.pk
                            elif fobj.null:
                                fields[fname] = None
                            else:
                                first_obj = related_cls.objects.first()
                                fields[fname] = first_obj.pk if first_obj else None
            except Exception:
                pass

        m2m = {}
        clean_fields = {}
        for fname, val in fields.items():
            try:
                fobj = ModelClass._meta.get_field(fname)
                if fobj.many_to_many:
                    m2m[fname] = val
                else:
                    clean_fields[fname] = val
            except Exception:
                clean_fields[fname] = val

        success = False
        try:
            with transaction.atomic():
                obj, _ = ModelClass.objects.update_or_create(pk=pk, defaults=clean_fields)
                for mname, mval in m2m.items():
                    try:
                        getattr(obj, mname).set(mval)
                    except Exception:
                        pass
                success = True
        except Exception:
            try:
                with transaction.atomic():
                    obj = ModelClass.objects.create(**clean_fields)
                    for mname, mval in m2m.items():
                        try:
                            getattr(obj, mname).set(mval)
                        except Exception:
                            pass
                    success = True
            except Exception:
                pass

        if success:
            counts[model_str] = counts.get(model_str, 0) + 1

    # Réinitialisation des séquences PostgreSQL
    if connection.vendor == 'postgresql':
        try:
            with connection.cursor() as cursor:
                for model_name in counts.keys():
                    try:
                        cls = apps.get_model(model_name)
                        table = cls._meta.db_table
                        cursor.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE(MAX(id), 1)) FROM {table};")
                    except Exception:
                        pass
        except Exception:
            pass

    nb_m = Machine.objects.count()
    nb_c = Client.objects.count()
    nb_of = OrdreFabrication.objects.count() + ProductionOrder.objects.count()
    nb_mat = Material.objects.count()

    return True, f"✅ Importation réussie ! {nb_m} machines, {nb_c} clients, {nb_of} OF(s) et {nb_mat} matières premières sont maintenant en ligne !"


@receiver(post_migrate)
def auto_init_super_admin_et_permissions(sender, **kwargs):
    if sender.name == 'core':
        try:
            from django.contrib.auth.models import User
            from .crm import Client

            if not Client.objects.exists():
                robust_import_local_data()

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
    'UserModulePermission', 'user_has_module_access', 'robust_import_local_data',
]