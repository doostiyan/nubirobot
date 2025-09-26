""" API views for user plans """
import datetime
import random

import pytz
from django.db import DatabaseError, transaction
from django.utils.timezone import now
from django_ratelimit.decorators import ratelimit

from exchange.accounts.models import UserPlan
from exchange.accounts.userlevels import UserPlanManager
from exchange.base.api import api
from exchange.base.models import Settings
from exchange.base.parsers import parse_choices


@api
def plans_list(request):
    user = request.user
    plans = UserPlan.get_user_plans(user)
    return {
        'status': 'ok',
        'plans': plans
    }


@ratelimit(key='user_or_ip', rate='1/10s', block=True)
@ratelimit(key='user_or_ip', rate='10/10m', block=True)
@api
def activate_plan(request):
    """API for activating a user plan.

        POST /users/plans/activate
    """
    user = request.user
    plan = parse_choices(UserPlan.TYPE, request.g('plan'), required=True)
    if UserPlan.user_has_active_plan(user, plan):
        return {
            'status': 'failed',
            'message': 'Plan is already activated.',
            'code': 'PlanAlreadyActivated',
        }

    # Check plan rules
    if not UserPlanManager.is_eligible_to_activate(user, plan):
        return {
            'status': 'failed',
            'message': 'Not eligible to activate, please consult plan rules.',
            'code': 'NotEligibleToActivatePlan',
        }

    # Concurrency control
    with transaction.atomic():
        try:
            UserPlan.objects.filter(user=user).select_for_update(nowait=True).first()
        except DatabaseError:
            return {
                'status': 'failed',
                'code': 'MultipleRequests',
                'error': 'Multiple Requests',
            }

    # Activate plan
    UserPlan(user=user, type=plan).activate()
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='1/10s', block=True)
@ratelimit(key='user_or_ip', rate='10/10m', block=True)
@api
def deactivate_plan(request):
    """API for deactivating a user plan.

        POST /users/plans/deactivate
    """
    user = request.user
    input_plan = parse_choices(UserPlan.TYPE, request.g('plan'), required=True)
    user_plan = UserPlan.get_user_active_plan_by_type(user, input_plan)
    if not user_plan:
        return {
            'status': 'failed',
            'message': 'There is no active \'{}\' plan'.format(input_plan),
            'code': 'NoSuchActivePlan',
        }

    # Check plan rules
    if not UserPlanManager.is_eligible_to_deactivate(user_plan):
        return {
            'status': 'failed',
            'message': 'Not eligible to deactivate, please consult plan rules.',
            'code': 'NotEligibleToDeactivatePlan',
        }

    # Concurrency control
    with transaction.atomic():
        try:
            UserPlan.objects.filter(user=user).select_for_update(nowait=True).first()
        except DatabaseError:
            return {
                'status': 'failed',
                'code': 'MultipleRequests',
                'error': 'Multiple Requests',
            }

    # Deactivate plan
    user_plan.deactivate()
    return {
        'status': 'ok',
    }


@api
@ratelimit(key='user_or_ip', rate='3/m', block=False)
def plans_developer2021(request):
    user = request.user
    launch_date = datetime.datetime(2021, 9, 13, 11, 30, 0, 0, pytz.utc)
    if getattr(request, 'limited', False):
        request.limited = False
        return {
            'status': 'ok',
            'challenge': 'https://http.cat/429',
        }
    if now() < launch_date:
        return {
            'status': 'ok',
            'challenge': 'https://http.cat/425',
        }
    if user.user_type < 44:
        return {
            'status': 'ok',
            'challenge': 'https://http.cat/426',
        }
    if user.date_joined > launch_date:
        return {
            'status': 'ok',
            'challenge': 'https://http.cat/412',
        }

    # Get challenge
    challenges = Settings.get_json_object('developers2021', '[]')
    if not challenges:
        return {
            'status': 'ok',
            'challenge': 'https://http.cat/410',
        }
    challenge = challenges[user.pk % len(challenges)]

    # Encrypt
    shift = random.randint(1, 35)
    alphabet = 'abcdefghijklmnopqrstuvwxyz0123456789'
    shifted_alphabet = alphabet[shift:] + alphabet[:shift]
    table = str.maketrans(alphabet, shifted_alphabet)
    encrypted_challenge = challenge.translate(table)

    return {
        'status': 'ok',
        'challenge': encrypted_challenge,
    }
