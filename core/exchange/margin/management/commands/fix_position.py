from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.base.helpers import stage_changes
from exchange.margin.models import Position, PositionOrder
from exchange.margin.services import MarginManager
from exchange.pool.models import LiquidityPool
from exchange.wallet.models import Transaction


class Command(BaseCommand):
    """
    Examples:
        python manage.py fix_position 112 --detach-order 3245
    """
    help = 'Fix position pnl calculations.'

    def add_arguments(self, parser):
        parser.add_argument('pid', type=int, help='Position id to fix')
        parser.add_argument('--detach-order', type=int, help='Order id to detach')
        parser.add_argument('--cancel', action='store_true', default=False, help='Cancel Position')

    def handle(self, pid, detach_order, cancel, **options):
        with transaction.atomic():
            position = Position.objects.select_for_update().get(id=pid)
            self.reset_pnl(position)
            if detach_order:
                position_order = PositionOrder.objects.get(position_id=pid, order_id=detach_order)
                position_order.delete()
                MarginManager.update_position_on_order_change(position_order)
                position.refresh_from_db()
            elif cancel:
                self.cancel_new(position)
            self.fix_pnl(position)

    @staticmethod
    def reset_pnl(position):
        if position.pnl is None:
            return

        position.pnl = None
        position.save(update_fields=('pnl',))

        margin_wallet = position.pnl_transaction.wallet
        margin_wallet.balance_blocked += position.collateral
        margin_wallet.save(update_fields=('balance_blocked',))

    @staticmethod
    def fix_pnl(position):
        if not position.pnl_transaction:
            return

        description = f'تراکنش اصلاحی برای برگردان سودوزیان موقعیت تعهدی #{position.id}'
        user_reverse = position.pnl_transaction.wallet.create_transaction(
            tp='manual', amount=position.pnl - position.pnl_transaction.amount, description=description
        )

        pool_wallet = LiquidityPool.objects.get(currency=position.src_currency).get_dst_wallet(position.dst_currency)
        pool_reverse = pool_wallet.create_transaction(tp='manual', amount=position.pnl, description=description)

        if not all((user_reverse, pool_reverse)):
            raise ValueError('Irreversible Trade')

        user_reverse.commit(ref=Transaction.Ref('ReverseTransaction', position.pnl_transaction.pk))
        pool_reverse.commit()

    @staticmethod
    def cancel_new(position):
        if position.status == Position.STATUS.new and len(position.cached_orders) == 0:
            with stage_changes(position, update_fields=('status', 'pnl', 'pnl_transaction')):
                position.set_status()
                position.set_pnl()
