from decimal import Decimal
from typing import List

from django.core.management.base import BaseCommand
from django.db import transaction

from exchange.market.models import Order, OrderMatching
from exchange.wallet.models import Transaction


class Command(BaseCommand):
    """
    Examples:
        python manage.py reverse_trade --trade 1
        python manage.py reverse_trade --trade 1 --force
    """

    def add_arguments(self, parser):
        parser.add_argument('--trade', type=int)
        parser.add_argument(
            '--force', action='store_true', default=False, help='Reverse trade even if results in negative balance.'
        )

    def reverse_order(self, order: Order):
        order.status = Order.STATUS.canceled
        order.matched_amount = Decimal('0')
        order.matched_total_price = Decimal('0')
        if not order.fee:
            order.fee = Decimal('1')
        order.save()

    def reverse_transaction(self, t, *, is_force=False):
        t_reverse = t.wallet.create_transaction(
            tp='manual',
            amount=-t.amount,
            description='تراکنش اصلاحی برای برگردان معامله',
            allow_negative_balance=is_force,
        )
        if t_reverse is None:
            print(f'Not reverting transaction #{t.pk}')
            raise ValueError('Irreversible Trade')
        t_reverse.commit(ref=Transaction.Ref('ReverseTransaction', t.pk), allow_negative_balance=is_force)

    def reverse_fee_amounts(self, trade: OrderMatching, update_fields: List[str]):
        if trade.sell_fee is None and trade.sell_fee_amount:
            trade.sell_fee_amount = 0
            update_fields.append('sell_fee_amount')

        if trade.buy_fee is None and trade.buy_fee_amount:
            trade.buy_fee_amount = 0
            update_fields.append('buy_fee_amount')

    def handle(self, *args, **kwargs):
        is_force = kwargs['force']
        trade = OrderMatching.objects.get(id=kwargs['trade'])

        print(f'Reversing trade #{trade.pk}: {trade.matched_amount} @ {trade.matched_price}')
        print(f'  {trade.seller.email} => {trade.buyer.email}')

        if not trade.sell_withdraw or not trade.sell_deposit or not trade.buy_withdraw or not trade.buy_deposit:
            print('Trade has not completed transactions yet. They are probably still being processed. Try again later.')
            print(
                f'Transaction ids:\n'
                f'sell_withdraw:{trade.sell_withdraw}, sell_deposit: {trade.sell_deposit},'
                f'buy_withdraw: {trade.buy_withdraw}, buy_deposit:{trade.buy_deposit}',
            )
            return

        with transaction.atomic():
            update_fields = ['matched_amount']
            trade.matched_amount = Decimal('0')

            if trade.rial_value:
                trade.rial_value = Decimal('0')
                update_fields.append('rial_value')

            self.reverse_order(trade.sell_order)
            self.reverse_order(trade.buy_order)
            self.reverse_transaction(trade.sell_withdraw, is_force=is_force)
            self.reverse_transaction(trade.buy_withdraw, is_force=is_force)
            self.reverse_transaction(trade.sell_deposit, is_force=is_force)
            self.reverse_transaction(trade.buy_deposit, is_force=is_force)
            if trade.sell_fee:
                self.reverse_transaction(trade.sell_fee, is_force=is_force)
            if trade.buy_fee:
                self.reverse_transaction(trade.buy_fee, is_force=is_force)

            self.reverse_fee_amounts(trade, update_fields)
            trade.save(update_fields=update_fields)
