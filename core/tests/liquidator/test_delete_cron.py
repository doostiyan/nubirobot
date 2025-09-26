from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import RIAL, TETHER, Currencies
from exchange.liquidator.crons import DeleteEmptyLiquidation
from exchange.liquidator.models import Liquidation, LiquidationRequest
from exchange.market.models import Market
from exchange.wallet.models import Wallet

AMOUNT = Decimal('1')
PRICE = Decimal('10')
IR_NOW = ir_now()


@patch('exchange.liquidator.crons.ir_now', lambda: IR_NOW)
class TestLiquidationRequestProcess(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pool_manager = User.objects.get(pk=410)
        cls.src_wallet = Wallet.get_user_wallet(cls.pool_manager, Currencies.btc)
        cls.dst_wallets = []
        for currency in (RIAL, TETHER):
            cls.dst_wallets.append(Wallet.get_user_wallet(cls.pool_manager, currency))

        cls.markets = {
            RIAL: Market.objects.get(src_currency=Currencies.btc, dst_currency=RIAL, is_active=True),
            TETHER: Market.objects.get(src_currency=Currencies.btc, dst_currency=TETHER, is_active=True),
        }
        cls.liquidation_requests = [
            LiquidationRequest(
                src_wallet=cls.src_wallet,
                dst_wallet=cls.dst_wallets[0],
                side=LiquidationRequest.SIDES.buy,
                status=LiquidationRequest.STATUS.in_progress,
                amount=AMOUNT,
            ),
            LiquidationRequest(
                src_wallet=cls.src_wallet,
                dst_wallet=cls.dst_wallets[0],
                side=LiquidationRequest.SIDES.sell,
                status=LiquidationRequest.STATUS.in_progress,
                amount=AMOUNT,
            ),
        ]
        LiquidationRequest.objects.bulk_create(cls.liquidation_requests)

    def tearDown(self):
        cache.clear()

    @staticmethod
    def _create_liquidation(
        request: LiquidationRequest,
        status: int,
        amount: Decimal,
        market_type: int,
        primary_price: Decimal,
    ):
        liquidation = Liquidation.objects.create(
            src_currency=request.src_currency,
            dst_currency=request.dst_currency,
            side=request.side,
            amount=amount,
            status=status,
            market_type=market_type,
            primary_price=primary_price,
        )
        liquidation.liquidation_requests.add(request)
        return liquidation

    @classmethod
    def create_liquidation(
        cls,
        request: LiquidationRequest,
        status: int,
        amount: Decimal = AMOUNT / 10,
        market_type: int = Liquidation.MARKET_TYPES.internal,
        primary_price: Decimal = PRICE,
        *,
        is_new: bool = False,
    ):
        if not is_new:
            with patch('django.utils.timezone.now', lambda: IR_NOW - timedelta(minutes=6)):
                return cls._create_liquidation(request, status, amount, market_type, primary_price)
        return cls._create_liquidation(request, status, amount, market_type, primary_price)

    def test_request_has_new_liquidations(self):
        self.create_liquidation(self.liquidation_requests[0], Liquidation.STATUS.new)
        self.create_liquidation(self.liquidation_requests[0], Liquidation.STATUS.new, is_new=True)

        self.create_liquidation(self.liquidation_requests[1], Liquidation.STATUS.new)
        self.create_liquidation(self.liquidation_requests[1], Liquidation.STATUS.new, is_new=True)

        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.in_progress).count() == 2
        assert Liquidation.objects.filter(status=Liquidation.STATUS.new).count() == 4
        DeleteEmptyLiquidation().run()
        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.in_progress).count() == 2
        assert Liquidation.objects.count() == 2
        assert Liquidation.objects.filter(status=Liquidation.STATUS.new).count() == 2

    def test_request_has_new_and_done_liquidations(self):
        self.create_liquidation(self.liquidation_requests[0], Liquidation.STATUS.new)
        self.create_liquidation(self.liquidation_requests[0], Liquidation.STATUS.done, is_new=True)

        self.create_liquidation(self.liquidation_requests[1], Liquidation.STATUS.new)
        self.create_liquidation(self.liquidation_requests[1], Liquidation.STATUS.new, is_new=True)

        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.in_progress).count() == 2
        assert Liquidation.objects.filter(status=Liquidation.STATUS.new).count() == 3
        assert Liquidation.objects.filter(status=Liquidation.STATUS.done).count() == 1
        DeleteEmptyLiquidation().run()
        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.in_progress).count() == 1
        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.pending).count() == 1
        assert Liquidation.objects.count() == 2
        assert Liquidation.objects.filter(status=Liquidation.STATUS.new).count() == 1

    def test_request_has_new_and_overstock_liquidations(self):
        self.create_liquidation(self.liquidation_requests[0], Liquidation.STATUS.new)
        self.create_liquidation(self.liquidation_requests[0], Liquidation.STATUS.overstock, is_new=True)

        self.create_liquidation(self.liquidation_requests[1], Liquidation.STATUS.new)
        self.create_liquidation(self.liquidation_requests[1], Liquidation.STATUS.overstock, is_new=True)
        self.create_liquidation(self.liquidation_requests[1], Liquidation.STATUS.new, is_new=True)

        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.in_progress).count() == 2
        assert Liquidation.objects.filter(status=Liquidation.STATUS.new).count() == 3
        assert Liquidation.objects.filter(status=Liquidation.STATUS.overstock).count() == 2
        DeleteEmptyLiquidation().run()
        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.in_progress).count() == 1
        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.pending).count() == 1
        assert Liquidation.objects.count() == 3
        assert Liquidation.objects.filter(status=Liquidation.STATUS.new).count() == 1

    def test_request_has_new_and_open_liquidations(self):
        self.create_liquidation(self.liquidation_requests[0], Liquidation.STATUS.new)
        self.create_liquidation(self.liquidation_requests[0], Liquidation.STATUS.open)

        self.create_liquidation(self.liquidation_requests[1], Liquidation.STATUS.new)
        self.create_liquidation(self.liquidation_requests[1], Liquidation.STATUS.open, is_new=True)

        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.in_progress).count() == 2
        assert Liquidation.objects.filter(status=Liquidation.STATUS.new).count() == 2
        assert Liquidation.objects.filter(status=Liquidation.STATUS.open).count() == 2
        DeleteEmptyLiquidation().run()
        assert LiquidationRequest.objects.filter(status=LiquidationRequest.STATUS.in_progress).count() == 2
        assert Liquidation.objects.count() == 2
