from django.utils.html import escape
from django_ratelimit.decorators import ratelimit

from exchange.accounts.functions import validate_request_captcha
from exchange.accounts.models import User
from exchange.base.api import public_api, public_post_v2_api
from exchange.base.normalizers import normalize_email, normalize_mobile, normalize_name
from exchange.base.validators import validate_email, validate_mobile, validate_name
from exchange.marketing.models import Suggestion, SuggestionCategory


@ratelimit(key='user_or_ip', rate='10/1m', block=True)
@public_api
def suggestion_category_list(request):
    return {
        'status': 'ok',
        'categories': SuggestionCategory.objects.all().order_by('-priority'),
    }


@ratelimit(key='user_or_ip', rate='1/1m', block=True)
@public_post_v2_api
def add_user_suggestion(request):
    user = request.user
    category = SuggestionCategory.objects.filter(pk=request.g('suggestionCategory')).first()
    email = request.g('email')
    mobile = request.g('mobile')
    name = request.g('name')
    description = request.g('description')

    request.data = {}
    for item in ('captchaType', 'client', 'captcha', 'key'):
        request.data[item] = request.g(item)

    # Validate captcha
    is_captcha_valid = validate_request_captcha(request)

    if not is_captcha_valid:
        return {
            'status': 'failed',
            'code': 'InvalidCaptcha',
            'message': 'Invalid Captcha',
        }
    if name:
        name = normalize_name(name)
        if not validate_name(name):
            return {
                'status': 'failed',
                'code': 'ValidationError',
                'message': 'NameValidationFailed',
            }
    if mobile:
        mobile = normalize_mobile(mobile)
        if not validate_mobile(mobile, strict=True):
            return {
                'status': 'failed',
                'code': 'ValidationError',
                'message': 'MobileValidationFailed',
            }
    if email:
        email = normalize_email(email)
        if not validate_email(email):
            return {
                'status': 'failed',
                'code': 'ValidationError',
                'message': 'EmailValidationFailed',
            }
    if not description or not isinstance(description, str) or not 3 < len(description.strip()) < 1000:
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'DescriptionValidationFailed',
        }
    description = escape(description.strip())
    if not category:
        return {'status': 'failed', 'code': 'ValidationError', 'message': 'CategoryValidationFailed'}
    if isinstance(user, User):
        email = user.email or email
        mobile = user.mobile or mobile
        name = str(user) or name

    suggestion = Suggestion.objects.create(
        category=category,
        description=description,
        email=email,
        name=name,
        mobile=mobile,
        allocated_by=user if isinstance(user, User) else None,
    )
    return {
        'status': 'ok',
        'suggestion': suggestion,
    }
