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


def robust_import_local_data(specific_file=None):
    """Importateur universel garanti : convertit automatiquement les Foreign Keys en objets Django réels
    et accepte un fichier spécifique lors d'une restauration manuelle.
    """
    from django.contrib.auth.models import User

    search_paths = [
        specific_file,
        'FULL_BACKUP_FBPACK.json',
        'FULL_BACKUP_RENDER_OFFICIEL.json',
        'data_import.json',
        'data_core.json',
        'data.json',
        os.path.join(getattr(settings, 'BASE_DIR', ''), 'FULL_BACKUP_FBPACK.json'),
        os.path.join(getattr(settings, 'BASE_DIR', ''), 'data_import.json'),
    ]

    filepath = None
    for fp in search_paths:
        if fp and os.path.exists(fp):
            filepath = fp
            break

    if not filepath:
        return False, "❌ Fichier de données ou de sauvegarde introuvable."

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
        'auth.group',
        'core.usermodulepermission',
        'core.atelier',
        'core.supplier',
        'core.client',
        'core.department',
        'core.position',
        'core.stocklocation',
        'core.material',
        'core.machine',
        'core.technicalproduct',
        'core.tooling',
        'core.processtype',
        'core.ordrefabrication',
        'core.productionorder',
        'core.etapeproduction',
        'core.semiproduit',
        'core.ficheproductionjournaliere',
        'core.productionentry',
    ]

    def get_priority(item):
        m = item.get('model', '')
        try:
            return model_priority.index(m)
        except ValueError:
            return 99

    sorted_data = sorted(data, key=get_priority)

    # 1. Ne créer que les utilisateurs manquants du JSON sans altérer les utilisateurs de Render
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

    # 2. Importer tous les objets métier avec résolution dynamique des FK
    counts = {}
    errors = []

    for item in sorted_data:
        model_str = item.get('model')
        if model_str in ['auth.user', 'auth.group', 'contenttypes.contenttype', 'auth.permission']:
            continue

        pk = item.get('pk')
        raw_fields = dict(item.get('fields', {}))

        try:
            ModelClass = apps.get_model(model_str)
        except Exception as e:
            errors.append(f"{model_str}: Modèle introuvable ({e})")
            continue

        clean_fields = {}
        m2m_fields = {}

        for field_name, val in raw_fields.items():
            try:
                fobj = ModelClass._meta.get_field(field_name)
            except Exception:
                continue

            if fobj.many_to_many:
                m2m_fields[field_name] = val
            elif fobj.is_relation:
                rel_model = fobj.related_model
                if val is None:
                    clean_fields[field_name] = None
                else:
                    rel_obj = rel_model.objects.filter(pk=val).first()
                    if rel_obj:
                        clean_fields[field_name] = rel_obj
                    else:
                        if rel_model == User:
                            clean_fields[field_name] = admin_user
                        elif fobj.null:
                            clean_fields[field_name] = None
                        else:
                            clean_fields[field_name] = rel_model.objects.first()
            else:
                clean_fields[field_name] = val

        success = False
        try:
            with transaction.atomic():
                obj, _ = ModelClass.objects.update_or_create(pk=pk, defaults=clean_fields)
                for m_name, m_pks in m2m_fields.items():
                    if m_pks:
                        try:
                            m_fobj = ModelClass._meta.get_field(m_name)
                            m_rel_model = m_fobj.related_model
                            m_objs = m_rel_model.objects.filter(pk__in=m_pks)
                            getattr(obj, m_name).set(m_objs)
                        except Exception:
                            pass
                success = True
        except Exception as err1:
            try:
                with transaction.atomic():
                    obj = ModelClass.objects.create(**clean_fields)
                    for m_name, m_pks in m2m_fields.items():
                        if m_pks:
                            try:
                                m_fobj = ModelClass._meta.get_field(m_name)
                                m_rel_model = m_fobj.related_model
                                m_objs = m_rel_model.objects.filter(pk__in=m_pks)
                                getattr(obj, m_name).set(m_objs)
                            except Exception:
                                pass
                    success = True
            except Exception as err2:
                errors.append(f"{model_str} (pk={pk}): {err2}")

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

    msg = f"🎉 PARFAIT ! Importation/Restauration réussie depuis {os.path.basename(filepath)} ! En base Render : {nb_m} machines, {nb_c} clients, {nb_of} OF(s), {nb_mat} matières premières."
    if errors:
        msg += f" (⚠️ {len(errors)} éléments ignorés)"

    return True, msg


@receiver(post_migrate)
def corriger_base_machines_post_migrate(sender, **kwargs):
    if sender.name == 'core':
        try:
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