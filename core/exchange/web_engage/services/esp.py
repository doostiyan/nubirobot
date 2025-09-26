from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from django.conf import settings
from rest_framework.status import HTTP_400_BAD_REQUEST

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.logging import report_event
from exchange.integrations.errors import ConnectionFailedException
from exchange.integrations.infobip import InfoBipService
from exchange.web_engage.exceptions import ESPSendMessageException
from exchange.web_engage.externals.infobip import translate_infobip_error_codes, translate_infobip_status_codes
from exchange.web_engage.externals.web_engage import web_engage_email_delivery_report_api
from exchange.web_engage.models.email_log import WebEngageEmailLog, WebEngageEmailRecipientLog
from exchange.web_engage.tasks import task_send_dsn_to_web_engage
from exchange.web_engage.types import EmailStatusEventData, ESPDeliveryStatusCode


def send_email(data: dict) -> None:
    response = _send_email_request(data)
    email_responses = _to_email_responses(response)
    _create_email_logs(data, email_responses)


def process_delivery_status(data: dict) -> None:
    """
    Change real emails with web_engage_cuid in delivery status data sent from Infobip
    and send these DSNs to web_engage asynchronously
    see response example schema at /tests/webengage/test_data/email_delivery_response.json
    """
    email_events = _process_email_delivery_logs(data)
    for status_event in email_events:
        try:
            task_send_dsn_to_web_engage.delay(asdict(status_event))
        except Exception as e:
            report_event(f'INFOBIP: Send DSN error for {status_event.email}: {str(e)}')


def cleanup_email_logs() -> None:
    max_history = settings.ESP_LOG['max_history'] or 90
    max_size = settings.ESP_LOG['max_size'] or 1000
    pks = (
        WebEngageEmailLog.objects.filter(created_at__lte=ir_now() - timedelta(days=max_history))
        .order_by('created_at')
        .values_list('pk')[:max_size]
    )
    WebEngageEmailLog.objects.filter(pk__in=pks).delete()


def _send_email_request(data: dict):
    email = data.get("email", {})
    metadata = data.get("metadata", {})
    _message_id = metadata.get("messageId", "")
    recipients = email.get("recipients", {})

    try:
        ok, http_status_code, response = InfoBipService.send(
            from_email=email.get("from", ""),
            subject=email.get("subject", ""),
            text=email.get("text", ""),
            message_id=_message_id,
            html=email.get("html", ""),
            reply_to=email.get("replyTo", []),
            recipient_emails=[t.get('email') for t in recipients.get("to", [])],
            cc=recipients.get("cc", []),
            bcc=recipients.get("bcc", []),
        )

    except ConnectionFailedException:
        raise ESPSendMessageException(
            ESPDeliveryStatusCode.UNKNOWN_REASON.value,
            ESPDeliveryStatusCode.UNKNOWN_REASON.name,
            HTTP_400_BAD_REQUEST,
        )

    if ok:
        return response

    error_object = response.get("requestError", {}).get("serviceException", {})
    error_code = error_object.get("messageId", 255)
    try:
        error_code, error_code_description = translate_infobip_error_codes(error_code)
    except:
        error_code = ESPDeliveryStatusCode.UNKNOWN_REASON.value
        error_code_description = ESPDeliveryStatusCode.UNKNOWN_REASON.name

    http_status_code = http_status_code or HTTP_400_BAD_REQUEST
    raise ESPSendMessageException(error_code, error_code_description, http_status_code)


def _to_email_responses(response) -> Dict[str, Dict]:
    return {
        message['to']: {'message_id': message['messageId'], 'status': message['status']['name']}
        for message in response.get("messages", [])
    }


def _get_email_response(email_responses, email) -> Tuple[Optional[str], str]:
    if email not in email_responses:
        return None, 'PENDING'

    data = email_responses[email]
    return data['message_id'], data['status']


def _create_email_logs(data: dict, email_responses: dict) -> None:
    metadata = data.get("metadata", dict())
    email_data = data.get("email", dict())
    recipients = email_data.get("recipients", dict())
    email_body = WebEngageEmailLog.objects.create(
        subject=email_data.get("subject"),
        message=email_data.get("text") or 'None',
        html_message=email_data.get("html") or 'None',
        from_address=email_data.get("from", ""),
        from_name=email_data.get("fromName", ""),
        reply_to=email_data.get("replyTo", ""),
        track_id=metadata.get("messageId", ""),
        custom_data=metadata,
    )

    logs = []
    for recipient in recipients.get("to", dict()):
        message_id, status = _get_email_response(email_responses, recipient.get("email"))
        logs.append(
            WebEngageEmailRecipientLog(
                to=recipient.get("email"),
                subject_type=WebEngageEmailRecipientLog.SUBJECT_TYPES.normal,
                email_body=email_body,
                status=status,
                message_id=message_id,
            )
        )
    for cc in recipients.get("cc", dict()):
        message_id, status = _get_email_response(email_responses, cc)
        logs.append(
            WebEngageEmailRecipientLog(
                to=cc,
                subject_type=WebEngageEmailRecipientLog.SUBJECT_TYPES.cc,
                email_body=email_body,
                status=status,
                message_id=message_id,
            )
        )
    for bcc in recipients.get("cc", dict()):
        message_id, status = _get_email_response(email_responses, bcc)
        logs.append(
            WebEngageEmailRecipientLog(
                to=bcc,
                subject_type=WebEngageEmailRecipientLog.SUBJECT_TYPES.bcc,
                email_body=email_body,
                status=status,
                message_id=message_id,
            )
        )

    WebEngageEmailRecipientLog.objects.bulk_create(logs)


def _process_email_delivery_logs(data: dict) -> List[EmailStatusEventData]:
    delivery_status_events = []
    delivery_data = data.get("results", list())
    for delivery_item in delivery_data:
        _to = delivery_item.get("to", "")
        _track_id = delivery_item.get("bulkId", "")  # webengage parent message id
        _message_id = delivery_item.get("messageId", "")  # email service provider msg id
        _status = delivery_item.get("status", dict()).get("name", "")
        _status_code = delivery_item.get("status", {}).get("id", 255)
        _done_at = datetime.strptime(delivery_item.get("doneAt", ""), "%Y-%m-%dT%H:%M:%S.%f%z")

        updated_count = WebEngageEmailRecipientLog.objects.filter(to=_to, email_body__track_id=_track_id).update(
            message_id=_message_id, status=_status, done_at=_done_at
        )
        if updated_count == 0:
            report_event(f"Log for DSN not found, email: {_to}, status: {_status}, track_id: {_track_id}")

        translated_status_code, translated_status_message, event = translate_infobip_status_codes(_status_code)
        data = EmailStatusEventData(
            message_id=_track_id,
            timestamp=int(_done_at.timestamp()),
            email=_to,
            event=event,  # SENT, DELIVERED, BOUNCE or UNSUBSCRIBE
            status_code=translated_status_code,
            message=translated_status_message,
        )
        delivery_status_events.append(data)

    return delivery_status_events


def send_email_delivery_status_to_webengage(data: EmailStatusEventData) -> None:
    user = User.objects.get(email=data.email)
    web_engage_email_delivery_report_api.send(str(user.webengage_cuid), data)


def get_recipients_by_webengage_ids(recipients: List[str]) -> Dict[str, User]:
    """Hashed emails are equal with user webengage cuid"""
    page_size = 50
    last_index = len(recipients) - 1
    users = []
    webengage_user_ids = []

    for index, hashed_email in enumerate(recipients):
        webengage_user_ids.append(hashed_email)
        if len(webengage_user_ids) == page_size or index == last_index:
            users.extend(User.objects.filter(webengage_cuid__in=webengage_user_ids).order_by('id'))
            webengage_user_ids.clear()

    return {
        str(u.webengage_cuid): u
        for u in users
        if u.user_type
        not in {
            User.USER_TYPES.inactive,
            User.USER_TYPES.blocked,
            User.USER_TYPES.suspicious,
        }
    }
