from django.db import transaction
from django_ratelimit.decorators import ratelimit

from exchange.base.api import api
from exchange.redeem.models import RedeemRequest


@ratelimit(key='user_or_ip', rate='10/1m', block=True)
@api
def get_redeem_info(request):
    user = request.user
    plan = RedeemRequest.PLAN.pgala2022
    try:
        redeem_request = RedeemRequest.objects.get(plan=plan, user=user)
    except RedeemRequest.DoesNotExist:
        return {
            'status': 'failed',
            'code': 'NoRedeemRequest',
            'message': 'NoRedeemRequest',
        }
    return {
        'status': 'ok',
        'redeem': redeem_request,
    }


@ratelimit(key='user_or_ip', rate='10/10m', block=True)
@api
def request_redeem(request):
    user = request.user
    plan = RedeemRequest.PLAN.pgala2022
    try:
        redeem_request = RedeemRequest.objects.get(plan=plan, user=user)
    except RedeemRequest.DoesNotExist:
        return {
            'status': 'failed',
            'code': 'NoRedeemRequest',
            'message': 'NoRedeemRequest',
        }
    with transaction.atomic():
        result, err = redeem_request.do_redeem()
    if not result:
        return {
            'status': 'failed',
            'code': err,
            'message': err,
        }
    return {
        'status': 'ok',
        'redeem': redeem_request,
    }


@ratelimit(key='user_or_ip', rate='10/10m', block=True)
@api
def request_unblock(request):
    user = request.user
    plan = RedeemRequest.PLAN.pgala2022
    try:
        redeem_request = RedeemRequest.objects.get(plan=plan, user=user)
    except RedeemRequest.DoesNotExist:
        return {
            'status': 'failed',
            'code': 'NoRedeemRequest',
            'message': 'NoRedeemRequest',
        }
    if redeem_request.status != RedeemRequest.STATUS.confirmed:
        if redeem_request.status == RedeemRequest.STATUS.done:
            return {
                'status': 'failed',
                'code': 'AlreadyUnblocked',
                'message': 'AlreadyUnblocked',
            }
        return {
            'status': 'failed',
            'code': 'NotRedeemedYet',
            'message': 'NotRedeemedYet',
        }
    if not redeem_request.has_sana:
        return {
            'status': 'failed',
            'code': 'MissingSanaConfirmation',
            'message': 'کد تأیید وکالت سامانه ثنا هنوز دریافت نشده است.',
        }

    with transaction.atomic():
        result, err = redeem_request.do_unblock()
    if not result:
        return {
            'status': 'failed',
            'code': err,
            'message': err,
        }
    return {
        'status': 'ok',
        'redeem': redeem_request,
    }
