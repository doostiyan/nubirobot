SWAGGER_SETTINGS = {
    'SECURITY_DEFINITIONS': {
        'API-KEY': {
            'type': 'apiKey',
            'name': 'NOBITEXPLORER-API-KEY',
            'in': 'header',
        },
        'Bearer': {
            'type': 'apiKey',
            'name': 'AUTHORIZATION',
            'in': 'header'
        }
    },
    'USE_SESSION_AUTH': False
}
