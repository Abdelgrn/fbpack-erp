from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse

from .models.permissions import user_has_module_access


def _wants_json(request):
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
        or request.path.startswith('/api/')
        or '/api/' in request.path
    )


def module_required(module_name):
    """Contrôle serveur strict d'accès à un module ERP."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if _wants_json(request):
                    return JsonResponse({'detail': 'Authentification requise.'}, status=401)
                return redirect_to_login(request.get_full_path())

            if request.user.is_superuser or user_has_module_access(request.user, module_name):
                return view_func(request, *args, **kwargs)

            if _wants_json(request):
                return JsonResponse({'detail': 'Accès refusé à ce module.'}, status=403)
            raise PermissionDenied("Vous n'avez pas accès à ce module.")

        return wrapper
    return decorator
