import os
from .main import DEBUG

USE_PROXY = os.environ.get('USE_PROXY') == 'true'
if USE_PROXY and not DEBUG:
    DEFAULT_PROXY = {
        'http': 'http://host:port',  # TODO complete if proxy is needed
        'https': 'http://host:port',  # TODO complete if proxy is needed
    }
else:
    DEFAULT_PROXY = None
