from typing import Dict, List

from django.core.management.base import BaseCommand
from django.db.models import Exists, OuterRef, Subquery

from exchange.accounts.constants import SYSTEM_USER_IDS
from exchange.accounts.models import Notification
from exchange.base.decorators import measure_time
from exchange.base.helpers import sleep_remaining
from exchange.base.logging import metric_incr, report_exception
from exchange.base.models import Settings
from exchange.config.config.derived_data import get_currency_codename
from exchange.margin.models import Position
from exchange.pool.models import LiquidityPool
from exchange.wallet.exceptions import InsufficientBalanceError
from exchange.wallet.models import Transaction, Wallet
from exchange.wallet.wallet_manager import WalletTransactionManager


class Command(BaseCommand):
    """
    Examples:
        python manage.py create_pool_pnl_transactions
    """

    help = 'Create PNL transactions for pools and save them in positions.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Run once [useful for testing]')

    def handle(self, once, **options):
        pending_positions_count = 0
        try:
            while not Settings.is_disabled('create_pool_pnl_transactions'):
                gap = max(60 - pending_positions_count / 2, 2)
                with sleep_remaining(seconds=0 if once else gap):
                    pending_positions_count = self.create_pool_pnl_transactions()
                    metric_incr(
                        'metric_pool_pnl_positions_count', amount=pending_positions_count, labels=('pendingPositions',)
                    )
                    if once:
                        break
        except KeyboardInterrupt:
            print('\n\nAborted!')

    @staticmethod
    @measure_time(metric='create_pool_pnl_transactions_time')
    def create_pool_pnl_transactions():
        pending_positions = list(
            Position.objects.filter(pnl__isnull=False, pnl_transaction__isnull=True)
            .exclude(pnl=0)
            .annotate(
                has_pool_txn=Exists(
                    Transaction.objects.filter(
                        ref_module=Transaction.REF_MODULES['PositionPoolPNL'],
                        ref_id=OuterRef('id'),
                    )
                ),
                has_adjust_txn=Exists(
                    Transaction.objects.filter(
                        ref_module=Transaction.REF_MODULES['PositionAdjustPNL'],
                        ref_id=OuterRef('id'),
                    )
                ),
                user_transaction_id=Subquery(
                    Transaction.objects.filter(
                        ref_module=Transaction.REF_MODULES['PositionUserPNL'], ref_id=OuterRef('id')
                    ).values('id')[:1]
                )
            )
        )
        to_be_updated_positions: List[Position] = []

        pools = LiquidityPool.objects.all().in_bulk(field_name='currency')

        pool_managers: Dict[int, WalletTransactionManager] = {}
        adjust_managers: Dict[int, WalletTransactionManager] = {}

        for position in pending_positions:
            if position.is_short:
                pool_wallet = pools[position.src_currency].get_dst_wallet(position.dst_currency)
            else:
                pool_wallet = pools[position.dst_currency].src_wallet

            if not position.has_pool_txn:
                pm = pool_managers.setdefault(pool_wallet.id, WalletTransactionManager(pool_wallet))
                try:
                    pm.add_transaction(
                        tp='pnl',
                        amount=-position.earned_amount,
                        description=position.pnl_transaction_description,
                        ref_module='PositionPoolPNL',
                        ref_id=position.id,
                    )
                except ValueError:
                    report_exception()
                    continue

            pool_pnl = position.earned_amount - position.pnl
            if pool_pnl and not position.has_adjust_txn:
                provider_id = SYSTEM_USER_IDS.system_fix if pool_pnl < 0 else SYSTEM_USER_IDS.system_pool_profit
                adjust_wallet = Wallet.get_user_wallet(user=provider_id, currency=position.dst_currency)
                am = adjust_managers.setdefault(adjust_wallet.id, WalletTransactionManager(adjust_wallet))
                try:
                    am.add_transaction(
                        tp='pnl',
                        amount=pool_pnl,
                        description=position.pnl_transaction_description,
                        ref_module='PositionAdjustPNL',
                        ref_id=position.id,
                        allow_negative_balance=True,
                    )
                except ValueError:
                    report_exception()
                    continue

            position.pnl_transaction_id = position.user_transaction_id
            to_be_updated_positions.append(position)

        for manager in adjust_managers.values():
            manager.commit(allow_negative_balance=True)

        for manager in pool_managers.values():
            try:
                manager.commit()
            except InsufficientBalanceError:
                report_exception()
                Notification.notify_admins(
                    f'Bulk commit for PositionPoolPNL failed: {get_currency_codename(manager.wallet.currency)} '
                    f'pool is out of funds possibly',
                    title='📤 Bulk Commit Error',
                    channel='pool',
                )
                to_be_updated_positions = list(
                    filter(
                        lambda p: manager.wallet.currency != (p.src_currency if p.is_short else p.dst_currency),
                        to_be_updated_positions,
                    )
                )

        Position.objects.bulk_update(to_be_updated_positions, fields=['pnl_transaction'], batch_size=500)

        return len(pending_positions)
