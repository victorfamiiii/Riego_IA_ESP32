"""
Django settings for backend project.
"""

from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
# Use environment variable, or generate temporary key for build time
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY') or os.getenv('SECRET_KEY')
if not SECRET_KEY:
    # Temporary key for build/development - MUST be replaced in production
    import warnings
    warnings.warn(
        '⚠️  SECRET_KEY no está configurado en variables de entorno. '
        'Usando clave temporal solo para build/desarrollo. '
        'En producción, configura SECRET_KEY en .env o variables de entorno del sistema.',
        RuntimeWarning
    )
    SECRET_KEY = 'django-insecure-build-key-change-in-production-h9kz8x2q4r7t'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False  # Siempre False en producción; usar variable de entorno explícita si se necesita cambiar

ALLOWED_HOSTS = [
    'riegoesp32.victorfg.work',
    'victorfg.work',
    '127.0.0.1',
    'localhost',
    'web',  # Para Docker Compose
]

# ============================================
# SECURITY VALIDATION
# ============================================
# En producción (DEBUG=False), SECRET_KEY DEBE estar configurado
# if not DEBUG and SECRET_KEY == 'django-insecure-build-key-change-in-production-h9kz8x2q4r7t':
#     raise ValueError(
#         '❌ SEGURIDAD CRÍTICA: SECRET_KEY debe estar configurado en producción. '
#         'Configura la variable de entorno SECRET_KEY con un valor seguro. '
#         'Genera uno con: python3 -c "import secrets, string; '
#         'chars = string.ascii_letters + string.digits + \'!@#$%^&*(-_=+)\'; '
#         'print(\'\'.join(secrets.choice(chars) for _ in range(50)))"'
#     )

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'measurements.apps.MeasurementsConfig',
]

# MIDDLEWARE - Orden correcto (CORS PRIMERO)
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # ← DEBE SER EL PRIMERO
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ============================================
# CORS CONFIGURATION
# ============================================
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'https://riegoesp32.victorfg.work',
    'http://riegoesp32.victorfg.work',
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

# ============================================
# CSRF CONFIGURATION
# ============================================
CSRF_TRUSTED_ORIGINS = [
    'https://riegoesp32.victorfg.work',
    'https://victorfg.work',
    'https://*.victorfg.work',
    'http://riegoesp32.victorfg.work',
]

CSRF_COOKIE_HTTPONLY = False  # Permitir acceso desde JavaScript
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = True  # Solo HTTPS
CSRF_COOKIE_NAME = 'csrftoken'
CSRF_HEADER_NAME = 'HTTP_X_CSRFTOKEN'

# ============================================
# SESSION CONFIGURATION
# ============================================
SESSION_COOKIE_HTTPONLY = False  # Permitir acceso desde JavaScript
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = True  # Solo HTTPS
SESSION_COOKIE_AGE = 86400  # 24 horas
SESSION_COOKIE_DOMAIN = None

# ============================================
# SSL/HTTPS CONFIGURATION
# ============================================
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False  # Nginx maneja la redirección
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# ============================================
# URL CONFIGURATION
# ============================================
ROOT_URLCONF = 'backend.urls'
APPEND_SLASH = False  # Añadir slash final automáticamente
PREPEND_WWW = False  # No añadir www

# ============================================
# TEMPLATES
# ============================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'measurements' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

# ============================================
# DATABASE
# ============================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'esp32db'),
        'USER': os.getenv('POSTGRES_USER', 'postgres'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'root'),
        'HOST': os.getenv('DB_HOST', 'db'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# ============================================
# CACHE (for rate limiting)
# ============================================
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'OPTIONS': {
            'MAX_ENTRIES': 1000
        }
    }
}

# ============================================
# PASSWORD VALIDATION
# ============================================
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

# ============================================
# INTERNATIONALIZATION
# ============================================
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'Europe/Madrid'
USE_I18N = True
USE_TZ = True

# ============================================
# STATIC FILES
# ============================================
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# WhiteNoise configuration
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ============================================
# DEFAULT SETTINGS
# ============================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================
# AEMET API CONFIGURATION
# ============================================
# Obtén tu API key en: https://opendata.aemet.es/centrodedescargas/obtencionAPIKey
AEMET_API_KEY = os.getenv('AEMET_API_KEY', '')
AEMET_DEFAULT_STATION = os.getenv('AEMET_DEFAULT_STATION', '2614')  # Zamora por defecto
AEMET_SYNC_INTERVAL = int(os.getenv('AEMET_SYNC_INTERVAL', '3600'))  # Segundos entre sincronizaciones

# ============================================
# DJANGO REST FRAMEWORK
# ============================================
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
}

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
