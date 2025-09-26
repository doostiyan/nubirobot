from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.liquidator.models import Liquidation, LiquidationRequest, LiquidationRequestLiquidationAssociation
from exchange.wallet.models import Wallet


@patch('exchange.liquidator.services.liquidation_creator.LIQUIDATOR_EXTERNAL_CURRENCIES', {Currencies.btc})
class TestLiquidationAssociationFillCommand(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pool_manager = User.objects.get(pk=410)
        cls.pool_btc_wallet = Wallet.get_user_wallet(cls.pool_manager, Currencies.btc)
        cls.pool_usdt_wallet = Wallet.get_user_wallet(cls.pool_manager, Currencies.usdt)

    def setUp(self):
        cache.clear()

        self.liquidation_request = LiquidationRequest.objects.create(
            src_wallet=self.pool_btc_wallet,
            dst_wallet=self.pool_usdt_wallet,
            side=LiquidationRequest.SIDES.sell,
            status=LiquidationRequest.STATUS.in_progress,
            amount=Decimal('1'),
        )

        self.liquidation = Liquidation.objects.create(
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Liquidation.SIDES.sell,
            amount=Decimal('0.5'),
            primary_price=Decimal('10'),
            status=Liquidation.STATUS.ready_to_share,
            market_type=Liquidation.MARKET_TYPES.external,
            filled_amount=Decimal('0.5'),
            filled_total_price=Decimal('5'),
        )
        self.liquidation2 = Liquidation.objects.create(
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Liquidation.SIDES.sell,
            amount=Decimal('0.5'),
            primary_price=Decimal('10'),
            status=Liquidation.STATUS.ready_to_share,
            market_type=Liquidation.MARKET_TYPES.external,
            filled_amount=Decimal('0.5'),
            filled_total_price=Decimal('5'),
        )
        self.association = LiquidationRequestLiquidationAssociation.objects.create(
            liquidation_request=self.liquidation_request,
            liquidation=self.liquidation,
        )
        self.association2 = LiquidationRequestLiquidationAssociation.objects.create(
            liquidation_request=self.liquidation_request,
            liquidation=self.liquidation2,
        )

    def tearDown(self) -> None:
        cache.clear()

    def test_associations_filled_correctly(self):
        call_command('fill_liquidation_association')

        self.association.refresh_from_db()
        self.association2.refresh_from_db()

        assert self.association.amount == self.liquidation.paid_amount
        assert self.association.total_price == self.liquidation.paid_total_price
        assert self.association2.amount == self.liquidation2.paid_amount
        assert self.association2.total_price == self.liquidation2.paid_total_price
