import datetime
from decimal import Decimal
from unittest import mock

import pytz
from django.core.cache import cache
from django.test import TestCase
from django.utils.timezone import now

from exchange.base.models import Currencies, Settings
from exchange.market.marketmanager import MarketManager
from exchange.market.models import Market


class MarketTest(TestCase):

    def test_get_cached(self):
        market1 = Market.get_cached(1)
        assert market1.src_currency == Currencies.btc
        assert market1.dst_currency == Currencies.rls
        assert market1.is_active
        market1 = cache.get('object_market_1')
        assert isinstance(market1, Market)
        assert market1.src_currency == Currencies.btc
        assert market1.dst_currency == Currencies.rls
        assert market1.is_active
        market2 = Market.get_cached(8)
        assert market2.src_currency == Currencies.eth
        assert market2.dst_currency == Currencies.usdt
        assert market2.is_active

    def test_by_symbol(self):
        assert Market.by_symbol('BTCUSD') is None
        assert Market.by_symbol('BTCRLS') is None
        assert Market.by_symbol('ETHBTC') is None
        market = Market.by_symbol('BTCIRT')
        assert market.src_currency == Currencies.btc
        assert market.dst_currency == Currencies.rls
        market = Market.by_symbol('BTCUSDT')
        assert market.src_currency == Currencies.btc
        assert market.dst_currency == Currencies.usdt
        market = Market.by_symbol('ETHUSDT')
        assert market.src_currency == Currencies.eth
        assert market.dst_currency == Currencies.usdt
        market = Market.by_symbol('DAIIRT')
        assert market.src_currency == Currencies.dai
        assert market.dst_currency == Currencies.rls
        market = Market.by_symbol('LINKIRT')
        assert market.src_currency == Currencies.link
        assert market.dst_currency == Currencies.rls
        market = Market.by_symbol('LINKUSDT')
        assert market.src_currency == Currencies.link
        assert market.dst_currency == Currencies.usdt
        market = Market.by_symbol('DOGEIRT')
        assert market.src_currency == Currencies.doge
        assert market.dst_currency == Currencies.rls
        market = Market.by_symbol('DOGEUSDT')
        assert market.src_currency == Currencies.doge
        assert market.dst_currency == Currencies.usdt
        market = Market.by_symbol('DOTIRT')
        assert market.src_currency == Currencies.dot
        assert market.dst_currency == Currencies.rls

    def test_get_last_trade_price(self):
        cache.set('market_1_last_price', Decimal('7218649420.0000000000'))
        btcirt = Market.objects.get(id=1)
        assert btcirt.get_last_trade_price() == Decimal('7218649420')
        cache.set('market_7_last_price', Decimal('23951.9900000000'))
        btcusdt = Market.objects.get(id=7)
        assert btcusdt.get_last_trade_price() == Decimal('23951.99')

    def test_alpha_market(self):
        launch_date = now() + datetime.timedelta(hours=3)
        mocked_dict = {Currencies.btc: {'launch_date': launch_date}}
        mocked_launching_currencies = [Currencies.btc]
        with mock.patch(
            'exchange.market.models.LAUNCHING_CURRENCIES',
            mocked_launching_currencies,
        ) as _, mock.patch.dict(
            'exchange.market.models.CURRENCY_INFO',
            mocked_dict,
        ):
            btc_irt = Market.objects.get(id=1)
            assert btc_irt.is_alpha
            assert (
                MarketManager.get_market_promotion_end_date(
                    btc_irt.src_currency,
                    btc_irt.dst_currency,
                )
                == launch_date + datetime.timedelta(days=3)
            )

    def test_launched_market(self):
        launch_date = now() - datetime.timedelta(hours=3)
        mocked_dict = {Currencies.btc: {'launch_date': launch_date}}
        mocked_launching_currencies = [Currencies.btc]
        with mock.patch(
            'exchange.market.models.LAUNCHING_CURRENCIES',
            mocked_launching_currencies,
        ) as _, mock.patch.dict(
            'exchange.market.models.CURRENCY_INFO',
            mocked_dict,
        ):
            btc_irt = Market.objects.get(id=1)
            assert not btc_irt.is_alpha
            assert (
                MarketManager.get_market_promotion_end_date(
                    btc_irt.src_currency,
                    btc_irt.dst_currency,
                )
                == launch_date + datetime.timedelta(days=3)
            )

    def test_promote_market(self):
        launch_date = now() + datetime.timedelta(hours=3)
        mocked_dict = {
            Currencies.btc: {
                'launch_date': launch_date,
                'promote_date': launch_date + datetime.timedelta(days=1),
            },
        }
        mocked_launching_currencies = [Currencies.btc]
        with mock.patch(
            'exchange.market.models.LAUNCHING_CURRENCIES',
            mocked_launching_currencies,
        ) as _, mock.patch.dict(
            'exchange.market.models.CURRENCY_INFO',
            mocked_dict,
        ):
            btc_irt = Market.objects.get(id=1)
            assert btc_irt.is_alpha
            assert (
                MarketManager.get_market_promotion_end_date(
                    btc_irt.src_currency,
                    btc_irt.dst_currency,
                )
                == launch_date + datetime.timedelta(days=1)
            )

    def test_normal_market(self):
        btc_irt = Market.objects.get(id=1)
        assert not btc_irt.is_alpha
        assert (
            MarketManager.get_market_promotion_end_date(
                btc_irt.src_currency,
                btc_irt.dst_currency,
            )
            == pytz.utc.localize(datetime.datetime.min) + datetime.timedelta(days=3)
        )

    def test_temporal_alpha_market(self):
        btc_irt = Market.objects.get(id=1)
        assert not btc_irt.is_alpha

        Market.get_temporal_alpha_markets.clear()
        Settings.set_cached_json('temporal_alpha_markets', ['BTCIRT'])
        assert btc_irt.is_alpha

        # Cleanup
        Market.get_temporal_alpha_markets.clear()
        Settings.set_cached_json('temporal_alpha_markets', [])
