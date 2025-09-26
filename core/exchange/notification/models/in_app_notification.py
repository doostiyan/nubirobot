import json
from typing import List

from django.conf import settings
from django.core.cache import cache
from django.db import models

from exchange.accounts.models import User
from exchange.base.logging import log_event
from exchange.notification.managers import BulkCreateWithSignalManager
from exchange.notification.switches import NotificationConfig
from exchange.notification.tasks import send_telegram_message


class InAppNotification(models.Model):
    TELEGRAM_TASK_TIMEOUT = 1800  # 30 Mins

    objects = BulkCreateWithSignalManager()

    user = models.ForeignKey(User, related_name='new_notifications', on_delete=models.CASCADE)
    admin = models.ForeignKey(User, related_name='new_sent_notifications', on_delete=models.CASCADE, null=True)
    message = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_read = models.BooleanField(default=False)
    sent_to_telegram = models.BooleanField(default=False)
    sent_to_fcm = models.BooleanField(default=False, null=True)

    class Meta:
        verbose_name = 'اعلان‌ها'
        verbose_name_plural = verbose_name

    def get_telegram_text(self, title='🔵 Notification'):
        return f'*{title}*\n{self.message}'

    def create(self):
        self.save()
        self.send_to_telegram_conversation()

    def send_to_telegram_conversation(self, save=True, title='🔵 Notification'):
        if not NotificationConfig.is_notification_broker_enabled():
            return
        if self.user.telegram_conversation_id:
            text = self.get_telegram_text(title)
            send_telegram_message.apply_async(
                (text, self.user.telegram_conversation_id),
                expires=self.TELEGRAM_TASK_TIMEOUT,
                queue=settings.TELEGRAM_CELERY_QUEUE,
            )
        else:
            if settings.DEBUG:
                print('*Telegram Message for {}*\n{}'.format(self.user.username, self.message))
        self.sent_to_telegram = True
        # TODO save telegram sent message when we don't have notification object
        if save:
            self.save(update_fields=['sent_to_telegram'])

    @classmethod
    def mark_notifs_as_read(cls, user_id: int, notif_ids: List[int]) -> int:
        processed = cls.objects.filter(user_id=user_id, id__in=notif_ids, is_read=False).update(is_read=True)
        return processed

    @classmethod
    def notify_admins(
        cls,
        message,
        title=None,
        channel=None,
        message_id=None,
        codename=None,
        pin=False,
        cache_key=None,
        cache_timeout=None,
    ):
        """Send a notification to admins groups.

        Note: if codename is given, the message is ratelimited (to cache_timeout or 60s)
        """
        if not NotificationConfig.is_notification_broker_enabled():
            return
        channel = channel or 'notifications'
        title = title or '🔵 Notification'
        text = '*{}*\n{}'.format(title, message)
        text = text.replace('_', '-')
        # Log in console for development
        if settings.DEBUG:
            print(text)
        # Not resending same message too frequently
        if codename:
            lock_cache_key = 'lock_notification_{}'.format(codename)
            has_lock = cache.get(lock_cache_key)
            if has_lock:
                return
            cache.set(lock_cache_key, 1, cache_timeout or 60)
        # Send message to admins telegram group
        chat_id = settings.TELEGRAM_GROUPS_IDS.get(channel)
        if not chat_id or settings.IS_TESTNET:
            chat_id = settings.ADMINS_TELEGRAM_GROUP
        send_telegram_message.apply_async(
            (text, chat_id),
            {'message_id': message_id, 'pin': pin, 'cache_key': cache_key, 'cache_timeout': cache_timeout},
            expires=1200,
            queue=settings.TELEGRAM_ADMIN_CELERY_QUEUE,
        )
        if settings.IS_TESTNET:  # To receive some logs in testnet
            log_event(title, category='notice', details=message)
