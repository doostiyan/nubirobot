""" Support Views """
import base64
import re

from django.conf import settings
from django.db.models import Q
from django.http import JsonResponse
from django_ratelimit.decorators import ratelimit
from rest_framework.permissions import IsAuthenticated

from exchange.accounts.models import User
from exchange.base.api import api, api_with_perms, public_post_api
from exchange.celery import app as celery_app
from exchange.support.forms import CallReasonForm
from exchange.support.permissions import HasCallReasonApiPerm


@ratelimit(key='user_or_ip', rate='5/m', block=True)
@public_post_api
def nxbo_register(request):
    """ POST /support/nxbo/register
    """
    user_email = request.g('email') or ''
    m = re.match(r'\w{3,30}@nobitex\.(ir|net)$', user_email)
    if not m:
        response = JsonResponse({
            'status': 'failed',
            'code': 'InvalidEmail',
            'message': 'Invalid email address',
        })
    else:
        celery_app.send_task('support.register_nxbo', kwargs={'email': user_email})
        response = JsonResponse({
            'status': 'ok',
        })
    response['Access-Control-Allow-Origin'] = 'https://register.nxbo.ir'
    response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response['Access-Control-Max-Age'] = '86400'
    response['Access-Control-Allow-Headers'] = ', '.join(settings.CORS_ALLOW_HEADERS)
    return response


@ratelimit(key='user_or_ip', rate='5/m', block=True)
@api
def kyc_refresh_mobile_identity(request):
    """ POST /support/kyc/refresh-mobile-identity
    """
    user_email = request.user.email
    celery_app.send_task('support.update_mobile_identity_status', kwargs={'email': user_email})
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='5/m', block=True)
@api
def kyc_refresh_level1(request):
    """ POST /support/kyc/refresh-level1
    """
    user_email = request.user.email
    celery_app.send_task('support.update_user_verification_level_one', kwargs={'email': user_email})
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='5/m', block=True)
@api
def wallets_refresh_deposit(request):
    """ POST /support/wallets/refresh-deposit

        # TODO: Check TX hash and directly call local celery
    """
    user_email = request.user.email
    celery_app.send_task('support.refresh_user_deposit', kwargs={'email': user_email, 'wallet_address_id': 0})
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='20/1m', block=True)
@api_with_perms([IsAuthenticated, HasCallReasonApiPerm])
def get_next_call_reason_url(request):
    form = CallReasonForm(request.data)
    if form.is_valid():
        mobile = form.cleaned_data['mobile']
        caller_id = form.cleaned_data['caller_id']
        national_code = form.cleaned_data['national_code']
        unique_id = form.cleaned_data['unique_id']

        base_url = f'{settings.ADMIN_URL}/accounts/callreason/create?'

        user = User.objects.none()
        if mobile:
            base_url += '&mobile={}'.format(mobile)
            user = User.objects.filter(Q(mobile=mobile) | Q(phone=mobile))

        if not user and national_code:
            base_url += '&national_code={}'.format(national_code)
            user = User.objects.filter(national_code=national_code)

        if user.exists():
            user = user[0]
            base_url += '&user_id={}'.format(user.id)

        if unique_id:
            base_url += '&unique_id={}'.format(unique_id)

        if caller_id:
            base_url += '&caller_id={}'.format(caller_id)

        return {
            'status': 'ok',
            'url': base64.b64encode(base_url.encode(encoding='ascii', errors='ignore')).decode()
        }

    return JsonResponse({
        'status': 'failed',
        'message': ' اطلاعات ارسالی ناقص می باشد',
        'errors': dict(form.errors.items()),
        'code': 'ValidationError',
    }, status=400)
