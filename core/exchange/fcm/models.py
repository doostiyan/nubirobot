""" FCM Connection Data Model """
from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from model_utils import Choices

from exchange.base.connections import get_fcm
from exchange.base.logging import metric_incr, report_event


class FCMDevice(models.Model):
    DEVICE_TYPES = Choices(
        (0, 'none', 'None'),
        (1, 'web', 'Web'),
        (2, 'android', 'Android'),
        (3, 'ios', 'iOS'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.CASCADE,
                             verbose_name=_('User'), related_name='fcm_devices')
    token = models.CharField(verbose_name=_('FCM registration token'), max_length=255, unique=True)
    device_type = models.IntegerField(choices=DEVICE_TYPES, default=DEVICE_TYPES.none)
    is_active = models.BooleanField(verbose_name=_('Is active'), default=True)
    created_at = models.DateTimeField(verbose_name=_('Creation date'), default=now)

    class Meta:
        verbose_name = _('دستگاه FCM')
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'U#{self.user_id}-{self.get_device_type_display()}-{self.token[:5]}...'

    def create_notification_push(self, notification=None):
        """ Create a FCM push message for notifying clients that a new user Notification
             is available
        """
        fcm = get_fcm()
        message = fcm.Message(
            data={'action': 'notif'},
            token=self.token,
        )
        message.device = self
        message.notification_id = notification.id if notification else None
        return message

    @classmethod
    def set_user_token(cls, user, device_type, token):
        """ Register a device id token for the given user
        """
        if not token or not device_type:
            return None
        device = FCMDevice.objects.filter(
            user=user,
            device_type=device_type,
        ).order_by('-id').last()
        try:
            if device:
                update_fields = []
                if device.token != token:
                    device.token = token
                    update_fields.append('token')
                if not device.is_active and device.token == token:
                    device.is_active = True
                    update_fields.append('is_active')
                if update_fields:
                    device.save(update_fields=update_fields)
            else:
                device = FCMDevice.objects.create(
                    user=user,
                    token=token,
                    device_type=device_type,
                )
        except IntegrityError:
            metric_incr('metric_fcm_duplicate_device', labels=(device_type,))
            return None
        return device
