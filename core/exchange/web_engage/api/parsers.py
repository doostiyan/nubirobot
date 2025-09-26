from rest_framework.status import HTTP_500_INTERNAL_SERVER_ERROR

from exchange.base.logging import report_event
from exchange.web_engage.exceptions import ESPSendMessageException, UnsupportedRequestVersion
from exchange.web_engage.models.email_log import WebEngageEmailLog
from exchange.web_engage.types import ESPDeliveryStatusCode, SmsMessage


class SSPMessageParser:
    _supported_versions = ("1.0", "2.0")

    @classmethod
    def parse(cls, data: dict) -> SmsMessage:
        if not cls._is_version_supported(data):
            raise UnsupportedRequestVersion()

        sms_data = data.get("smsData", dict())
        return SmsMessage(
            receiver_number=sms_data.get("toNumber"),
            body=sms_data.get("body"),
            message_id=data["metadata"]["messageId"],
        )

    @classmethod
    def _is_version_supported(cls, data) -> bool:
        if data.get('version') in cls._supported_versions:
            return True
        return False


class ESPMessageParser:
    _supported_versions = ("1.0",)

    @classmethod
    def parse(cls, data):
        if not cls._is_version_supported(data):
            raise UnsupportedRequestVersion()

        if not cls._is_valid_payload(data):
            raise ESPSendMessageException(
                ESPDeliveryStatusCode.ERROR_PROCESSING_EMAIL_AT_ESP.value,
                ESPDeliveryStatusCode.ERROR_PROCESSING_EMAIL_AT_ESP.name,
                HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return data

    @classmethod
    def _is_version_supported(cls, data: dict) -> bool:
        if data.get("version") in cls._supported_versions:
            return True
        return False

    @classmethod
    def _is_valid_payload(cls, data: dict) -> bool:
        is_valid = True
        message_id = data.get("metadata", dict()).get("messageId", "")
        try:
            _ = WebEngageEmailLog.objects.get(track_id=message_id)
            report_event("ESP send message error: Web_engage sent a request with duplicate message_id")
            is_valid = False
        except WebEngageEmailLog.DoesNotExist:
            pass

        _from_email = data.get("email", dict()).get("from", "")
        if not _from_email.endswith("@n1.nobitex.net"):
            report_event("ESP send message error: Web_engage sent a request with invalid _from email address")
            is_valid = False

        return is_valid
