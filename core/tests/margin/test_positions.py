import datetime
import random
from decimal import Decimal
from functools import partial
from typing import Optional, Union
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import Notification, User, VerificationProfile
from exchange.base.models import Currencies, Settings
from exchange.liquidator.models import LiquidationRequest
from exchange.margin.models import Position, PositionLiquidationRequest
from exchange.margin.services import MarginManager
from exchange.market.models import Market, Order
from exchange.pool.models import LiquidityPool
from exchange.wallet.models import Wallet
from tests.base.utils import create_order
from tests.market.test_order import OrderTestMixin


class PositionModelTest(OrderTestMixin, TestCase):

    MARKET_SYMBOL = 'BTCUSDT'
    MARKET_PRICE = 21220

    market: Market
    user: User

    def create_position(self, is_sell: bool = True, collateral: int = 0, **extra_fields) -> Position:
        return Position.objects.create(
            user=self.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell if is_sell else Position.SIDES.buy,
            collateral=collateral,
            **extra_fields,
        )

    def add_order(
        self,
        position: Position,
        amount: str,
        price: str,
        *,
        sell: bool,
        market: bool = False,
        stop: Optional[str] = None,
        pair: Optional[Order] = None,
    ) -> Order:
        order = create_order(
            self.user,
            src=Currencies.btc,
            dst=Currencies.usdt,
            amount=amount,
            price=price,
            sell=sell,
            market=market,
            stop=stop,
            pair=pair,
            client_order_id=f'{position.id}-{position.orders.count() + 1}',
        )
        position.orders.add(order, through_defaults={})
        return order

    @staticmethod
    def add_liquidation_request(position: Position) -> LiquidationRequest:
        pool_currency = position.src_currency if position.is_short else position.dst_currency
        pool_manager_id = 400 + pool_currency
        liquidation_request = LiquidationRequest.objects.create(
            src_wallet=Wallet.get_user_wallet(pool_manager_id, position.src_currency),
            dst_wallet=Wallet.get_user_wallet(pool_manager_id, position.dst_currency),
            side=LiquidationRequest.SIDES.buy if position.is_short else LiquidationRequest.SIDES.sell,
            amount=position.delegated_amount,
            filled_amount=0,
            filled_total_price=0,
            fee=0,
        )
        position.liquidation_requests.add(liquidation_request, through_defaults={})
        return liquidation_request

    @staticmethod
    def fill_order(order: Order, filled_amount: str, filled_total_price: str, fee: str):
        order.matched_amount += Decimal(filled_amount)
        order.matched_total_price += Decimal(filled_total_price)
        order.fee += Decimal(fee)
        if order.matched_amount < order.amount:
            order.status = Order.STATUS.active
        else:
            order.status = Order.STATUS.done
        order.save(update_fields=('matched_amount', 'matched_total_price', 'fee', 'status'))

    @staticmethod
    def fill_liquidation_request(liq_quest: LiquidationRequest, filled_amount: str, filled_total_price: str, fee: str):
        liq_quest.filled_amount += Decimal(filled_amount)
        liq_quest.filled_total_price += Decimal(filled_total_price)
        liq_quest.fee += Decimal(fee)
        if liq_quest.filled_amount < liq_quest.amount:
            liq_quest.status = LiquidationRequest.STATUS.in_progress
        else:
            liq_quest.status = LiquidationRequest.STATUS.done
        liq_quest.save(update_fields=('filled_amount', 'filled_total_price', 'fee', 'status'))

    @staticmethod
    def finish_liquidation_request(liq_quest: LiquidationRequest):
        liq_quest.status = LiquidationRequest.STATUS.done
        liq_quest.save(update_fields=('status',))
        PositionLiquidationRequest.objects.filter(liquidation_request=liq_quest).update(is_processed=True)

    def test_sell_position_market(self):
        position = self.create_position(is_sell=True, collateral=213)
        assert position.market == self.market
        assert position.market.symbol == 'BTCUSDT'

    def test_sell_position_fee(self):
        position = self.create_position(is_sell=True, collateral=213)
        assert position.trade_fee_rate == Decimal('0.0013')

    def test_sell_position_order_related_fields_on_no_sell(self):
        position = self.create_position(is_sell=True, collateral=213)
        self.add_order(position, amount='0.01', price='21300', sell=True)
        position.set_delegated_amount()
        assert position.liability == 0
        position.set_earned_amount()
        assert position.earned_amount == 0
        assert position.total_asset == 213
        position.set_liquidation_price()
        assert position.liquidation_price is None
        assert position.margin_ratio == Decimal('2')
        assert position.unrealized_pnl == Decimal('0')
        position.set_entry_price()
        assert position.entry_price is None
        position.set_exit_price()
        assert position.exit_price is None
        assert position.unrealized_pnl_percent == Decimal('0')
        assert position.pnl_percent == Decimal('0')

    def test_buy_position_order_related_fields_on_no_buy(self):
        position = self.create_position(is_sell=False, collateral=106, leverage=2)
        self.add_order(position, amount='0.01', price='21200', sell=False)
        position.set_delegated_amount()
        assert position.liability == 0
        position.set_earned_amount()
        assert position.earned_amount == 0
        assert position.total_asset == 106
        position.set_liquidation_price()
        assert position.liquidation_price is None
        assert position.margin_ratio == Decimal('1.5')
        assert position.unrealized_pnl == Decimal('0')
        position.set_entry_price()
        assert position.entry_price is None
        position.set_exit_price()
        assert position.exit_price is None
        assert position.unrealized_pnl_percent == Decimal('0')
        assert position.pnl_percent == Decimal('0')

    def test_sell_position_order_related_fields_on_partial_sell(self):
        position = self.create_position(is_sell=True, collateral=213)
        sell_order = self.add_order(position, amount='0.01', price='21300', sell=True)
        self.fill_order(sell_order, filled_amount='0.005', filled_total_price='106.5', fee='0.15975')
        position.set_delegated_amount()
        assert position.liability == Decimal('0.0050065085')
        position.set_earned_amount()
        assert position.earned_amount == Decimal('106.34025')
        assert position.total_asset == Decimal('319.34025')
        position.set_liquidation_price()
        assert position.liquidation_price == Decimal('57986.38')
        assert position.margin_ratio == Decimal('2')
        assert position.unrealized_pnl == Decimal('0.1011182337')
        position.set_entry_price()
        assert position.entry_price == Decimal('21300')
        position.set_exit_price()
        assert position.exit_price is None
        assert position.unrealized_pnl_percent == Decimal('0.11')
        assert position.pnl_percent == Decimal('0')

    def test_buy_position_order_related_fields_on_partial_buy(self):
        position = self.create_position(is_sell=False, collateral=106, leverage=2)
        buy_order = self.add_order(position, amount='0.01', price='21200', sell=False)
        self.fill_order(buy_order, filled_amount='0.005', filled_total_price='105.5', fee='0.0000065')
        position.set_delegated_amount()
        assert position.liability == Decimal('0.0049935')
        position.set_earned_amount()
        assert position.earned_amount == Decimal('-105.5')
        assert position.total_asset == Decimal('211.96207')
        position.set_liquidation_price()
        assert position.liquidation_price == Decimal('2012.62')
        assert position.margin_ratio == Decimal('1.5')
        assert position.unrealized_pnl == Decimal('0.32107611591')
        position.set_entry_price()
        assert position.entry_price == Decimal('21100')
        position.set_exit_price()
        assert position.exit_price is None
        assert position.unrealized_pnl_percent == Decimal('0.61')
        assert position.pnl_percent == Decimal('0')

    def test_sell_position_order_related_fields_on_full_sell(self):
        position = self.create_position(is_sell=True, collateral=213)
        sell_order = self.add_order(position, amount='0.01', price='21300', sell=True)
        self.fill_order(sell_order, filled_amount='0.01', filled_total_price='213', fee='0.3195')
        position.set_delegated_amount()
        assert position.liability == Decimal('0.010013017')
        position.set_earned_amount()
        assert position.earned_amount == Decimal('212.6805')
        assert position.total_asset == Decimal('425.6805')
        position.set_liquidation_price()
        assert position.liquidation_price == Decimal('38647.92')
        assert position.margin_ratio == Decimal('2')
        assert position.unrealized_pnl == Decimal('0.2022364674')
        position.set_entry_price()
        assert position.entry_price == Decimal('21300')
        position.set_exit_price()
        assert position.exit_price is None
        assert position.unrealized_pnl_percent == Decimal('0.11')
        assert position.pnl_percent == Decimal('0')

    def test_buy_position_order_related_fields_on_full_buy(self):
        position = self.create_position(is_sell=False, collateral=106, leverage=2)
        buy_order = self.add_order(position, amount='0.01', price='21200', sell=False)
        self.fill_order(buy_order, filled_amount='0.01', filled_total_price='211', fee='0.000013')
        position.set_delegated_amount()
        assert position.liability == Decimal('0.009987')
        position.set_earned_amount()
        assert position.earned_amount == Decimal('-211')
        assert position.total_asset == Decimal('317.92414')
        position.set_liquidation_price()
        assert position.liquidation_price == Decimal('12626.41')
        assert position.margin_ratio == Decimal('1.5')
        assert position.unrealized_pnl == Decimal('0.64215223182')
        position.set_entry_price()
        assert position.entry_price == Decimal('21100')
        position.set_exit_price()
        assert position.exit_price is None
        assert position.unrealized_pnl_percent == Decimal('0.61')
        assert position.pnl_percent == Decimal('0')

    def test_sell_position_order_related_fields_on_partial_buy(self):
        position = self.create_position(is_sell=True, collateral=213)
        sell_order = self.add_order(position, amount='0.01', price='21300', sell=True)
        self.fill_order(sell_order, filled_amount='0.007', filled_total_price='149.1', fee='0.22365')
        buy_order = self.add_order(position, amount='0.005', price='20000', sell=False)
        self.fill_order(buy_order, filled_amount='0.004', filled_total_price='80', fee='0.000006')
        position.set_delegated_amount()
        assert position.liability == Decimal('0.0030099129')
        position.set_earned_amount()
        assert position.earned_amount == Decimal('68.87635')
        assert position.total_asset == Decimal('281.87635')
        position.set_liquidation_price()
        assert position.liquidation_price == Decimal('85135.76')
        assert position.margin_ratio == Decimal('2.71')
        assert position.unrealized_pnl == Decimal('4.955938279380')
        position.set_entry_price()
        assert position.entry_price == Decimal('21300')
        position.set_exit_price()
        assert position.exit_price == Decimal('20000')
        assert position.unrealized_pnl_percent == Decimal('3.36')
        assert position.pnl_percent == Decimal('0')

    def test_buy_position_order_related_fields_on_partial_sell(self):
        position = self.create_position(is_sell=False, collateral=106, leverage=2)
        buy_order = self.add_order(position, amount='0.01', price='21200', sell=False)
        self.fill_order(buy_order, filled_amount='0.007', filled_total_price='147.7', fee='0.0000091')
        sell_order = self.add_order(position, amount='0.005', price='22000', sell=True)
        self.fill_order(sell_order, filled_amount='0.004', filled_total_price='88', fee='0.1144')
        position.set_delegated_amount()
        assert position.liability == Decimal('0.0029909')
        position.set_earned_amount()
        assert position.earned_amount == Decimal('-59.8144')
        assert position.total_asset == Decimal('169.466898')
        position.set_liquidation_price()
        assert position.liquidation_price == Decimal('0')
        assert position.margin_ratio == Decimal('1.88')
        assert position.unrealized_pnl == Decimal('3.534291122274')
        position.set_entry_price()
        assert position.entry_price == Decimal('21100')
        position.set_exit_price()
        assert position.exit_price == Decimal('22000')
        assert position.unrealized_pnl_percent == Decimal('4.79')
        assert position.pnl_percent == Decimal('0')

    def test_sell_position_order_related_fields_on_payoff(self):
        position = self.create_position(is_sell=True, collateral=213)
        sell_order = self.add_order(position, amount='0.01', price='21300', sell=True)
        sell_order.status = Order.STATUS.done
        sell_order.matched_amount = '0.01'
        sell_order.matched_total_price = '213'
        sell_order.fee = '0.2769'
        sell_order.save(update_fields=('status', 'matched_amount', 'matched_total_price', 'fee'))
        buy_order = self.add_order(position, amount='0.0100130169', price='20000', sell=False)
        buy_order.status = Order.STATUS.done
        buy_order.matched_amount = '0.0100130169'
        buy_order.matched_total_price = '200.260338'
        buy_order.fee = '0.0000130169'
        buy_order.save(update_fields=('status', 'matched_amount', 'matched_total_price', 'fee'))
        position.set_delegated_amount()
        assert position.liability == 0
        position.set_earned_amount()
        assert position.earned_amount == Decimal('12.462762')
        assert position.margin_ratio is None
        assert position.unrealized_pnl == Decimal('12.33813438')
        position.set_entry_price()
        assert position.entry_price == Decimal('21300')
        position.set_exit_price()
        assert position.exit_price == Decimal('20000')
        position.closed_at = position.created_at = timezone.now()
        position.pnl = position.unrealized_pnl
        assert position.unrealized_pnl_percent == Decimal('0')
        assert position.pnl_percent == Decimal('5.80')

    def test_buy_position_order_related_fields_on_payoff(self):
        position = self.create_position(is_sell=False, collateral=106, leverage=2)
        buy_order = self.add_order(position, amount='0.01', price='21200', sell=False)
        buy_order.status = Order.STATUS.done
        buy_order.matched_amount = '0.01'
        buy_order.matched_total_price = '211'
        buy_order.fee = '0.000013'
        buy_order.save(update_fields=('status', 'matched_amount', 'matched_total_price', 'fee'))
        sell_order = self.add_order(position, amount='0.009987', price='22000', sell=True)
        sell_order.status = Order.STATUS.active
        sell_order.matched_amount = '0.009987'
        sell_order.matched_total_price = '219.714'
        sell_order.fee = '0.2856282'
        sell_order.save(update_fields=('status', 'matched_amount', 'matched_total_price', 'fee'))
        position.set_delegated_amount()
        assert position.liability == 0
        position.set_earned_amount()
        assert position.earned_amount == Decimal('8.4283718')
        assert position.margin_ratio == Decimal('999')
        assert position.unrealized_pnl == Decimal('8.344088082')
        position.set_entry_price()
        assert position.entry_price == Decimal('21100')
        position.set_exit_price()
        assert position.exit_price == Decimal('22000')
        position.closed_at = position.created_at = timezone.now()
        position.pnl = position.unrealized_pnl
        assert position.unrealized_pnl_percent == Decimal('0')
        assert position.pnl_percent == Decimal('7.91')

    def test_sell_position_order_related_fields_on_market_order(self):
        best_active_price = Decimal(21220)
        cache.set('orderbook_BTCUSDT_best_active_buy', best_active_price)
        position = self.create_position(is_sell=True, collateral=213)
        self.add_order(position, amount='0.01', price='0', sell=True, market=True)
        position.set_delegated_amount()
        assert position.liability == 0
        position.set_earned_amount()
        assert position.total_asset == 213
        assert position.margin_ratio == Decimal('2')
        cache.delete('orderbook_BTCUSDT_best_active_buy')

    def test_buy_position_order_related_fields_on_market_order(self):
        best_active_price = Decimal(21220)
        amount = '0.01'
        cache.set('orderbook_BTCUSDT_best_active_sell', best_active_price)
        self.charge_wallet(Currencies.usdt, best_active_price * Decimal(amount))
        position = self.create_position(is_sell=False, collateral=106, leverage=2)
        self.add_order(position, amount=amount, price='0', sell=False, market=True)
        position.set_delegated_amount()
        assert position.liability == 0
        position.set_earned_amount()
        assert position.total_asset == 106
        assert position.margin_ratio == Decimal('1.49')
        cache.delete('orderbook_BTCUSDT_best_active_sell')

    def test_sell_position_order_related_fields_on_stop_loss_order(self):
        position = self.create_position(is_sell=True, collateral=212)
        self.add_order(position, amount='0.01', price='20100', sell=True, stop='20200')
        position.set_delegated_amount()
        assert position.liability == 0
        position.set_earned_amount()
        assert position.total_asset == Decimal('212')
        assert position.margin_ratio == Decimal('1.99')

    def test_buy_position_order_related_fields_on_stop_loss_order(self):
        position = self.create_position(is_sell=False, collateral=109, leverage=2)
        self.add_order(position, amount='0.01', price='21800', sell=False, stop='22000')
        position.set_delegated_amount()
        assert position.liability == 0
        position.set_earned_amount()
        assert position.total_asset == Decimal('109')
        assert position.margin_ratio == Decimal('1.5')

    def test_sell_position_order_related_fields_on_oco_order(self):
        position = self.create_position(is_sell=True, collateral=213)
        limit_order = self.add_order(position, amount='0.01', price='21300', sell=True)
        stop_order = self.add_order(position, amount='0.01', price='20100', sell=True, stop='20200', pair=limit_order)
        position.set_delegated_amount()
        assert position.liability == 0
        position.set_earned_amount()
        assert position.total_asset == 213
        assert position.margin_ratio == Decimal('2')

        Order.objects.filter(id=stop_order.id).update(status=Order.STATUS.active)
        Order.objects.filter(id=limit_order.id).update(status=Order.STATUS.canceled)
        del position.cached_orders
        assert position.margin_ratio == Decimal('2')

    def test_buy_position_order_related_fields_on_oco_order(self):
        position = self.create_position(is_sell=False, collateral=109, leverage=2)
        limit_order = self.add_order(position, amount='0.01', price='21200', sell=False)
        stop_order = self.add_order(position, amount='0.01', price='21800', sell=False, stop='22000', pair=limit_order)
        position.set_delegated_amount()
        assert position.liability == 0
        position.set_earned_amount()
        assert position.total_asset == 109
        assert position.margin_ratio == Decimal('1.5')

        Order.objects.filter(id=stop_order.id).update(status=Order.STATUS.canceled)
        Order.objects.filter(id=limit_order.id).update(matched_amount='0.002', matched_total_price='42.4', fee='2.6E-6')
        del position.cached_orders
        assert position.margin_ratio == Decimal('1.64')

    def test_sell_position_order_related_fields_on_liquidation_partial_fill(self):
        position = self.create_position(
            is_sell=True, collateral=213, status=Position.STATUS.liquidated, freezed_at=timezone.now()
        )
        sell_order = self.add_order(position, amount='0.01', price='21300', sell=True)
        self.fill_order(sell_order, filled_amount='0.01', filled_total_price='213', fee='0.2769')
        liq_quest = self.add_liquidation_request(position)
        self.fill_liquidation_request(liq_quest, filled_amount='0.005', filled_total_price='193.25', fee='0.05')
        position.set_delegated_amount()
        assert position.delegated_amount == Decimal('0.005')
        position.set_earned_amount()
        assert position.earned_amount == Decimal('19.4231')
        assert position.margin_ratio == Decimal('2.18')
        assert position.unrealized_pnl == Decimal('-86.81501037')
        position.set_entry_price()
        assert position.entry_price == Decimal('21300')
        position.set_exit_price()
        assert position.exit_price == Decimal('38660')
        assert position.unrealized_pnl_percent == Decimal('-40.9')
        assert position.pnl_percent == Decimal('0')

    def test_buy_position_order_related_fields_on_liquidation_partial_fill(self):
        position = self.create_position(
            is_sell=False, collateral=106, leverage=2, status=Position.STATUS.liquidated, freezed_at=timezone.now()
        )
        buy_order = self.add_order(position, amount='0.01', price='21200', sell=False)
        self.fill_order(buy_order, filled_amount='0.01', filled_total_price='211', fee='0.000013')
        liq_quest = self.add_liquidation_request(position)
        self.fill_liquidation_request(liq_quest, filled_amount='0.005', filled_total_price='63', fee='0.02')
        position.set_delegated_amount()
        assert position.delegated_amount == Decimal('0.004987')
        position.set_earned_amount()
        assert position.earned_amount == Decimal('-148.02')
        assert position.margin_ratio == Decimal('1.43')
        assert position.unrealized_pnl == Decimal('-42.333431382')
        position.set_entry_price()
        assert position.entry_price == Decimal('21100')
        position.set_exit_price()
        assert position.exit_price == Decimal('12596')
        assert position.unrealized_pnl_percent == Decimal('-40.2')
        assert position.pnl_percent == Decimal('0')

    def test_sell_position_order_related_fields_on_liquidation_payoff(self):
        position = self.create_position(
            is_sell=True, collateral=213, status=Position.STATUS.liquidated, freezed_at=timezone.now()
        )
        sell_order = self.add_order(position, amount='0.01', price='21300', sell=True)
        self.fill_order(sell_order, filled_amount='0.01', filled_total_price='213', fee='0.2769')
        liq_quest_1 = self.add_liquidation_request(position)
        self.fill_liquidation_request(liq_quest_1, filled_amount='0.007', filled_total_price='270.55', fee='0.07')
        self.finish_liquidation_request(liq_quest_1)
        liq_quest_2 = self.add_liquidation_request(position)
        self.fill_liquidation_request(liq_quest_2, filled_amount='0.003', filled_total_price='115.65', fee='0.03')
        position.set_delegated_amount()
        assert position.liability == 0
        position.set_earned_amount()
        assert position.earned_amount == Decimal('-173.5769')
        assert position.margin_ratio is None
        assert position.unrealized_pnl == Decimal('-173.5769')
        position.set_entry_price()
        assert position.entry_price == Decimal('21300')
        position.set_exit_price()
        assert position.exit_price == Decimal('38630')
        position.set_closed_at()
        assert position.closed_at == liq_quest_2.updated_at
        position.pnl = position.unrealized_pnl
        assert position.unrealized_pnl_percent == Decimal('0')
        assert position.pnl_percent == Decimal('-81.83')

    def test_buy_position_order_related_fields_on_liquidation_payoff(self):
        position = self.create_position(
            is_sell=False, collateral=106, leverage=2, status=Position.STATUS.liquidated, freezed_at=timezone.now()
        )
        buy_order = self.add_order(position, amount='0.01', price='21200', sell=False)
        self.fill_order(buy_order, filled_amount='0.01', filled_total_price='211', fee='0.000013')
        liq_quest_1 = self.add_liquidation_request(position)
        self.fill_liquidation_request(liq_quest_1, filled_amount='0.007', filled_total_price='88.2', fee='0.03')
        self.finish_liquidation_request(liq_quest_1)
        liq_quest_2 = self.add_liquidation_request(position)
        self.fill_liquidation_request(liq_quest_2, filled_amount='0.003', filled_total_price='37.5', fee='0.01')
        position.set_delegated_amount()
        assert position.liability == 0
        position.set_earned_amount()
        assert position.earned_amount == Decimal('-85.34')
        assert position.margin_ratio == Decimal('1.24')
        assert position.unrealized_pnl == Decimal('-85.34')
        position.set_entry_price()
        assert position.entry_price == Decimal('21100')
        position.set_exit_price()
        assert position.exit_price == Decimal('12566')
        position.set_closed_at()
        assert position.closed_at == liq_quest_2.updated_at
        position.pnl = position.unrealized_pnl
        assert position.unrealized_pnl_percent == Decimal('0')
        assert position.pnl_percent == Decimal('-81.2')

    def test_position_final_notification(self):
        for status, side, message in (
            (Position.STATUS.liquidated, Position.SIDES.sell, 'موقعیت فروش شما بر روی BTC-USDT لیکوئید شد'),
            (Position.STATUS.liquidated, Position.SIDES.buy, 'موقعیت خرید شما بر روی BTC-USDT لیکوئید شد'),
            (Position.STATUS.expired, Position.SIDES.sell, 'موقعیت فروش شما بر روی BTC-USDT منقضی شد'),
            (Position.STATUS.expired, Position.SIDES.buy, 'موقعیت خرید شما بر روی BTC-USDT منقضی شد'),
        ):
            Notification.objects.all().delete()
            position = self.create_position(is_sell=side == Position.SIDES.sell, collateral=213, status=status)
            position.notify_on_complete()
            notifications = Notification.objects.all()
            assert len(notifications) == 1
            assert notifications[0].user_id == self.user.id
            assert notifications[0].message == message

    def test_position_double_spend(self):
        position = self.create_position(is_sell=True, collateral=213, status=Position.STATUS.liquidated, user_id=201)
        sell_order = self.add_order(position, amount='0.01', price='21300', sell=True)
        self.fill_order(sell_order, filled_amount='0.01', filled_total_price='213', fee='0.2769')
        buy_order = self.add_order(position, amount='0.0100130169', price='20000', sell=False)
        self.fill_order(buy_order, filled_amount='0.0100130169', filled_total_price='200.260338', fee='0.0000130169')
        buy_order_prime = self.add_order(position, amount='0.0100130169', price='19800', sell=False)
        self.fill_order(buy_order_prime, filled_amount='0.002', filled_total_price='39.6', fee='0.0000026')
        with patch.object(Notification, 'notify_admins') as notify_admins_patch:
            position.set_delegated_amount()
        assert position.delegated_amount == 0
        notify_admins_patch.assert_called_once_with(
            f'Check out position #{position.id} for user1@example.com in BTCUSDT\n0.0100000000 vs 0.0119974000',
            title='‼️‼️‼️ Certain double spend in margin',
            channel='pool',
        )

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_liquidation_call_email(self):
        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('update_email_templates')
        for position_data in (
            {'is_sell': True, 'collateral': 213, 'liquidation_price': Decimal('48193.2700000000')},
            {'is_sell': False, 'collateral': 106, 'leverage': 2, 'liquidation_price': Decimal('11681.9400000000')},
        ):
            position = self.create_position(
                **position_data,
                status=Position.STATUS.liquidated,
                closed_at=timezone.now(),
            )
            position.notify_on_complete()
        with patch('django.db.connection.close'):
            call_command('send_queued_mail')

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_position_expired_email(self):
        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('update_email_templates')
        # Short position after max extension
        position = self.create_position(
            is_sell=True,
            status=Position.STATUS.expired,
            collateral=206,
            delegated_amount='0.01',
            entry_price=21300,
            created_at=timezone.now() - datetime.timedelta(days=31),
        )
        position.notify_on_complete()
        call_command('update_email_templates')
        # Long position after max extension
        position = self.create_position(
            is_sell=False,
            status=Position.STATUS.expired,
            collateral=1,
            earned_amount=-1065,
            leverage=5,
            created_at=timezone.now() - datetime.timedelta(days=20),
        )
        position.notify_on_complete()
        with patch('django.db.connection.close'):
            call_command('send_queued_mail')

    @staticmethod
    def _assert_position_user_pnl(position, total_pnl, extension_days, expected_user_pnl):
        closed_at = position.created_at + datetime.timedelta(days=extension_days)
        with patch('exchange.margin.models.ir_today', return_value=closed_at.date()):
            assert Decimal(position.get_user_pnl(Decimal(total_pnl), closed_at)) == Decimal(expected_user_pnl)

    def test_position_user_pnl(self):
        position = Position(created_at=timezone.now())
        self._assert_position_user_pnl(position, total_pnl=100, extension_days=0, expected_user_pnl=99)
        self._assert_position_user_pnl(position, total_pnl=100, extension_days=10, expected_user_pnl=89)
        self._assert_position_user_pnl(position, total_pnl=100, extension_days=30, expected_user_pnl=69)
        for extension_days in (0, 10, 30):
            self._assert_position_user_pnl(position, total_pnl=-5, extension_days=extension_days, expected_user_pnl=-5)


class PositionTestMixin(OrderTestMixin):
    MARKET_SYMBOL = 'BTCUSDT'
    MARKET_PRICE = 21220

    user: User
    assistant_user: User
    src_pool: LiquidityPool
    dst_pool: LiquidityPool

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        Settings.set(f'margin_max_leverage_{User.USER_TYPES.level1}', '5')
        User.objects.filter(pk=cls.user.pk).update(user_type=User.USER_TYPES.trader)
        rnd = random.randint(0, 10 ** 16)
        cls.assistant_user = User.objects.create_user(username=f'PositionTestMixinAssistant{rnd}@nobitex.ir')
        LiquidityPool.objects.filter(currency__in=[Currencies.btc, Currencies.usdt]).delete()
        cls.src_pool = cls._create_pool(Currencies.btc, capacity='10', filled_capacity='2')
        cls.dst_pool = cls._create_pool(Currencies.usdt, capacity='100_000', filled_capacity='40_000')
        LiquidityPool.get_for(Currencies.btc, skip_cache=True)
        VerificationProfile.objects.filter(id=cls.user.get_verification_profile().id).update(email_confirmed=True)
        Settings.set(f'position_fee_rate_{Currencies.btc}', Decimal('0.0005'))
        Settings.set(f'position_fee_rate_{Currencies.usdt}', Decimal('0.0005'))

    @staticmethod
    def _create_pool(currency: int, capacity: str, filled_capacity: str, *, is_active: bool = True) -> LiquidityPool:
        pool = LiquidityPool.objects.create(
            currency=currency,
            capacity=Decimal(capacity),
            filled_capacity=Decimal(filled_capacity),
            manager_id=400 + currency,
            is_active=is_active,
        )
        pool.src_wallet.create_transaction('manual', filled_capacity).commit()
        return pool

    @classmethod
    def _create_margin_order(
        cls,
        amount: Union[Decimal, int, str],
        price: Union[Decimal, int, str] = 0,
        execution: Optional[int] = None,
        param1: Union[Decimal, int, str, None] = None,
        pair: Optional[Order] = None,
        leverage: Optional[str] = None,
        src: Optional[int] = None,
        dst: Optional[int] = None,
        user: Optional[User] = None,
        order_type: Optional[int] = None,
    ) -> Order:
        return MarginManager.create_margin_order(
            user=user or cls.user,
            order_type=order_type,
            src_currency=src or cls.market.src_currency,
            dst_currency=dst or cls.market.dst_currency,
            amount=Decimal(amount),
            price=Decimal(price),
            channel=Order.CHANNEL.unknown,
            execution_type=execution or Order.EXECUTION_TYPES.limit,
            param1=param1 and Decimal(param1),
            pair=pair,
            leverage=Decimal(leverage) if leverage else Position.BASE_LEVERAGE,
        )

    @classmethod
    def create_short_margin_order(cls, *args, **kwargs):
        return cls._create_margin_order(*args, order_type=Order.ORDER_TYPES.sell, **kwargs)

    @classmethod
    def create_long_margin_order(cls, *args, **kwargs):
        return cls._create_margin_order(*args, order_type=Order.ORDER_TYPES.buy, **kwargs)

    @classmethod
    def create_margin_close_order(
        cls,
        amount: Union[Decimal, int, str],
        price: Union[Decimal, int, str],
        position: Position,
        execution: Optional[int] = None,
        param1: Union[Decimal, int, str, None] = None,
        pair: Optional[Order] = None,
    ) -> Order:
        return MarginManager.create_position_close_order(
            pid=position.id if position else 0,
            amount=Decimal(amount),
            price=Decimal(price),
            channel=Order.CHANNEL.unknown,
            execution_type=execution or Order.EXECUTION_TYPES.limit,
            param1=param1 and Decimal(param1),
            pair=pair,
        )

    def _check_position_status(
        self,
        position: Position,
        side: int,
        collateral: Union[str, int],
        liability: Union[str, int] = 0,
        earned_amount: Union[str, int] = 0,
        status: Optional[int] = None,
        liquidation_price: Optional[str] = None,
        orders_count: int = 1,
        liquidation_requests_count: int = 0,
        pnl: Optional[str] = None,
        entry_price: Optional[str] = None,
        exit_price: Optional[str] = None,
    ):
        call_command('create_pool_pnl_transactions', '--once')
        position.refresh_from_db()

        assert position.user_id == self.user.id
        assert position.src_currency == self.market.src_currency
        assert position.dst_currency == self.market.dst_currency
        assert position.side == side
        assert position.status == (status or position.STATUS.new)
        assert position.collateral == Decimal(collateral)
        assert position.liability == Decimal(liability)
        assert position.earned_amount == Decimal(earned_amount)
        assert position.liquidation_price == (liquidation_price and Decimal(liquidation_price))
        assert position.orders.count() == orders_count
        assert position.liquidation_requests.count() == liquidation_requests_count
        assert position.pnl == (pnl and Decimal(pnl))
        assert bool(position.pnl_transaction) == bool(position.pnl) == bool(position.closed_at)
        assert bool(position.entry_price) == bool(position.opened_at)
        assert position.entry_price == (entry_price and Decimal(entry_price))
        assert position.exit_price == (exit_price and Decimal(exit_price))
        if status in (Position.STATUS.subset('liquidated', 'expired')):
            assert position.freezed_at


class RoundedDecimalFieldInPositionTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(id=202)
        self.position = Position.objects.create(
            user=self.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            collateral=0,
            liquidation_price='12.12345678915',
        )

    def test_liquidation_price_rounding(self):
        self.position.refresh_from_db()
        assert self.position.liquidation_price == Decimal('12.1234567892')

        self.position.liquidation_price = '12.12345678925'
        self.position.save()
        self.position.refresh_from_db()
        assert self.position.liquidation_price == Decimal('12.1234567892')
        self.position.liquidation_price = Decimal('12.12345678915')
        self.position.save()
        self.position.refresh_from_db()
        assert self.position.liquidation_price == Decimal('12.1234567892')
        self.position.liquidation_price = Decimal('12.12345678911')
        self.position.save()
        self.position.refresh_from_db()
        assert self.position.liquidation_price == Decimal('12.1234567891')
        self.position.liquidation_price = Decimal('12.12345678916')
        self.position.save()
        self.position.refresh_from_db()
        assert self.position.liquidation_price == Decimal('12.1234567892')

    def test_entry_price_rounding(self):
        self.position.entry_price = Decimal('12.12345678925')
        self.position.save()
        self.position.refresh_from_db()
        assert self.position.entry_price == Decimal('12.1234567892')
        self.position.entry_price = Decimal('12.12345678915')
        self.position.save()
        self.position.refresh_from_db()
        assert self.position.entry_price == Decimal('12.1234567892')
        self.position.entry_price = Decimal('12.12345678911')
        self.position.save()
        self.position.refresh_from_db()
        assert self.position.entry_price == Decimal('12.1234567891')
        self.position.entry_price = Decimal('12.12345678916')
        self.position.save()
        self.position.refresh_from_db()
        assert self.position.entry_price == Decimal('12.1234567892')

    def test_exit_price_rounding(self):
        self.position.exit_price = Decimal('12.12345678925')
        self.position.save()
        self.position.refresh_from_db()
        assert self.position.exit_price == Decimal('12.1234567892')
        self.position.exit_price = Decimal('12.12345678915')
        self.position.save()
        self.position.refresh_from_db()
        assert self.position.exit_price == Decimal('12.1234567892')
        self.position.exit_price = Decimal('12.12345678911')
        self.position.save()
        self.position.refresh_from_db()
        assert self.position.exit_price == Decimal('12.1234567891')
        self.position.exit_price = Decimal('12.12345678916')
        self.position.save()
        self.position.refresh_from_db()
        assert self.position.exit_price == Decimal('12.1234567892')

    def test_pnl_rounding(self):
        self.position.pnl = Decimal('12.12345678925')
        self.position.save()
        self.position.refresh_from_db()
        assert self.position.pnl == Decimal('12.1234567892')
        self.position.pnl = Decimal('12.12345678915')
        self.position.save()
        self.position.refresh_from_db()
        assert self.position.pnl == Decimal('12.1234567892')
        self.position.pnl = Decimal('12.12345678911')
        self.position.save()
        self.position.refresh_from_db()
        assert self.position.pnl == Decimal('12.1234567891')
        self.position.pnl = Decimal('12.12345678916')
        self.position.save()
        self.position.refresh_from_db()
        assert self.position.pnl == Decimal('12.1234567892')


class TestPredictView(PositionTestMixin, APITestCase):
    def test_non_existing_predict_category(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        response = self.client.post('/margin/predict/fee', {})
        assert response.status_code == status.HTTP_404_NOT_FOUND
