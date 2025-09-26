import datetime

from django.utils.timezone import now
from django_ratelimit.decorators import ratelimit

from exchange.accounts.models import User, UserSms
from exchange.base.api import get_user_by_token, public_post_api
from exchange.base.normalizers import normalize_mobile
from exchange.base.validators import validate_mobile


@ratelimit(key='user_or_ip', rate='2/h', block=False)
@public_post_api
def request_link(request):
    mobile = request.g('mobile') or ''
    mobile = normalize_mobile(mobile)
    if not validate_mobile(mobile, strict=True):
        return {
            'status': 'failed',
            'code': 'InvalidMobileNumber',
            'message': 'شماره تلفن همراه نامعتبر است',
        }

    # Determine requesting user
    user = get_user_by_token(request)
    if not user.is_authenticated:
        user = User.get_generic_system_user()

    # Check ratelimit
    is_limited = getattr(request, 'limited', False)
    recent_sms = UserSms.objects.filter(
        user=user,
        tp=UserSms.TYPES.android,
        created_at__gt=now() - datetime.timedelta(hours=4),
        to=mobile,
    )
    if recent_sms.exists():
        is_limited = True
    if is_limited:
        return {
            'status': 'failed',
            'code': 'RateLimit',
            'message': 'پیامک قبلاً ارسال شده است',
        }

    # Send SMS
    UserSms.objects.create(
        user=user,
        tp=UserSms.TYPES.android,
        to=mobile,
        text='نصب اپلیکیشن نوبیتکس از:\nhttps://bit.ly/2pfKZRz',
    )
    return {
        'status': 'success',
    }
