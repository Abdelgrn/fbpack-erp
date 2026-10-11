import os

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

from core.views.security import SecureLoginView

# Permet de remplacer /admin/ par une URL moins évidente via Render.
# Exemple : ADMIN_URL=gestion-securisee-fbpack/
ADMIN_URL = os.environ.get('ADMIN_URL', 'admin/').strip('/') + '/'

urlpatterns = [
    path(ADMIN_URL, admin.site.urls),

    # AUTHENTIFICATION RENFORCÉE
    path('accounts/login/', SecureLoginView.as_view(), name='login'),
    path(
        'accounts/logout/',
        auth_views.LogoutView.as_view(next_page='/accounts/login/'),
        name='logout',
    ),

    # APPLICATION
    path('', include('core.urls')),
]

# Les médias ne sont servis directement par Django qu'en développement local.
# En production, utilisez un stockage persistant/protégé adapté aux documents ERP.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
