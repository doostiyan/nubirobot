import logging
from collections import deque
from datetime import timedelta
from functools import partial
from typing import Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.decorators import measure_time
from exchange.base.logging import metric_incr, report_exception
from exchange.integrations.errors import APICallException, ConnectionFailedException
from exchange.integrations.finnotext import FinnotextSMSService
from exchange.web_engage.exceptions import InvalidPhoneNumber, RecipientBlackListed
from exchange.web_engage.externals.finnotext import parse_finnotext_response_code
from exchange.web_engage.externals.web_engage import web_engage_ssp_api
from exchange.web_engage.models import WebEngageSMSLog
from exchange.web_engage.models.sms_log import WebEngageSMSBatch
from exchange.web_engage.tasks import task_send_batch_sms_to_ssp
from exchange.web_engage.types import SmsMessage

logger = logging.getLogger(__name__)

_supported_versions = ('1.0', '2.0')


def queue_message_to_send(message: SmsMessage):
    user = _get_user_by_web_engage_cuid(message.receiver_number)
    if _get_user_phone_number(user) is None:
        return None

    WebEngageSMSLog.objects.create(
        user=user, phone_number=user.mobile.strip(), text=message.body, message_id=message.message_id
    )


def _is_version_supported(data) -> bool:
    if data.get('version') in _supported_versions:
        return True
    return False


def _get_user_by_web_engage_cuid(cuid: str) -> User:
    try:
        user = User.objects.get(webengage_cuid=cuid)
        if user.user_type in (User.USER_TYPES.inactive, User.USER_TYPES.blocked, User.USER_TYPES.suspicious):
            # todo check user mobile is verified
            raise RecipientBlackListed()

        return user
    except (User.DoesNotExist, ValidationError):
        raise InvalidPhoneNumber()


def _get_user_phone_number(user: User) -> Optional[str]:
    phone_number = user.mobile
    if phone_number is None or phone_number == '':
        return None
    return phone_number


@transaction.atomic
def batch_and_send_sms_messages(batch_group_size: int = 25):
    logs = (
        WebEngageSMSLog.objects.filter(status=WebEngageSMSLog.STATUS.new, batch__isnull=True)
        .order_by('id')
        .select_for_update()
    )

    log_queue = deque(logs)
    while len(log_queue) > 0:
        batched_sms_logs = []
        phone_numbers = set()  # batches should not contain repetitive phone numbers.
        for i in range(batch_group_size):
            log = log_queue.popleft()
            if log.phone_number not in phone_numbers:
                phone_numbers.add(log.phone_number)
                batched_sms_logs.append(log)
            else:
                log_queue.append(log)
                continue
            if len(log_queue) == 0:
                break

        batch = WebEngageSMSBatch.objects.create()
        for b in batched_sms_logs:
            b.batch = batch
        WebEngageSMSLog.objects.bulk_update(batched_sms_logs, fields=['batch'])
        partial_task = partial(task_send_batch_sms_to_ssp.delay, batch_id=batch.id)
        transaction.on_commit(partial_task)


def send_batch_sms(batch_id, retry_number, max_retry):
    batch = WebEngageSMSBatch.objects.get(id=batch_id, status=WebEngageSMSBatch.STATUS.new)
    logs = batch.sms_logs.all()

    try:
        FinnotextSMSService.send_sms(
            body=[log.text for log in logs],
            phone_numbers=[log.phone_number for log in logs],
            track_id=batch.track_id,
            from_number=settings.MARKETING_FINNOTEXT_FROM_NUMBER,
        )
    except (ConnectionFailedException, APICallException) as e:
        if isinstance(e, APICallException):
            batch.set_call_log(status_code=e.status_code, response_body=e.response_body, save=True)
        else:
            batch.set_call_log(status_code=0, response_body=e.actual_exception, save=True)
        if retry_number < max_retry:
            raise e
        batch.status = WebEngageSMSBatch.STATUS.failed_to_send_to_ssp
        batch.save(update_fields=['status'])
    except Exception as e:
        report_exception()
        batch.status = WebEngageSMSBatch.STATUS.failed_to_send_to_ssp
        batch.save(update_fields=['status'])
        raise e
    else:
        batch.status = WebEngageSMSBatch.STATUS.sent_to_ssp
        batch.save(update_fields=['status'])


def inquire_sent_batch_sms():
    batch_logs = _get_pending_batch_sms_logs()
    _inquire_batch_sms_logs(batch_logs)


def _get_pending_batch_sms_logs():
    return WebEngageSMSBatch.objects.filter(
        status__in=(WebEngageSMSBatch.STATUS.sent_to_ssp, WebEngageSMSBatch.STATUS.failed_to_send_to_ssp),
        created_at__lt=ir_now() - timedelta(minutes=10),
        created_at__gte=ir_now() - timedelta(days=10),
    ).order_by('-id')[:10]


def _inquire_batch_sms_logs(batches):
    for batch in batches:
        try:
            if batch.status == WebEngageSMSBatch.STATUS.failed_to_send_to_ssp:
                finnotext_inquiry_status = 10
                sms_logs = batch.sms_logs.all()
                for log in sms_logs:
                    _send_dsn(log, finnotext_inquiry_status, save=False)
            else:
                inquiry_result = FinnotextSMSService.inquiry(batch.track_id)
                if not inquiry_result:
                    continue
                sms_logs = batch.sms_logs.all()
                for log in sms_logs:
                    try:
                        _send_dsn(log, inquiry_result['+98' + log.phone_number[1:]], save=False)
                    except:
                        logger.exception('Error sending inquiry to web engage')
        except:
            logger.exception('error receiving inquiry')
        else:
            with transaction.atomic():
                WebEngageSMSLog.objects.bulk_update(sms_logs, ['status'])
                batch.status = batch.STATUS.inquired
                batch.save(update_fields=['status'])


@measure_time(metric='webengage_dsn')
def _send_dsn(sms_log: WebEngageSMSLog, finnotext_inquiry_status: int, save=False):
    user = User.objects.filter(mobile=sms_log.phone_number).first()
    if not user:
        return

    sms_status_data = parse_finnotext_response_code(
        finnotext_inquiry_status, user.get_webengage_id(), sms_log.message_id
    )
    if sms_status_data.status == 'sms_sent':
        sms_log.status = WebEngageSMSLog.STATUS.succeeded
    if sms_status_data.status == 'sms_failed':
        sms_log.status = WebEngageSMSLog.STATUS.failed

    if sms_status_data.message_id.startswith('cmp'):
        sms_log.save(update_fields=['status'])
        return

    try:
        response = web_engage_ssp_api.send(sms_status_data)
    except:
        metric_incr(f'metric_integrations_errors__webengage_sspWebhook_connection')
        sms_log.status = WebEngageSMSLog.STATUS.sent_to_ssp
    else:
        if 200 <= response.status_code < 300:
            if save:
                sms_log.save(update_fields=['status'])
        else:
            metric_incr(f'metric_integrations_errors__webengage_sspWebhook_{response.status_code}')
            sms_log.status = WebEngageSMSLog.STATUS.sent_to_ssp
    finally:
        metric_incr('metric_integrations_calls__webengage_sspWebhook')
