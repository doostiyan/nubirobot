from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from exchange.features.models import QueueItem
from exchange.features.tasks import send_feature_web_engage


@receiver(pre_save, sender=QueueItem, dispatch_uid='send_feature_web_engage_event_on_edit')
def send_feature_web_engage_event_on_edit(sender, instance: QueueItem, **_):
    """
    Signal handler to send a WebEngage feature event when a QueueItem's status changes to 'done'.

    """
    if instance.status == QueueItem.STATUS.done:
        old = QueueItem.objects.filter(id=instance.id).first()
        if old and old.status != QueueItem.STATUS.done:
            send_feature_web_engage.delay(instance.user.id, instance.feature)


@receiver(post_save, sender=QueueItem, dispatch_uid='send_feature_web_engage_event_on_create')
def send_feature_web_engage_event_on_create(sender, instance, created, **kwargs):
    """
    Signal handler to send a WebEngage feature event when a new QueueItem with 'status' set to 'done' is created.

    """
    if created and instance.status == QueueItem.STATUS.done:
        send_feature_web_engage.delay(instance.user.id, instance.feature)
