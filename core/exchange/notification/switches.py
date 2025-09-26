from exchange.base.models import Settings


class NotificationConfig:
    @classmethod
    def is_kafka_enabled(cls):
        return Settings.get_value('is_kafka_enabled', default='false').strip().lower() == 'true'

    @classmethod
    def is_sms_logging_enabled(cls):
        return cls.is_kafka_enabled() and cls._is_notif_app_logging_enabled('sms')

    @classmethod
    def is_email_logging_enabled(cls):
        return cls.is_kafka_enabled() and cls._is_notif_app_logging_enabled('email')

    @classmethod
    def is_notification_logging_enabled(cls):
        return cls.is_kafka_enabled() and cls._is_notif_app_logging_enabled('notification')

    @classmethod
    def is_sms_broker_enabled(cls):
        return cls.is_kafka_enabled() and cls._is_notif_app_broker_enabled('sms')

    @classmethod
    def is_email_broker_enabled(cls):
        return cls.is_kafka_enabled() and cls._is_notif_app_broker_enabled('email')

    @classmethod
    def is_notification_broker_enabled(cls):
        return cls.is_kafka_enabled() and cls._is_notif_app_broker_enabled('notification')

    @classmethod
    def _is_notif_app_logging_enabled(cls, app_name: str):
        return Settings.get_value(f'is_{app_name}_logging_enabled', default='false').strip().lower() == 'true'

    @classmethod
    def _is_notif_app_broker_enabled(cls, app_name: str):
        return Settings.get_value(f'is_{app_name}_broker_enabled', default='false').strip().lower() == 'true'
