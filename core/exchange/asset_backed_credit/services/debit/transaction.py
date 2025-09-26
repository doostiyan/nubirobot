from typing import Optional, Union

from django.db.models import QuerySet

from exchange.accounts.models import User
from exchange.asset_backed_credit.externals.wallet import TransactionType
from exchange.asset_backed_credit.models import DebitSettlementTransaction, Transaction, Wallet
from exchange.asset_backed_credit.services.debit.card import get_debit_card
from exchange.asset_backed_credit.services.wallet.transaction import TransactionService
from exchange.asset_backed_credit.services.wallet.wallet import WalletService
from exchange.asset_backed_credit.types import RequestFilters
from exchange.base.models import CURRENCY_CODENAMES
from exchange.wallet.models import Transaction as ExchangeTransaction


def get_debit_card_transfers(
    user: User, card_id: int, filters: Optional[RequestFilters] = None
) -> QuerySet[Union[Transaction, ExchangeTransaction]]:
    get_debit_card(user, card_id)
    wallets = WalletService.get_user_wallets_by_currencies(
        user_id=user.uid, exchange_user_id=user.id, wallet_type=Wallet.WalletType.DEBIT
    )
    wallets = {wallet['id']: wallet['currency'] for wallet in wallets}
    wallet_ids = list(wallets.keys())
    transactions = TransactionService.get_transactions(wallet_ids, tp=TransactionType.transfer, filters=filters)

    for transaction in transactions:
        transaction['currency'] = CURRENCY_CODENAMES.get(wallets[transaction['wallet_id']], '').lower()

    return transactions


def get_debit_card_settlements(
    user: User, card_id: int, filters: Optional[RequestFilters] = None
) -> QuerySet[DebitSettlementTransaction]:
    card = get_debit_card(user, card_id)
    settlements = DebitSettlementTransaction.objects.filter(
        pan=card.pan,
        status__in=[DebitSettlementTransaction.STATUS.confirmed, DebitSettlementTransaction.STATUS.unknown_confirmed],
    )
    if filters.from_date:
        settlements = settlements.filter(created_at__date__gte=filters.from_date)
    if filters.to_date:
        settlements = settlements.filter(created_at__date__lte=filters.to_date)

    return settlements.values('id', 'created_at', 'amount', 'remaining_rial_wallet_balance').order_by(
        '-created_at', '-id'
    )
