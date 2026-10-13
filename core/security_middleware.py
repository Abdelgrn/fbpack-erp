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


class RequestSecurityMiddleware:
    """Durcissement des requêtes et suivi sécurisé des sessions ERP."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.max_bytes = getattr(settings, 'MAX_REQUEST_BODY_BYTES', 25 * 1024 * 1024)
        self.reconcile_seconds = max(
            30,
            int(getattr(settings, 'SECURITY_MONITOR_RECONCILE_SECONDS', 120)),
        )

    def _secure_response_headers(self, request, response, authenticated_before=False):
        response.headers['Permissions-Policy'] = (
            'camera=(self), microphone=(), geolocation=(), payment=(), '
            'usb=(), serial=(), interest-cohort=()'
        )
        response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
        response.headers['X-Permitted-Cross-Domain-Policies'] = 'none'

        user = getattr(request, 'user', None)
        is_authenticated = bool(getattr(user, 'is_authenticated', False))
        sensitive_path = request.path.startswith(
            (
                '/accounts/',
                '/admin/',
                '/administration/',
                '/assistant/',
                '/chat/api/',
            )
        )
        # Les pages authentifiées et les réponses sensibles ne doivent pas être mises en cache.
        if authenticated_before or is_authenticated or sensitive_path:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    def _periodic_maintenance(self):
        lock_key = 'security-monitoring:periodic-maintenance'
        if cache.add(lock_key, 1, timeout=self.reconcile_seconds):
            release_expired_temporary_disables()
            reconcile_expired_sessions()

    def __call__(self, request):
        content_length = request.META.get('CONTENT_LENGTH')
        if content_length:
            try:
                effective_max_bytes = self.max_bytes
                # La restauration complète existante possède sa propre limite et reste
                # strictement réservée au superadministrateur côté vue.
                if (
                    request.path == '/administration/backup/restore/'
                    and getattr(getattr(request, 'user', None), 'is_superuser', False)
                ):
                    effective_max_bytes = int(
                        getattr(settings, 'BACKUP_MAX_UPLOAD_BYTES', self.max_bytes)
                    )
                if int(content_length) > effective_max_bytes:
                    logger.warning('request_too_large route=%s bytes=%s', safe_route(request), content_length)
                    response = JsonResponse({'detail': 'Requête trop volumineuse.'}, status=413)
                    return self._secure_response_headers(request, response)
            except (TypeError, ValueError):
                response = JsonResponse({'detail': 'Taille de requête invalide.'}, status=400)
                return self._secure_response_headers(request, response)

        try:
            self._periodic_maintenance()
        except Exception as exc:
            # Le déploiement peut exécuter brièvement le code avant la migration 0047.
            logger.error('security_periodic_maintenance_failed error=%s', type(exc).__name__)

        user_before = getattr(request, 'user', None)
        authenticated_before = bool(getattr(user_before, 'is_authenticated', False))
        fingerprint_before = current_session_fingerprint(request) if authenticated_before else ''

        if authenticated_before:
            monitored = track_authenticated_request(request)
            if monitored and monitored.status != SecuritySession.Status.ACTIVE:
                # Défense supplémentaire : une session marquée close ne doit jamais être ressuscitée.
                try:
                    auth_logout(request)
                except Exception as exc:
                    logger.error('forced_logout_failed error=%s', type(exc).__name__)

        response = self.get_response(request)

        if response.status_code == 403:
            record_access_denied(request)

        session_after = getattr(getattr(request, 'session', None), 'session_key', None)
        if authenticated_before and fingerprint_before and not session_after:
            record_logout(request, fingerprint=fingerprint_before)

        return self._secure_response_headers(
            request,
            response,
            authenticated_before=authenticated_before,
        )
