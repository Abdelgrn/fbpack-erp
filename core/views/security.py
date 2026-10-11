import hashlib
import hmac
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.http import HttpResponse

logger = logging.getLogger('security')


class SecureLoginView(LoginView):
    """Connexion protégée sans dépendance externe ni stockage de mot de passe."""

    template_name = 'registration/login.html'
    redirect_authenticated_user = True
    max_identity_attempts = 5
    max_ip_attempts = 20
    lock_seconds = 15 * 60

    def _client_ip(self):
        # Render remplace X-Forwarded-For au niveau de son proxy de confiance.
        forwarded = self.request.META.get('HTTP_X_FORWARDED_FOR', '')
        return forwarded.split(',')[0].strip() if forwarded else self.request.META.get('REMOTE_ADDR', 'unknown')

    def _cache_key(self, scope):
        username = (self.request.POST.get('username') or '').strip().lower()
        identity = self._client_ip() if scope == 'ip' else f'{self._client_ip()}|{username}'
        digest = hmac.new(settings.SECRET_KEY.encode(), identity.encode(), hashlib.sha256).hexdigest()
        return f'login-security:{scope}:{digest}'

    def _attempts(self, scope):
        return int(cache.get(self._cache_key(scope), 0) or 0)

    def _locked(self):
        return (
            self._attempts('identity') >= self.max_identity_attempts
            or self._attempts('ip') >= self.max_ip_attempts
        )

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST' and self._locked():
            logger.warning('login_locked ip=%s', self._client_ip())
            response = HttpResponse(
                'Trop de tentatives. Attendez 15 minutes avant de réessayer.',
                status=429,
                content_type='text/plain; charset=utf-8',
            )
            response.headers['Retry-After'] = str(self.lock_seconds)
            return response
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        for scope in ('identity', 'ip'):
            key = self._cache_key(scope)
            cache.set(key, self._attempts(scope) + 1, timeout=self.lock_seconds)

        identity_attempts = self._attempts('identity')
        logger.warning('login_failed ip=%s attempts=%s', self._client_ip(), identity_attempts)
        remaining = max(0, self.max_identity_attempts - identity_attempts)
        if remaining:
            messages.error(self.request, f'Identifiants incorrects. {remaining} tentative(s) restante(s).')
        else:
            messages.error(self.request, 'Connexion temporairement protégée pendant 15 minutes.')
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(self._cache_key('identity'))
        cache.delete(self._cache_key('ip'))
        user = form.get_user()
        logger.info('login_success user_id=%s ip=%s', user.pk, self._client_ip())
        return super().form_valid(form)
