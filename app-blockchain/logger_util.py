import logging

from django.conf import settings

if settings.IS_TESTNET:
    logger = logging.getLogger('wrapper_file_logger')
else:
    logger = logging.getLogger('app')
