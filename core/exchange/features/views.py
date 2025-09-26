from django.conf import settings
from django_ratelimit.decorators import ratelimit

from exchange.base.api import api
from exchange.features.models import QueueItem


@ratelimit(key='user_or_ip', rate='100/10m', block=True)
@api
def register_request_in_queue(request, feature):
    """Request a feature for this user. Feature requests are placed in a queue
    and are enabled gradually when the feature is developed.

    POST /users/feature/add-request/FEATURE
    """
    user = request.user
    if not feature:
        return {
            'status': 'failed',
            'code': 'register_item_in_queue',
            'message': 'مقدار feature نمیتواند خالی باشد.',
        }
    try:
        feature_key = QueueItem.FEATURES.__getattr__(feature.lower())
    except AttributeError:
        return {
            'status': 'failed',
            'code': 'register_item_in_queue',
            'message': 'مقدار feature معتبر نمی باشد.',
        }

    # Check for existing requests
    existed_queue_item = QueueItem.objects.filter(feature=feature_key, user=user).first()
    if existed_queue_item:
        if existed_queue_item.status == QueueItem.STATUS.done:
            return {
                'status': 'failed',
                'code': 'register_item_in_queue',
                'message': 'درخواست قبلا انجام شده است.',
            }
        elif existed_queue_item.status == QueueItem.STATUS.failed:
            return {
                'status': 'failed',
                'code': 'register_item_in_queue',
                'message': f'درخواست انجام نشده است. {existed_queue_item.description}'
            }
        else:
            # existed_queue_item.status == QueueItem.STATUS.waiting and other status
            return {
                'status': 'failed',
                'code': 'register_item_in_queue',
                'message': 'درخواست تکراری می باشد.',
            }

    # Auto-enabling finalized features
    can_auto_enable = False
    is_feature_in_beta = feature_key in QueueItem.BETA_FEATURES
    is_feature_in_alpha = feature_key in QueueItem.ALPHA_FEATURES
    if feature_key in QueueItem.ENABLED_FEATURES:
        can_auto_enable = True
    elif is_feature_in_beta and settings.IS_TESTNET:
        can_auto_enable = True
    elif is_feature_in_alpha or is_feature_in_beta:
        if user.has_tag(QueueItem.ALPHA_USERS_TAG):
            can_auto_enable = True

    # Create new feature request
    queue_item = QueueItem.objects.create(feature=feature_key, user=user)
    if can_auto_enable:
        queue_item.enable_feature()
    return {
        'status': 'ok',
        'result': {
            'position_in_queue': queue_item.get_position_in_queue(),
            'request_status': queue_item.status,
            'request_status_value': queue_item.get_status_display()
        }
    }


@ratelimit(key='user_or_ip', rate='100/10m', block=True)
@api
def get_request_status(request, feature):
    """
    Retrieve status of request with this key(feature)
    """
    user = request.user
    if not feature:
        return {
            'status': 'failed',
            'code': 'get_request_status',
            'message': 'مقدار feature نمیتواند خالی باشد.',
        }

    try:
        feature_key = QueueItem.FEATURES.__getattr__(feature.lower())
    except AttributeError:
        return {
            'status': 'failed',
            'code': 'get_request_status',
            'message': 'مقدار feature معتبر نمی باشد.',
        }

    request_item = QueueItem.objects.filter(feature=feature_key, user=user).first()
    if not request_item:
        return {
            'status': 'failed',
            'code': 'get_request_status',
            'message': 'چنین درخواستی ثبت نشده است.',
        }

    return {
        'status': 'ok',
        'result': {
            'position_in_queue': request_item.get_position_in_queue(),
            'request_status': request_item.status,
            'request_status_value': request_item.get_status_display()
        }
    }
