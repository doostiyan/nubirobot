import json
import logging.config
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse, urlunparse

import requests
from django.conf import settings
from logstash_async.constants import Constants
from logstash_async.formatter import LogstashFormatter
from logstash_async.transport import HttpTransport
from rest_framework import status

from .main import BASE_DIR, STATIC_ROOT

## Logstash Setting
LOGSTASH_URL: str = os.environ.get('LOGSTASH_URL', '')
LOGSTASH_USERNAME: str = os.environ.get('LOGSTASH_USERNAME', '')
LOGSTASH_PASSWORD: str = os.environ.get('LOGSTASH_PASSWORD', '')

LOGGING_CONFIG: None = None
LOG_DIR: str = os.path.join(STATIC_ROOT, 'logs')  # this is for debug mode
BASE_LOG_DIR: str = os.path.join(BASE_DIR, 'logs')
Path(BASE_LOG_DIR).mkdir(parents=True, exist_ok=True)

PYTHON_LOGGING_FORMAT: str = '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
DJANGO_LOGGING_FORMAT: str = '{levelname} {asctime} {module} {process:d} {thread:d} {message}'
FILE_FORMATTER: str = '%(asctime)s - %(levelname)s - %(message)s'
DATEFMT: str = '%d/%b/%Y %H:%M:%S'
DEFAULT_LOG_LEVEL: str = 'INFO'

ENABLE_LOGSTASH_PROXIES = os.environ.get('ENABLE_LOGSTASH_PROXIES', '').lower() == 'true'

LOGSTASH_LOGGER_CONFIG: Dict[str, Any] = {
    'logstash_host': LOGSTASH_URL,
    'logstash_port': 8083,
    'logstash_username': LOGSTASH_USERNAME,
    'logstash_password': LOGSTASH_PASSWORD,
    'logstash_timeout': 5,  # seconds
    'logstash_ssl_enable': settings.IS_PROD or settings.DEBUG,
    'logstash_ssl_verify': settings.IS_PROD or settings.DEBUG,
    'logstash_ca_cert': os.path.join(BASE_DIR, os.environ.get('LOGSTASH_CA_CERTS', '')),
    'logstash_client_cert': os.path.join(BASE_DIR, os.environ.get('LOGSTASH_CERTFILE', '')),
    'logstash_client_key': os.path.join(BASE_DIR, os.environ.get('LOGSTASH_KEYFILE', '')),
    'logstash_logs_ttl': 5 * 60,  # time in seconds to wait before expiring log messages in the cache
    'logstash_database_path': None,  # for failure scenarios. None means using memory cache
}


class CustomHttpTransport(HttpTransport):
    def __init__(
            self,
            *args: Any,
            ca_certs: Optional[str] = None,
            certfile: Optional[str] = None,
            keyfile: Optional[str] = None,
            **kwargs: Any,
    ) -> None:
        self._ca_certs = ca_certs
        self._certfile = certfile
        self._keyfile = keyfile
        super().__init__(*args, **kwargs)

    @property
    def url(self) -> str:
        if LOGSTASH_URL:
            protocol: str = 'https' if self._ssl_enable else 'http'
            parsed_url = urlparse(self._host)

            if not parsed_url.netloc:
                host_parts: List[str] = self._host.split('/', 1)
                netloc: str = host_parts[0]
                path: str = f'/{host_parts[1]}' if len(host_parts) > 1 else ''
            else:
                netloc = parsed_url.netloc
                path = parsed_url.path

            netloc_with_port: str = f'{netloc}:{self._port}' if ':' not in netloc else netloc
            return urlunparse((protocol, netloc_with_port, path, '', '', ''))

        return 'http://localhost'

    def send(self, events: List[Dict[str, Any]], **kwargs: Any) -> None:  # noqa:ARG002
        session = requests.Session()
        batches = self._HttpTransport__batches(events)
        for batch in batches:
            if ENABLE_LOGSTASH_PROXIES:
                proxies = {
                    'http': os.environ.get('LOGSTASH_HTTP_PROXY', None),
                    'https': os.environ.get('LOGSTASH_HTTPS_PROXY', None),
                }
            else:
                proxies = None
            response = session.post(
                self.url,
                headers={'Content-Type': 'application/json'},
                json=batch,
                verify=self._ca_certs if self._ssl_verify else False,
                timeout=self._timeout,
                cert=(self._certfile, self._keyfile) if self._certfile and self._keyfile else None,
                proxies= proxies,
            )
            if response.status_code != status.HTTP_200_OK:
                session.close()
                response.raise_for_status()
        session.close()


class SafeLogstashRecordFormatter(LogstashFormatter):
    def format(self, record: logging.LogRecord) -> str:
        record.env = settings.ENV
        record_dict: Dict[str, Any] = dict(record.__dict__)
        if record_dict.get('msg'):
            record_dict['message'] = record.getMessage()
        record_dict['extra'] = {'index_name': record_dict.get('index_name', 'log')}
        extra_fields: Set[str] = {
            'name',
            'levelname',
            'pathname',
            'filename',
            'module',
            'exc_info',
            'exc_text',
            'stack_info',
            'lineno',
            'funcName',
            'msecs',
            'thread',
            'threadName',
            'processName',
            'process',
        }
        [record_dict.pop(field, None) for field in extra_fields]
        return json.dumps(record_dict, ensure_ascii=self._ensure_ascii)


class NoExtraFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record_dict: Dict[str, Any] = record.__dict__
        extra_keys: Set[str] = set(record_dict.keys()) - set(Constants.FORMATTER_RECORD_FIELD_SKIP_LIST)
        return not extra_keys


LOGGING: Dict[str, Any] = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': DJANGO_LOGGING_FORMAT,
            'datefmt': DATEFMT,
            'style': '{',
        },
        'wrapper': {
            'format': FILE_FORMATTER,
            'datefmt': DATEFMT,
        },
        'logstash': {
            '()': SafeLogstashRecordFormatter,
        },
    },
    'filters': {
        'no_extra': {
            '()': NoExtraFilter,
        }
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'filters': ['no_extra'],
        },
        'gunicorn': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'verbose',
            'filename': os.path.join(BASE_LOG_DIR, 'error.log'),
            'maxBytes': 1024 * 1024 * 100,  # 100MB
        },
        'wrapper_file_handler': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'wrapper',
            'filename': os.path.join(BASE_LOG_DIR, 'api_wrapper.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5
        },
        'cron_file_handler': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'wrapper',
            'filename': os.path.join(BASE_LOG_DIR, 'cron.log'),
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5
        },
        'logstash': {
            'level': 'INFO',
            'class': 'logstash_async.handler.AsynchronousLogstashHandler',
            'formatter': 'logstash',
            'host': LOGSTASH_LOGGER_CONFIG.get('logstash_host'),
            'port': LOGSTASH_LOGGER_CONFIG.get('logstash_port'),
            'username': LOGSTASH_LOGGER_CONFIG.get('logstash_username'),
            'password': LOGSTASH_LOGGER_CONFIG.get('logstash_password'),
            'transport': 'exchange.settings.logging.CustomHttpTransport',
            'database_path': LOGSTASH_LOGGER_CONFIG.get('logstash_database_path'),
            'ssl_enable': LOGSTASH_LOGGER_CONFIG.get('logstash_ssl_enable'),
            'ssl_verify': LOGSTASH_LOGGER_CONFIG.get('logstash_ssl_verify'),
            'ca_certs': LOGSTASH_LOGGER_CONFIG.get('logstash_ca_cert'),
            'certfile': LOGSTASH_LOGGER_CONFIG.get('logstash_client_cert'),
            'keyfile': LOGSTASH_LOGGER_CONFIG.get('logstash_client_key'),
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': DEFAULT_LOG_LEVEL,
            'propagate': False,
        },
        'django.server': {
            'handlers': ['console'],
            'level': DEFAULT_LOG_LEVEL,
            'propagate': False,
        },
        'local': {
            'handlers': ['console', 'gunicorn'],
            'level': DEFAULT_LOG_LEVEL,
        },
        'app': {
            'handlers': ['console', 'gunicorn', 'logstash'],
            'level': DEFAULT_LOG_LEVEL,
        },
        'gunicorn.errors': {
            'level': 'DEBUG',
            'handlers': ['gunicorn'],
            'propagate': True,
        },
        'wrapper_file_logger': {
            'handlers': ['wrapper_file_handler'],
            'level': 'DEBUG'
        },
        'cron_file_logger': {
            'handlers': ['cron_file_handler'],
            'level': 'DEBUG'
        }
    }
}

logging.config.dictConfig(LOGGING)
