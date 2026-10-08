from django.utils import timezone
from datetime import timedelta
from django.contrib.messages import get_messages

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
                'drh', 'chat', 'import', 'admin', 'kpi'
            ],
            'is_super_admin': True,
        }

    try:
        perms = request.user.module_permissions
        modules = list(perms.get_allowed_modules())

        if 'kpi' not in modules:
            modules.append('kpi')

        return {
            'user_modules': modules,
            'is_super_admin': False,
        }

    except UserModulePermission.DoesNotExist:
        return {'user_modules': ['dashboard', 'kpi'], 'is_super_admin': False}


def _is_message_kpi_chat_noise(message):
    """
    Détecte tous les messages d'alertes automatiques KPI / Stock / Usine.
    """
    try:
        txt = str(message.message if hasattr(message, 'message') else message)
    except Exception:
        txt = ""

    if not txt:
        return False

    signatures = [
        'KPI-ALERTE',
        'ChatMessage object',
        'Alertes Usine',
        'Stock bas',
        'Stock actuel',
        'seuil min',
        'outillage usé',
        'retard production',
        '📦',
        '🚨',
        '📌',
        '[KPI-',
    ]

    txt_upper = txt.upper()
    return any(sig.upper() in txt_upper for sig in signatures)


def alertes_usine_chat(request):
    """
    1) Compteur des alertes KPI envoyées dans le salon Alertes Usine sur les dernières 24h.
    2) Suppression stricte des messages parasites pour les bandeaux bleus.
    """

    # ==========================================================
    # 1. COMPTEUR ALERTES USINE
    # ==========================================================
    if not request.user.is_authenticated:
        return {
            'alertes_usine_count': 0,
            'messages_flash': [],
        }

    try:
        from .models import ChatMessage
        limite = timezone.now() - timedelta(hours=24)
        count = ChatMessage.objects.filter(
            room__slug='alertes-usine',
            type_message='ALERT',
            date_envoi__gte=limite
        ).count()
    except Exception:
        count = 0

    # ==========================================================
    # 2. PURGE DES BANDEAUX EN SESSION
    # ==========================================================
    messages_filtres = []

    try:
        storage = get_messages(request)

        for msg in storage:
            if _is_message_kpi_chat_noise(msg):
                continue
            messages_filtres.append(msg)

        storage.used = True

        if hasattr(request, 'session') and '_messages' in request.session:
            try:
                del request.session['_messages']
            except KeyError:
                pass

    except Exception:
        messages_filtres = []

    return {
        'alertes_usine_count': count,
        'messages_flash': messages_filtres,
    }