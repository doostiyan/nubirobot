import datetime
from decimal import Decimal
from unittest.mock import patch

import responses
from django.core.cache import cache
from django.test import TestCase

from exchange.base.calendar import ir_now
from exchange.base.models import PRICE_PRECISIONS, Currencies
from exchange.base.serializers import serialize_timestamp
from exchange.market.markprice import BinanceExchange, InternalExchange, MarkPriceCalculator, OKXExchange
from exchange.market.models import Market


class MarkPriceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usdt_price_cache_key = f'market_{Market.by_symbol("USDTIRT").id}_last_price'

    def setUp(self):
        self.USDT_PRICE = 270000
        cache.set(self.usdt_price_cache_key, self.USDT_PRICE)

    def tearDown(self):
        MarkPriceCalculator.delete_mark_price(Currencies.btc)
        MarkPriceCalculator.delete_mark_price(Currencies.shib)

    @staticmethod
    def _set_external_prices(exchange_name: str, update_time: datetime.datetime, **prices):
        response = [{'symbol': f'{currency.upper()}USDT', 'price': str(price)} for currency, price in prices.items()]
        response.append({'symbol': 'LASTUPDATE', 'price': str(int(update_time.timestamp()))})
        responses.get(url=f'https://cdn.nobitex.ir/data/prices/{exchange_name}-spot.json', json=response)

    @classmethod
    def set_binance_prices(cls, update_time: datetime.datetime, **prices):
        cls._set_external_prices('binance', update_time, **prices)

    @classmethod
    def set_okx_prices(cls, update_time: datetime.datetime, **prices):
        cls._set_external_prices('okx', update_time, **prices)

    @staticmethod
    def set_internal_prices(symbol, sell_price, buy_price, update_time: datetime.datetime):
        cache.set(f'orderbook_{symbol}_best_active_sell', Decimal(sell_price))
        cache.set(f'orderbook_{symbol}_best_active_buy', Decimal(buy_price))
        cache.set(f'orderbook_{symbol}_update_time', str(serialize_timestamp(update_time)))

    @staticmethod
    def _error_external_prices(exchange_name: str):
        responses.get(url=f'https://cdn.nobitex.ir/data/prices/{exchange_name}-spot.json', status=400)

    @classmethod
    def error_binance_prices(cls):
        cls._error_external_prices('binance')

    @classmethod
    def error_okx_prices(cls):
        cls._error_external_prices('okx')

    @staticmethod
    def flush_internal_prices(symbol):
        cache.delete_many(
            f'orderbook_{symbol}_{param}'
            for param in ('best_active_sell', 'best_active_buy', 'last_trade_price', 'update_time')
        )

    @responses.activate
    def test_get_mark_price_usdt_price(self):
        now = ir_now()
        self.set_binance_prices(update_time=now)
        self.set_okx_prices(update_time=now)
        self.set_internal_prices('USDTIRT', 270500, 266000, update_time=now)

        calculator = MarkPriceCalculator()

        assert calculator.get_mark_price(Currencies.usdt, Currencies.rls) is None
        calculator.set_mark_price(Currencies.usdt)
        # USDTIRT mark price should always be equal to Nobitex's last_price
        assert calculator.get_mark_price(Currencies.usdt, Currencies.rls) == self.USDT_PRICE

    @responses.activate
    def test_get_mark_price_three_price_in_tune(self):
        now = ir_now()
        self.set_binance_prices(btc=48985.5, eth=1787.56, update_time=now)
        self.set_okx_prices(btc=49276.566, eth=1772.8078, update_time=now)
        self.set_internal_prices('BTCUSDT', 48782, 48781, update_time=now)

        calculator = MarkPriceCalculator()

        calculator.set_mark_price(Currencies.btc)
        expected_mark_price = (
            (
                Decimal('48985.5') * 45
                + Decimal('49276.566') * 45
                + (Decimal(sum([48782, 48781])) / 2).quantize(PRICE_PRECISIONS.get('BTCUSDT')) * 10
            )
            / 100
        ).quantize(PRICE_PRECISIONS.get('BTCUSDT'))
        assert calculator.get_mark_price(Currencies.btc, Currencies.usdt) == expected_mark_price

        expected_mark_price *= self.USDT_PRICE
        assert calculator.get_mark_price(Currencies.btc, Currencies.rls) == expected_mark_price

    @responses.activate
    def test_get_mark_price_one_distant_price(self):
        now = ir_now()
        self.set_binance_prices(btc=48985.5, eth=1787.56, update_time=now)
        self.set_okx_prices(btc=49276.566, eth=1772.8078, update_time=now)
        # Sell shadow
        self.set_internal_prices('BTCUSDT', 53782, 50781, update_time=now)

        calculator = MarkPriceCalculator()

        calculator.set_mark_price(Currencies.btc)
        expected_mark_price = (
            (Decimal('48985.5') * 45 + Decimal('49276.566') * 45 + (Decimal('49276.566') * Decimal('1.05')) * 10) / 100
        ).quantize(PRICE_PRECISIONS.get('BTCUSDT'))
        assert calculator.get_mark_price(Currencies.btc, Currencies.usdt) == expected_mark_price

        expected_mark_price *= self.USDT_PRICE
        assert calculator.get_mark_price(Currencies.btc, Currencies.rls) == expected_mark_price

    @responses.activate
    def test_get_mark_price_two_distant_prices(self):
        now = ir_now()
        self.set_binance_prices(btc=48985.5, eth=1787.56, update_time=now)
        self.set_okx_prices(btc=45276.566, eth=1772.8078, update_time=now)
        self.set_internal_prices('BTCUSDT', 53782, 50781, update_time=now)

        calculator = MarkPriceCalculator()

        calculator.set_mark_price(Currencies.btc)
        expected_mark_price = (
            (
                Decimal('48985.5') * 45
                + Decimal('48985.5') * Decimal('0.95') * 45
                + Decimal('48985.5') * Decimal('1.05') * 10
            )
            / 100
        ).quantize(PRICE_PRECISIONS.get('BTCUSDT'))
        assert calculator.get_mark_price(Currencies.btc, Currencies.usdt) == expected_mark_price

    @responses.activate
    def test_get_mark_price_one_price_expired(self):
        now = ir_now()
        self.set_binance_prices(btc=48985.5, eth=1787.56, update_time=now)
        self.set_okx_prices(btc=49276.566, eth=1772.8078, update_time=now - datetime.timedelta(seconds=65))
        self.set_internal_prices('BTCUSDT', 48782, 48781, update_time=now)

        calculator = MarkPriceCalculator()

        calculator.set_mark_price(Currencies.btc)
        expected_mark_price = (
            (
                Decimal('48985.5') * 45
                + (Decimal(sum([48782, 48781])) / 2).quantize(PRICE_PRECISIONS.get('BTCUSDT')) * 10
            )
            / 55
        ).quantize(PRICE_PRECISIONS.get('BTCUSDT'))
        assert calculator.get_mark_price(Currencies.btc, Currencies.usdt) == expected_mark_price

        expected_mark_price *= self.USDT_PRICE
        assert calculator.get_mark_price(Currencies.btc, Currencies.rls) == expected_mark_price

    @responses.activate
    def test_get_mark_price_two_prices_expired(self):
        now = ir_now()
        self.set_binance_prices(btc=48985.5, eth=1787.56, update_time=now - datetime.timedelta(seconds=65))
        self.set_okx_prices(btc=49276.566, eth=1772.8078, update_time=now - datetime.timedelta(seconds=75))
        self.set_internal_prices('BTCUSDT', 48782, 48781, update_time=now)

        calculator = MarkPriceCalculator()

        calculator.set_mark_price(Currencies.btc)
        expected_mark_price = (
            (Decimal(sum([48782, 48781])) / 2).quantize(PRICE_PRECISIONS.get('BTCUSDT')) * 10 / 10
        ).quantize(PRICE_PRECISIONS.get('BTCUSDT'))
        assert calculator.get_mark_price(Currencies.btc, Currencies.usdt) == expected_mark_price

        expected_mark_price *= self.USDT_PRICE
        assert calculator.get_mark_price(Currencies.btc, Currencies.rls) == expected_mark_price

    @responses.activate
    def test_get_mark_price_all_prices_expired(self):
        past = ir_now() - datetime.timedelta(seconds=70)
        self.set_binance_prices(btc=48985.5, eth=1787.56, update_time=past)
        self.set_okx_prices(btc=49276.566, eth=1772.8078, update_time=past)
        self.set_internal_prices('BTCUSDT', 48782, 48781, update_time=past)

        calculator = MarkPriceCalculator()

        calculator.set_mark_price(Currencies.btc)
        assert calculator.get_mark_price(Currencies.btc, Currencies.usdt) is None
        assert calculator.get_mark_price(Currencies.btc, Currencies.rls) is None

    @responses.activate
    def test_get_mark_price_service_stops(self):
        near_past = ir_now() - datetime.timedelta(seconds=40)
        self.set_binance_prices(btc=48985.5, eth=1787.56, update_time=near_past)
        self.set_okx_prices(btc=49276.566, eth=1772.8078, update_time=near_past)
        self.set_internal_prices('BTCUSDT', 48782, 48781, update_time=near_past)

        calculator = MarkPriceCalculator()
        calculator.set_mark_price(Currencies.btc)
        calculator.set_mark_price(Currencies.btc)

        near_future = ir_now() + datetime.timedelta(seconds=30)
        with patch('exchange.market.markprice.ir_now', return_value=near_future):
            calculator = MarkPriceCalculator()
            calculator.set_mark_price(Currencies.btc)

            assert calculator.get_mark_price(Currencies.btc, Currencies.usdt) is not None
            assert calculator.get_mark_price(Currencies.btc, Currencies.rls) is not None

    @responses.activate
    def test_get_mark_price_one_missing_price(self):
        now = ir_now()
        self.set_binance_prices(eth=1787.56, update_time=now)
        self.set_okx_prices(btc=49276.566, eth=1772.8078, update_time=now)
        self.set_internal_prices('BTCUSDT', 48782, 48781, update_time=now)

        calculator = MarkPriceCalculator()

        calculator.set_mark_price(Currencies.btc)
        expected_mark_price = (
            (
                Decimal('49276.566') * 45
                + (Decimal(sum([48782, 48781])) / 2).quantize(PRICE_PRECISIONS.get('BTCUSDT')) * 10
            )
            / 55
        ).quantize(PRICE_PRECISIONS.get('BTCUSDT'))
        assert calculator.get_mark_price(Currencies.btc, Currencies.usdt) == expected_mark_price

        expected_mark_price *= self.USDT_PRICE
        assert calculator.get_mark_price(Currencies.btc, Currencies.rls) == expected_mark_price

    @responses.activate
    def test_get_mark_price_two_missing_prices(self):
        self.set_binance_prices(btc=48985.5, eth=1787.56, update_time=ir_now())
        self.error_okx_prices()
        self.flush_internal_prices('BTCUSDT')
        self.flush_internal_prices('BTCIRT')

        calculator = MarkPriceCalculator()

        calculator.set_mark_price(Currencies.btc)
        expected_mark_price = (Decimal('48985.5') * 45 / 45).quantize(PRICE_PRECISIONS.get('BTCUSDT'))
        assert calculator.get_mark_price(Currencies.btc, Currencies.usdt) == expected_mark_price

        expected_mark_price *= self.USDT_PRICE
        assert calculator.get_mark_price(Currencies.btc, Currencies.rls) == expected_mark_price

    @responses.activate
    def test_get_mark_price_all_prices_missing(self):
        self.set_binance_prices(eth=1787.56, update_time=ir_now())
        self.error_okx_prices()
        self.flush_internal_prices('BTCUSDT')
        self.flush_internal_prices('BTCIRT')

        calculator = MarkPriceCalculator()

        calculator.set_mark_price(Currencies.btc)
        assert calculator.get_mark_price(Currencies.btc, Currencies.usdt) is None
        assert calculator.get_mark_price(Currencies.btc, Currencies.rls) is None

    @responses.activate
    def test_get_mark_price_one_missing_and_one_distant_price(self):
        now = ir_now()
        self.set_binance_prices(eth=1787.56, update_time=now)
        self.set_okx_prices(btc=49276.566, eth=1772.8078, update_time=now)
        self.set_internal_prices('BTCUSDT', 53782, 50781, update_time=now)

        calculator = MarkPriceCalculator()

        calculator.set_mark_price(Currencies.btc)
        expected_mark_price = (
            (
                Decimal('49276.566') * 45 + (Decimal('49276.566') * Decimal('1.05')) * 10
            )
            / 55
        ).quantize(PRICE_PRECISIONS.get('BTCUSDT'))
        assert calculator.get_mark_price(Currencies.btc, Currencies.usdt) == expected_mark_price

        expected_mark_price *= self.USDT_PRICE
        assert calculator.get_mark_price(Currencies.btc, Currencies.rls) == expected_mark_price

    @responses.activate
    def test_get_mark_price_rial_market_with_usdt_price_missing(self):
        now = ir_now()
        self.set_binance_prices(btc=48985.5, eth=1787.56, update_time=now)
        self.set_okx_prices(btc=49276.566, eth=1772.8078, update_time=now)
        cache.delete(self.usdt_price_cache_key)

        calculator = MarkPriceCalculator()

        calculator.set_mark_price(Currencies.btc)
        assert calculator.get_mark_price(Currencies.btc, Currencies.rls) is None

    @responses.activate
    def test_get_mark_price_internal_price_calculation(self):
        self.error_binance_prices()
        self.error_okx_prices()
        self.set_internal_prices('BTCUSDT', 48782, 48781, ir_now())

        calculator = MarkPriceCalculator()

        calculator.set_mark_price(Currencies.btc)
        expected_mark_price = (
            (Decimal(sum([48782, 48781])) / 2).quantize(PRICE_PRECISIONS.get('BTCUSDT')) * 10 / 10
        ).quantize(PRICE_PRECISIONS.get('BTCUSDT'))
        assert calculator.get_mark_price(Currencies.btc, Currencies.usdt) == expected_mark_price

        cache.delete('orderbook_BTCUSDT_best_active_sell')
        calculator.set_mark_price(Currencies.btc)
        expected_mark_price = ((Decimal(48781)).quantize(PRICE_PRECISIONS.get('BTCUSDT')) * 10 / 10).quantize(
            PRICE_PRECISIONS.get('BTCUSDT')
        )
        assert calculator.get_mark_price(Currencies.btc, Currencies.usdt) == expected_mark_price

        cache.delete('orderbook_BTCUSDT_best_active_buy')
        calculator.delete_mark_price(Currencies.btc)
        calculator.set_mark_price(Currencies.btc)
        assert calculator.get_mark_price(Currencies.btc, Currencies.usdt) is None

    @responses.activate
    def test_get_mark_price_for_scaled_markets(self):
        now = ir_now()
        self.set_binance_prices(shib=0.000010880, eth=1787.56, update_time=now)
        self.set_okx_prices(shib=0.000010880, eth=1772.8078, update_time=now)
        self.set_internal_prices('SHIBUSDT', 0.01088, 0.01088, update_time=now)

        calculator = MarkPriceCalculator()

        calculator.set_mark_price(Currencies.shib)
        expected_mark_price = (
            (
                Decimal('0.000010880') * 45 * Decimal(1000)
                + Decimal('0.000010880') * 45 * Decimal(1000)
                + (sum([Decimal('0.01088'), Decimal('0.01088')]) / 2).quantize(PRICE_PRECISIONS.get('SHIBUSDT')) * 10
            )
            / 100
        ).quantize(PRICE_PRECISIONS.get('SHIBUSDT'))
        assert calculator.get_mark_price(Currencies.shib, Currencies.usdt) == expected_mark_price == Decimal('0.01088')

    @responses.activate
    def test_get_mark_price_binance_prices(self):
        now = ir_now()
        self.set_binance_prices(btc='48985.5', update_time=now)
        exchange = BinanceExchange()
        price = exchange.get_price(Currencies.btc)
        assert price.value == Decimal('48985.5')
        assert price.weight == 45
        assert price.is_valid()
        with patch('exchange.market.markprice.ir_now', return_value=now + datetime.timedelta(seconds=65)):
            assert not price.is_valid()

    @responses.activate
    def test_get_mark_price_okx_prices(self):
        now = ir_now()
        self.set_okx_prices(btc='49276.566', update_time=now)
        exchange = OKXExchange()
        price = exchange.get_price(Currencies.btc)
        assert price.value == Decimal('49276.566')
        assert price.weight == 45
        assert price.is_valid()
        with patch('exchange.market.markprice.ir_now', return_value=now + datetime.timedelta(seconds=65)):
            assert not price.is_valid()

    def test_get_mark_price_nobitex_prices(self):
        now = ir_now()
        self.set_internal_prices('BTCUSDT', 48782, 48781, ir_now())
        price_mean = (Decimal(48782) + Decimal(48781)) / 2
        exchange = InternalExchange()
        price = exchange.get_price(Currencies.btc)
        assert price.value == price_mean.quantize(PRICE_PRECISIONS.get('BTCUSDT'))
        assert price.weight == 10
        assert price.is_valid()
        with patch('exchange.market.markprice.ir_now', return_value=now + datetime.timedelta(seconds=65)):
            assert not price.is_valid()
