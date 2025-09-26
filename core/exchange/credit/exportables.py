import decimal

from exchange.credit import helpers
from exchange.credit import models


def check_if_user_could_withdraw(user_id: int, currency: int, amount: decimal.Decimal,) -> bool:
    user_debt = helpers.get_user_debt_worth(user_id)
    if not user_debt:
        return True

    try:
        minimum_required_assets = user_debt / models.CreditPlan.get_active_plan(
            user_id,
        ).maximum_withdrawal_percentage
    except models.CreditPlan.DoesNotExist:
        return False

    user_controlled_assets = helpers.get_user_net_worth(user_id)
    user_assets = user_controlled_assets - user_debt
    withdraw_request_worth = helpers.ToUsdtConvertor(currency).get_price() * amount
    return user_assets - withdraw_request_worth > minimum_required_assets
