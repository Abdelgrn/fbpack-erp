import logging

from django.conf import settings
from django.contrib.auth import logout as auth_logout
from django.core.cache import cache
from django.http import JsonResponse

from .models.security_audit import SecuritySession
from .services.security_monitoring import (
    current_session_fingerprint,
    record_access_denied,
    record_logout,
    reconcile_expired_sessions,
    release_expired_temporary_disables,
    safe_route,
    track_authenticated_request,
)

logger = logging.getLogger('security')

BODY_METHODS = ('POST', 'PUT', 'PATCH')
SENSITIVE_PREFIXES = (
    '/accounts/',
    '/admin/',
    '/administration/',
    '/assistant/',
    '/chat/api/',
)


class RequestSecurityMiddleware:
    """Durcissement des requêtes et suivi sécurisé des sessions ERP."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.max_bytes = getattr(settings, 'MAX_REQUEST_BODY_BYTES', 25 * 1024 * 1024)
        self.reconcile_seconds = max(
            30,
            int(getattr(settings, 'SECURITY_MONITOR_RECONCILE_SECONDS', 120)),
        )

    # ------------------------------------------------------------------ #
    # Utilitaires
    # ------------------------------------------------------------------ #
    @staticmethod
    def _safe_call(label, func, *args, **kwargs):
        """Le suivi de sécurité ne doit jamais transformer une requête en erreur 500."""
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            logger.error('%s_failed error=%s', label, type(exc).__name__)
            return None

    def _secure_response_headers(self, request, response, authenticated_before=False):
        response.headers['Permissions-Policy'] = (
            'camera=(self), microphone=(), geolocation=(), payment=(), '
            'usb=(), serial=(), interest-cohort=()'
        )
        response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
        response.headers['X-Permitted-Cross-Domain-Policies'] = 'none'
        # Ne casse pas les scripts/styles inline existants : on verrouille seulement
        # l'intégration en cadre, les balises <base> et les plugins.
        if 'Content-Security-Policy' not in response.headers:
            response.headers['Content-Security-Policy'] = (
                "frame-ancestors 'none'; base-uri 'self'; object-src 'none'"
            )

        user = getattr(request, 'user', None)
        is_authenticated = bool(getattr(user, 'is_authenticated', False))
        sensitive_path = request.path.startswith(SENSITIVE_PREFIXES)
        # Les pages authentifiées et les réponses sensibles ne doivent pas être mises en cache.
        if authenticated_before or is_authenticated or sensitive_path:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    def _reject(self, request, status, detail):
        response = JsonResponse({'detail': detail}, status=status)
        return self._secure_response_headers(request, response)

    def _periodic_maintenance(self):
        lock_key = 'security-monitoring:periodic-maintenance'
        if cache.add(lock_key, 1, timeout=self.reconcile_seconds):
            release_expired_temporary_disables()
            reconcile_expired_sessions()

    # ------------------------------------------------------------------ #
    # Traitement de la requête
    # ------------------------------------------------------------------ #
    def __call__(self, request):
        content_length = request.META.get('CONTENT_LENGTH')

        if content_length:
            try:
                effective_max_bytes = self.max_bytes
                # La restauration complète possède sa propre limite et reste
                # strictement réservée au superadministrateur côté vue.
                if (
                    request.path == '/administration/backup/restore/'
                    and getattr(getattr(request, 'user', None), 'is_superuser', False)
                ):
                    effective_max_bytes = int(
                        getattr(settings, 'BACKUP_MAX_UPLOAD_BYTES', self.max_bytes)
                    )
                declared = int(content_length)
                if declared < 0:
                    return self._reject(request, 400, 'Taille de requête invalide.')
                if declared > effective_max_bytes:
                    logger.warning(
                        'request_too_large route=%s bytes=%s',
                        safe_route(request),
                        content_length,
                    )
                    return self._reject(request, 413, 'Requête trop volumineuse.')
            except (TypeError, ValueError):
                return self._reject(request, 400, 'Taille de requête invalide.')
        elif (
            not settings.DEBUG
            and request.method in BODY_METHODS
            and 'chunked' in request.META.get('HTTP_TRANSFER_ENCODING', '').lower()
        ):
            # Sans Content-Length, la limite de taille ne pourrait pas être appliquée.
            logger.warning('request_chunked_refused route=%s', safe_route(request))
            return self._reject(request, 411, 'Taille de requête requise.')

        self._safe_call('security_periodic_maintenance', self._periodic_maintenance)

        user_before = getattr(request, 'user', None)
        authenticated_before = bool(getattr(user_before, 'is_authenticated', False))
        fingerprint_before = ''
        if authenticated_before:
            fingerprint_before = self._safe_call(
                'session_fingerprint', current_session_fingerprint, request
            ) or ''

            monitored = self._safe_call(
                'security_track_request', track_authenticated_request, request
            )
            if monitored and monitored.status != SecuritySession.Status.ACTIVE:
                # Une session marquée close ne doit jamais être ressuscitée.
                self._safe_call('forced_logout', auth_logout, request)

        response = self.get_response(request)

        if response.status_code == 403:
            self._safe_call('record_access_denied', record_access_denied, request)

        session_after = getattr(getattr(request, 'session', None), 'session_key', None)
        if authenticated_before and fingerprint_before and not session_after:
            self._safe_call(
                'record_logout', record_logout, request, fingerprint=fingerprint_before
            )

        return self._secure_response_headers(
            request,
            response,
            authenticated_before=authenticated_before,
        )
