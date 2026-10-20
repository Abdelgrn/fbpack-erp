from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
IS_RENDER = bool(os.environ.get('RENDER'))


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    return [item.strip() for item in os.environ.get(name, default).split(',') if item.strip()]


# En production, aucune clé faible de secours n'est autorisée.
SECRET_KEY = os.environ.get('SECRET_KEY', '')
if not SECRET_KEY:
    if IS_RENDER:
        raise RuntimeError('La variable Render SECRET_KEY est obligatoire.')
    SECRET_KEY = 'dev-only-change-me-never-use-in-production'

DEBUG = env_bool('DJANGO_DEBUG', default=not IS_RENDER)

render_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME', '').strip()
default_hosts = '127.0.0.1,localhost'
if render_hostname:
    default_hosts += f',{render_hostname}'
ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', default_hosts)
if '*' in ALLOWED_HOSTS and not DEBUG:
    raise RuntimeError("ALLOWED_HOSTS='*' est interdit en production.")

CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')
if render_hostname:
    render_origin = f'https://{render_hostname}'
    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(render_origin)


if IS_RENDER:
    INSTALLED_APPS = [
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'core',
    ]
else:
    INSTALLED_APPS = [
        'daphne',
        'django.contrib.admin',
        'django.contrib.auth',
        'django.contrib.contenttypes',
        'django.contrib.sessions',
        'django.contrib.messages',
        'django.contrib.staticfiles',
        'channels',
        'core',
    ]
    ASGI_APPLICATION = 'fbpack.asgi.application'
    CHANNEL_LAYERS = {
        'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}
    }

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.security_middleware.RequestSecurityMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'fbpack.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.maintenance_alerts',
                'core.context_processors.user_permissions',
                'core.context_processors.alertes_usine_chat',
                'core.context_processors.security_monitoring_status',
            ],
        },
    },
]

WSGI_APPLICATION = 'fbpack.wsgi.application'

if IS_RENDER and os.environ.get('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ['DATABASE_URL'],
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = os.environ.get('TIME_ZONE', 'Africa/Algiers')
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
LOGIN_URL = '/accounts/login/'

# Sessions et cookies
SESSION_COOKIE_NAME = 'fbpack_sessionid'
CSRF_COOKIE_NAME = 'fbpack_csrftoken'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = IS_RENDER
CSRF_COOKIE_SECURE = IS_RENDER
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = int(os.environ.get('SESSION_COOKIE_AGE', 8 * 60 * 60))
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_SAVE_EVERY_REQUEST = True

# HTTPS et en-têtes de sécurité Render
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = IS_RENDER and not env_bool('DISABLE_SSL_REDIRECT', False)
SECURE_HSTS_SECONDS = 31536000 if IS_RENDER else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'DENY'

# Limites anti-abus : 25 Mo maximum par requête/import.
MAX_REQUEST_BODY_BYTES = int(os.environ.get('MAX_REQUEST_BODY_BYTES', 25 * 1024 * 1024))
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_REQUEST_BODY_BYTES
FILE_UPLOAD_MAX_MEMORY_SIZE = min(MAX_REQUEST_BODY_BYTES, 5 * 1024 * 1024)
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000
# Jeton de la pesée (à définir dans Render : PESEE_SYNC_TOKEN, valeur longue et aléatoire)
PESEE_SYNC_TOKEN = os.environ.get('PESEE_SYNC_TOKEN', '')
# Centre de surveillance des connexions (migration core 0047).
# Render remplace X-Forwarded-For ; en local cette confiance reste désactivée.
SECURITY_TRUST_PROXY_HEADERS = env_bool('SECURITY_TRUST_PROXY_HEADERS', default=IS_RENDER)
SECURITY_MONITOR_ONLINE_MINUTES = 5
SECURITY_MONITOR_RECONCILE_SECONDS = int(
    os.environ.get('SECURITY_MONITOR_RECONCILE_SECONDS', 120)
)
SECURITY_EVENT_RETENTION_DAYS = int(
    os.environ.get('SECURITY_EVENT_RETENTION_DAYS', 90)
)
SECURITY_EVENT_EXPORT_LIMIT = int(
    os.environ.get('SECURITY_EVENT_EXPORT_LIMIT', 50000)
)
SECURITY_BUSINESS_HOUR_START = int(
    os.environ.get('SECURITY_BUSINESS_HOUR_START', 6)
)
SECURITY_BUSINESS_HOUR_END = int(
    os.environ.get('SECURITY_BUSINESS_HOUR_END', 22)
)

# Le cache sert notamment au verrouillage temporaire des connexions.
# Sur une instance unique Render, LocMem est suffisant. REDIS_URL pourra être ajouté plus tard.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'fbpack-security-cache',
        'TIMEOUT': 900,
        'OPTIONS': {'MAX_ENTRIES': 10000},
    }
}

# Journal de sécurité envoyé aux logs Render, sans mot de passe ni contenu sensible.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'security': {'format': '{asctime} {levelname} {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'security'},
    },
    'loggers': {
        'security': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'django.security': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
}


# Sauvegarde automatique FB PACK. Définir une valeur longue et aléatoire dans Render.
BACKUP_AGENT_TOKEN = os.environ.get('BACKUP_AGENT_TOKEN', '')
# Taille maximale restauration complète (1 Go). Réservée à la vue superadmin protégée.
BACKUP_MAX_UPLOAD_BYTES = int(os.environ.get('BACKUP_MAX_UPLOAD_BYTES', 1024 * 1024 * 1024))
DATA_UPLOAD_MAX_MEMORY_SIZE = BACKUP_MAX_UPLOAD_BYTES
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
