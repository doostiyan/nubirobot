from decimal import Decimal
from typing import Union

Transaction = Union['StakingTransaction', 'PlanTransaction']


def add_to_transaction_amount(transaction: Transaction, amount: Decimal) -> None:
    transaction.amount += amount
    transaction.save(update_fields=('amount',))
