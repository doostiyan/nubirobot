"""Metric keys are defined here."""
import enum


class Metrics(enum.Enum):
    """
    - sms
        - metric_notification_sms_time
            - smsir
                - simple
                - fast
        - metric_notification_sms_count
            - smsir
                - simple
                    - ok
                    - failed
                - fast
                    - ok
                    - failed
    - email
    - notif
        - metric_notification_notif_time
        - metric_notification_notif_count
    """

    SMS_SMSIR_SIMPLE_REQUEST_TIME = 'sms_time__smsir_simple'
    SMS_SMSIR_FAST_REQUEST_TIME = 'sms_time__smsir_fast'

    SMS_SMSIR_SIMPLE_REQUEST_OK_COUNT = 'sms_count__smsir_simple_ok'
    SMS_SMSIR_SIMPLE_REQUEST_FAILED_COUNT = 'sms_count__smsir_simple_failed'
    SMS_SMSIR_FAST_REQUEST_OK_COUNT = 'sms_count__smsir_fast_ok'
    SMS_SMSIR_FAST_REQUEST_FAILED_COUNT = 'sms_count__smsir_fast_failed'

    def __str__(self) -> str:
        return 'metric_notification_' + self.value
