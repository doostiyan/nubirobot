import datetime
from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.utils.timezone import now

from exchange.accounts.models import User
from exchange.base.coins_info import CURRENCY_INFO
from exchange.base.models import Currencies
from exchange.market.models import Market
from tests.base.utils import create_order, do_matching_round


class MatcherFeesTest(TestCase):
    def setUp(self) -> None:
        self.user1 = User.objects.get(pk=205)
        self.user2 = User.objects.get(pk=206)
        self.market = Market.objects.get(src_currency=Currencies.btc, dst_currency=Currencies.usdt)

    def make_trade(self, *, reinitialize_caches=True, amount=None):
        amount = amount or Decimal('0.002')
        price = Decimal('61234')
        o1 = create_order(
            self.user1,
            self.market.src_currency,
            self.market.dst_currency,
            amount,
            price,
            sell=True,
        )
        o2 = create_order(
            self.user2,
            self.market.src_currency,
            self.market.dst_currency,
            amount,
            price,
            sell=False,
        )
        do_matching_round(self.market, reinitialize_caches=reinitialize_caches)
        o1.refresh_from_db()
        o2.refresh_from_db()
        assert o1.matched_amount == amount
        assert o1.matched_total_price == amount * price
        return o1, o2

    def test_trade_fee_manual_fields(self):
        # Fee Level 0
        o1, o2 = self.make_trade()
        assert o1.fee == Decimal('0.122468')
        assert o2.fee == Decimal('0.0000026')
        # Manual Fee
        self.user1.base_fee_usdt = Decimal('0.05')
        self.user1.save(update_fields=['base_fee_usdt'])
        o1, o2 = self.make_trade()
        assert o1.fee == Decimal('0.061234')
        assert o2.fee == Decimal('0.0000026')
        # More manual fee fields
        self.user1.base_maker_fee_usdt = Decimal('0.04')
        self.user1.save(update_fields=['base_maker_fee_usdt'])
        self.user2.base_fee_usdt = Decimal('0.01')
        self.user2.save(update_fields=['base_fee_usdt'])
        o1, o2 = self.make_trade()
        assert o1.fee == Decimal('0.0489872')
        assert o2.fee == Decimal('0.0000002')

    def test_trade_fee_vip_levels(self):
        # Fee Level 1/2
        cache.set('user_205_vipLevel', 1)
        cache.set('user_206_vipLevel', 2)
        o1, o2 = self.make_trade()
        assert o1.fee == Decimal('0.1163446')
        assert o2.fee == Decimal('0.0000022')
        # Levels should be cached in matcher
        cache.set('user_205_vipLevel', 4)
        cache.set('user_206_vipLevel', 3)
        o1, o2 = self.make_trade(reinitialize_caches=False)
        assert o1.fee == Decimal('0.1163446')
        assert o2.fee == Decimal('0.0000022')
        # Fee Level 3/4
        o1, o2 = self.make_trade()
        assert o1.fee == Decimal('0.0857276')
        assert o2.fee == Decimal('0.000002')
        # Reset fees
        cache.delete('user_205_vipLevel')
        cache.delete('user_206_vipLevel')

    @patch('exchange.market.marketmanager.LAUNCHING_CURRENCIES', [Currencies.glm])
    def test_trade_fee_promotion(self):
        CURRENCY_INFO[Currencies.glm]['promote_date'] = now() + datetime.timedelta(hours=1)
        self.market, _ = Market.objects.get_or_create(
            src_currency=Currencies.glm,
            dst_currency=Currencies.usdt,
            defaults={'is_active': True},
        )
        o1, o2 = self.make_trade(amount=Decimal(1))
        assert o1.fee == Decimal('0')
        assert o2.fee == Decimal('0')
        CURRENCY_INFO[Currencies.glm].pop('promote_date')
