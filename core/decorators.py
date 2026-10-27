from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse

from .models.permissions import user_has_module_access


def _wants_json(request):
    return (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('Accept', '')
        or '/api/' in request.path
    )


def module_required(*module_names):
    """Contrôle serveur strict d'accès à un ou plusieurs modules ERP (refus par défaut).

    @module_required('drh')                     -> module RH requis
    @module_required('stock', 'dashboard')     -> l'un OU l'autre suffit
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user

            if not user.is_authenticated:
                if _wants_json(request):
                    return JsonResponse({'detail': 'Authentification requise.'}, status=401)
                return redirect_to_login(request.get_full_path())

            # Un compte désactivé ne passe jamais, même avec une session encore valide.
            if not user.is_active:
                if _wants_json(request):
                    return JsonResponse({'detail': 'Compte désactivé.'}, status=403)
                raise PermissionDenied('Compte désactivé.')

            allowed = False
            try:
                allowed = bool(
                    user.is_superuser
                    or any(user_has_module_access(user, name) for name in module_names)
                )
            except Exception:
                # En cas d'erreur de calcul des droits, on refuse (jamais d'ouverture par défaut).
                allowed = False

            if allowed:
                return view_func(request, *args, **kwargs)

            if _wants_json(request):
                return JsonResponse({'detail': 'Accès refusé à ce module.'}, status=403)
            raise PermissionDenied("Vous n'avez pas accès à ce module.")

        return wrapper
    return decorator
