from decimal import Decimal
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User, VerificationProfile
from exchange.base.models import Currencies
from exchange.margin.models import Position
from exchange.market.models import Order
from exchange.settings import NOBITEX_OPTIONS
from exchange.wallet.models import Wallet
from tests.margin.test_positions import PositionTestMixin
from tests.market.test_order import OrderAPITestMixin


@patch.dict(NOBITEX_OPTIONS['positionLimits'], {User.USER_TYPES.trader: Decimal('0.001')})
class MarginDelegationLimitAPITest(PositionTestMixin, OrderAPITestMixin, APITestCase):
    def _test_successful_delegation_limit_view(self, currency: str, expected_limit: str):
        response = self.client.get('/margin/delegation-limit', {'currency': currency})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert Decimal(data['limit']) == Decimal(expected_limit)

    def _test_unsuccessful_delegation_limit_view(self, data: dict, code: str):
        response = self.client.get('/margin/delegation-limit', data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST if code in ['ParseError', 'UnverifiedEmail'] else status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == code

    def test_delegation_limit_invalid_data(self):
        for data in ({}, {'currency': 10}, {'currency': 'IRT'}):
            self._test_unsuccessful_delegation_limit_view(data, code='ParseError')

    def test_delegation_limit_non_existent_pool(self):
        self._test_unsuccessful_delegation_limit_view({'currency': 'ltc'}, code='UnsupportedMarginSrc')

    def test_delegation_limit_level0_user(self):
        User.objects.filter(pk=self.user.id).update(user_type=User.USER_TYPES.level0)
        self._test_unsuccessful_delegation_limit_view({'currency': 'btc'}, code='TradeLimitation')

    def test_delegation_limit_with_no_position(self):
        self._test_successful_delegation_limit_view('btc', expected_limit='0.002')

    def test_delegation_limit_with_no_active_sell_position(self):
        for _status in ('liquidated', 'closed', 'expired'):
            Position.objects.create(
                user=self.user,
                src_currency=self.market.src_currency,
                dst_currency=self.market.dst_currency,
                side=Position.SIDES.sell,
                collateral='213',
                earned_amount='10',
                pnl='10',
                status=getattr(Position.STATUS, _status),
            )
        self._test_successful_delegation_limit_view('btc', expected_limit='0.002')

    def test_delegation_limit_with_no_active_buy_position(self):
        for _status in ('liquidated', 'closed', 'expired'):
            Position.objects.create(
                user=self.user,
                src_currency=self.market.src_currency,
                dst_currency=self.market.dst_currency,
                side=Position.SIDES.buy,
                collateral='21.3',
                delegated_amount='42.44',
                earned_amount='0.002',
                pnl='10',
                leverage='2',
                status=getattr(Position.STATUS, _status),
            )
        self._test_successful_delegation_limit_view('usdt', expected_limit='40')

    def test_delegation_limit_with_new_sell_position(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        self.create_short_margin_order(amount='0.001', price='21300')
        self._test_successful_delegation_limit_view('btc', expected_limit='0.001')

    def test_delegation_limit_with_new_buy_position(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        self.create_long_margin_order(amount='0.001', price='21200')
        self._test_successful_delegation_limit_view('usdt', expected_limit='18.8')

    def test_delegation_limit_with_new_both_side_positions(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        self.create_long_margin_order(amount='0.001', price='21200')
        self.charge_wallet(Currencies.rls, 500_000_0, Wallet.WALLET_TYPE.margin)
        self.create_short_margin_order(amount='10', price='50_000_0', src=Currencies.usdt, dst=Currencies.rls)
        self._test_successful_delegation_limit_view('usdt', expected_limit='8.8')

    def test_delegation_limit_with_open_sell_position(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        self.create_short_margin_order(amount='0.001', price='21300')
        Order.objects.update(matched_amount='0.0005')
        Position.objects.update(delegated_amount='0.0005', status=Position.STATUS.open)
        Position.objects.create(
            user=self.user,
            src_currency=self.market.src_currency,
            dst_currency=Currencies.rls,
            side=Position.SIDES.sell,
            collateral='64000000',
            delegated_amount='0.00025',
            earned_amount='16000000',
            status=Position.STATUS.open,
        )
        self._test_successful_delegation_limit_view('btc', expected_limit='0.00075')

    def test_delegation_limit_with_open_buy_position(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        self.create_long_margin_order(amount='0.001', price='21200')
        Order.objects.update(matched_amount='0.0005')
        Position.objects.update(earned_amount='-10.6', status=Position.STATUS.open)
        Position.objects.create(
            user=self.user,
            src_currency=Currencies.ltc,
            dst_currency=self.market.dst_currency,
            side=Position.SIDES.buy,
            collateral='20.6',
            delegated_amount='0.05',
            earned_amount='-5.15',
            status=Position.STATUS.open,
        )
        Position.objects.create(
            user=self.user,
            src_currency=Currencies.ltc,
            dst_currency=self.market.dst_currency,
            side=Position.SIDES.buy,
            collateral='20.6',
            delegated_amount='0.01',
            earned_amount='1.08',
            status=Position.STATUS.open,
        )
        self._test_successful_delegation_limit_view('usdt', expected_limit='13.65')

    def test_delegation_limit_with_market_sell_order(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        self.create_short_margin_order(amount='0.001', price='21000', execution=Order.EXECUTION_TYPES.market)
        self._test_successful_delegation_limit_view('btc', expected_limit='0.001')

    def test_delegation_limit_with_market_buy_order(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        self.create_long_margin_order(amount='0.001', price='23000', execution=Order.EXECUTION_TYPES.market)
        self._test_successful_delegation_limit_view('usdt', expected_limit='17')

    def test_delegation_limit_with_stop_loss_sell_order(self):
        self.charge_wallet(Currencies.usdt, 50, Wallet.WALLET_TYPE.margin)
        self.create_short_margin_order(amount='0.001', execution=Order.EXECUTION_TYPES.stop_market, param1='20000')
        self._test_successful_delegation_limit_view('btc', expected_limit='0.001')
        self.create_short_margin_order(
            amount='0.001', execution=Order.EXECUTION_TYPES.stop_limit, param1='20000', price='20500'
        )
        self._test_successful_delegation_limit_view('btc', expected_limit='0')

    def test_delegation_limit_with_stop_loss_buy_order(self):
        self.charge_wallet(Currencies.usdt, 50, Wallet.WALLET_TYPE.margin)
        self.create_long_margin_order(amount='0.0005', execution=Order.EXECUTION_TYPES.stop_market, param1='22000')
        self._test_successful_delegation_limit_view('usdt', expected_limit='29')
        self.create_long_margin_order(
            amount='0.001', execution=Order.EXECUTION_TYPES.stop_limit, param1='22000', price='22100'
        )
        self._test_successful_delegation_limit_view('usdt', expected_limit='6.9')

    def test_delegation_limit_with_oco_sell_order(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        limit_order = self.create_short_margin_order(amount='0.001', price='21300')
        stop_order = self.create_short_margin_order(
            amount='0.001', execution=Order.EXECUTION_TYPES.stop_limit, param1='20000', price='20500', pair=limit_order
        )
        self._test_successful_delegation_limit_view('btc', expected_limit='0.001')
        stop_order.do_cancel()
        self._test_successful_delegation_limit_view('btc', expected_limit='0.002')

    def test_delegation_limit_with_oco_buy_order(self):
        self.charge_wallet(Currencies.usdt, 25, Wallet.WALLET_TYPE.margin)
        limit_order = self.create_long_margin_order(amount='0.001', price='21000')
        stop_order = self.create_long_margin_order(
            amount='0.001', execution=Order.EXECUTION_TYPES.stop_limit, param1='22000', price='22100', pair=limit_order
        )
        self._test_successful_delegation_limit_view('usdt', expected_limit='17.9')
        stop_order.do_cancel()
        self._test_successful_delegation_limit_view('usdt', expected_limit='40')

    def test_delegation_limit_not_verified_email(self):
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=False)
        self._test_unsuccessful_delegation_limit_view({'currency': 'ltc'}, code='UnverifiedEmail')
