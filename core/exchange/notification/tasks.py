from celery import shared_task
from celery.exceptions import Ignore
from django.conf import settings
from django.core.cache import cache

from exchange.base.connections import get_telegram_bot  # coupling with core
from exchange.base.decorators import measure_time
from exchange.base.logging import metric_incr  # coupling with core


@measure_time(metric='metric_notification_telegram_time')
def base_send_telegram_message(self, message, chat_id, message_id=None, pin=False, cache_key=None, cache_timeout=None):
    """Main task for sending Telegram messages."""
    # Only send Telegram messages on production that has a specific celery queue config for it
    if not settings.IS_PROD:
        metric_incr('metric_notification_telegram_message_count__ignored')
        return
    # Telegram does not support large messages, probably here we should split them automatically?
    if len(message) > 4096:
        message = message[:4096]
    # Send message
    bot = get_telegram_bot()
    try:
        if message_id:
            bot.edit_message_text(message, chat_id=chat_id, message_id=message_id, parse_mode='Markdown')
        else:
            telegram_message = bot.send_message(chat_id, message, parse_mode='Markdown', timeout=20)
            if telegram_message and cache_key:
                cache.set(cache_key, telegram_message.message_id, cache_timeout)
            metric_incr(f'metric_notification_telegram_message_count__sent')

    # Handle common errors
    except Exception as e:
        error_message = str(e)
        # Ignore unrecoverable errors
        ignored_errors = [
            'Chat not found',
            'Forbidden: bot was blocked by the user',  # TODO: Remove conversation from user if blocked
            'Forbidden: user is deactivated',
            "Forbidden: bots can't send messages to bots",
        ]
        if error_message in ignored_errors:
            metric_incr('metric_notification_telegram_message_count__ignored')
            raise Ignore()
        # Only increment a metric if this message has reached max_retries
        retries_done = self.request.retries
        if error_message.startswith('Flood control exceeded.'):
            if retries_done >= settings.TELEGRAM_MAX_RETRIES:
                metric_incr('metric_notification_telegram_message_count__failed')
                raise Ignore()
        # Retry send
        metric_incr('metric_notification_telegram_message_count__retried')
        raise self.retry(exc=ValueError(error_message), countdown=30 ** retries_done)


@shared_task(bind=True, max_retries=settings.TELEGRAM_MAX_RETRIES)
def send_telegram_message(self, message, chat_id, message_id=None, pin=False, cache_key=None, cache_timeout=None):
    base_send_telegram_message(
        self, message, chat_id, message_id=message_id, pin=pin, cache_key=cache_key, cache_timeout=cache_timeout
    )


@shared_task(name='send_sms', max_retries=2)
def task_send_sms(sms_id: int, is_fast: bool):
    from exchange.notification.models import Sms
    Sms.objects.get(id=sms_id).send(is_fast=is_fast)
