"""
Django settings for noteghar project.

Sensitive values are loaded from environment variables (or a .env file via
python-decouple).  Copy .env.example to .env and fill in your values before
running the server.
"""

from pathlib import Path
from decouple import config, Csv

# BASE
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')

DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost', cast=Csv())

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://127.0.0.1:8000,http://localhost:8000',
    cast=Csv()
)
# APPLICATIONS
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # Third-party
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'django_recaptcha',
    'crispy_forms',
    'crispy_bootstrap5',

    # Local
    'accounts',
    'core',
    'notes.apps.NotesConfig',
    'moderation',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # serve static files in production
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'noteghar.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'core' / 'templates', BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'notes.context_processors.moderation_stats',
            ],
        },
    },
]

WSGI_APPLICATION = 'noteghar.wsgi.application'

# DATABASE
# Supports DATABASE_URL Railway or individual DB_* variables
import os as _os

_database_url = config('DATABASE_URL', default='')

if _database_url:
    # Railway/Heroku style — parse the URL directly
    import dj_database_url as _dj
    DATABASES = {
        'default': _dj.parse(_database_url, conn_max_age=60)
    }
else:
    _db_engine = config('DB_ENGINE', default='sqlite3')

    if _db_engine == 'postgresql':
        DATABASES = {
            'default': {
                'ENGINE':       'django.db.backends.postgresql',
                'NAME':         config('DB_NAME'),
                'USER':         config('DB_USER'),
                'PASSWORD':     config('DB_PASSWORD'),
                'HOST':         config('DB_HOST',         default='localhost'),
                'PORT':         config('DB_PORT',         default='5432'),
                'CONN_MAX_AGE': config('DB_CONN_MAX_AGE', default=60, cast=int),
                'OPTIONS': {
                    'connect_timeout': 10,
                },
            }
        }
    else:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }

# AUTHENTICATION
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# EMAIL
_email_backend = config('EMAIL_BACKEND', default='console')

if _email_backend == 'smtp':
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST          = config('EMAIL_HOST',          default='smtp.gmail.com')
    EMAIL_PORT          = config('EMAIL_PORT',          default=587, cast=int)
    EMAIL_USE_TLS       = config('EMAIL_USE_TLS',       default=True, cast=bool)
    EMAIL_HOST_USER     = config('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL  = config('DEFAULT_FROM_EMAIL',  default=EMAIL_HOST_USER)
else:
    # Prints emails to the console — safe for development
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ALLAUTH
SITE_ID = 1

ACCOUNT_LOGIN_METHODS       = {'email', 'username'}
ACCOUNT_SIGNUP_FIELDS       = ['email*', 'username*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION  = config('ACCOUNT_EMAIL_VERIFICATION', default='optional')
ACCOUNT_CONFIRM_EMAIL_ON_GET         = True
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3

LOGIN_URL                = '/accounts/login/student/'
ACCOUNT_LOGIN_ON_SIGNUP  = True   # Log in immediately after signup
# ACCOUNT_SIGNUP_REDIRECT_URL = '/'  # Where to go after signup
LOGIN_REDIRECT_URL       = 'core:home'
ACCOUNT_LOGOUT_REDIRECT_URL = 'core:home'
ACCOUNT_LOGOUT_ON_GET    = True   # skip the "are you sure?" page

SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True

ACCOUNT_ADAPTER = 'accounts.adapters.CustomAccountAdapter'
ACCOUNT_FORMS   = {'signup': 'accounts.forms.CustomSignupForm'}

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    }
}

# RECAPTCHA
RECAPTCHA_PUBLIC_KEY    = config('RECAPTCHA_PUBLIC_KEY',  default='')
RECAPTCHA_PRIVATE_KEY   = config('RECAPTCHA_PRIVATE_KEY', default='')
RECAPTCHA_REQUIRED_SCORE = config('RECAPTCHA_REQUIRED_SCORE', default=0.85, cast=float)

# CRISPY FORMS
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK          = 'bootstrap5'

# CUSTOM APP SETTINGS
ADMIN_REGISTRATION_KEY = config('ADMIN_REGISTRATION_KEY')

FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS   = ['.pdf', '.docx', '.doc', '.ppt', '.pptx', '.txt']

# INTERNATIONALISATION
LANGUAGE_CODE = 'en-us'
TIME_ZONE     = 'Asia/Kathmandu'
USE_I18N      = True
USE_TZ        = True

# STATIC & MEDIA
STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'   # collectstatic target
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

#CLOUDINARY 
CLOUDINARY_CLOUD_NAME = config('CLOUDINARY_CLOUD_NAME', default='')
CLOUDINARY_API_KEY    = config('CLOUDINARY_API_KEY',    default='')
CLOUDINARY_API_SECRET = config('CLOUDINARY_API_SECRET', default='')
 
if CLOUDINARY_CLOUD_NAME:
    import cloudinary
    cloudinary.config(
        cloud_name = CLOUDINARY_CLOUD_NAME,
        api_key    = CLOUDINARY_API_KEY,
        api_secret = CLOUDINARY_API_SECRET,
        secure     = True,
    )
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
 
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
# SECURITY HEADERS (only meaningful when DEBUG=False)
if not DEBUG:
    # Railway terminates SSL before reaching Django — don't redirect again
    SECURE_SSL_REDIRECT            = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
    SECURE_PROXY_SSL_HEADER        = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS            = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD            = True
    SESSION_COOKIE_SECURE          = True
    CSRF_COOKIE_SECURE             = True
    SECURE_BROWSER_XSS_FILTER      = True
    SECURE_CONTENT_TYPE_NOSNIFF    = True
    X_FRAME_OPTIONS                = 'DENY'