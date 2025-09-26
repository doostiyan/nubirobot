import datetime
from decimal import ROUND_UP, Decimal
from unittest.mock import patch

import pytest
import responses
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework import status

from exchange.accounts.models import Notification, UserSms
from exchange.accounts.userstats import UserStatsManager
from exchange.asset_backed_credit.exceptions import CannotEstimateSrcAmount
from exchange.asset_backed_credit.externals.liquidation import LiquidationProvider
from exchange.asset_backed_credit.externals.price import PriceProvider
from exchange.asset_backed_credit.externals.wallet import WalletListAPI
from exchange.asset_backed_credit.models import Service, SettlementTransaction, Wallet
from exchange.asset_backed_credit.services.liquidation import liquidate_margin_call, liquidate_settlement
from exchange.asset_backed_credit.services.margin_call import send_liquidation_notification
from exchange.asset_backed_credit.services.price import PricingService
from exchange.asset_backed_credit.services.wallet.wallet import WalletService
from exchange.base.calendar import ir_now
from exchange.base.models import AMOUNT_PRECISIONS_V2, RIAL, Currencies, Settings
from exchange.market.models import Order
from exchange.wallet.models import Wallet as ExternalWallet
from tests.asset_backed_credit.helper import ABCMixins

USDT_PRICE = Decimal(1_000_0)
BTC_PRICE = Decimal(1_000_000_0)
ETH_PRICE = Decimal(2_000_0)


def mock_get_mark_price(src_currency: int, _):
    if src_currency == RIAL:
        return Decimal(1)
    elif src_currency == Currencies.usdt:
        return USDT_PRICE + 20
    elif src_currency == Currencies.btc:
        return BTC_PRICE + 2000_0
    elif src_currency == Currencies.eth:
        return ETH_PRICE + 20_0
    return None


def mock_get_last_trade_price(self):
    if self.src_currency == RIAL:
        return Decimal(1)
    elif self.src_currency == Currencies.usdt:
        return USDT_PRICE
    elif self.src_currency == Currencies.btc:
        return BTC_PRICE
    elif self.src_currency == Currencies.eth:
        return ETH_PRICE
    return None


def mock_get_price_range(src_currency: int, dst_currency: int):
    if src_currency == RIAL:
        return Decimal(1), Decimal(1)
    elif src_currency == Currencies.usdt:
        return USDT_PRICE, USDT_PRICE
    elif src_currency == Currencies.btc:
        return BTC_PRICE, BTC_PRICE
    elif src_currency == Currencies.eth:
        return ETH_PRICE
    return None


def mock_get_price_range_bad_shadow(src_currency: int, dst_currency: int):
    if src_currency == RIAL:
        return Decimal(1), Decimal(1)
    elif src_currency == Currencies.usdt:
        return USDT_PRICE - 200_0, USDT_PRICE - 200_0
    elif src_currency == Currencies.btc:
        return BTC_PRICE - 100_000_0, BTC_PRICE - 100_000_0
    elif src_currency == Currencies.eth:
        return ETH_PRICE - 300_0, ETH_PRICE - 300_0
    return None


class TestLiquidationProvider(ABCMixins, TestCase):
    def setUp(self):
        self.user = self.create_user()

    def test_liquidate_success(self):
        self.charge_exchange_wallet(self.user, Currencies.btc, 2)
        orders = LiquidationProvider()._liquidate(
            self.user, Currencies.btc, Decimal('1.234567'), Decimal('1000.123456'), Wallet.WalletType.COLLATERAL
        )

        assert len(orders) == 1
        order = orders[0]
        assert order.status == Order.STATUS.active
        assert order.user == self.user
        assert order.is_credit
        assert order.price == Decimal('1000')  # Because of rounding
        assert order.amount == Decimal('1.234567')
        assert order.total_price == Decimal('1000') * Decimal('1.234567')

    def test_liquidate_debit_success(self):
        self.charge_exchange_wallet(self.user, Currencies.btc, 2, tp=ExternalWallet.WALLET_TYPE.debit)
        orders = LiquidationProvider()._liquidate(
            self.user, Currencies.btc, Decimal('1.234567'), Decimal('1000.123456'), Wallet.WalletType.DEBIT
        )

        assert len(orders) == 1
        order = orders[0]
        assert order.status == Order.STATUS.active
        assert order.user == self.user
        assert order.is_debit
        assert order.price == Decimal('1000')  # Because of rounding
        assert order.amount == Decimal('1.234567')
        assert order.total_price == Decimal('1000') * Decimal('1.234567')

    def test_liquidate_success_large_amount(self):
        self.charge_exchange_wallet(self.user, Currencies.btc, 20)
        orders = LiquidationProvider()._liquidate(
            self.user, Currencies.btc, Decimal('20'), Decimal(1_000_000_000_0), Wallet.WalletType.COLLATERAL
        )

        assert len(orders) == 21
        for order in orders[:20]:
            assert order.price == Decimal('1_000_000_000_0')
            assert order.amount == Decimal('0.999999')
            assert order.total_price == Decimal('1_000_000_000_0') * Decimal('0.999999')

        assert orders[20].price == Decimal('1_000_000_000_0')
        assert orders[20].amount == 20 - 20 * Decimal('0.999999')
        assert orders[20].total_price == Decimal('1_000_000_000_0') * (20 - 20 * Decimal('0.999999'))


class TestLiquidateSettlement(ABCMixins, TestCase):
    def setUp(self) -> None:
        self.settlement = self.create_settlement(1_106_000_0)
        self.user = self.settlement.user_service.user

    @patch.object(PriceProvider, 'get_last_trade_price', mock_get_last_trade_price)
    def test_liquidate_settlement_success(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal(100))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal(1))
        self.charge_exchange_wallet(self.user, Currencies.eth, Decimal(25))

        tolerance = Decimal('0.03')
        liquidate_settlement(settlement_id=self.settlement.id, tolerance=tolerance)

        self.settlement.refresh_from_db()
        assert self.settlement.orders.count() == 3
        usdt_order = self.settlement.orders.get(src_currency=Currencies.usdt)
        assert usdt_order.amount == Decimal(100)
        assert usdt_order.price == USDT_PRICE * (1 - tolerance)

        trade_fee = UserStatsManager.get_user_fee(self.user, is_maker=True)
        btc_order = self.settlement.orders.get(src_currency=Currencies.btc)
        remaining_amount = (self.settlement.amount - usdt_order.total_price / (1 + trade_fee)).quantize(
            AMOUNT_PRECISIONS_V2[RIAL], ROUND_UP
        )
        assert btc_order.amount == Decimal(1)
        assert btc_order.price == BTC_PRICE * (1 - tolerance)

        eth_order = self.settlement.orders.get(src_currency=Currencies.eth)
        remaining_amount = (remaining_amount - btc_order.total_price / (1 + trade_fee)).quantize(
            AMOUNT_PRECISIONS_V2[RIAL], ROUND_UP
        )
        assert eth_order.amount == (
            (remaining_amount / ETH_PRICE / (1 - tolerance) * (1 + trade_fee)).quantize(
                AMOUNT_PRECISIONS_V2[Currencies.btc], ROUND_UP
            )
        )
        assert self.settlement.liquidation_retry == 1

    @patch.object(PriceProvider, 'get_last_trade_price', mock_get_last_trade_price)
    def test_liquidate_debit_settlement_success(self):
        Settings.set('abc_debit_wallet_enabled', 'yes')

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal(100), tp=ExternalWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal(1), tp=ExternalWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.eth, Decimal(25), tp=ExternalWallet.WALLET_TYPE.debit)

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        user_service = self.create_user_service(self.user, service)
        self.settlement.user_service = user_service
        self.settlement.save(update_fields=['user_service'])

        tolerance = Decimal('0.03')
        liquidate_settlement(settlement_id=self.settlement.id, tolerance=tolerance)

        self.settlement.refresh_from_db()
        assert self.settlement.orders.count() == 3
        usdt_order = self.settlement.orders.get(src_currency=Currencies.usdt)
        assert usdt_order.amount == Decimal(100)
        assert usdt_order.price == USDT_PRICE * (1 - tolerance)

        trade_fee = UserStatsManager.get_user_fee(self.user, is_maker=True)
        btc_order = self.settlement.orders.get(src_currency=Currencies.btc)
        remaining_amount = (self.settlement.amount - usdt_order.total_price / (1 + trade_fee)).quantize(
            AMOUNT_PRECISIONS_V2[RIAL], ROUND_UP
        )
        assert btc_order.amount == Decimal(1)
        assert btc_order.price == BTC_PRICE * (1 - tolerance)

        eth_order = self.settlement.orders.get(src_currency=Currencies.eth)
        remaining_amount = (remaining_amount - btc_order.total_price / (1 + trade_fee)).quantize(
            AMOUNT_PRECISIONS_V2[RIAL], ROUND_UP
        )
        assert eth_order.amount == (
            (remaining_amount / ETH_PRICE / (1 - tolerance) * (1 + trade_fee)).quantize(
                AMOUNT_PRECISIONS_V2[Currencies.btc], ROUND_UP
            )
        )

    @patch.object(PriceProvider, 'get_last_trade_price', mock_get_last_trade_price)
    def test_liquidate_debit_settlement_on_credit_wallet_success(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal(100), tp=ExternalWallet.WALLET_TYPE.credit)
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal(1), tp=ExternalWallet.WALLET_TYPE.credit)
        self.charge_exchange_wallet(self.user, Currencies.eth, Decimal(25), tp=ExternalWallet.WALLET_TYPE.credit)

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        user_service = self.create_user_service(self.user, service)
        self.settlement.user_service = user_service
        self.settlement.save(update_fields=['user_service'])

        tolerance = Decimal('0.03')
        liquidate_settlement(settlement_id=self.settlement.id, tolerance=tolerance)

        self.settlement.refresh_from_db()
        assert self.settlement.orders.count() == 3
        usdt_order = self.settlement.orders.get(src_currency=Currencies.usdt)
        assert usdt_order.amount == Decimal(100)
        assert usdt_order.price == USDT_PRICE * (1 - tolerance)

        trade_fee = UserStatsManager.get_user_fee(self.user, is_maker=True)
        btc_order = self.settlement.orders.get(src_currency=Currencies.btc)
        remaining_amount = (self.settlement.amount - usdt_order.total_price / (1 + trade_fee)).quantize(
            AMOUNT_PRECISIONS_V2[RIAL], ROUND_UP
        )
        assert btc_order.amount == Decimal(1)
        assert btc_order.price == BTC_PRICE * (1 - tolerance)

        eth_order = self.settlement.orders.get(src_currency=Currencies.eth)
        remaining_amount = (remaining_amount - btc_order.total_price / (1 + trade_fee)).quantize(
            AMOUNT_PRECISIONS_V2[RIAL], ROUND_UP
        )
        assert eth_order.amount == (
            (remaining_amount / ETH_PRICE / (1 - tolerance) * (1 + trade_fee)).quantize(
                AMOUNT_PRECISIONS_V2[Currencies.btc], ROUND_UP
            )
        )

    @patch.object(PriceProvider, 'get_last_trade_price', mock_get_last_trade_price)
    def test_liquidate_settlement_partial_filled_multiple_retry_success(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal(100))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal(1))
        self.charge_exchange_wallet(self.user, Currencies.eth, Decimal(25))

        tolerance = Decimal('0.03')
        liquidate_settlement(
            settlement_id=self.settlement.id, tolerance=tolerance, wait_before_retry=datetime.timedelta(minutes=2)
        )

        self.settlement.refresh_from_db()
        assert self.settlement.orders.count() == 3
        usdt_order = self.settlement.orders.get(src_currency=Currencies.usdt)
        assert usdt_order.amount == Decimal(100)
        assert usdt_order.price == USDT_PRICE * (1 - tolerance)

        trade_fee = UserStatsManager.get_user_fee(self.user, is_maker=True)
        btc_order = self.settlement.orders.get(src_currency=Currencies.btc)
        remaining_amount = (self.settlement.amount - usdt_order.total_price / (1 + trade_fee)).quantize(
            AMOUNT_PRECISIONS_V2[RIAL], ROUND_UP
        )
        assert btc_order.amount == Decimal(1)
        assert btc_order.price == BTC_PRICE * (1 - tolerance)

        eth_order = self.settlement.orders.get(src_currency=Currencies.eth)
        remaining_amount = (remaining_amount - btc_order.total_price / (1 + trade_fee)).quantize(
            AMOUNT_PRECISIONS_V2[RIAL], ROUND_UP
        )
        assert eth_order.amount == (
            (remaining_amount / ETH_PRICE / (1 - tolerance) * (1 + trade_fee)).quantize(
                AMOUNT_PRECISIONS_V2[Currencies.btc], ROUND_UP
            )
        )

        assert self.settlement.liquidation_retry == 1

        self.settlement.liquidation_run_at = ir_now() - datetime.timedelta(minutes=1)
        self.settlement.save(update_fields=('liquidation_run_at',))

        # next attempt to liquidate
        liquidate_settlement(
            settlement_id=self.settlement.id, tolerance=tolerance, wait_before_retry=datetime.timedelta(minutes=2)
        )

        self.settlement.refresh_from_db()
        assert self.settlement.orders.count() == 3

        assert self.settlement.liquidation_retry == 1

        self.settlement.liquidation_run_at = ir_now() - datetime.timedelta(minutes=2)
        self.settlement.save(update_fields=('liquidation_run_at',))

        self.settlement.cancel_active_orders()

        # next attempt to liquidate
        liquidate_settlement(
            settlement_id=self.settlement.id, tolerance=tolerance, wait_before_retry=datetime.timedelta(minutes=2)
        )

        self.settlement.refresh_from_db()
        assert self.settlement.orders.count() == 6

        assert self.settlement.liquidation_retry == 2

        # next attempt to liquidate
        liquidate_settlement(settlement_id=self.settlement.id, tolerance=tolerance)

        self.settlement.refresh_from_db()
        assert self.settlement.orders.count() == 9

        assert self.settlement.liquidation_retry == 3

    @patch.object(PriceProvider, 'get_last_trade_price', mock_get_last_trade_price)
    def test_liquidate_settlement_when_orders_matched_total_price_is_enough_skip_liquidation(self):
        order_1 = self.create_order(
            self.user, net_matched_total_price=self.settlement.amount - Decimal(10000), src_currency=Currencies.usdt
        )
        self.settlement.orders.add(order_1)
        order_2 = self.create_order(
            self.user, net_matched_total_price=Decimal(5000), src_currency=Currencies.usdt, status=Order.STATUS.canceled
        )
        self.settlement.orders.add(order_2)
        order_3 = self.create_order(
            self.user, net_matched_total_price=Decimal(5000), src_currency=Currencies.usdt, status=Order.STATUS.new
        )
        self.settlement.orders.add(order_3)
        buyer = self.create_user()
        self.create_order_matching(seller=self.user, buyer=buyer, sell_order=order_1)
        self.create_order_matching(seller=self.user, buyer=buyer, sell_order=order_2)
        self.create_order_matching(seller=self.user, buyer=buyer, sell_order=order_3)

        liquidate_settlement(settlement_id=self.settlement.id)

        self.settlement.refresh_from_db()
        assert self.settlement.orders.count() == 3

    @patch.object(PriceProvider, 'get_last_trade_price', mock_get_last_trade_price)
    def test_liquidate_settlement_when_active_order_exists_skip_liquidation(self):
        self.settlement.orders.add(
            self.create_order(
                self.user, self.settlement.amount - Decimal(1000), Currencies.usdt, status=Order.STATUS.active
            )
        )
        liquidate_settlement(settlement_id=self.settlement.id)

        self.settlement.refresh_from_db()
        assert self.settlement.orders.count() == 1

    @patch.object(PriceProvider, 'get_last_trade_price', lambda _: None)
    def test_liquidate_settlement_cannot_estimate(self):
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('1.23'))

        with pytest.raises(CannotEstimateSrcAmount):
            liquidate_settlement(settlement_id=self.settlement.id)

        self.settlement.refresh_from_db()
        assert self.settlement.orders.count() == 0

    @patch.object(PriceProvider, 'get_last_trade_price', mock_get_last_trade_price)
    def test_liquidate_settlement_not_confirmed(self):
        self.settlement.status = SettlementTransaction.STATUS.initiated
        self.settlement.save(update_fields=['status'])
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal(100))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal(1))

        tolerance = Decimal('0.03')
        liquidate_settlement(settlement_id=self.settlement.id, tolerance=tolerance)

        self.settlement.refresh_from_db()
        assert self.settlement.orders.count() == 0

    @patch.object(PriceProvider, 'get_last_trade_price', mock_get_last_trade_price)
    def test_liquidate_settlement_user_has_active_liquidation_order(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal(100))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal(1))
        order = self.create_order(
            self.user,
            net_matched_total_price=self.settlement.amount - Decimal(10000),
            src_currency=Currencies.usdt,
            status=Order.STATUS.active,
        )
        self.create_margin_call(
            total_debt=Decimal(10000),
            total_assets=Decimal(2000),
            user=self.settlement.user_service.user,
            orders=[order],
        )

        tolerance = Decimal('0.03')
        liquidate_settlement(settlement_id=self.settlement.id, tolerance=tolerance)

        self.settlement.refresh_from_db()
        assert self.settlement.orders.count() == 0

    @responses.activate
    @patch.object(PriceProvider, 'get_last_trade_price', mock_get_last_trade_price)
    @patch('exchange.asset_backed_credit.externals.liquidation.LiquidationProvider._liquidate')
    def test_liquidate_settlement_success_when_wallet_internal_api_is_enabled(self, mock_liquidate):
        mock_liquidate.return_value = [
            self.create_order(self.user, Decimal(100), Currencies.usdt, Order.STATUS.active),
            self.create_order(self.user, Decimal(1), Currencies.btc, Order.STATUS.active),
            self.create_order(self.user, Decimal(25), Currencies.eth, Order.STATUS.active)
        ]
        Settings.set('abc_use_wallet_list_internal_api', 'yes')
        responses.post(
            url=WalletListAPI.url,
            json={str(self.user.uid): [
                {
                    "activeBalance": "1",
                    "balance": "1",
                    "blockedBalance": "0",
                    "currency": "btc",
                    "type": "credit",
                    "userId": str(self.user.uid)
                },
                {
                    "activeBalance": "100",
                    "balance": "100",
                    "blockedBalance": "0",
                    "currency": "usdt",
                    "type": "credit",
                    "userId": str(self.user.uid)
                },
                {
                    "activeBalance": "25",
                    "balance": "25",
                    "blockedBalance": "0",
                    "currency": "eth",
                    "type": "credit",
                    "userId": str(self.user.uid)
                },
            ]
            },
            status=status.HTTP_200_OK,
        )

        liquidate_settlement(settlement_id=self.settlement.id, tolerance=Decimal('0.03'))

        self.settlement.refresh_from_db()
        assert self.settlement.orders.count() == 3

    @responses.activate
    @patch.object(PriceProvider, 'get_last_trade_price', mock_get_last_trade_price)
    @patch('exchange.asset_backed_credit.externals.liquidation.LiquidationProvider._liquidate')
    def test_liquidate_settlement_success_when_wallet_internal_api_is_enabled_and_cached_recently(self, mock_liquidate):
        mock_liquidate.return_value = [
            self.create_order(self.user, Decimal(100), Currencies.usdt, Order.STATUS.active),
            self.create_order(self.user, Decimal(1), Currencies.btc, Order.STATUS.active),
            self.create_order(self.user, Decimal(25), Currencies.eth, Order.STATUS.active),
        ]
        Settings.set('abc_use_wallet_list_internal_api', 'yes')
        responses.post(
            url=WalletListAPI.url,
            json={
                str(self.user.uid): [
                    {
                        'activeBalance': '1',
                        'balance': '1',
                        'blockedBalance': '0',
                        'currency': 'btc',
                        'type': 'credit',
                        'userId': str(self.user.uid),
                    },
                    {
                        'activeBalance': '100',
                        'balance': '100',
                        'blockedBalance': '0',
                        'currency': 'usdt',
                        'type': 'credit',
                        'userId': str(self.user.uid),
                    },
                    {
                        'activeBalance': '25',
                        'balance': '25',
                        'blockedBalance': '0',
                        'currency': 'eth',
                        'type': 'credit',
                        'userId': str(self.user.uid),
                    },
                ]
            },
            status=status.HTTP_200_OK,
        )

        # Cache wallets
        WalletService.get_user_wallets(
            user_id=self.user.uid, exchange_user_id=self.user.id, wallet_type=Wallet.WalletType.COLLATERAL
        )

        with patch.object(WalletListAPI, 'request') as mock_request:
            liquidate_settlement(settlement_id=self.settlement.id, tolerance=Decimal('0.03'))

            mock_request.assert_not_called()

        self.settlement.refresh_from_db()
        assert self.settlement.orders.count() == 3


@patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', mock_get_mark_price)
@patch.object(PriceProvider, 'get_last_trade_price', mock_get_last_trade_price)
@patch('exchange.wallet.estimator.PriceEstimator.get_price_range', mock_get_price_range)
class TestLiquidationUseCase(ABCMixins, TestCase):
    def setUp(self) -> None:
        self.margin_call = self.create_margin_call(total_assets=Decimal(100_000_0), total_debt=Decimal(90_000_0))
        self.user = self.margin_call.user
        self.usdt_price = Decimal(50_000_0)
        self.usdt_price = Decimal(40_000_000_0)

    def test_liquidate_margin_call_success(self):
        tolerance = Decimal('0.03')

        self.create_user_service(self.margin_call.user, initial_debt=23300000)

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('1.23'))

        liquidate_margin_call(margin_call_id=self.margin_call.id)

        self.margin_call.refresh_from_db()
        assert self.margin_call.orders.count() == 2

        usdt_order = self.margin_call.orders.get(src_currency=Currencies.usdt)
        assert usdt_order.amount == Decimal(100)
        assert usdt_order.price == USDT_PRICE * (1 - tolerance)

        btc_order = self.margin_call.orders.get(src_currency=Currencies.btc)
        assert btc_order.amount == Decimal('1.23')
        assert btc_order.price == BTC_PRICE * (1 - tolerance)

    def test_liquidate_margin_call_weighted_avg_above_threshold_do_nothing(self):
        with patch('exchange.wallet.estimator.PriceEstimator.get_price_range', mock_get_price_range_bad_shadow):
            self.create_user_service(self.margin_call.user, initial_debt=13300000)

            self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
            self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('1.23'))

            liquidate_margin_call(margin_call_id=self.margin_call.id)

            self.margin_call.refresh_from_db()
            assert self.margin_call.orders.count() == 0

            pricing_service = PricingService(self.margin_call.user)
            assert pricing_service.get_total_assets().weighted_avg > 0.04

    def test_liquidate_margin_call_cancel_orders(self):
        user_service = self.create_user_service(self.margin_call.user, initial_debt=1000000)
        settlement = self.create_settlement(Decimal(1_000_000_0), user_service=user_service)
        settlement.orders.add(self.create_order(self.user, settlement.amount, Currencies.usdt, Order.STATUS.active))
        settlement.orders.add(self.create_order(self.user, settlement.amount, Currencies.usdt, Order.STATUS.new))
        settlement.orders.add(self.create_order(self.user, settlement.amount, Currencies.usdt, Order.STATUS.inactive))
        settlement.orders.add(self.create_order(self.user, settlement.amount, Currencies.usdt, Order.STATUS.done))
        settlement.orders.add(self.create_order(self.user, settlement.amount, Currencies.usdt, Order.STATUS.canceled))

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))

        self.margin_call.orders.add(
            self.create_order(self.user, settlement.amount, Currencies.usdt, Order.STATUS.active)
        )
        self.margin_call.orders.add(self.create_order(self.user, settlement.amount, Currencies.usdt, Order.STATUS.new))
        self.margin_call.orders.add(
            self.create_order(self.user, settlement.amount, Currencies.usdt, Order.STATUS.inactive)
        )
        self.margin_call.orders.add(self.create_order(self.user, settlement.amount, Currencies.usdt, Order.STATUS.done))
        self.margin_call.orders.add(
            self.create_order(self.user, settlement.amount, Currencies.usdt, Order.STATUS.canceled)
        )

        assert self.margin_call.orders.filter(status__in=[Order.STATUS.done, Order.STATUS.canceled]).count() == 2
        assert (
            self.margin_call.orders.filter(
                status__in=Order.OPEN_STATUSES,
            ).count()
            == 3
        )

        assert settlement.orders.filter(status__in=[Order.STATUS.done, Order.STATUS.canceled]).count() == 2
        assert (
            settlement.orders.filter(
                status__in=Order.OPEN_STATUSES,
            ).count()
            == 3
        )

        liquidate_margin_call(margin_call_id=self.margin_call.id)

        assert self.margin_call.orders.filter(status=Order.STATUS.done).count() == 1
        assert self.margin_call.orders.filter(status=Order.STATUS.canceled).count() == 4
        assert (
            self.margin_call.orders.filter(
                status__in=Order.OPEN_STATUSES,
            ).count()
            == 1
        )

        settlement.refresh_from_db()
        assert settlement.orders.filter(status=Order.STATUS.done).count() == 1
        assert settlement.orders.filter(status=Order.STATUS.canceled).count() == 4
        assert (
            settlement.orders.filter(
                status__in=Order.OPEN_STATUSES,
            ).count()
            == 0
        )

    def test_liquidate_margin_call_notif(self):
        self.create_user_service(self.margin_call.user, initial_debt=13300000)

        self.margin_call.is_margin_call_sent = True
        self.margin_call.save(update_fields=['is_margin_call_sent'])

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('1.23'))

        liquidate_margin_call(margin_call_id=self.margin_call.id)

        self.margin_call.refresh_from_db()

        send_liquidation_notification(self.margin_call.id)

        assert self.margin_call.orders.count() == 2

        notif = Notification.objects.filter(
            user=self.user, message='وثیقه شما در سرویس اعتبار ریالی نوبیتکس تبدیل شد.'
        ).first()
        assert notif

        sms = UserSms.objects.filter(
            user=self.user, tp=UserSms.TYPES.abc_margin_call_liquidate, to=self.user.mobile
        ).first()
        assert sms
        assert sms.text == 'اعتبار ریالی'
        assert sms.template == UserSms.TEMPLATES.abc_margin_call_liquidate

    def test_liquidate_margin_call_notif_when_already_sent(self):
        self.margin_call.is_liquidation_notif_sent = True
        self.margin_call.save(update_fields=['is_liquidation_notif_sent'])

        liquidate_margin_call(margin_call_id=self.margin_call.id)

        send_liquidation_notification(self.margin_call.id)

        notif = Notification.objects.filter(
            user=self.user, message='وثیقه شما در سرویس اعتبار ریالی نوبیتکس تبدیل شد.'
        ).first()
        assert notif is None

        sms = UserSms.objects.filter(
            user=self.user, tp=UserSms.TYPES.abc_margin_call_liquidate, to=self.user.mobile
        ).first()
        assert sms is None

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_liquidate_margin_call_email(self):
        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('update_email_templates')
        vp = self.user.get_verification_profile()
        vp.email_confirmed = True
        vp.save()

        self.create_user_service(self.margin_call.user, initial_debt=13300000)

        self.margin_call.is_margin_call_sent = True
        self.margin_call.save(update_fields=['is_margin_call_sent'])

        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        self.charge_exchange_wallet(self.user, Currencies.btc, Decimal('1.23'))

        liquidate_margin_call(margin_call_id=self.margin_call.id)

        self.margin_call.refresh_from_db()
        self.margin_call.send_liquidation_notifications()

        assert self.margin_call.orders.count() == 2

        with patch('django.db.connection.close'):
            call_command('send_queued_mail')

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.liquidation.LiquidationProvider._liquidate')
    def test_liquidate_margin_call_success_when_wallet_internal_api_is_enabled(self, mock_liquidate):
        mock_liquidate.return_value = [
            self.create_order(self.user, Decimal("100"), Currencies.usdt, Order.STATUS.active),
            self.create_order(self.user, Decimal("1.23"), Currencies.btc, Order.STATUS.active)
        ]

        self.create_user_service(self.margin_call.user, initial_debt=13300000)

        Settings.set('abc_use_wallet_list_internal_api', 'yes')
        responses.post(
            url=WalletListAPI.url,
            json={str(self.user.uid): [
                {
                    "activeBalance": "1.23",
                    "balance": "1.23",
                    "blockedBalance": "0",
                    "currency": "btc",
                    "type": "credit",
                    "userId": str(self.user.uid)
                }, {
                    "activeBalance": "100",
                    "balance": "100",
                    "blockedBalance": "0",
                    "currency": "usdt",
                    "type": "credit",
                    "userId": str(self.user.uid)
                },
            ]},
            status=status.HTTP_200_OK,
        )

        liquidate_margin_call(margin_call_id=self.margin_call.id)

        self.margin_call.refresh_from_db()
        assert self.margin_call.orders.count() == 2

    @responses.activate
    @patch('exchange.asset_backed_credit.externals.liquidation.LiquidationProvider._liquidate')
    def test_liquidate_margin_call_success_when_wallet_internal_api_is_enabled_and_cached_recently(
        self, mock_liquidate
    ):
        mock_liquidate.return_value = [
            self.create_order(self.user, Decimal('100'), Currencies.usdt, Order.STATUS.active),
            self.create_order(self.user, Decimal('1.23'), Currencies.btc, Order.STATUS.active),
        ]

        self.create_user_service(self.margin_call.user, initial_debt=13300000)

        Settings.set('abc_use_wallet_list_internal_api', 'yes')
        responses.post(
            url=WalletListAPI.url,
            json={
                str(self.user.uid): [
                    {
                        'activeBalance': '1.23',
                        'balance': '1.23',
                        'blockedBalance': '0',
                        'currency': 'btc',
                        'type': 'credit',
                        'userId': str(self.user.uid),
                    },
                    {
                        'activeBalance': '100',
                        'balance': '100',
                        'blockedBalance': '0',
                        'currency': 'usdt',
                        'type': 'credit',
                        'userId': str(self.user.uid),
                    },
                ]
            },
            status=status.HTTP_200_OK,
        )

        # Cache wallets
        WalletService.get_user_wallets(
            user_id=self.margin_call.user.uid,
            exchange_user_id=self.margin_call.user.id,
            wallet_type=Wallet.WalletType.COLLATERAL,
        )

        with patch.object(WalletListAPI, 'request') as mock_request:
            liquidate_margin_call(margin_call_id=self.margin_call.id)

            mock_request.assert_not_called()

        self.margin_call.refresh_from_db()
        assert self.margin_call.orders.count() == 2
