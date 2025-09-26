import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.xchange.crons import XchangeNotifyAdminOnMarketApproachingLimitsCron
from exchange.xchange.helpers import calculate_market_consumption_percentage
from exchange.xchange.limitation import DefaultStrategyInLimitation, USDTRLSStrategyInLimitation
from exchange.xchange.models import ExchangeTrade, MarketLimitation
from exchange.xchange.types import ConsumedPercentageOfMarket
from tests.xchange.helpers import BaseMarketLimitationTest


class TestUserMarketLimitation(BaseMarketLimitationTest):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.btc_usdt_market = self.create_btc_usdt_market()
        self.usdt_rls_market = self.create_usdt_rls_market()

        self.user_sell_limitation = MarketLimitation.objects.create(
            interval=1,
            max_amount=Decimal('100.0'),
            market=self.btc_usdt_market,
            is_active=True,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.USER,
        )
        self.user_buy_limitation = MarketLimitation.objects.create(
            interval=1,
            max_amount=Decimal('120.0'),
            market=self.btc_usdt_market,
            is_active=True,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.USER,
        )

    def test_no_active_limit(self):
        amount = Decimal('1000')
        is_sell = True
        limit_exceeded = self.btc_usdt_market.has_market_exceeded_limit(
            amount=amount, is_sell=is_sell, reference_currency=Currencies.usdt
        )
        assert not limit_exceeded

    def test_sell_limitation(self):
        self.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.00005'),
            dst_amount=Decimal('50.0'),
        )
        self.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.00005'),
            dst_amount=Decimal('40.0'),
        )
        # total trades 50 + 40 = 90, limitation is 100, rest is 100 - 90 = 10
        assert not self.btc_usdt_market.has_user_exceeded_limit(
            self.user.id, Decimal('9.0'), is_sell=True, reference_currency=Currencies.usdt
        )
        assert self.btc_usdt_market.has_user_exceeded_limit(
            self.user.id, Decimal('11.0'), is_sell=True, reference_currency=Currencies.usdt
        )
        assert not self.btc_usdt_market.has_user_exceeded_limit(
            self.user.id, self.user_buy_limitation.max_amount, is_sell=False, reference_currency=Currencies.usdt
        )

    def test_buy_limitation(self):
        self.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.00005'),
            dst_amount=Decimal('50.0'),
        )
        self.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.00005'),
            dst_amount=Decimal('60.0'),
        )
        assert not self.btc_usdt_market.has_user_exceeded_limit(
            self.user.id, Decimal('9.0'), is_sell=False, reference_currency=Currencies.usdt
        )
        assert self.btc_usdt_market.has_user_exceeded_limit(
            self.user.id, Decimal('11.0'), is_sell=False, reference_currency=Currencies.usdt
        )
        assert not self.btc_usdt_market.has_user_exceeded_limit(
            self.user.id, self.user_sell_limitation.max_amount, is_sell=True, reference_currency=Currencies.usdt
        )

    def test_check_limitation_when_limitation_is_disable(self):
        self.user_sell_limitation.is_active = False
        self.user_sell_limitation.save()
        self.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.00005'),
            dst_amount=Decimal('50.0'),
        )
        self.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.00005'),
            dst_amount=Decimal('120.0'),
        )
        assert not self.btc_usdt_market.has_user_exceeded_limit(
            self.user.id, Decimal('1000.0'), is_sell=True, reference_currency=Currencies.usdt
        )
        assert self.btc_usdt_market.has_user_exceeded_limit(
            self.user.id,
            self.user_buy_limitation.max_amount + Decimal('10'),
            is_sell=False,
            reference_currency=Currencies.usdt,
        )

    def test_check_limitation_when_there_are_trades_out_of_interval(self):
        self.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.00005'),
            dst_amount=Decimal('50.0'),
        )
        self.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.00005'),
            dst_amount=Decimal('120.0'),
            created_at=ir_now() - datetime.timedelta(hours=self.user_sell_limitation.interval),
        )
        assert not self.btc_usdt_market.has_user_exceeded_limit(
            self.user.id, Decimal('50.0'), is_sell=True, reference_currency=Currencies.usdt
        )

    def test_trades_with_different_statuses(self):
        self.user_buy_limitation.max_amount = Decimal('10000')
        self.user_buy_limitation.save()
        # Create trades with different statuses
        self.create_trade(
            src_currency=self.btc_usdt_market.base_currency,
            dst_currency=self.btc_usdt_market.quote_currency,
            src_amount=Decimal('2'),
            dst_amount=Decimal('8000'),
            created_at=ir_now(),
            status=ExchangeTrade.STATUS.failed,  # Should be ignored
            is_sell=False,
            user=self.user,
        )
        self.create_trade(
            src_currency=self.btc_usdt_market.base_currency,
            dst_currency=self.btc_usdt_market.quote_currency,
            src_amount=Decimal('1'),
            dst_amount=Decimal('4000'),
            created_at=ir_now(),
            status=ExchangeTrade.STATUS.succeeded,  # Should be counted
            is_sell=False,
            user=self.user,
        )

        amount = Decimal('6000')
        is_sell = False
        limit_exceeded = self.btc_usdt_market.has_user_exceeded_limit(
            user_id=self.user.id, amount=amount, is_sell=is_sell, reference_currency=Currencies.usdt
        )
        assert not limit_exceeded

    def test_there_are_no_trades_total_amount_is_zero(self):
        amount = Decimal('120')
        is_sell = False
        limit_exceeded = self.btc_usdt_market.has_user_exceeded_limit(
            user_id=self.user.id, amount=amount, is_sell=is_sell, reference_currency=Currencies.usdt
        )
        assert not limit_exceeded

    def test_user_limit_without_user_id(self):
        amount = Decimal('5000')
        is_sell = True

        with self.assertRaises(ValueError):
            self.btc_usdt_market.has_user_exceeded_limit(
                user_id=None, amount=amount, is_sell=is_sell, reference_currency=Currencies.usdt
            )

    def test_user_limit_in_usdtrls_market_when_reference_is_usdt_sell(self):
        MarketLimitation.objects.create(
            interval=1,
            max_amount=Decimal('5.0'),
            market=self.usdt_rls_market,
            is_active=True,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.USER,
        )
        self.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=Decimal('3'),
            dst_amount=Decimal('2100000'),
        )
        self.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=Decimal('1'),
            dst_amount=Decimal('700000'),
        )
        # create buy trade must be ignored
        self.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=Decimal('2'),
            dst_amount=Decimal('1400000'),
        )
        # total trades 3 + 1 = 4, limitation is 5, rest is 5 - 4 = 1
        assert not self.usdt_rls_market.has_user_exceeded_limit(
            self.user.id, Decimal('1'), is_sell=True, reference_currency=Currencies.usdt
        )
        assert self.usdt_rls_market.has_user_exceeded_limit(
            self.user.id, Decimal('2'), is_sell=True, reference_currency=Currencies.usdt
        )
        # check buy usdtrls market
        assert not self.usdt_rls_market.has_user_exceeded_limit(
            self.user.id, Decimal('10'), is_sell=False, reference_currency=Currencies.usdt
        )

    def test_user_limit_in_usdtrls_market_when_reference_is_rls_sell(self):
        MarketLimitation.objects.create(
            interval=1,
            max_amount=Decimal('5.0'),
            market=self.usdt_rls_market,
            is_active=True,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.USER,
        )
        self.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=Decimal('3'),
            dst_amount=Decimal('2100000'),
        )
        self.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=Decimal('1'),
            dst_amount=Decimal('700000'),
        )
        # create buy trade must be ignored
        self.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=Decimal('2'),
            dst_amount=Decimal('1400000'),
        )
        # total trades 3 + 1 = 4, limitation is 5, rest is 5 - 4 = 1
        assert not self.usdt_rls_market.has_user_exceeded_limit(
            self.user.id, Decimal('670000'), reference_currency=Currencies.rls, is_sell=True
        )  # about 1 usdt price
        assert self.usdt_rls_market.has_user_exceeded_limit(
            self.user.id, Decimal('700000'), reference_currency=Currencies.rls, is_sell=True
        )  # more than 1 usdt
        # check buy usdt-rls market
        assert not self.usdt_rls_market.has_user_exceeded_limit(
            self.user.id, Decimal('96600000'), is_sell=False, reference_currency=Currencies.rls
        )

    def test_a_user_exceeded_limit_but_other_not(self):
        self.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.97'),
            dst_amount=Decimal('70.0'),
        )
        other_user = User.objects.create_user(username='test1234')
        self.create_trade(
            user=other_user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.9'),
            dst_amount=Decimal('50.0'),
        )
        assert not self.btc_usdt_market.has_user_exceeded_limit(
            self.user.id, Decimal('30'), is_sell=True, reference_currency=Currencies.usdt
        )
        assert self.btc_usdt_market.has_user_exceeded_limit(
            self.user.id, Decimal('40'), is_sell=True, reference_currency=Currencies.usdt
        )
        assert not self.btc_usdt_market.has_user_exceeded_limit(
            other_user.id, Decimal('40'), is_sell=True, reference_currency=Currencies.usdt
        )
        assert self.btc_usdt_market.has_user_exceeded_limit(
            other_user.id, Decimal('60'), is_sell=True, reference_currency=Currencies.usdt
        )


class TestEntireMarketLimitation(BaseMarketLimitationTest):
    def setUp(self):
        self.user_1 = User.objects.get(pk=201)
        self.user_2 = User.objects.get(pk=202)
        self.btc_usdt_market = self.create_btc_usdt_market()
        self.usdt_rls_market = self.create_usdt_rls_market()
        self.sell_limitation = MarketLimitation.objects.create(
            interval=1,
            max_amount=Decimal('100.0'),
            market=self.btc_usdt_market,
            is_active=True,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        self.buy_limitation = MarketLimitation.objects.create(
            interval=1,
            max_amount=Decimal('120.0'),
            market=self.btc_usdt_market,
            is_active=True,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )

    def test_sell_limitation(self):
        self.create_trade(
            user=self.user_1,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.00005'),
            dst_amount=Decimal('50.0'),
        )
        self.create_trade(
            user=self.user_2,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.00004'),
            dst_amount=Decimal('40.0'),
        )
        assert not self.btc_usdt_market.has_market_exceeded_limit(
            Decimal('9.0'), is_sell=True, reference_currency=Currencies.usdt
        )
        assert self.btc_usdt_market.has_market_exceeded_limit(
            Decimal('11.0'), is_sell=True, reference_currency=Currencies.usdt
        )
        assert not self.btc_usdt_market.has_market_exceeded_limit(
            self.buy_limitation.max_amount, is_sell=False, reference_currency=Currencies.usdt
        )

    def test_buy_limitation(self):
        self.create_trade(
            user=self.user_1,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.00005'),
            dst_amount=Decimal('50.0'),
        )
        self.create_trade(
            user=self.user_2,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.00006'),
            dst_amount=Decimal('60.0'),
        )
        assert not self.btc_usdt_market.has_market_exceeded_limit(
            Decimal('9.0'), is_sell=False, reference_currency=Currencies.usdt
        )
        assert self.btc_usdt_market.has_market_exceeded_limit(
            Decimal('11.0'), is_sell=False, reference_currency=Currencies.usdt
        )
        assert not self.btc_usdt_market.has_market_exceeded_limit(
            self.sell_limitation.max_amount, is_sell=True, reference_currency=Currencies.usdt
        )

    def test_check_limitation_when_user_has_unknown_trades(self):
        self.create_trade(
            user=self.user_1,
            status=ExchangeTrade.STATUS.unknown,
            is_sell=False,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.00010'),
            dst_amount=Decimal('50.0'),
        )
        self.create_trade(
            user=self.user_2,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.00006'),
            dst_amount=Decimal('60.0'),
        )
        assert not self.btc_usdt_market.has_market_exceeded_limit(
            Decimal('10.0'), is_sell=False, reference_currency=Currencies.usdt
        )
        assert self.btc_usdt_market.has_market_exceeded_limit(
            Decimal('11.0'), is_sell=False, reference_currency=Currencies.usdt
        )

    def test_check_limitation_when_limitation_is_disable(self):
        self.sell_limitation.is_active = False
        self.sell_limitation.save()
        self.create_trade(
            user=self.user_1,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.00005'),
            dst_amount=Decimal('50.0'),
        )
        self.create_trade(
            user=self.user_2,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.00005'),
            dst_amount=Decimal('120.0'),
        )
        assert not self.btc_usdt_market.has_market_exceeded_limit(
            self.sell_limitation.max_amount + Decimal('100'), is_sell=True, reference_currency=Currencies.usdt
        )
        assert self.btc_usdt_market.has_market_exceeded_limit(
            self.buy_limitation.max_amount + Decimal('1'), is_sell=False, reference_currency=Currencies.usdt
        )

    def test_check_limitation_when_there_are_trades_out_of_interval(self):
        self.create_trade(
            user=self.user_1,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.00005'),
            dst_amount=Decimal('50.0'),
        )
        self.create_trade(
            user=self.user_2,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('0.00005'),
            dst_amount=Decimal('120.0'),
            created_at=ir_now() - datetime.timedelta(hours=self.sell_limitation.interval),
        )
        assert not self.btc_usdt_market.has_market_exceeded_limit(
            Decimal('50.0'), is_sell=True, reference_currency=Currencies.usdt
        )

    def test_total_amount_equals_limit(self):
        self.sell_limitation.max_amount = Decimal('50005000')
        self.sell_limitation.save()

        # Create a previous trade to contribute to total_traded_amount
        trade = self.create_trade(
            src_currency=self.btc_usdt_market.base_currency,
            dst_currency=self.btc_usdt_market.quote_currency,
            src_amount=Decimal('5000'),
            dst_amount=Decimal('50000000'),
            created_at=ir_now(),
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            user=self.user_1,
        )

        amount = self.sell_limitation.max_amount - trade.dst_amount
        is_sell = True
        limit_exceeded = self.btc_usdt_market.has_market_exceeded_limit(
            amount=amount, is_sell=is_sell, reference_currency=Currencies.usdt
        )
        assert not limit_exceeded  # Assuming equal to limit does not exceed

    def test_amount_conversion_when_reference_currency_is_the_base_currency(self):
        self.sell_limitation.max_amount = Decimal('70000')  # 1 btc is 71407
        self.sell_limitation.save()

        # Reference currency is base_currency (BTC)
        reference_currency = self.btc_usdt_market.base_currency

        amount = Decimal('1')  # 1 BTC
        is_sell = True

        limit_exceeded = self.btc_usdt_market.has_market_exceeded_limit(
            amount=amount, is_sell=is_sell, reference_currency=reference_currency
        )

        # Since total_traded_amount is zero, the converted amount should not exceed the limit
        assert not limit_exceeded

    def test_market_limit_in_usdtrls_market_when_reference_is_usdt_sell(self):
        MarketLimitation.objects.create(
            interval=1,
            max_amount=Decimal('5.0'),
            market=self.usdt_rls_market,
            is_active=True,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        self.create_trade(
            user=self.user_1,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=Decimal('3'),
            dst_amount=Decimal('2100000'),
        )
        self.create_trade(
            user=self.user_2,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=Decimal('1'),
            dst_amount=Decimal('700000'),
        )
        # create buy trade must be ignored
        self.create_trade(
            user=self.user_2,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=Decimal('2'),
            dst_amount=Decimal('1400000'),
        )
        # total trades 3 + 1 = 4, limitation is 5, rest is 5 - 4 = 1
        assert not self.usdt_rls_market.has_market_exceeded_limit(
            Decimal('1'), is_sell=True, reference_currency=Currencies.usdt
        )
        assert self.usdt_rls_market.has_market_exceeded_limit(
            Decimal('2'), is_sell=True, reference_currency=Currencies.usdt
        )
        # check buy usdtrls market
        assert not self.usdt_rls_market.has_market_exceeded_limit(
            Decimal('10'), is_sell=False, reference_currency=Currencies.usdt
        )

    def test_market_limit_in_usdtrls_market_when_reference_is_rls_sell(self):
        MarketLimitation.objects.create(
            interval=1,
            max_amount=Decimal('5.0'),
            market=self.usdt_rls_market,
            is_active=True,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        self.create_trade(
            user=self.user_1,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=Decimal('3'),
            dst_amount=Decimal('2100000'),
        )
        self.create_trade(
            user=self.user_2,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=Decimal('1'),
            dst_amount=Decimal('700000'),
        )
        # create buy trade must be ignored
        self.create_trade(
            user=self.user_2,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=Decimal('2'),
            dst_amount=Decimal('1400000'),
        )
        # total trades 3 + 1 = 4, limitation is 5, rest is 5 - 4 = 1
        assert not self.usdt_rls_market.has_market_exceeded_limit(
            Decimal('670000'), reference_currency=Currencies.rls, is_sell=True
        )  # about 1 usdt price
        assert self.usdt_rls_market.has_market_exceeded_limit(
            Decimal('700000'), reference_currency=Currencies.rls, is_sell=True
        )  # more than 1 usdt
        # check buy usdt-rls market
        assert not self.usdt_rls_market.has_market_exceeded_limit(
            Decimal('96600000'), is_sell=False, reference_currency=Currencies.rls
        )


class TestMarketStrategies(BaseMarketLimitationTest):
    def setUp(self):
        self.usdt_rls_market = self.create_usdt_rls_market()
        self.btc_usdt_market = self.create_btc_usdt_market()
        self.input_amount = Decimal('100')

    def test_usdtrls_amount_reference_equals_quote_currency_sell(self):
        strategy = USDTRLSStrategyInLimitation(
            market=self.usdt_rls_market, input_amount=self.input_amount, is_sell=True, reference_currency=Currencies.rls
        )
        expected_amount = self.input_amount * self.usdt_rls_market.quote_to_base_price_sell
        assert strategy.amount == expected_amount

    def test_usdtrls_amount_reference_equals_quote_currency_buy(self):
        strategy = USDTRLSStrategyInLimitation(
            market=self.usdt_rls_market,
            input_amount=self.input_amount,
            is_sell=False,
            reference_currency=Currencies.rls,
        )
        expected_amount = self.input_amount * self.usdt_rls_market.quote_to_base_price_buy
        assert strategy.amount == expected_amount

    def test_usdtrls_amount_reference_not_equals_quote_currency(self):
        strategy = USDTRLSStrategyInLimitation(
            market=self.usdt_rls_market,
            input_amount=self.input_amount,
            is_sell=True,
            reference_currency=Currencies.usdt,
        )
        expected_amount = self.input_amount
        assert strategy.amount == expected_amount

    def test_usdtrls_amount_field(self):
        strategy = USDTRLSStrategyInLimitation(
            market=self.usdt_rls_market,
            input_amount=self.input_amount,
            is_sell=True,
            reference_currency=self.usdt_rls_market.quote_currency,
        )
        assert strategy.amount_field == 'src_amount'

    def test_default_market_amount_reference_equals_base_currency_sell(self):
        strategy = DefaultStrategyInLimitation(
            market=self.btc_usdt_market, input_amount=self.input_amount, is_sell=True, reference_currency=Currencies.btc
        )
        expected_amount = self.input_amount * self.btc_usdt_market.base_to_quote_price_sell
        assert strategy.amount == expected_amount

    def test_default_market_amount_reference_equals_base_currency_buy(self):
        strategy = DefaultStrategyInLimitation(
            market=self.btc_usdt_market,
            input_amount=self.input_amount,
            is_sell=False,
            reference_currency=Currencies.btc,
        )
        expected_amount = self.input_amount * self.btc_usdt_market.base_to_quote_price_buy
        assert strategy.amount == expected_amount

    def test_default_market_amount_reference_not_equals_base_currency(self):
        strategy = DefaultStrategyInLimitation(
            market=self.btc_usdt_market,
            input_amount=self.input_amount,
            is_sell=True,
            reference_currency=Currencies.usdt,
        )
        expected_amount = self.input_amount
        assert strategy.amount == expected_amount

    def test_default_amount_field(self):
        strategy = DefaultStrategyInLimitation(
            market=self.btc_usdt_market,
            input_amount=self.input_amount,
            is_sell=False,
            reference_currency=self.btc_usdt_market.base_currency,
        )
        assert strategy.amount_field == 'dst_amount'

    def test_usdtrls_reference_currency_unexpected_value(self):
        with self.assertRaises(ValueError):
            USDTRLSStrategyInLimitation(
                market=self.usdt_rls_market,
                input_amount=self.input_amount,
                is_sell=True,
                reference_currency=999,  # An unexpected currency ID
            )

    def test_default_reference_currency_unexpected_value(self):
        with self.assertRaises(ValueError):
            DefaultStrategyInLimitation(
                market=self.btc_usdt_market,
                input_amount=self.input_amount,
                is_sell=False,
                reference_currency=999,  # An unexpected currency ID
            )

    def test_usdtrls_is_sell_true_false(self):
        strategy_sell = USDTRLSStrategyInLimitation(
            market=self.usdt_rls_market, input_amount=self.input_amount, is_sell=True, reference_currency=Currencies.rls
        )
        expected_amount_sell = self.input_amount * self.usdt_rls_market.quote_to_base_price_sell
        assert strategy_sell.amount == expected_amount_sell

        strategy_buy = USDTRLSStrategyInLimitation(
            market=self.usdt_rls_market,
            input_amount=self.input_amount,
            is_sell=False,
            reference_currency=Currencies.rls,
        )
        expected_amount_buy = self.input_amount * self.usdt_rls_market.quote_to_base_price_buy
        assert strategy_buy.amount == expected_amount_buy

    def test_default_is_sell_true_false(self):
        strategy_sell = DefaultStrategyInLimitation(
            market=self.btc_usdt_market, input_amount=self.input_amount, is_sell=True, reference_currency=Currencies.btc
        )
        expected_amount_sell = self.input_amount * self.btc_usdt_market.base_to_quote_price_sell
        assert strategy_sell.amount == expected_amount_sell

        strategy_buy = DefaultStrategyInLimitation(
            market=self.btc_usdt_market,
            input_amount=self.input_amount,
            is_sell=False,
            reference_currency=Currencies.btc,
        )
        expected_amount_buy = self.input_amount * self.btc_usdt_market.base_to_quote_price_buy
        assert strategy_buy.amount == expected_amount_buy

    def test_usdtrls_reference_currency_is_base_currency(self):
        strategy = USDTRLSStrategyInLimitation(
            market=self.usdt_rls_market,
            input_amount=self.input_amount,
            is_sell=True,
            reference_currency=Currencies.usdt,  # base_currency
        )
        expected_amount = self.input_amount
        assert strategy.amount == expected_amount

    def test_default_reference_currency_is_quote_currency(self):
        strategy = DefaultStrategyInLimitation(
            market=self.btc_usdt_market,
            input_amount=self.input_amount,
            is_sell=False,
            reference_currency=Currencies.usdt,  # quote_currency
        )
        expected_amount = self.input_amount
        assert strategy.amount == expected_amount


class TestCalculateConsumedPercentages(BaseMarketLimitationTest):
    def setUp(self):
        self.btc_usdt_market = self.create_btc_usdt_market()
        self.usdt_rls_market = self.create_usdt_rls_market()

        self.market_btsusdt_sell_limitation = MarketLimitation.objects.create(
            interval=1,
            max_amount=Decimal('100.0'),
            market=self.btc_usdt_market,
            is_active=True,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        self.market_btsusdt_buy_limitation = MarketLimitation.objects.create(
            interval=1,
            max_amount=Decimal('120.0'),
            market=self.btc_usdt_market,
            is_active=True,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        self.market_usdtrls_sell_limitation = MarketLimitation.objects.create(
            interval=1,
            max_amount=Decimal('500.0'),
            market=self.usdt_rls_market,
            is_active=True,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        self.market_usdtrls_buy_limitation = MarketLimitation.objects.create(
            interval=1,
            max_amount=Decimal('550.0'),
            market=self.usdt_rls_market,
            is_active=True,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        self.user = User.objects.create(username='testalitaqvazade', password='<PASSWORD>')

    def test_calculate_successful(self):
        self._create_sample_trades()
        percentages = calculate_market_consumption_percentage()
        assert ConsumedPercentageOfMarket(symbol='BTCUSDT', percentage=Decimal('75.00'), is_sell=False) in percentages
        assert ConsumedPercentageOfMarket(symbol='BTCUSDT', percentage=Decimal('90.0'), is_sell=True) in percentages
        assert (
            ConsumedPercentageOfMarket(
                symbol='USDTRLS', percentage=Decimal('100.1818181818181818181818182'), is_sell=False
            )
            in percentages
        )
        assert ConsumedPercentageOfMarket(symbol='USDTRLS', percentage=Decimal('0.200'), is_sell=True) in percentages

    @patch('exchange.xchange.crons.Notification.notify_admins')
    def test_call_notify_admin_in_cron_successful(self, notify_admins_mock):
        self._create_sample_trades()
        XchangeNotifyAdminOnMarketApproachingLimitsCron().run()
        notify_admins_mock.assert_called_once()

        _, call_kwargs = notify_admins_mock.call_args
        called_message = call_kwargs['message']

        assert '🚨درصد مصرف شده‌ی بازار‌ها🚨:' in called_message
        assert '- BTCUSDT buy 75.0%' in called_message
        assert '- BTCUSDT sell 90.0%' in called_message
        assert '- USDTRLS buy 100.2%' in called_message

        assert call_kwargs['title'] == 'هشدار بازار‌های صرافی 🔔'
        assert call_kwargs['channel'] == "important_xchange"

    def _create_sample_trades(self):
        self.create_trade(
            src_currency=self.btc_usdt_market.base_currency,
            dst_currency=self.btc_usdt_market.quote_currency,
            src_amount=Decimal('1'),
            dst_amount=Decimal('90'),
            created_at=ir_now(),
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            user=self.user,
        )
        self.create_trade(
            src_currency=self.btc_usdt_market.base_currency,
            dst_currency=self.btc_usdt_market.quote_currency,
            src_amount=Decimal('1'),
            dst_amount=Decimal('90'),
            created_at=ir_now(),
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            user=self.user,
        )
        self.create_trade(
            src_currency=self.usdt_rls_market.base_currency,
            dst_currency=self.usdt_rls_market.quote_currency,
            src_amount=Decimal('1'),
            dst_amount=Decimal('80000'),
            created_at=ir_now(),
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            user=self.user,
        )
        self.create_trade(
            src_currency=self.usdt_rls_market.base_currency,
            dst_currency=self.usdt_rls_market.quote_currency,
            src_amount=Decimal('1'),
            dst_amount=Decimal('79000'),
            created_at=ir_now(),
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            user=self.user,
        )
        self.create_trade(
            src_currency=self.usdt_rls_market.base_currency,
            dst_currency=self.usdt_rls_market.quote_currency,
            src_amount=Decimal('550'),  # 550 + 1 = 551 but limitation is 550
            dst_amount=Decimal('79000000'),
            created_at=ir_now(),
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            user=self.user,
        )
