from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from .models.permissions import user_has_module_access


def module_required(module_name):
    """Décorateur pour restreindre l'accès à un module"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            if user_has_module_access(request.user, module_name):
                return view_func(request, *args, **kwargs)

            messages.error(request, f"❌ Vous n'avez pas accès à ce module.")
            return redirect('dashboard')
        return wrapper
    return decorator