from django.core.management import call_command
from django.test import TestCase

from exchange.config.config.models import Currencies
from exchange.liquidator.models import Liquidation
from exchange.market.models import Order


class TestLiquidationRequestProcess(TestCase):
    def setUp(self):
        self.liquidation = Liquidation.objects.create(
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Order.ORDER_TYPES.sell,
            amount='0.0001',
            market_type=Liquidation.MARKET_TYPES.internal,
            primary_price='27100',
        )
        self.unrelated_liquidation = Liquidation.objects.create(
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Order.ORDER_TYPES.sell,
            amount='0.0001',
            market_type=Liquidation.MARKET_TYPES.internal,
            primary_price='27100',
        )

        self.orders = [
            Order.objects.create(
                user_id=201,
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                order_type=Order.ORDER_TYPES.sell,
                execution_type=Order.EXECUTION_TYPES.limit,
                trade_type=Order.TRADE_TYPES.spot,
                amount='0.0001',
                price='27100',
                status=Order.STATUS.active,
                client_order_id=f'!liquidation_{self.liquidation.id}',
            ),
            Order.objects.create(
                user_id=202,
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                order_type=Order.ORDER_TYPES.buy,
                execution_type=Order.EXECUTION_TYPES.limit,
                trade_type=Order.TRADE_TYPES.spot,
                amount='0.0001',
                price='27000',
                status=Order.STATUS.active,
                client_order_id=f'!liquidation_blah1218blah',
            ),
        ]

    def test_fill_liquidator_command(self):
        call_command('fill_liquidations_order_field')

        self.liquidation.refresh_from_db()
        self.unrelated_liquidation.refresh_from_db()

        assert self.liquidation.order is not None
        assert self.unrelated_liquidation.order is None
