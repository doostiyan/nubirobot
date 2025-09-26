
from exchange.base.api_v2_1 import api, NobitexError
from exchange.base.parsers import parse_money, parse_currency
from exchange.base.models import get_currency_codename
from exchange.features.utils import require_feature

from exchange.credit import errors
from exchange.credit import helpers
from exchange.credit.models import CreditPlan
from exchange.credit.serializers import serialize_computed_decimal


def handle_exceptions(view):
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except CreditPlan.DoesNotExist as e:
            raise NobitexError(status_code=404, code='NoCreditPlan', message='Plan does not exist.',) from e
        except errors.CreditError as e:
            raise NobitexError(status_code=400, code=e.__class__.__name__, message=e.message,) from e
    return wrapper


@api(POST='5/1m')
@require_feature('vip_credit')
@handle_exceptions
def lend_view(request):
    """POST /credit/lend"""
    amount = parse_money(request.g('amount'), required=True,)
    currency = parse_currency(request.g('currency'), required=True,)
    return CreditPlan.lend(request.user.id, currency, amount,)


@api(POST='5/1m')
@require_feature('vip_credit')
@handle_exceptions
def repay_view(request):
    """POST /credit/repay"""
    amount = parse_money(request.g('amount'), required=True,)
    currency = parse_currency(request.g('currency'), required=True,)
    return CreditPlan.repay(request.user.id, currency, amount,)


@api(GET='5/1m')
@require_feature('vip_credit')
@handle_exceptions
def user_debt_detail_view(request):
    """GET /credit/debt-detail"""
    user_debts = CreditPlan.get_user_debts_and_usdt_values(request.user.id,)
    total_debt = sum(debt['value'] for debt in user_debts.values())
    return {
        'totalAssetsValue': serialize_computed_decimal(helpers.get_user_net_worth(request.user.id,) - total_debt),
        'totalDebtValue': serialize_computed_decimal(total_debt),
        'debts': {
            get_currency_codename(currency): {
                'amount': serialize_computed_decimal(amount_and_value['amount']),
                'value': serialize_computed_decimal(amount_and_value['value']),
            } for currency, amount_and_value in user_debts.items()
        },
    }


@api(GET='10/1m')
@require_feature('vip_credit')
@handle_exceptions
def user_credit_plan_view(request):
    """GET /credit/plan"""
    return CreditPlan.get_last_plan(request.user.id,)


@api(GET='5/1m')
@require_feature('vip_credit')
@handle_exceptions
def user_history_view(request):
    """GET /credit/transactions"""
    return CreditPlan.get_user_transactions(request.user.id,)


@api(GET='1/30s')
@require_feature('vip_credit')
@handle_exceptions
def lending_calculator_view(request):
    """GET /credit/lend-calculator"""
    return {
        get_currency_codename(currency): serialize_computed_decimal(amount)
        for currency, amount in CreditPlan.get_user_max_possible_lendings(request.user.id,).items()
    }


@api(GET='1/30s')
@require_feature('vip_credit')
@handle_exceptions
def withdraw_calculator_view(request):
    """GET /credit/withdraw-calculator"""
    return {
        get_currency_codename(currency): serialize_computed_decimal(amount)
        for currency, amount in CreditPlan.get_user_max_possible_withdraws(request.user.id,).items()
    }
