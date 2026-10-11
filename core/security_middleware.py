import logging
from django.conf import settings
from django.http import JsonResponse

logger = logging.getLogger('security')


class RequestSecurityMiddleware:
    """Durcissement léger sans dépendance externe."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.max_bytes = getattr(settings, 'MAX_REQUEST_BODY_BYTES', 25 * 1024 * 1024)

    def __call__(self, request):
        content_length = request.META.get('CONTENT_LENGTH')
        if content_length:
            try:
                if int(content_length) > self.max_bytes:
                    logger.warning('request_too_large path=%s bytes=%s', request.path, content_length)
                    return JsonResponse({'detail': 'Requête trop volumineuse.'}, status=413)
            except (TypeError, ValueError):
                return JsonResponse({'detail': 'Taille de requête invalide.'}, status=400)

        response = self.get_response(request)
        response.headers['Permissions-Policy'] = (
            'camera=(self), microphone=(), geolocation=(), payment=(), '
            'usb=(), serial=(), interest-cohort=()'
        )
        response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
        response.headers['X-Permitted-Cross-Domain-Policies'] = 'none'

        # Les pages authentifiées et les réponses sensibles ne doivent pas être mises en cache.
        if request.user.is_authenticated or request.path.startswith(('/accounts/', '/admin/', '/assistant/', '/chat/api/')):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
        return response
