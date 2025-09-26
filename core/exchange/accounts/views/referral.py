""" API views for referral program """
import datetime

from django.db.models import Count, Sum
from django.utils.timezone import now
from django_ratelimit.decorators import ratelimit

from exchange.accounts.models import ReferralProgram, User, UserReferral
from exchange.base.api import api
from exchange.base.parsers import parse_choices, parse_int
from exchange.base.serializers import serialize
from exchange.market.models import ReferralFee


@ratelimit(key='user_or_ip', rate='50/10m', block=True)
@api
def users_set_referrer(request):
    """ POST /users/referral/set-referrer """
    referrer_code = request.g('referrerCode')
    if request.user.date_joined < now() - datetime.timedelta(days=1):
        return {
            'status': 'failed',
            'code': 'ReferrerChangeUnavailable',
            'message': 'تعریف معرف تنها تا یک روز بعد از ثبت‌نام ممکن است.',
        }
    success = UserReferral.set_user_referrer(request.user, referrer_code, channel='panel')
    return {
        'status': 'ok' if success else 'failed',
    }


@ratelimit(key='user_or_ip', rate='50/10m', block=True)
@api
def users_get_referral_code(request):
    """ POST /users/get-referral-code
        This API is deprecated in favor of /users/referral/links-list
    """
    # Default referral program
    user = User.objects.select_for_update(no_key=True).get(pk=request.user.pk)
    program = ReferralProgram.objects.filter(user=user, friend_share=0).first()
    if not program:
        program, error = ReferralProgram.create(user, 0)
        if error:
            return {
                'status': 'failed',
                'code': error,
                'message': 'Failed to get default referral link',
            }
    # Referral total stats
    fees = ReferralFee.objects.filter(user=user).aggregate(count=Count('*'), sum=Sum('amount'))
    user_referrals = UserReferral.objects.filter(parent=user)
    return {
        'status': 'ok',
        'referralCode': program.referral_code,
        'referredUsersCount': user_referrals.count(),
        'referralFeeTotal': round(fees['sum'] or 0),
        'referralFeeTotalCount': fees['count'] or 0,
        'hasReferrer': UserReferral.get_referrer(user) is not None,
    }



@ratelimit(key='user_or_ip', rate='50/10m', block=True)
@api
def users_referral_status(request):
    """ POST /users/referral/referral-status
    """
    return {
        'status': 'ok',
        'hasReferrer': UserReferral.get_referrer(request.user) is not None,
    }


@ratelimit(key='user_or_ip', rate='5/1m', block=True)
@api
def users_referral_links_add(request):
    """ POST /users/referral/links-add
    """
    input_friend_share = parse_int(request.g('friendShare')) or 0
    agenda = (
        parse_choices(ReferralProgram.AGENDA, request.g('agenda'), required=False) or ReferralProgram.AGENDA.default
    )
    ref_program, error = ReferralProgram.create(request.user, input_friend_share, agenda=agenda)
    if error:
        return {
            'status': 'failed',
            'code': error,
            'message': 'Failed to create the requested referral link',
        }
    return {
        'status': 'ok',
        'result': ref_program,
    }


@ratelimit(key='user_or_ip', rate='50/10m', block=True)
@api
def users_referral_links_list(request):
    """ POST /users/referral/links-list
    """
    user = request.user
    links = []
    referral_programs = ReferralProgram.objects.filter(user=user).order_by('created_at')
    default_program = None
    for program in referral_programs:
        if program.user_share == 30:
            default_program = program
            break
    for program in referral_programs:
        links.append(serialize(program, {'level': 2, 'includeOldFees': program == default_program}))
    return {
        'status': 'ok',
        'links': links,
    }
