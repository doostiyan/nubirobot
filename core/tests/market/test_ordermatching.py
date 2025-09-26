from decimal import Decimal

from django.test import TestCase

from exchange.base.models import Currencies
from exchange.accounts.models import User
from exchange.market.models import Market, OrderMatching
from ..base.utils import create_trade


class MarketTest(TestCase):

    def setUp(self):
        self.user1 = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)

    def test_is_market_cached(self):
        trade = OrderMatching(market_id=1)
        assert not trade.is_market_cached
        trade = OrderMatching(market=Market.objects.get(id=2))
        assert trade.is_market_cached
        trade = create_trade(self.user1, self.user2, amount=Decimal('0.032'), price=Decimal('2.7e9'))
        assert trade.is_market_cached
        trade.refresh_from_db()
        assert not trade.is_market_cached
        assert trade.market_id == 1
        assert not trade.is_market_cached
        assert trade.market.id == 1
        assert trade.is_market_cached

    def test_src_currency(self):
        # Assign from DB
        trade = OrderMatching(market_id=1)
        assert not trade.is_market_cached
        trade.market = Market.objects.get(id=1)
        assert trade.is_market_cached
        assert trade.market_id == 1
        assert trade.src_currency == Currencies.btc
        assert trade.dst_currency == Currencies.rls

        # Assign from cache
        trade = OrderMatching(market_id=1)
        assert not trade.is_market_cached
        trade = OrderMatching(market_id=1)
        trade.market = Market.get_cached(1)
        assert trade.is_market_cached
        assert trade.market_id == 1
        assert trade.src_currency == Currencies.btc
        assert trade.dst_currency == Currencies.rls
