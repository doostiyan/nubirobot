from decimal import Decimal
from typing import Optional

from exchange.base.serializers import register_serializer, serialize_choices, serialize_currency
from exchange.base.money import quantize_number
from exchange.credit import models


@register_serializer(model=models.CreditTransaction)
def serialize_transaction(
    transaction: models.CreditTransaction, opts: Optional[dict] = None,  # pylint: disable=unused-argument
):
    return {
        'id': transaction.pk,
        'type': serialize_choices(models.CreditTransaction.TYPES, transaction.tp,),
        'currency': serialize_currency(transaction.currency,),
        'createdAt': transaction.created_at,
        'amount': transaction.amount,
    }


@register_serializer(model=models.CreditPlan)
def serialize_plan(
    plan: models.CreditPlan, opts: Optional[dict] = None,  # pylint: disable=unused-argument
):
    return {
        'id': plan.pk,
        'startsAt': plan.starts_at,
        'expiresAt': plan.expires_at,
        'maximumWithdrawalPercentage': plan.maximum_withdrawal_percentage,
        'creditLimitPercentage': plan.credit_limit_percentage,
        'creditLimitInUsdt': plan.credit_limit_in_usdt,
    }


def serialize_computed_decimal(value) -> Decimal:
    '''Note that computed decimals (in contrast to model fields) would have
        a redundantly large number of decimal place, this method would cut these
        numbers to have at most ten decimal places.
    '''
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return quantize_number(value, precision=Decimal('0.000_000_000_1'))
