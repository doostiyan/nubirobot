from django.http import JsonResponse

from exchange.base.api_v2_1 import NobitexError, api, paginate, public_api
from exchange.base.decorators import measure_api_execution
from exchange.base.parsers import parse_bool, parse_choices, parse_int, parse_money
from exchange.staking import best_performing_plans, errors
from exchange.staking.helpers import (
    Restriction,
    check_user_restriction,
    env_aware_ratelimit,
    staking_exc_to_api_exc_translator,
    staking_user_level,
)
from exchange.staking.models import ExternalEarningPlatform, Plan, StakingTransaction, UserWatch
from exchange.staking.serializers import (
    serialize_staking_transaction,
    serialize_user_subscriptions,
    serialize_user_unsubscriptions,
    serialize_v1_end_request,
)
from exchange.staking.service.auto_renewal import set_plan_auto_renewal, validate_can_auto_renew_plan
from exchange.staking.service.instant_end import add_and_apply_instant_end_request
from exchange.staking.service.staking import get_user_stakings
from exchange.staking.service.subscription import subscribe
from exchange.staking.service.unstaking import get_user_unstakings


@measure_api_execution(api_label='stakingPlans')
@public_api(env_aware_ratelimit('20/m'))
def plans_view(request):
    """GET /earn/plan"""
    tp = parse_choices(ExternalEarningPlatform.TYPES, request.g('type'), required=False)
    plans = Plan.all_active_plans()
    if tp:
        plans = Plan.filter_by_tp(plans, tp)
    return plans


@measure_api_execution(api_label='stakingPlanOffers')
@public_api(env_aware_ratelimit('20/m'))
def plan_offers_view(request):
    """GET /earn/plan/offers"""
    # deprecated API. User /earn/plan/best-performing
    return []


@measure_api_execution(api_label='stakingRequestsList')
@api(GET=env_aware_ratelimit('6/30s'))
@staking_user_level
def requests_list_view(request):
    """GET /earn/request"""
    plan_type = parse_choices(ExternalEarningPlatform.TYPES, request.g('planType'), required=False)
    staking_requests = StakingTransaction.active_requests(request.user.id, plan_type=plan_type)
    serialization_level = 2 if plan_type else 1
    return [serialize_staking_transaction(r, opts={'level': serialization_level}) for r in staking_requests]


@measure_api_execution(api_label='stakingCreateRequest')
@api(POST=env_aware_ratelimit('3/1m'))
@staking_user_level
@check_user_restriction(Restriction.CREATE_REQUEST)
def create_request_view(request):
    """POST /earn/request/create"""
    plan_id = parse_int(request.g('planId'), required=True)
    amount = parse_money(request.g('amount'), required=True)
    auto_extend = parse_bool(request.g('autoExtend'), required=False)
    try:
        create_request = subscribe(request.user, plan_id, amount, auto_extend)
    except errors.LowPlanCapacity as e:
        raise NobitexError(
            status_code=400,
            code='LowPlanCapacity',
            message='Insufficient plan capacity',
        ) from e
    except (errors.FailedAssetTransfer, errors.InsufficientWalletBalance) as e:
        raise NobitexError(
            status_code=400,
            code='FailedAssetTransfer',
            message='Asset Transfer failure',
        ) from e
    except Exception as e:
        api_exception = staking_exc_to_api_exc_translator(e)
        if api_exception is None:
            raise
        raise api_exception from e

    return create_request


@measure_api_execution(api_label='stakingEndRequest')
@api(POST=env_aware_ratelimit('3/1m'))
@staking_user_level
@check_user_restriction(Restriction.INSTANT_END)
def end_request_view(request):
    """POST /earn/request/end
    Note: This API is deprecated and was used in
    staking V1.
    We change it to instant end.
    """

    plan_id = parse_int(request.g('planId'), required=True)
    amount = parse_money(request.g('amount'), required=True)
    try:
        staking_transaction = add_and_apply_instant_end_request(request.user.id, plan_id, amount)
        return serialize_v1_end_request(staking_transaction)
    except errors.ParentIsNotCreated as e:
        raise NobitexError(
            status_code=404,
            code='NoStaking',
            message='No Staking on with plan id',
        ) from e
    except Exception as e:
        api_exception = staking_exc_to_api_exc_translator(e)
        if api_exception is None:
            raise
        raise api_exception from e


@measure_api_execution(api_label='stakingInstantEndRequest')
@api(POST=env_aware_ratelimit('3/1m'))
@staking_user_level
@check_user_restriction(Restriction.INSTANT_END)
def instant_end_request_view(request):
    """POST /earn/request/instant-end"""

    plan_id = parse_int(request.g('planId'), required=True)
    amount = parse_money(request.g('amount'), required=True)
    try:
        instant_end_transaction = add_and_apply_instant_end_request(
            user_id=request.user.id, plan_id=plan_id, amount=amount
        )
        return instant_end_transaction
    except errors.PlanIsNotInstantlyUnstakable as e:
        raise NobitexError(
            status_code=400,
            code='PlanIsNotInstantlyUnstakable',
            message='Creating instant end request for this plan is not possible.',
        ) from e

    except Exception as e:
        api_exception = staking_exc_to_api_exc_translator(e)
        if api_exception is None:
            raise
        raise api_exception from e


@measure_api_execution(api_label='stakingUserSubscription')
@api(GET=env_aware_ratelimit('30/3m'))
@staking_user_level
def user_subscription_view(request):
    """GET /earn/subscription
        List User Subscriptions
    """
    plan_type = parse_choices(ExternalEarningPlatform.TYPES, request.g('type'), required=False)
    qs = get_user_stakings(request.user.id, plan_type)
    paginated_result = paginate(qs, request)
    return JsonResponse(
        {
            'status': 'ok',
            'hasNext': paginated_result['hasNext'],
            'result': [serialize_user_subscriptions(obj) for obj in paginated_result['result']],
        },
        safe=False,
    )


@measure_api_execution(api_label='stakingUserUnSubscription')
@api(GET=env_aware_ratelimit('30/3m'))
@staking_user_level
def user_unsubscription_view(request):
    """GET /earn/unsubscription
    List User UnSubscriptions
    """
    plan_type = parse_choices(ExternalEarningPlatform.TYPES, request.g('type'), required=False)
    qs = get_user_unstakings(request.user.id, plan_type)
    paginated_result = paginate(qs, request)
    return JsonResponse(
        {
            'status': 'ok',
            'hasNext': paginated_result['hasNext'],
            'result': [serialize_user_unsubscriptions(obj) for obj in paginated_result['result']],
        },
        safe=False,
    )


@measure_api_execution(api_label='stakingWatchedPlan')
@api(GET=env_aware_ratelimit('6/30s'))
@staking_user_level
def watch_plan_view(request):
    """GET /earn/plan/watch
        List All Marked Plans
    """
    return UserWatch.get(request.user.id)


@measure_api_execution(api_label='stakingAddWatchedPlan')
@api(POST=env_aware_ratelimit('5/50s'))
@staking_user_level
def add_plan_watch_view(request):
    """POST /earn/plan/watch/add
        Add a plan to user marked plans list
    """
    plan_id = parse_int(request.g('planId'), required=True)
    try:
        UserWatch.add(request.user.id, plan_id)
    except Exception as e:
        api_exception = staking_exc_to_api_exc_translator(e)
        if api_exception is None:
            raise
        raise api_exception from e


@measure_api_execution(api_label='stakingRemoveWatchedPlan')
@api(POST=env_aware_ratelimit('5/50s'))
@staking_user_level
def remove_plan_watch_view(request):
    """POST /earn/plan/watch/remove
        Remove a plan from user marked plans list
    """
    plan_id = parse_int(request.g('planId'), required=True)
    try:
        UserWatch.remove(request.user.id, plan_id)
    except Exception as e:
        api_exception = staking_exc_to_api_exc_translator(e)
        if api_exception is None:
            raise
        raise api_exception from e


@measure_api_execution(api_label='stakingEnableAutoExtend')
@api(POST=env_aware_ratelimit('3/1m'))
@staking_user_level
@check_user_restriction(Restriction.AUTO_EXTEND)
def enable_auto_extend_view(request):
    """POST /earn/plan/auto-extend/enable"""
    plan_id = parse_int(request.g('planId'), required=True)
    try:
        validate_can_auto_renew_plan(plan_id=plan_id)
        set_plan_auto_renewal(user_id=request.user.id, plan_id=plan_id, allow_renewal=True)
    except Exception as e:
        api_exception = staking_exc_to_api_exc_translator(e)
        if api_exception is None:
            raise
        raise api_exception from e


@measure_api_execution(api_label='stakingDisableAutoExtend')
@api(POST=env_aware_ratelimit('3/1m'))
@staking_user_level
@check_user_restriction(Restriction.AUTO_EXTEND)
def disable_auto_extend_view(request):
    """POST /earn/plan/auto-extend/disable"""
    plan_id = parse_int(request.g('planId'), required=True)
    try:
        validate_can_auto_renew_plan(plan_id=plan_id)
        set_plan_auto_renewal(user_id=request.user.id, plan_id=plan_id, allow_renewal=False)
    except Exception as e:
        api_exception = staking_exc_to_api_exc_translator(e)
        if api_exception is None:
            raise
        raise api_exception from e


@measure_api_execution(api_label='stakingBestPerformingPlans')
@public_api(env_aware_ratelimit('20/1m'))
def best_performing_plans_view(request):
    """GET /earn/plan/best-performing"""
    tp = parse_choices(
        ExternalEarningPlatform.TYPES, request.g('type'),
        required=False,
    ) or ExternalEarningPlatform.TYPES.staking
    return best_performing_plans.get_plans(tp)
