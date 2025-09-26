from .main import DEBUG

REST_FRAMEWORK = {
    'EXCEPTION_HANDLER': 'exchange.explorer.utils.exception.exception_handler',
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ) if DEBUG else (
        'rest_framework.renderers.JSONRenderer',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': []
}

API_KEY_CUSTOM_HEADER_CLIENT_FORMAT = 'NOBITEXPLORER-API-KEY'
API_KEY_CUSTOM_HEADER = 'HTTP_{}'.format(API_KEY_CUSTOM_HEADER_CLIENT_FORMAT.replace('-', '_'))

ALLOWED_CLIENT_IPS = [
    '127.0.0.1',
]
