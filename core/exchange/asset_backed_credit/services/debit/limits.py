from typing import Union

from exchange.asset_backed_credit.api.serializers import DebitCardOverViewSchema, DebitCardSpendingLimitsSchema
from exchange.asset_backed_credit.exceptions import CardTransactionLimitExceedError, CardUnknownLevelError
from exchange.asset_backed_credit.models import Card, CardSetting, CardTransactionLimit, Wallet
from exchange.asset_backed_credit.services.wallet.balance import get_total_wallet_balance
from exchange.base.formatting import format_money
from exchange.base.models import Currencies


def check_card_transaction_limits(card: Card, new_transaction_amount: int):
    card_setting = card.setting
    if not card_setting:
        raise CardUnknownLevelError('card has no level specified to it')

    if new_transaction_amount > card_setting.per_transaction_amount_limit:
        raise CardTransactionLimitExceedError(
            f'transaction amount must be lower than {format_money(card_setting.per_transaction_amount_limit, Currencies.rls)} Toman'
        )

    if (
        new_transaction_amount + CardTransactionLimit.get_card_daily_total_amount(card)
        > card_setting.daily_transaction_amount_limit
    ):
        raise CardTransactionLimitExceedError('transaction amount exceeds daily total limits of card.')

    if (
        new_transaction_amount + CardTransactionLimit.get_card_monthly_total_amount(card)
        > card_setting.monthly_transaction_amount_limit
    ):
        raise CardTransactionLimitExceedError('transaction amount exceeds monthly total limits of card.')


def get_default_card_settings() -> Union[None, CardSetting]:
    try:
        return CardSetting.objects.get(level=CardSetting.DEFAULT_CARD_LEVEL)
    except CardSetting.DoesNotExist:
        return None


def get_card_overview_info(card: Card) -> Union[None, DebitCardOverViewSchema]:
    card_level = card.setting
    if not card_level:
        return None

    this_month_spent_amount = CardTransactionLimit.get_card_monthly_total_amount(card)
    monthly_remaining_amount = card_level.monthly_transaction_amount_limit - this_month_spent_amount
    today_spent_amount = CardTransactionLimit.get_card_daily_total_amount(card)
    daily_remaining_amount = min(
        card_level.daily_transaction_amount_limit - today_spent_amount, monthly_remaining_amount
    )
    today_remaining_spending_percent = int(100 * daily_remaining_amount / card_level.daily_transaction_amount_limit)
    monthly_remaining_spending_percent = int(
        100 * monthly_remaining_amount / card_level.monthly_transaction_amount_limit
    )
    debit_wallet_rial_balance = get_total_wallet_balance(
        user_id=card.user.uid, exchange_user_id=card.user.id, wallet_type=Wallet.WalletType.DEBIT
    )

    return DebitCardOverViewSchema(
        available_balance=debit_wallet_rial_balance,
        today_spending=today_spent_amount,
        this_month_spending=this_month_spent_amount,
        today_remaining_spending=daily_remaining_amount,
        today_remaining_spending_percent=today_remaining_spending_percent,
        this_month_remaining_spending=monthly_remaining_amount,
        this_month_remaining_spending_percent=monthly_remaining_spending_percent,
        this_month_cashback=0,  # fixme after cashback completed
        this_month_cashback_percentage=card_level.cashback_percentage,
        limits=DebitCardSpendingLimitsSchema(
            daily_limit=card_level.daily_transaction_amount_limit,
            monthly_limit=card_level.monthly_transaction_amount_limit,
            transaction_limit=card_level.per_transaction_amount_limit,
        ),
    )
