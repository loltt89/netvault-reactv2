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

    # Local apps
    'accounts',
    'devices',
    'backups',
    'notifications',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # CORS must be before CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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
        'anon': '10/hour',  # Anonymous users: 10 requests per hour
        'user': '1000/hour',  # Authenticated users: 1000 per hour
        'login': '5/hour',  # Login attempts: 5 per hour per IP
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
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('JWT_ACCESS_TOKEN_LIFETIME', '60'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('JWT_REFRESH_TOKEN_LIFETIME', '1440'))),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': os.getenv('JWT_ALGORITHM', 'HS256'),
    'SIGNING_KEY': SECRET_KEY,
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

# Default includes localhost and common private network ranges
_default_cors = 'http://localhost:3000,http://127.0.0.1:3000,http://localhost,http://127.0.0.1'
# Add common private IP patterns (will be matched by CORS_ALLOWED_ORIGIN_REGEXES)
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', _default_cors).split(',')

# Allow private network IPs (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https?://192\.168\.\d{1,3}\.\d{1,3}(:\d+)?$",
    r"^https?://10\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?$",
    r"^https?://172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}(:\d+)?$",
]

CORS_ALLOW_CREDENTIALS = True

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

# Backup Configuration
BACKUP_RETENTION_DAYS = int(os.getenv('BACKUP_RETENTION_DAYS', '90'))
BACKUP_PARALLEL_WORKERS = int(os.getenv('BACKUP_PARALLEL_WORKERS', '5'))

# Security: Allow public registration (disabled by default for corporate environments)
ALLOW_PUBLIC_REGISTRATION = os.getenv('ALLOW_PUBLIC_REGISTRATION', 'False') == 'True'

# SSRF Protection - Allowed Private Network Ranges
# Leave empty to allow all private IPs (default for backward compatibility)
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
