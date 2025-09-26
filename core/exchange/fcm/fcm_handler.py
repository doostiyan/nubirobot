from firebase_admin.messaging import UnregisteredError

from exchange.accounts.models import Notification
from exchange.base.connections import get_fcm
from exchange.base.logging import log_event, metric_incr
from exchange.fcm.models import FCMDevice


def send_batch(notifications):
    """ Send a batch of notifications to FCM server, to a maximum of 5000 FCM messages
    """
    messages = []
    last_notification_id = None
    for notification in notifications:
        devices = notification.user.fcm_devices.filter(is_active=True)
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
        else:
            log_event(
                f'fcm_error',
                level='ERROR',
                module='fcm_notification',
                runner='generic',
                category='general',
                details=f'error: {str(response.exception)},'
                f' notif_id: {str(messages[i].notification_id)},'
                f' device_id: {str(messages[i].device.id)},'
                f' device_type: {str(messages[i].device.device_type)}',
            )

    metric_incr('metric_fcm_send', amount=success_count, labels=('successful',))
    metric_incr('metric_fcm_send', amount=len(results.responses) - success_count, labels=('failed',))
    if successful_notifications:
        Notification.objects.filter(id__in=successful_notifications).update(sent_to_fcm=True)
    if invalid_devices:
        FCMDevice.objects.filter(id__in=invalid_devices).update(is_active=False)

    return last_notification_id
