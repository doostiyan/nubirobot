from firebase_admin.messaging import UnregisteredError

from exchange.base.connections import get_fcm  # coupling with core
from exchange.base.decorators import measure_time  # coupling with core
from exchange.base.logging import metric_incr  # coupling with core
from exchange.fcm.models import FCMDevice  # coupling with core
from exchange.notification.models.in_app_notification import InAppNotification as Notification


@measure_time(metric='metric_notification_fcm_time')
def send_batch(notifications):
    """Send a batch of notifications to FCM server, to a maximum of 5000 FCM messages"""
    messages = []
    last_notification_id = None
    for notification in notifications:
        devices = notification.user.fcm_devices.filter(is_active=True)  # coupling with FCMDevice
        if len(messages) + len(devices) >= 5000:
            break
        for device in devices:
            messages.append(device.create_notification_push(notification))
        last_notification_id = notification.id

    if not messages:
        return [], [], last_notification_id

    fcm = get_fcm()
    results = fcm.send_each(messages)
    return messages, results, last_notification_id


def send_batch_fcm_notifications(notifications):
    messages, results, last_notification_id = send_batch(notifications)
    if not messages:
        return last_notification_id

    invalid_devices = []
    successful_notifications = []
    success_count = 0
    for i, response in enumerate(results.responses):
        if response.success:
            success_count += 1
            successful_notifications.append(messages[i].notification_id)
        elif isinstance(response.exception, UnregisteredError):
            invalid_devices.append(messages[i].device.id)

    metric_incr('metric_notification_fcm_count__sent', success_count)
    metric_incr('metric_notification_fcm_count__failed', len(results.responses) - success_count)

    if successful_notifications:
        Notification.objects.filter(id__in=successful_notifications).update(sent_to_fcm=True)
    if invalid_devices:
        FCMDevice.objects.filter(id__in=invalid_devices).update(is_active=False)

    return last_notification_id
