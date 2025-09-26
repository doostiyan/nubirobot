import random
import string
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import Notification, User
from exchange.base.models import Currencies
from exchange.xchange.constants import XCHANGE_PAIR_PRICES_CACHE_KEY
from exchange.xchange.models import ExchangeTrade, MarketStatus


class SignalsTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        Notification.objects.filter(user=self.user).delete()

    def test_send_notification_for_newly_created_trade(self):
        assert Notification.objects.filter(user=self.user).count() == 0
        self._create_xchange_trade()
        trade_notifs = Notification.objects.filter(user=self.user)
        assert len(trade_notifs) == 1
        assert trade_notifs[0].message == 'تبدیل انجام شد: فروش 10.123456 بیت‌کوین'

    def test_send_notification_for_status_changed_to_succeeded(self):
        trade = self._create_xchange_trade(status=ExchangeTrade.STATUS.unknown, is_sell=False)
        assert Notification.objects.filter(user=self.user).count() == 0
        trade.status = ExchangeTrade.STATUS.succeeded
        trade.save()
        trade_notifs = Notification.objects.filter(user=self.user)
        assert len(trade_notifs) == 1
        assert trade_notifs[0].message == 'تبدیل انجام شد: خرید 10.123456 بیت‌کوین'

    def test_send_trade_notification_for_different_currencies(self):
        self._create_xchange_trade(src_currency=Currencies.rls, is_sell=False)
        self._create_xchange_trade(src_currency=Currencies.usdt, is_sell=True)
        self._create_xchange_trade(src_currency=Currencies.eth, src_amount=Decimal('0.12'), is_sell=False)
        trade_notifs = Notification.objects.filter(user=self.user).order_by('pk')
        assert len(trade_notifs) == 3
        assert trade_notifs[0].message == 'تبدیل انجام شد: خرید 10 ﷼'
        assert trade_notifs[1].message == 'تبدیل انجام شد: فروش 10.12 تتر'
        assert trade_notifs[2].message == 'تبدیل انجام شد: خرید 0.120 اتریوم'

    @patch('exchange.xchange.status_collector.XCHANGE_CURRENCIES', [Currencies.bnt])
    def test_cache_new_xchange_only_price(self):
        bnt_to_usdt_key = XCHANGE_PAIR_PRICES_CACHE_KEY.format(currency=Currencies.bnt, to_currency=Currencies.usdt)
        usdt_to_bnt_key = XCHANGE_PAIR_PRICES_CACHE_KEY.format(currency=Currencies.usdt, to_currency=Currencies.bnt)
        assert cache.get(bnt_to_usdt_key) is None
        assert cache.get(usdt_to_bnt_key) is None

        self._create_or_update_market_status(
            base_currency=Currencies.bnt,
            quote_currency=Currencies.usdt,
            base_to_quote_price_buy=Decimal('0.672357'),
            quote_to_base_price_buy=Decimal('1.4873051073'),
            base_to_quote_price_sell=Decimal('0.658944'),
            quote_to_base_price_sell=Decimal('1.5175796426'),
        )
        bnt_to_usdt_cached_prices = cache.get(bnt_to_usdt_key)
        assert bnt_to_usdt_cached_prices == {
            'buy_price': Decimal('0.672357'),
            'sell_price': Decimal('0.658944'),
        }
        usdt_to_bnt_cached_prices = cache.get(usdt_to_bnt_key)
        assert usdt_to_bnt_cached_prices == {
            'buy_price': Decimal('1.4873051073'),
            'sell_price': Decimal('1.5175796426'),
        }

        self._create_or_update_market_status(
            base_currency=Currencies.bnt,
            quote_currency=Currencies.usdt,
            base_to_quote_price_buy=Decimal('0.670438'),
            quote_to_base_price_buy=Decimal('1.4915622325'),
            base_to_quote_price_sell=Decimal('0.657063'),
            quote_to_base_price_sell=Decimal('1.5219240773'),
        )
        bnt_to_usdt_cached_prices = cache.get(bnt_to_usdt_key)
        assert bnt_to_usdt_cached_prices == {
            'buy_price': Decimal('0.670438'),
            'sell_price': Decimal('0.657063'),
        }
        usdt_to_bnt_cached_prices = cache.get(usdt_to_bnt_key)
        assert usdt_to_bnt_cached_prices == {
            'buy_price': Decimal('1.4915622325'),
            'sell_price': Decimal('1.5219240773'),
        }

    @patch('exchange.xchange.status_collector.XCHANGE_CURRENCIES', [Currencies.bnt])
    def test_dont_cache_new_xchange_price_of_market_coins(self):
        btc_to_usdt_key = XCHANGE_PAIR_PRICES_CACHE_KEY.format(currency=Currencies.btc, to_currency=Currencies.usdt)
        usdt_to_btc_key = XCHANGE_PAIR_PRICES_CACHE_KEY.format(currency=Currencies.usdt, to_currency=Currencies.btc)
        assert cache.get(btc_to_usdt_key) is None
        assert cache.get(usdt_to_btc_key) is None

        self._create_or_update_market_status(
            base_currency=Currencies.btc,
            quote_currency=Currencies.usdt,
            base_to_quote_price_buy=Decimal('61918.353'),
            quote_to_base_price_buy=Decimal('0.0000161503'),
            base_to_quote_price_sell=Decimal('60692.14'),
            quote_to_base_price_sell=Decimal('0.0000164766'),
        )
        assert cache.get(btc_to_usdt_key) is None
        assert cache.get(usdt_to_btc_key) is None

    def _create_xchange_trade(
        self,
        src_currency: int = Currencies.btc,
        dst_currency: int = Currencies.rls,
        src_amount: Decimal = Decimal('10.123456'),
        dst_amount: Decimal = Decimal('1.234'),
        is_sell: bool = True,
        status: int = ExchangeTrade.STATUS.succeeded,
    ) -> ExchangeTrade:
        return ExchangeTrade.objects.create(
            user=self.user,
            status=status,
            is_sell=is_sell,
            src_currency=src_currency,
            dst_currency=dst_currency,
            src_amount=src_amount,
            dst_amount=dst_amount,
            quote_id=''.join(random.choice(string.ascii_letters) for i in range(10)),
            client_order_id=''.join(random.choice(string.ascii_letters) for i in range(10)),
        )

    def _create_or_update_market_status(
        self,
        base_currency: int,
        quote_currency: int,
        base_to_quote_price_buy: Decimal,
        quote_to_base_price_buy: Decimal,
        base_to_quote_price_sell: Decimal,
        quote_to_base_price_sell: Decimal,
    ):
        return MarketStatus.objects.update_or_create(
            base_currency=base_currency,
            quote_currency=quote_currency,
            defaults={
                'base_to_quote_price_buy': base_to_quote_price_buy,
                'quote_to_base_price_buy': quote_to_base_price_buy,
                'base_to_quote_price_sell': base_to_quote_price_sell,
                'quote_to_base_price_sell': quote_to_base_price_sell,
                'min_base_amount': Decimal(1),
                'max_base_amount': Decimal(100),
                'min_quote_amount': Decimal(1),
                'max_quote_amount': Decimal(100),
                'base_precision': Decimal('0.01'),
                'quote_precision': Decimal('0.01'),
                'status': MarketStatus.STATUS_CHOICES.available,
            },
        )

