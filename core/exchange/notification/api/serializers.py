from exchange.base.serializers import register_serializer
from exchange.notification.models import InAppNotification as Notification


@register_serializer(model=Notification)
def serialize_notification(notification, opts):
    return {
        'id': notification.pk,
        'createdAt': notification.created_at,
        'is_read': notification.is_read,
        'message': notification.message,
    }
