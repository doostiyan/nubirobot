from celery import shared_task
from celery.exceptions import Ignore
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command

from exchange.base.logging import metric_incr, report_exception
from exchange.celery import app as celery_app

from .connections import get_telegram_bot
from .emailmanager import EmailManager


def run_admin_task(task, *args, **kwargs):
    admin_task_names = [
        'admin.daily_withdraw_manually_failed',
        'admin.assign_blacklist_tag',
        'admin.assign_deposit_blacklist_tag',
        'admin.add_withdraw_diff',
        'admin.add_deposit_diff',
        'admin.add_notification_log',
        'admin.create_transaction_request',
        'detectify.check_deposit_fraud',
        'detectify.check_bank_deposit_fraud',
        'detectify.check_cobank_deposit_fraud',
        'detectify.check_direct_deposit_fraud',
    ]

    if task not in admin_task_names:
        return False, 'Task Not Found!'
    try:
        celery_app.send_task(task, args, kwargs)
    except Exception as error:
        report_exception()
        return False, str(error)
    return True, None


def base_send_telegram_message(self, message, chat_id, message_id=None, pin=False, cache_key=None, cache_timeout=None):
    """Main task for sending Telegram messages."""
    # Only send Telegram messages on production that has a specific celery queue config for it
    if not settings.IS_PROD:
        metric_incr('metric_telegram_message__ignored')
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
            metric_incr(f'metric_telegram_message__sent')

    # Handle common errors
    except Exception as e:
        error_message = str(e)
        # Ignore unrecoverable errors
        ignored_errors = [
            'Chat not found',
            'Forbidden: bot was blocked by the user', # TODO: Remove conversation from user if blocked
            'Forbidden: user is deactivated',
            "Forbidden: bots can't send messages to bots",
        ]
        if error_message in ignored_errors:
            metric_incr('metric_telegram_message__ignored')
            raise Ignore()
        # Only increment a metric if this message has reached max_retries
        retries_done = self.request.retries
        if error_message.startswith('Flood control exceeded.'):
            if retries_done >= settings.TELEGRAM_MAX_RETRIES:
                metric_incr('metric_telegram_message__failed')
                raise Ignore()
        # Retry send
        metric_incr('metric_telegram_message__retried')
        raise self.retry(exc=ValueError(error_message), countdown=30 ** retries_done)


@shared_task(bind=True, max_retries=settings.TELEGRAM_MAX_RETRIES)
def send_telegram_message(self, message, chat_id, message_id=None, pin=False, cache_key=None, cache_timeout=None):
    base_send_telegram_message(self, message, chat_id,
        message_id=message_id, pin=pin, cache_key=cache_key, cache_timeout=cache_timeout)


@shared_task(bind=True, max_retries=settings.TELEGRAM_MAX_RETRIES, name='send_telegram_message')
def task_send_telegram_message(self, message, chat_id, message_id=None, pin=False, cache_key=None, cache_timeout=None):
    base_send_telegram_message(self, message, chat_id,
        message_id=message_id, pin=pin, cache_key=cache_key, cache_timeout=cache_timeout)


@shared_task(name='send_email')
def send_email(email, template, data=None, backend=None, priority='medium'):
    EmailManager.send_email(email, template, data, backend, priority=priority)


@shared_task(name='run_cron')
def task_run_cron(*class_names, run_every_mins: bool = False):
    call_command('runcrons', *class_names, force=run_every_mins)
