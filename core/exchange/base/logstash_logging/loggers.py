import logging
from urllib.parse import urlparse, urlunparse

from django.conf import settings
from logstash_async.formatter import LogstashFormatter
from logstash_async.handler import AsynchronousLogstashHandler
from logstash_async.transport import HttpTransport


class CustomHttpTransport(HttpTransport):
    @property
    def url(self) -> str:
        protocol = 'https' if self._ssl_enable else 'http'
        parsed_url = urlparse(self._host)

        if not parsed_url.netloc:
            host_parts = self._host.split('/', 1)
            netloc = host_parts[0]
            path = f'/{host_parts[1]}' if len(host_parts) > 1 else ''
        else:
            netloc = parsed_url.netloc
            path = parsed_url.path

        netloc_with_port = f'{netloc}:{self._port}' if ':' not in netloc else netloc
        updated_url = (protocol, netloc_with_port, path, '', '', '')

        return urlunparse(updated_url)

class CustomAsynchronousLogstashHandler(AsynchronousLogstashHandler):
    _settings = None

    def emit(self, record):
        if self.is_enabled:
            super().emit(record)

    @property
    def is_enabled(self):
        if self._settings is None:
            from exchange.base.models import Settings

            self.__class__._settings = Settings

        return self._settings.get_value('is_enabled_logstash_logger', default='false').strip().lower() == 'true'


log_level = logging.INFO
host = settings.LOGSTASH_LOGGER_CONFIG.get('logstash_host')
port = settings.LOGSTASH_LOGGER_CONFIG.get('logstash_port')
username = settings.LOGSTASH_LOGGER_CONFIG.get('logstash_username')
password = settings.LOGSTASH_LOGGER_CONFIG.get('logstash_password')
ssl_enable = settings.LOGSTASH_LOGGER_CONFIG.get('logstash_ssl_enable')
ssl_verify = settings.LOGSTASH_LOGGER_CONFIG.get('logstash_ssl_verify')
timeout = settings.LOGSTASH_LOGGER_CONFIG.get('logstash_timeout')
event_ttl = settings.LOGSTASH_LOGGER_CONFIG.get('logger_logs_ttl')
database_path = settings.LOGSTASH_LOGGER_CONFIG.get('logger_database_path')

logstash_logger = logging.getLogger('logstash-logger')
logstash_logger.setLevel(log_level)
logstash_transport = CustomHttpTransport(
    host,
    port,
    username=username,
    password=password,
    timeout=timeout,
    ssl_enable=ssl_enable,
    ssl_verify=ssl_verify,
)
logstash_handler = CustomAsynchronousLogstashHandler(
    host, port, enable=True, transport=logstash_transport, database_path=database_path, event_ttl=event_ttl
)
logstash_formatter = LogstashFormatter(extra={'env': settings.ENV})
logstash_handler.setFormatter(logstash_formatter)
logstash_logger.addHandler(logstash_handler)
