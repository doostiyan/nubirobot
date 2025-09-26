
from celery import shared_task

from exchange.base.models import Currencies
from exchange.base.parsers import parse_money
from exchange.accounts.models import User
from exchange.features.utils import is_feature_enabled

from exchange.credit import errors
from exchange.credit import models


@shared_task(name='credit.admin.lend')
def lend_task(
    user_id: int,
    currency: int,
    amount: str,
) -> None:
    amount = parse_money(amount)
    if currency not in Currencies._db_values:
        raise errors.AdminMistake('There is no such currency')
    if not is_feature_enabled(User.objects.get(pk=user_id), 'vip_credit',):
        raise errors.AdminMistake('Feature is not enable')
    models.CreditPlan.lend(user_id, currency, amount)


@shared_task(name='credit.admin.repay')
def repay_task(
    user_id: int,
    currency: int,
    amount: str,
) -> None:
    amount = parse_money(amount)
    if currency not in Currencies._db_values:
        raise errors.AdminMistake('There is no such currency')
    if not is_feature_enabled(User.objects.get(pk=user_id), 'vip_credit',):
        raise errors.AdminMistake('Feature is not enable')
    models.CreditPlan.repay(user_id, currency, amount)
