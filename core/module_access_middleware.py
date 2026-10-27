"""Contrôle d'accès central par module ERP.

Ce middleware associe chaque début d'adresse à un ou plusieurs modules
(UserModulePermission) et refuse l'accès aux utilisateurs qui n'y ont pas droit,
sans modifier aucune vue.

Deux modes (variable MODULE_ACCESS_ENFORCE dans settings.py / Render) :
  - False (défaut) : MODE OBSERVATION. Rien n'est bloqué. Chaque accès qui AURAIT
    été refusé est écrit dans les journaux (logger "security") :
        module_access_would_deny user_id=12 route=/drh/payslips/ need=drh
  - True : MODE BLOQUANT. Accès refusé (403) ou redirection vers la connexion.

Les deux routes à jeton (sauvegarde et pesée) sont toujours gardées, quel que soit
le mode : elles refusent toute requête si le jeton n'est pas configuré.
"""
import hmac
import logging
import os

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse

from .decorators import _wants_json
from .models.permissions import ModuleAdministrator, user_has_module_access

logger = logging.getLogger('security')

# Types de règles
PUBLIC = 'public'        # aucune connexion exigée (connexion, statiques, routes à jeton)
OPEN = 'open'            # tout utilisateur connecté
SUPERUSER = 'superuser'  # superadministrateur uniquement
ADMIN = 'admin'          # module « admin » ou administrateur délégué d'un module

# (préfixe d'adresse sans « / » initial, règle)
# Une règle est soit un type ci-dessus, soit un tuple de modules : l'accès est accordé
# si l'utilisateur possède AU MOINS UN de ces modules.
RULES = [
    # --- publiques ---
    ('accounts/', PUBLIC),
    ('static/', PUBLIC),
    ('admin/', PUBLIC),                       # admin Django : gère sa propre connexion
    (os.environ.get('ADMIN_URL', 'admin/').strip('/') + '/', PUBLIC),  # URL d'admin renommée (ADMIN_URL)
    ('manifest.json', PUBLIC),
    ('favicon.ico', PUBLIC),
    ('robots.txt', PUBLIC),
    ('sw.js', PUBLIC),
    ('service-worker.js', PUBLIC),
    ('api/pesee/sync/', PUBLIC),              # jeton (garde dédiée ci-dessous)
    ('administration/backup/download/', PUBLIC),  # jeton (garde dédiée ci-dessous)

    # --- administration ---
    ('administration/backup/restore/', SUPERUSER),
    ('administration/security/', SUPERUSER),
    ('administration/', ADMIN),

    # --- production, encre, traçabilité ---
    ('prod/encre/', ('production',)),
    ('prod/', ('production',)),
    ('production/', ('production',)),

    # --- stock ---
    ('stock/suivi-postes/', ('suivi_postes', 'stock')),
    ('stock/import/', ('import', 'stock')),
    ('stock/api/dashboard/', ('stock', 'dashboard')),
    ('stock/search/api/', ('stock', 'crm', 'prepress', 'production', 'planification')),
    ('stock/', ('stock',)),
    ('import/', ('import', 'stock', 'prepress', 'production')),

    # --- CRM, ordres de fabrication ---
    ('crm/of/', ('crm', 'planification', 'production', 'stock', 'prepress')),
    ('crm/', ('crm',)),
    ('of/', ('planification', 'production', 'crm')),

    # --- planification ---
    ('planification/gantt/', ('planning', 'planification')),
    ('planification/', ('planification',)),

    # --- prépresse, outillages, encre ---
    ('prepress/', ('prepress',)),
    ('tools/', ('prepress',)),
    ('ink/', ('prepress', 'crm')),

    # --- autres modules ---
    ('machines/', ('planification', 'production', 'maintenance', 'prepress')),
    ('maintenance/', ('maintenance',)),
    ('drh/', ('drh',)),
    ('chat/', ('chat',)),
    ('reporting/', ('reporting',)),

    # --- ouvertes à tout utilisateur connecté (comme dans context_processors.py) ---
    ('kpi/', OPEN),
    ('notifications/', OPEN),
    ('assistant/', OPEN),
    ('search/', OPEN),
    ('', OPEN),   # accueil et tout le reste : connexion obligatoire
]
# Le préfixe le plus long l'emporte.
RULES.sort(key=lambda rule: len(rule[0]), reverse=True)


def match_rule(path):
    """Retourne (préfixe, règle) pour une adresse sans « / » initial."""
    for prefix, rule in RULES:
        if path.startswith(prefix):
            return prefix, rule
    return '', OPEN


class ModuleAccessMiddleware:
    """À placer après AuthenticationMiddleware (et après RequestSecurityMiddleware)."""

    def __init__(self, get_response):
        self.get_response = get_response

    # ------------------------------------------------------------------ #
    # Routes à jeton : toujours gardées, quel que soit le mode
    # ------------------------------------------------------------------ #
    @staticmethod
    def _deny_json(status, detail):
        return JsonResponse({'detail': detail}, status=status)

    def _guard_token_routes(self, request):
        path = request.path_info.lstrip('/')

        if path == 'administration/backup/download/':
            expected = (getattr(settings, 'BACKUP_AGENT_TOKEN', '') or '').strip()
            auth = request.META.get('HTTP_AUTHORIZATION', '')
            if auth.startswith('Bearer '):
                provided = auth[7:].strip()
                # Jeton vide ou différent : refus. Comparaison à temps constant.
                if expected and hmac.compare_digest(
                    provided.encode('utf-8'), expected.encode('utf-8')
                ):
                    return None
                logger.warning('backup_download_token_refused configured=%s', bool(expected))
                return self._deny_json(403, 'Accès refusé.')
            user = getattr(request, 'user', None)
            if user is not None and user.is_authenticated and user.is_superuser:
                return None
            logger.warning('backup_download_refused anonymous_or_not_superuser')
            return self._deny_json(403, 'Accès refusé.')

        if path == 'api/pesee/sync/':
            if not (getattr(settings, 'PESEE_SYNC_TOKEN', '') or '').strip():
                logger.warning('pesee_sync_refused token_not_configured')
                return self._deny_json(503, 'Synchronisation désactivée.')
        return None

    # ------------------------------------------------------------------ #
    # Contrôle par module
    # ------------------------------------------------------------------ #
    @staticmethod
    def _evaluate(request, rule):
        """Retourne None si autorisé, sinon ('login'|'forbidden', description)."""
        if rule == PUBLIC:
            return None
        user = request.user
        if not user.is_authenticated:
            return ('login', 'authentication')
        if not user.is_active:
            return ('forbidden', 'active_account')
        if user.is_superuser or rule == OPEN:
            return None
        if rule == SUPERUSER:
            return ('forbidden', 'superuser')
        if rule == ADMIN:
            if user_has_module_access(user, 'admin'):
                return None
            if ModuleAdministrator.objects.filter(user=user, is_active=True).exists():
                return None
            return ('forbidden', 'admin|module_administrator')
        if any(user_has_module_access(user, module) for module in rule):
            return None
        return ('forbidden', '|'.join(rule))

    def _log_would_deny(self, request, prefix, need):
        user_id = getattr(request.user, 'id', None)
        # Une seule ligne de journal par utilisateur et par zone toutes les 5 minutes.
        if cache.add(f'module-access:{user_id}:{prefix}', 1, timeout=300):
            logger.warning(
                'module_access_would_deny user_id=%s route=%s need=%s',
                user_id,
                request.path[:200],
                need,
            )

    def __call__(self, request):
        blocked = self._guard_token_routes(request)
        if blocked is not None:
            return blocked

        enforce = bool(getattr(settings, 'MODULE_ACCESS_ENFORCE', False))
        path = request.path_info.lstrip('/')
        prefix, rule = match_rule(path)

        try:
            verdict = self._evaluate(request, rule)
        except Exception as exc:
            # Une panne de ce contrôle ne doit pas rendre l'ERP inutilisable.
            logger.error('module_access_check_failed error=%s', type(exc).__name__)
            verdict = None

        if verdict is None:
            return self.get_response(request)

        kind, need = verdict
        if not enforce:
            if kind == 'forbidden':
                self._log_would_deny(request, prefix, need)
            return self.get_response(request)

        if kind == 'login':
            if _wants_json(request):
                return self._deny_json(401, 'Authentification requise.')
            return redirect_to_login(request.get_full_path())

        logger.warning(
            'module_access_denied user_id=%s route=%s need=%s',
            getattr(request.user, 'id', None),
            request.path[:200],
            need,
        )
        if _wants_json(request):
            return self._deny_json(403, 'Accès refusé à ce module.')
        raise PermissionDenied("Vous n'avez pas accès à ce module.")
