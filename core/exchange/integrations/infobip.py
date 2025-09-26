import logging
from enum import Enum
from typing import List, Tuple

import requests
from django.conf import settings
from rest_framework.status import HTTP_401_UNAUTHORIZED

from exchange.base.email_utils import filter_no_send_emails
from exchange.base.logging import metric_incr, report_event
from exchange.integrations.errors import ConnectionFailedException

logger = logging.getLogger(__name__)


class InfoBipErrorCodes(Enum):
    """
    General email error codes
    See: https://infobip.com/docs/essentials/response-status-and-error-codes
    """
    # OK (group id: 0) - general error codes
    # The request has been completed successfully.
    NO_ERROR = 0

    # Dropped (group id: 1) - email error codes
    # The request has not been completed successfully as emails were dropped by the mail delivery system \
    # on the end-user side.
    EC_EMAIL_BLACKLISTED = 6001
    EC_EMAILS_SPAM_CONTENT = 6002
    EC_EMAIL_UNSUBSCRIBED_EMAIL_ADDRESS = 6003
    EC_BOUNCED_EMAIL_ADDRESS = 6004
    EC_EMAIL_DROPPED = 6005
    EC_EMAIL_SENDER_DOMAIN_BLOCKED = 6016
    EC_EMAIL_IP_BLACKLISTED = 6017
    EC_INVALID_GATEWAY_REQUEST = 6018
    EC_EMAIL_HANDLE_BARS_ERROR = 6021

    # Bounced (group id: 2) - email error codes
    # The request has not been completed successfully, and we received NDR (Non-delivery receipt).
    EC_INVALID_EMAIL_ADDRESS = 6006
    EC_MAILBOX_TEMPORARY_UNAVAILABLE = 6007
    EC_DEFERRED_DUE_TO_INSUFFICIENT_STORAGE = 6008
    EC_MAILBOX_UNAVAILABLE = 6009
    EC_STORAGE_LIMIT_EXCEEDED = 6010
    EC_HARD_BOUNCE = 6012

    # System Error (group id: 3) - email error codes
    # The request has not been completed successfully due to system-related errors.
    EC_TEMPORARY_SENDING_ERROR = 6013
    EC_PERMANENT_SENDING_ERROR = 6014
    EC_EMAIL_GATEWAY_ERROR = 6015

    EC_UNKNOWN_ERROR = 255  # 9999

    @classmethod
    def _missing_(cls, value):
        return cls.EC_UNKNOWN_ERROR


class InfoBipStatusCodes(Enum):
    """
    General email status codes
    See: https://infobip.com/docs/essentials/response-status-and-error-codes
    """
    # PENDING (group id: 1) - general status codes
    PENDING_WAITING_DELIVERY = 3
    PENDING_ENROUTE = 7
    PENDING_ACCEPTED = 26

    # UNDELIVERABLE (group id: 2) - general status codes
    UNDELIVERABLE_REJECTED_OPERATOR = 4
    UNDELIVERABLE_NOT_DELIVERED = 9

    # DELIVERED (group id: 3) - general status codes
    DELIVERED_TO_OPERATOR = 2
    DELIVERED_TO_HANDSET = 5

    # EXPIRED (group id: 4) - general status codes
    EXPIRED_EXPIRED = 15
    EXPIRED_DLR_UNKNOWN = 29

    # REJECTED (group id: 5) - general status codes
    REJECTED_NETWORK = 6
    REJECTED_PREFIX_MISSING = 8
    REJECTED_DND = 10
    REJECTED_SOURCE = 11
    REJECTED_NOT_ENOUGH_CREDITS = 12
    REJECTED_SENDER = 13
    REJECTED_DESTINATION_BLOCK = 14
    REJECTED_PREPAID_PACKAGE_EXPIRED = 17
    REJECTED_DESTINATION_NOT_REGISTERED = 18
    REJECTED_ROUTE_NOT_AVAILABLE = 19
    REJECTED_FLOODING_FILTER = 20
    REJECTED_SYSTEM_ERROR = 21
    REJECTED_DUPLICATE_MESSAGE_ID = 23
    REJECTED_INVALID_UDH = 24
    REJECTED_MESSAGE_TOO_LONG = 25
    MISSING_TO = 51
    REJECTED_DESTINATION = 52


class InfoBipService:

    @classmethod
    def send(cls, from_email: str, html: str, subject: str, text: str, message_id: str, reply_to: list,
             recipient_emails: List[str], cc: List[str], bcc: List[str]) -> Tuple[bool, int, dict]:

        _recipient_emails = filter_no_send_emails(recipient_emails)
        if len(_recipient_emails) == 0:
            return True, 200, {}

        _cc = filter_no_send_emails(cc)
        _bcc = filter_no_send_emails(bcc)

        payload = [
            ("from", (None, from_email, "text/plain")),
            ("subject", (None, subject, "text/plain")),
            ("text", (None, text, "text/plain")),
            ("html", (None, html, "text/plain")),
            ("bulkId", (None, message_id, "text/plain")),
            ("intermediateReport", (None, "true", "text/plain")),
            ("notifyUrl", (None, f"{settings.ESP_INFOBIP_NOTIFY_URL}/{message_id}", "text/plain")),
            *[("replyTo", (None, r, "text/plain")) for r in reply_to],
            *[("cc", (None, c, "text/plain")) for c in _cc],
            *[("bcc", (None, b, "text/plain")) for b in _bcc],
            *[("to", (None, t, "text/plain")) for t in _recipient_emails],
        ]
        payload = list(filter(lambda f: f[1][1], payload))
        status = True
        url = f"{settings.ESP_INFOBIP_URL}/email/3/send"
        headers = {"Authorization": f"App {settings.ESP_INFOBIP_API_KEY}"}
        try:
            response = requests.post(url=url, headers=headers, timeout=(10, 15), files=payload)
            metric_incr('metric_integrations_calls__infobip_send')
        except:
            metric_incr(f'metric_integrations_errors__infobip_send_connection')
            metric_incr('metric_integrations_calls__infobip_send')
            raise ConnectionFailedException()

        json_response = response.json()

        if response.status_code != 200:
            metric_incr(f'metric_integrations_errors__infobip_send_{response.status_code}')
            if response.status_code == HTTP_401_UNAUTHORIZED:
                report_event(f"ESP UNAUTHORIZED: Bad token sent to InfoBIP")
            else:
                report_event(f"ESP ERROR: InfoBip response: {response.text}")

            status = False

        return status, response.status_code, json_response
