from django_ratelimit.decorators import ratelimit

from exchange.base.api import api, post_api
from exchange.base.helpers import paginate
from exchange.notification.models import InAppNotification as Notification


@ratelimit(key='user_or_ip', rate='30/m', block=True)
@api
def notifications_list(request):
    user = request.user
    notifications = Notification.objects.filter(user=user).order_by('-created_at')
    notifications, has_next = paginate(
        notifications,
        page_size=10,
        request=request,
        check_next=True,
        max_page=100,
        max_page_size=100,
    )
    return {'status': 'ok', 'notifications': notifications, 'hasNext': has_next}


@ratelimit(key='user_or_ip', rate='10/m', block=True)
@ratelimit(key='user_or_ip', rate='60/h', block=True)
@post_api
def notifications_read(request):
    """Mark one or many notifications as read
    POST notifications/read
    """
    param_id = request.g('id') or ''  # TODO get list of ids
    notifications_id = str(param_id).split(',')
    processed = Notification.objects.filter(pk__in=notifications_id, user=request.user, is_read=False).update(
        is_read=True
    )
    return {
        'status': 'ok',
        'processed': processed,
    }
