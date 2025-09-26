import os
from pathlib import Path

import environ
from django.utils.translation import gettext_lazy as _

env = environ.Env(
    # set casting, default value
    ENV=(str, 'debug'),
    MASTERKEY=(str, 'master'),
    SECRET_KEY=(str, 'secret'),
    CIRUNNER=(bool, False),
    IS_GUNICORN=(bool, False),
    CORS_ORIGIN_WHITELIST=(list, []),
)

BASE_DIR = str(Path(__file__).parents[2])
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

IS_CI_RUNNER = env('CIRUNNER')
IS_TEST_RUNNER = False
IS_GUNICORN = env('IS_GUNICORN')

ENV = env.str('ENV')
DEBUG = ENV == 'debug'
IS_PROD = ENV == 'prod'
IS_TESTNET = ENV == 'testnet' or IS_CI_RUNNER
IS_VIP = os.environ.get('IS_VIP') == 'true'
IS_DIFF = env.bool('IS_DIFF', False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATIC_URL = '/static/'

DATA_DIR = os.path.join(BASE_DIR, 'data')

# SECURITY WARNING: don't run with debug turned on in production!
# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_cron',
    'django_prometheus',
    'rest_framework',
    'rest_framework_api_key',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'drf_yasg',
    'exchange.base.apps.BaseConfig',
    'exchange.explorer.basis.apps.BasisConfig',
    'exchange.explorer.accounts.apps.AccountsConfig',
    'exchange.explorer.authentication.apps.AuthenticationConfig',
    'exchange.explorer.monitoring',
    'exchange.explorer.core',
    'exchange.explorer.staking',
]

if IS_DIFF:
    INSTALLED_APPS += [
        'exchange.explorer.transactions.apps.TransactionsConfig',
    ]
else:
    INSTALLED_APPS += [
        'exchange.explorer.transactions.apps.TransactionsConfig',
        # the line above could be removed but we keep it to facilitate development.
        'exchange.explorer.wallets.apps.WalletsConfig',
        'exchange.explorer.blocks.apps.BlocksConfig',
        'exchange.explorer.networkproviders.apps.NetworkprovidersConfig'
    ]
# In this way we keep models, tests, management commands and static files separated.

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
    'exchange.explorer.monitoring.middleware.ExplorerPrometheusAfterMiddleware',
    'exchange.explorer.core.language.middlewares.LanguageMiddleware',
    'exchange.explorer.utils.logging_middleware.ELKLoggingMiddleware',
]

if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']

CORS_ORIGIN_WHITELIST = env.list('CORS_ORIGIN_WHITELIST')


ROOT_URLCONF = 'exchange.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
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

WSGI_APPLICATION = 'exchange.wsgi.application'

# Password validation
# https://docs.djangoproject.com/en/4.0/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/4.0/topics/i18n/


TIME_ZONE = 'Asia/Tehran'

USE_I18N = True

USE_TZ = True

LOCALE_PATHS = (
    os.path.join(BASE_DIR, 'locale/'),
)

LANGUAGES = [
    ('en', _('English')),
    ('fa', _('Persian'))
]

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.0/howto/static-files/


# Default primary key field type
# https://docs.djangoproject.com/en/4.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'accounts.User'

if IS_PROD:
    SESSION_COOKIE_SECURE = False  # TODO set to True after migrate to HTTPS
    CSRF_COOKIE_SECURE = False  # TODO set to True after migrate to HTTPS
    SECURE_CROSS_ORIGIN_OPENER_POLICY = None  # TODO set to True after migrate to HTTPS
    USE_X_FORWARDED_HOST = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

CERT_KEY_PATH = os.environ.get('CERT_KEY_PATH', '')
CERT_FILE_PATH = os.environ.get('CERT_FILE_PATH', '')

PROXY_HOST = os.environ.get('PROXY_HOST', '127.0.0.1')
PROXY_PORT = os.environ.get('PROXY_PORT', '2081')
