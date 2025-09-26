from abc import abstractmethod
from typing import Any, Dict

from exchange.base.logstash_logging.loggers import logstash_logger
from exchange.base.scrubber import scrub


class LogModelMixin:
    """
    Log mixin for Django models to provide structured logging functionality.

    This mixin is designed to integrate logging capabilities into any Django model
    by allowing model instances to log specific events upon saving. It provides a
    way to define log messages and parameters, leveraging python-logstash-async
    logging package.

    Class Attributes:
        ENABLE_LOGGING (bool): Global toggle for enabling or disabling logging
                               for all instances using this mixin.
        LOG_LEVEL (str): Default log level for logging events, choices are ('DEBUG'. 'INFO',
                         'WARNING', 'ERROR', 'CRITICAL').
        LOG_TYPE (str): Default log index name in elasticsearch. PLEASE write index name in
                        snake_case format like `request_log`

    Instance Attributes:
        log_on_save (bool): Instance-level toggle to enable/disable logging
                            per model instance. Defaults to True.

    Abstract Methods:
        log_message (str): Should return the message string to be logged. Each subclass
                           must implement this method to define a custom log message.
        log_params (dict): Should return a dictionary of parameters to log with
                           the message. Each subclass must implement this method to
                           provide custom parameters.

    Usage:
        - To use this mixin, subclass it in a Django model and implement the
          `log_message` and `log_params` methods.
        - This mixin should be inherited before `models.Model` in the class definition
          to ensure proper initialization order and functionality.
        - Set `log_on_save` to control logging at the instance level, or adjust
          `ENABLE_LOGGING` and `LOG_LEVEL` for class-wide settings.
        -

    Example:
        class MyModel(LogModelMixin, models.Model):
            def log_message(self):
                return 'MyModel instance saved.'

            def log_params(self):
                return {'field_name': self.field_value}

    """

    ENABLE_LOGGING = True
    LOG_LEVEL = 'INFO'
    LOG_TYPE = 'default'

    def __init__(self, *args, **kwargs):
        self.log_on_save = True
        super().__init__(*args, **kwargs)

    def _is_logging_enabled(self):
        return self.ENABLE_LOGGING and self.log_on_save

    def _process_log_params(self):
        return scrub(self.log_params())

    @abstractmethod
    def log_message(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def log_params(self) -> Dict[str, Any]:
        raise NotImplementedError

    def save(self, *args, **kwargs):

        super().save(*args, **kwargs)
        if self._is_logging_enabled():
            try:
                params = self._process_log_params()
                extra: Dict[str, Any] = {'params': params} if params else {}
                extra['log_model'] = self.__class__.__name__
                extra['index_name'] = self.LOG_TYPE
                log_method = getattr(logstash_logger, self.LOG_LEVEL.lower(), logstash_logger.info)
                log_method(self.log_message(), extra=extra)
            except Exception as e:
                from exchange.base.logging import report_exception

                report_exception()
