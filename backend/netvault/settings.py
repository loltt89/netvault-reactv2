"""
Django settings for netvault project.
NetVault - Network Device Configuration Backup System
"""

from pathlib import Path
from datetime import timedelta
import os
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured('SECRET_KEY environment variable is required. Set it in .env file.')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = [host.strip() for host in os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')]

# Self-hosted LAN appliance: this box's own address commonly moves under
# DHCP (already happened once — 192.168.8.124 -> .125) and re-editing
# ALLOWED_HOSTS by hand every time it does isn't sustainable. Off by
# default — same opt-in shape as CORS_ALLOW_PRIVATE_NETWORKS below, and
# meant to be turned on together with it. See core/host_validation.py for
# what this actually widens and why that's judged an acceptable trade-off
# only for a LAN deployment, not a default posture.
ALLOW_PRIVATE_NETWORK_HOSTS = os.getenv('ALLOW_PRIVATE_NETWORK_HOSTS', 'False') == 'True'


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'channels',
    'django_celery_beat',
    'drf_spectacular',
    'django_prometheus',

    # Local apps
    'core.apps.CoreConfig',  # Shared infrastructure: SystemSettings, crypto, dashboard/health endpoints
    'accounts',
    'devices',
    'backups',
    'notifications',
    'compliance',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # CORS must be before CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'netvault.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'netvault.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DB_ENGINE = os.getenv('DB_ENGINE', 'sqlite3')

if DB_ENGINE == 'sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / os.getenv('DB_NAME', 'db.sqlite3'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.getenv('DB_NAME', 'netvault'),
            'USER': os.getenv('DB_USER', 'netvault_user'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '3306'),
            'CONN_MAX_AGE': 600,  # Keep connections alive for 10 minutes
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
                'connect_timeout': 10,
                'read_timeout': 30,
                'write_timeout': 30,
            },
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

# Timezone configuration - automatically detected from system
# Priority: 1) TIME_ZONE env var (if set), 2) System timezone (/etc/timezone), 3) UTC fallback
def get_system_timezone():
    """Get timezone from system or environment variable"""
    # Check if explicitly set in .env (optional override)
    env_tz = os.getenv('TIME_ZONE', '').strip()
    if env_tz:
        return env_tz

    # Try to read system timezone
    try:
        with open('/etc/timezone', 'r') as f:
            system_tz = f.read().strip()
            if system_tz:
                return system_tz
    except (FileNotFoundError, PermissionError):
        pass

    # Fallback to UTC
    return 'UTC'

TIME_ZONE = get_system_timezone()

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'accounts.authentication.CookieJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        # Deliberately generous: also covers core/health_views.py's
        # health/readiness/liveness probes, which legitimate Docker/
        # Kubernetes monitoring can poll every few seconds — a tight
        # blanket limit here would risk throttling real infrastructure,
        # not just abuse. Endpoints that actually do sensitive or
        # expensive work under this scope (self-registration) get their
        # own tighter scope instead — see 'register' below.
        'anon': '10000/hour',  # Anonymous users: 10000 requests per hour
        'user': '100000/hour',  # Authenticated users: 100000 per hour
        'login': '200/hour',  # Login attempts: 200 per hour per IP
        'register': '30/hour',  # Self-registration attempts: 30 per hour per IP (see RegisterRateThrottle)
        'two_factor_verify': '10/hour',  # TOTP confirmation attempts: 10 per hour per user
        # Both of these open a real SSH/Telnet session to a device.
        # DeviceLock already stops two of these racing against the *same*
        # device; this instead bounds how many a single user can fire off
        # against *any number* of devices in a row.
        'device_connection_test': '60/hour',  # manual "Test Connection" clicks, per user
        'device_backup_now': '30/hour',  # manual "Backup Now" triggers, per user
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': (
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ),
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DATETIME_FORMAT': '%Y-%m-%d %H:%M:%S',
    'DATE_FORMAT': '%Y-%m-%d',
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',
}

# JWT Configuration
#
# SIGNING_KEY defaults to SECRET_KEY only as a fallback for deployments that
# haven't set JWT_SIGNING_KEY yet — set it explicitly and separately from
# SECRET_KEY in .env. SECRET_KEY also signs Django sessions, CSRF tokens,
# and password-reset tokens; sharing it with JWT means any exposure of one
# (a leaked .env, a misconfigured debug endpoint, an unrelated signing bug)
# lets an attacker forge the other too, instead of the blast radius being
# contained to whichever single-purpose secret actually leaked. Rotating
# JWT_SIGNING_KEY invalidates every outstanding access/refresh token,
# forcing re-login — same operational caveat as rotating SECRET_KEY today,
# just now scoped to auth tokens instead of also nuking sessions/CSRF.
JWT_SIGNING_KEY = os.getenv('JWT_SIGNING_KEY', '').strip() or SECRET_KEY

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('JWT_ACCESS_TOKEN_LIFETIME', '60'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('JWT_REFRESH_TOKEN_LIFETIME', '1440'))),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': os.getenv('JWT_ALGORITHM', 'HS256'),
    'SIGNING_KEY': JWT_SIGNING_KEY,
    'VERIFYING_KEY': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# CORS Configuration
# Only allow specified origins (set in .env or use defaults)
CORS_ALLOW_ALL_ORIGINS = False

# Default includes localhost only — install.sh always sets
# CORS_ALLOWED_ORIGINS explicitly to the real deployment domain, so this
# default is really only hit for local dev.
_default_cors = 'http://localhost:3000,http://127.0.0.1:3000,http://localhost,http://127.0.0.1'
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', _default_cors).split(',')

# Trusting "any origin that looks like a private IP" is a wider trust
# boundary than a self-hosted app with a known, install-time-configured
# domain (CORS_ALLOWED_ORIGINS above) actually needs — combined with
# CORS_ALLOW_CREDENTIALS below, it means literally anything else on the
# same LAN claiming a 192.168.x.x/10.x.x.x/172.16-31.x.x Origin header
# gets a credentialed CORS response. Off by default now; opt in only if
# you specifically need to reach this instance from multiple private IPs
# that aren't worth enumerating explicitly (e.g. no stable DNS yet).
if os.getenv('CORS_ALLOW_PRIVATE_NETWORKS', 'False') == 'True':
    CORS_ALLOWED_ORIGIN_REGEXES = [
        r"^https?://192\.168\.\d{1,3}\.\d{1,3}(:\d+)?$",
        r"^https?://10\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?$",
        r"^https?://172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}(:\d+)?$",
    ]

CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# WebAuthn (passkeys) — an alternative/additional 2FA factor to TOTP.
#
# The browser flatly refuses to run WebAuthn ceremonies outside a "secure
# context": HTTPS, or the literal hostname `localhost`. A bare IP address
# (the exact thing ALLOW_PRIVATE_NETWORK_HOSTS/CORS_ALLOW_PRIVATE_NETWORKS
# exist to make work for everything *else* in this app) does not qualify —
# WebAuthn's rp_id must be a real DNS domain, not an IP. So this feature is
# opt-in via the same domain that install.sh already puts in
# CORS_ALLOWED_ORIGINS, and simply won't offer itself (frontend
# feature-detects window.isSecureContext) on an HTTP/IP-only deployment.
#
# WEBAUTHN_RP_ID must be exactly the domain the browser sees in its address
# bar (no scheme, no port) — defaults to the hostname of the first
# CORS_ALLOWED_ORIGINS entry, which is already install-time-configured to
# the real deployment domain. Override explicitly via .env if that default
# is wrong for your setup (e.g. multiple domains, non-default port setups).
def _default_webauthn_rp_id():
    from urllib.parse import urlparse
    for origin in CORS_ALLOWED_ORIGINS:
        hostname = urlparse(origin).hostname
        if hostname:
            return hostname
    return ''

WEBAUTHN_RP_ID = os.getenv('WEBAUTHN_RP_ID', '').strip() or _default_webauthn_rp_id()
WEBAUTHN_RP_NAME = os.getenv('WEBAUTHN_RP_NAME', 'NetVault')
# Origins a WebAuthn response is accepted as having come from — reuse
# CORS_ALLOWED_ORIGINS by default since that's already the exact set of
# origins this deployment expects its frontend to be served from.
_webauthn_origins_env = os.getenv('WEBAUTHN_ORIGINS', '').strip()
WEBAUTHN_ORIGINS = (
    [o.strip() for o in _webauthn_origins_env.split(',') if o.strip()]
    if _webauthn_origins_env else CORS_ALLOWED_ORIGINS
)

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# Encryption Key for device credentials (REQUIRED)
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')
if not ENCRYPTION_KEY:
    raise ImproperlyConfigured(
        'ENCRYPTION_KEY environment variable is required. '
        'Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
    )

# Email Configuration
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('EMAIL_HOST_USER', 'noreply@netvault.local')

# Telegram Bot Configuration
TELEGRAM_ENABLED = os.getenv('TELEGRAM_ENABLED', 'False') == 'True'
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Notification Settings
NOTIFY_ON_BACKUP_SUCCESS = os.getenv('NOTIFY_ON_BACKUP_SUCCESS', 'False') == 'True'
NOTIFY_ON_BACKUP_FAILURE = os.getenv('NOTIFY_ON_BACKUP_FAILURE', 'True') == 'True'
NOTIFY_SCHEDULE_SUMMARY = os.getenv('NOTIFY_SCHEDULE_SUMMARY', 'False') == 'True'

# LDAP Configuration
LDAP_ENABLED = os.getenv('LDAP_ENABLED', 'False') == 'True'
LDAP_SERVER_URI = os.getenv('LDAP_SERVER_URI', '')
LDAP_BIND_DN = os.getenv('LDAP_BIND_DN', '')
LDAP_BIND_PASSWORD = os.getenv('LDAP_BIND_PASSWORD', '')
LDAP_USER_SEARCH_BASE = os.getenv('LDAP_USER_SEARCH_BASE', '')


def _parse_ldap_group_list(env_var, default):
    """Comma-separated AD/LDAP group CNs, lowercased for the case-insensitive
    *exact* match accounts.ldap_backend._map_ldap_groups_to_role does against
    them. Exact, not substring — a group merely containing one of these names
    (e.g. "IT-Administrators-Helpdesk" containing "administrators") must NOT
    match; only a group whose name equals one of these exactly does."""
    return {g.strip().lower() for g in os.getenv(env_var, default).split(',') if g.strip()}


# LDAP/AD group -> NetVault role mapping. Defaults match the group names
# LDAP_SETUP.md tells integrators to create; override per deployment if your
# AD groups are named differently. Every deployment's real group names are
# organization-specific — that's exactly why these were hardcoded fuzzy
# patterns in the code before instead of exact, configurable names.
LDAP_ADMIN_GROUPS = _parse_ldap_group_list('LDAP_ADMIN_GROUPS', 'NetVault-Admins,NetVault Admins,Domain Admins,Administrators')
LDAP_OPERATOR_GROUPS = _parse_ldap_group_list('LDAP_OPERATOR_GROUPS', 'NetVault-Operators,NetVault Operators,Network Operators')
LDAP_AUDITOR_GROUPS = _parse_ldap_group_list('LDAP_AUDITOR_GROUPS', 'NetVault-Auditors,NetVault Auditors,Security Auditors')

# Backup Configuration
BACKUP_RETENTION_DAYS = int(os.getenv('BACKUP_RETENTION_DAYS', '90'))
BACKUP_PARALLEL_WORKERS = int(os.getenv('BACKUP_PARALLEL_WORKERS', '5'))

# Security: Allow public registration (disabled by default for corporate environments)
ALLOW_PUBLIC_REGISTRATION = os.getenv('ALLOW_PUBLIC_REGISTRATION', 'False') == 'True'

# SSRF Protection - Allowed Private Network Ranges
#
# NetVault's entire purpose is SSHing into devices on private LANs, so
# "allow all private IPs" is the correct default for this setting — unlike
# most apps, private-range connections ARE the legitimate use case here.
# Leaving this empty does NOT mean unrestricted, though: devices/connection.py's
# validate_target_host() unconditionally rejects loopback, link-local
# (includes 169.254.169.254 cloud metadata), multicast, unspecified, and
# reserved addresses regardless of this setting — those are never a real
# device, in any deployment, so there's no legitimate reason to make them
# configurable. This setting exists for operators who want to further
# scope "private" down to their own known device subnets (e.g. to stop an
# operator-role user from pointing a "device" at other internal
# private-range infrastructure that isn't a network device at all).
# Format: comma-separated CIDR notation, e.g., "192.168.0.0/16,10.10.0.0/16"
ALLOWED_PRIVATE_NETWORKS = os.getenv('ALLOWED_PRIVATE_NETWORKS', '').strip()
if ALLOWED_PRIVATE_NETWORKS:
    import ipaddress
    ALLOWED_PRIVATE_NETWORKS = [
        ipaddress.ip_network(net.strip())
        for net in ALLOWED_PRIVATE_NETWORKS.split(',')
        if net.strip()
    ]
else:
    ALLOWED_PRIVATE_NETWORKS = []  # Empty = allow all private IPs

# CSV Import/Export Configuration
CSV_MAX_FILE_SIZE = int(os.getenv('CSV_MAX_FILE_SIZE', str(5 * 1024 * 1024)))  # 5MB default

# Backup Export Configuration
BACKUP_MAX_EXPORT_COUNT = int(os.getenv('BACKUP_MAX_EXPORT_COUNT', '1000'))  # Max backups in single ZIP
BACKUP_CONNECTION_TIMEOUT = int(os.getenv('BACKUP_CONNECTION_TIMEOUT', '30'))  # Connection timeout in seconds

# Config Search Configuration
CONFIG_SEARCH_REGEX_MAX_LENGTH = int(os.getenv('CONFIG_SEARCH_REGEX_MAX_LENGTH', '200'))  # Max regex pattern length

# Redis Configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Helper function to change Redis database number in URL
def get_redis_url_with_db(base_url, db_number):
    """Replace database number in Redis URL (e.g., /0 -> /1 for Channel Layers)"""
    import re
    # Match redis://[:password@]host:port/db_number
    return re.sub(r'/\d+$', f'/{db_number}', base_url)

# Celery Configuration
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE  # Use same timezone as Django
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_RESULT_EXPIRES = 3600  # 1 hour

# Security Settings
# Read from .env to support both HTTP and HTTPS installations
# Set USE_HTTPS=True in production for secure cookies
USE_HTTPS = os.getenv('USE_HTTPS', 'False') == 'True'

# Secure cookies for HTTPS (cookies only sent over HTTPS)
# SECURE_SSL_REDIRECT is NOT USED because Nginx handles HTTP->HTTPS redirects
SESSION_COOKIE_SECURE = USE_HTTPS
CSRF_COOKIE_SECURE = USE_HTTPS
# Trust X-Forwarded-Proto header from Nginx for request.is_secure()
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https') if USE_HTTPS else None

# Additional security headers (always enabled in production)
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000 if USE_HTTPS else 0  # 1 year HSTS
    SECURE_HSTS_INCLUDE_SUBDOMAINS = USE_HTTPS
    SECURE_HSTS_PRELOAD = USE_HTTPS

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'netvault.log',
            'formatter': 'verbose',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': True,
        },
        'accounts': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'devices': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'backups': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'core': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'notifications': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# ========================================
# Django Channels Configuration
# ========================================
ASGI_APPLICATION = 'netvault.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            # Use Redis DB 1 for Channel Layers (separate from Celery DB 0)
            "hosts": [get_redis_url_with_db(REDIS_URL, 1)],
        },
    },
}

# ========================================
# drf-spectacular (OpenAPI/Swagger) Configuration
# ========================================
SPECTACULAR_SETTINGS = {
    'TITLE': 'NetVault API',
    'DESCRIPTION': 'Network Device Configuration Backup System - REST API Documentation',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,

    # Security
    'SERVE_AUTHENTICATION': ['accounts.authentication.CookieJWTAuthentication'],
    'SERVE_PERMISSIONS': ['rest_framework.permissions.IsAuthenticated'],

    # JWT Authentication
    'SECURITY': [
        {
            'BearerAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
        }
    ],

    # UI Settings
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': False,
        'filter': True,
    },
    'SWAGGER_UI_DIST': 'SIDECAR',
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
    'REDOC_DIST': 'SIDECAR',

    # Schema generation
    'SCHEMA_PATH_PREFIX': '/api/v1/',
    'SORT_OPERATIONS': True,
}
