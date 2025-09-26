from typing import List, Optional, Union

from django.db import connection
from django.db.models import QuerySet

from exchange.asset_backed_credit.externals.wallet import TransactionType
from exchange.asset_backed_credit.models import Transaction
from exchange.asset_backed_credit.types import RequestFilters
from exchange.base.models import Settings
from exchange.wallet.models import Transaction as ExchangeTransaction


class TransactionService:
    @classmethod
    def get_transactions(
        cls, wallet_ids: List[int], tp: TransactionType, filters: Optional[RequestFilters] = None
    ) -> QuerySet[Union[Transaction, ExchangeTransaction]]:
        if Settings.get_flag('abc_debit_internal_wallet_enabled'):
            transactions = Transaction.objects.filter(wallet_id__in=wallet_ids, tp=tp)
        else:
            # Next lines will force postgres planner to use index instead of seq scan
            cursor = connection.cursor()
            cursor.execute('SET LOCAL random_page_cost = 0.1;')

            transactions = ExchangeTransaction.objects.filter(
                wallet_id__in=wallet_ids, tp=getattr(ExchangeTransaction.TYPE, tp.name)
            )

        if filters.from_date:
            transactions = transactions.filter(created_at__date__gte=filters.from_date)
        if filters.to_date:
            transactions = transactions.filter(created_at__date__lte=filters.to_date)

        transactions = transactions.order_by('-created_at', '-id')

        return transactions.values('id', 'amount', 'created_at', 'balance', 'tp', 'wallet_id')
