from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.liquidator.models import Liquidation, LiquidationRequest
from exchange.liquidator.tasks import task_update_liquidation_request
from exchange.wallet.models import Wallet


@patch('exchange.liquidator.services.liquidation_creator.LIQUIDATOR_EXTERNAL_CURRENCIES', {Currencies.btc})
class TestLiquidationAssociationUpdate(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pool_manager = User.objects.get(pk=410)
        cls.pool_btc_wallet = Wallet.get_user_wallet(cls.pool_manager, Currencies.btc)
        cls.pool_usdt_wallet = Wallet.get_user_wallet(cls.pool_manager, Currencies.usdt)

    def setUp(self):
        cache.clear()

        self.liquidation_requests = [
            LiquidationRequest.objects.create(
                src_wallet=self.pool_btc_wallet,
                dst_wallet=self.pool_usdt_wallet,
                side=LiquidationRequest.SIDES.sell,
                status=LiquidationRequest.STATUS.in_progress,
                amount=Decimal('1'),
            ),
            LiquidationRequest.objects.create(
                src_wallet=self.pool_btc_wallet,
                dst_wallet=self.pool_usdt_wallet,
                side=LiquidationRequest.SIDES.buy,
                status=LiquidationRequest.STATUS.in_progress,
                amount=Decimal('2'),
            ),
        ]

        self.liquidations = [
            Liquidation.objects.create(
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Liquidation.SIDES.sell,
                amount=Decimal('0.5'),
                primary_price=Decimal('10'),
                status=Liquidation.STATUS.ready_to_share,
                market_type=Liquidation.MARKET_TYPES.external,
                filled_amount=Decimal('0.5'),
                filled_total_price=Decimal('5'),
            ),
            Liquidation.objects.create(
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Liquidation.SIDES.sell,
                amount=Decimal('0.5'),
                primary_price=Decimal('10'),
                status=Liquidation.STATUS.ready_to_share,
                market_type=Liquidation.MARKET_TYPES.external,
                filled_amount=Decimal('0.5'),
                filled_total_price=Decimal('5'),
            ),
            Liquidation.objects.create(
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Liquidation.SIDES.buy,
                amount=Decimal('1'),
                primary_price=Decimal('10'),
                status=Liquidation.STATUS.ready_to_share,
                market_type=Liquidation.MARKET_TYPES.external,
                filled_amount=Decimal('1'),
                filled_total_price=Decimal('10'),
            ),
            Liquidation.objects.create(
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Liquidation.SIDES.buy,
                amount=Decimal('1'),
                primary_price=Decimal('10'),
                status=Liquidation.STATUS.ready_to_share,
                market_type=Liquidation.MARKET_TYPES.external,
                filled_amount=Decimal('1'),
                filled_total_price=Decimal('10'),
            ),
        ]
        self.liquidations[0].liquidation_requests.add(self.liquidation_requests[0])
        self.liquidations[1].liquidation_requests.add(self.liquidation_requests[0])
        self.liquidations[2].liquidation_requests.add(self.liquidation_requests[1])
        self.liquidations[3].liquidation_requests.add(self.liquidation_requests[1])

        self._charge_wallet(self.pool_btc_wallet, Decimal('3'))
        self._charge_wallet(self.pool_usdt_wallet, Decimal('100'))

    def tearDown(self) -> None:
        cache.clear()

    @staticmethod
    def _charge_wallet(wallet: Wallet, final_balance: Decimal):
        balance = wallet.balance
        wallet.create_transaction('manual', (final_balance - balance)).commit()

    def test_associations_filled_correctly(self):
        task_update_liquidation_request()

        for instance in self.liquidation_requests + self.liquidations:
            instance.refresh_from_db()

        for association in self.liquidation_requests[0].liquidation_associations.all():
            assert association.amount == Decimal('0.5')
            assert association.total_price == Decimal('5')

        for association in self.liquidation_requests[1].liquidation_associations.all():
            assert association.amount == Decimal('1')
            assert association.total_price == Decimal('10')
