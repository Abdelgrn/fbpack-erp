from pathlib import Path
import os
import warnings

import dj_database_url
import django

BASE_DIR = Path(__file__).resolve().parent.parent
IS_RENDER = bool(os.environ.get('RENDER'))


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(name, default=''):
    return [item.strip() for item in os.environ.get(name, default).split(',') if item.strip()]


# ---------------------------------------------------------------------- #
# Clé secrète, debug, hôtes
# ---------------------------------------------------------------------- #
DEV_SECRET_KEY = 'dev-only-change-me-never-use-in-production'

# En production, aucune clé faible de secours n'est autorisée.
SECRET_KEY = os.environ.get('SECRET_KEY', '')
if not SECRET_KEY:
    if IS_RENDER:
        raise RuntimeError('La variable Render SECRET_KEY est obligatoire.')
    SECRET_KEY = DEV_SECRET_KEY
if IS_RENDER and len(SECRET_KEY) < 50:
    # Avertissement seulement : ne bloque pas le démarrage. À corriger dans Render.
    warnings.warn('SECRET_KEY courte : utilisez au moins 50 caractères aléatoires.')

# DEBUG est toujours désactivé sur Render, quelle que soit la variable d'environnement.
DEBUG = env_bool('DJANGO_DEBUG', default=not IS_RENDER) and not IS_RENDER

if not DEBUG and SECRET_KEY == DEV_SECRET_KEY:
    warnings.warn('La clé de développement est utilisée avec DEBUG désactivé : définissez SECRET_KEY.')

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


# ---------------------------------------------------------------------- #
# Applications
# ---------------------------------------------------------------------- #
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
    'core.module_access_middleware.ModuleAccessMiddleware',
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


# ---------------------------------------------------------------------- #
# Base de données
# ---------------------------------------------------------------------- #
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
    # SQLite (développement local). Le chat et les notifications écrivent en continu :
    # sans réglage, SQLite répond « database is locked ».
    _sqlite_options = {'timeout': 30}  # attend jusqu'à 30 s qu'une écriture se termine
    if django.VERSION >= (5, 1):
        # IMMEDIATE : une transaction réserve l'écriture dès son début et attend son tour,
        #             au lieu d'échouer en cours de route.
        # WAL       : les lectures (chat, notifications) ne bloquent plus les écritures.
        _sqlite_options['transaction_mode'] = 'IMMEDIATE'
        _sqlite_options['init_command'] = 'PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;'
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'OPTIONS': _sqlite_options,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ---------------------------------------------------------------------- #
# Langue, fichiers statiques et médias
# ---------------------------------------------------------------------- #
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = os.environ.get('TIME_ZONE', 'Africa/Algiers')
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# STATICFILES_STORAGE est supprimé en Django 5.1 : STORAGES est utilisé dès Django 4.2.
if django.VERSION >= (4, 2):
    STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
    }
else:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
LOGIN_URL = '/accounts/login/'


# ---------------------------------------------------------------------- #
# Sessions et cookies
# ---------------------------------------------------------------------- #
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


# ---------------------------------------------------------------------- #
# HTTPS et en-têtes de sécurité
# ---------------------------------------------------------------------- #
# Ne faire confiance à X-Forwarded-Proto que derrière le proxy Render :
# en local, un client pourrait sinon falsifier cet en-tête.
if IS_RENDER:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = IS_RENDER and not env_bool('DISABLE_SSL_REDIRECT', False)
SECURE_HSTS_SECONDS = 31536000 if IS_RENDER else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'DENY'


# ---------------------------------------------------------------------- #
# Limites anti-abus
# ---------------------------------------------------------------------- #
# 25 Mo maximum par requête/import (appliqué aussi par le middleware via Content-Length).
MAX_REQUEST_BODY_BYTES = int(os.environ.get('MAX_REQUEST_BODY_BYTES', 25 * 1024 * 1024))
# Limite sur les données hors fichiers (formulaires, JSON), lues en mémoire.
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_REQUEST_BODY_BYTES
# Au-delà de 5 Mo, un fichier envoyé est écrit sur disque et non gardé en mémoire.
FILE_UPLOAD_MAX_MEMORY_SIZE = min(MAX_REQUEST_BODY_BYTES, 5 * 1024 * 1024)
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000
DATA_UPLOAD_MAX_NUMBER_FILES = 100

# Taille maximale de la restauration complète (1 Go par défaut). Réservée à la vue
# superadmin protégée. Cette limite ne s'applique qu'aux fichiers envoyés (multipart).
BACKUP_MAX_UPLOAD_BYTES = int(os.environ.get('BACKUP_MAX_UPLOAD_BYTES', 1024 * 1024 * 1024))


# ---------------------------------------------------------------------- #
# Jetons d'intégration (définir des valeurs longues et aléatoires dans Render)
# ---------------------------------------------------------------------- #
# Une valeur vide désactive la fonction : les vues doivent refuser si le jeton est vide.
PESEE_SYNC_TOKEN = os.environ.get('PESEE_SYNC_TOKEN', '')
BACKUP_AGENT_TOKEN = os.environ.get('BACKUP_AGENT_TOKEN', '')
if IS_RENDER:
    for _token_name, _token_value in (
        ('PESEE_SYNC_TOKEN', PESEE_SYNC_TOKEN),
        ('BACKUP_AGENT_TOKEN', BACKUP_AGENT_TOKEN),
    ):
        if _token_value and len(_token_value) < 32:
            warnings.warn(f'{_token_name} court : utilisez au moins 32 caractères aléatoires.')


# ---------------------------------------------------------------------- #
# Contrôle d'accès central par module (core/module_access_middleware.py)
# ---------------------------------------------------------------------- #
# False = mode observation : rien n'est bloqué, les accès qui seraient refusés
# sont écrits dans les journaux (« module_access_would_deny »).
# True  = mode bloquant. À activer seulement après quelques jours d'observation.
MODULE_ACCESS_ENFORCE = env_bool('MODULE_ACCESS_ENFORCE', default=False)

# False = personne (hors superadmin) ne peut valider sa propre demande
# (congé, bulletin de paie, demande d'achat). True = comportement actuel.
ERP_ALLOW_SELF_APPROVAL = env_bool('ERP_ALLOW_SELF_APPROVAL', default=True)


# ---------------------------------------------------------------------- #
# Centre de surveillance des connexions (migration core 0047)
# ---------------------------------------------------------------------- #
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


# ---------------------------------------------------------------------- #
# Cache
# ---------------------------------------------------------------------- #
# Le cache sert au verrouillage temporaire des connexions. LocMem est propre à chaque
# processus : avec plusieurs workers gunicorn, le verrouillage serait contourné.
# Définir REDIS_URL dans Render (et installer le paquet `redis`) pour un cache partagé.
REDIS_URL = os.environ.get('REDIS_URL', '').strip()
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'TIMEOUT': 900,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'fbpack-security-cache',
            'TIMEOUT': 900,
            'OPTIONS': {'MAX_ENTRIES': 10000},
        }
    }


# ---------------------------------------------------------------------- #
# Journalisation
# ---------------------------------------------------------------------- #
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