import os

LOCAL_MEMORY_MAX_ENTRIES = 1000000
REDIS_MAX_SOCKET_CONNECT_TIMEOUT = REDIS_MAX_SOCKET_TIMEOUT = 5
REDIS_MAX_CONNECTIONS = 1000
CACHE_DEFAULT_TIMEOUT = None

REDIS_URL = os.environ.get('REDIS_URL')
REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')

REDIS_HOST = os.environ.get('REDIS_HOST')
REDIS_PORT = os.environ.get('REDIS_PORT')

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': "{}/0".format(REDIS_URL),
        'KEY_FUNCTION': "exchange.explorer.utils.cache.key_function",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {'max_connections': REDIS_MAX_CONNECTIONS, 'retry_on_timeout': True},
            'PASSWORD': REDIS_PASSWORD,
            "PICKLE_VERSION": -1,  # Will use highest protocol version available
            'SOCKET_CONNECT_TIMEOUT': REDIS_MAX_SOCKET_CONNECT_TIMEOUT,  # seconds
            'SOCKET_TIMEOUT': REDIS_MAX_SOCKET_TIMEOUT,  # seconds
        }
    },
    'redis__throttling': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': "{}/0".format(REDIS_URL),
        'KEY_FUNCTION': "exchange.explorer.utils.cache.key_function",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {'max_connections': REDIS_MAX_CONNECTIONS, 'retry_on_timeout': True},
            'PASSWORD': REDIS_PASSWORD,
            "PICKLE_VERSION": -1,  # Will use highest protocol version available
            'SOCKET_CONNECT_TIMEOUT': REDIS_MAX_SOCKET_CONNECT_TIMEOUT,  # seconds
            'SOCKET_TIMEOUT': REDIS_MAX_SOCKET_TIMEOUT,  # seconds
        }
    },
    'redis__user_api_keys': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': "{}/0".format(REDIS_URL),
        'KEY_FUNCTION': "exchange.explorer.utils.cache.key_function",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {'max_connections': REDIS_MAX_CONNECTIONS, 'retry_on_timeout': True},
            'PASSWORD': REDIS_PASSWORD,
            'SERIALIZER': 'exchange.explorer.utils.cache.CustomJSONSerializer',
            'SOCKET_CONNECT_TIMEOUT': REDIS_MAX_SOCKET_CONNECT_TIMEOUT,  # seconds
            'SOCKET_TIMEOUT': REDIS_MAX_SOCKET_TIMEOUT,  # seconds
        }
    },
    'local__user_api_keys': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'user_api_keys',
        'KEY_FUNCTION': "exchange.explorer.utils.cache.key_function",
        'OPTIONS': {
            'MAX_ENTRIES': LOCAL_MEMORY_MAX_ENTRIES,
        },
        'TIMEOUT': CACHE_DEFAULT_TIMEOUT,
    },
}
