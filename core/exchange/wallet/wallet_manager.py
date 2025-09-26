from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from django.db import connection, transaction
from django.utils.timezone import now

from exchange.accounts.models import Notification
from exchange.base.internal.services import Services
from exchange.wallet.exceptions import InsufficientBalanceError
from exchange.wallet.models import Transaction, Wallet


class WalletTransactionManager:
    def __init__(self, wallet: Wallet):
        self.wallet = wallet
        self._starting_balance = wallet.balance
        self._transactions: List[Transaction] = []

    def add_transaction(
        self,
        tp: str,  # from `Transaction.TYPE`
        amount: Decimal,
        description: str,
        created_at: Optional[datetime] = None,
        ref_module: Optional[str] = None,  # from `Transaction.REF_MODULES` keys
        ref_id: Optional[int] = None,
        service: Optional[Services] = None,
        *,
        allow_negative_balance: bool = False,
    ):
        """Add a transaction to the bulk list. Does NOT commit them."""

        if not (
            txn := self.wallet.create_transaction(
                tp=tp,
                amount=amount,
                description=description,
                created_at=created_at,
                ref_module=Transaction.REF_MODULES.get(ref_module),
                ref_id=ref_id,
                service=service,
                allow_negative_balance=allow_negative_balance,
            )
        ):
            raise ValueError('Transaction would result in negative wallet balance')

        self._transactions.append(txn)
        self.wallet.balance += txn.amount

    @transaction.atomic
    def commit(self, allow_negative_balance=False):
        """
        Atomically commits all accumulated transactions and updates the wallet balance.
        """

        total_delta = sum(t.amount for t in self._transactions)

        with connection.cursor() as cursor:
            if allow_negative_balance:
                cursor.execute(
                    'UPDATE wallet_wallet SET balance = balance + %s WHERE id = %s RETURNING balance',
                    [total_delta, self.wallet.id],
                )
            else:
                cursor.execute(
                    'UPDATE wallet_wallet SET balance = balance + %s WHERE id = %s AND balance + %s >= 0 RETURNING balance',
                    [total_delta, self.wallet.id, total_delta],
                )

            result = cursor.fetchone()
            if result is None:
                Notification.notify_admins(
                    'Bulk commit failed: not enough funds', title='📤 Bulk Commit Error', channel='pool'
                )
                self.reinitialize()
                self.wallet.balance = self._starting_balance
                raise InsufficientBalanceError('InsufficientBalance')
        updated_balance = result[0]

        prev_amount = 0
        for tx in reversed(self._transactions):
            tx.balance = updated_balance - prev_amount
            prev_amount += tx.amount

        Transaction.objects.bulk_create(self._transactions)
        self.wallet.balance = updated_balance

        self.reinitialize()
        self._starting_balance = updated_balance
        return self.wallet

    def reinitialize(self):
        self._transactions.clear()
