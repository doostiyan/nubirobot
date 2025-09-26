import datetime
from decimal import Decimal
from unittest.mock import patch

import pytz
from django.test import TestCase

from exchange.accounts.models import Notification, User
from exchange.base.calendar import ir_now
from exchange.base.constants import MIN_DATETIME
from exchange.base.models import TETHER, Currencies
from exchange.market.marketmanager import MarketManager
from exchange.market.models import OrderMatching, UserTradeStatus
from tests.base.utils import create_trade


class MarketManagerTest(TestCase):

    def setUp(self):
        self.user1 = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)
        self.user3 = User.objects.get(pk=203)
        self.user4 = User.objects.get(pk=204)

    def test_get_bulk_latest_user_stats(self):
        yesterday = ir_now() - datetime.timedelta(days=1)
        last_month = ir_now() - datetime.timedelta(days=31)
        btc, eth = Currencies.btc, Currencies.eth
        create_trade(
            self.user4,
            self.user2,
            src_currency=btc,
            amount=Decimal('0.01'),
            price=Decimal('2.7e9'),
            created_at=yesterday,
        )
        create_trade(
            self.user4,
            self.user2,
            src_currency=eth,
            amount=Decimal('0.1'),
            price=Decimal('1.4e8'),
            created_at=last_month,
        )
        create_trade(
            self.user3,
            self.user2,
            src_currency=btc,
            amount=Decimal('0.032'),
            price=Decimal('2.65e9'),
            created_at=last_month,
        )
        midnight = ir_now().replace(hour=0, minute=0, second=0, microsecond=0)
        date_from = midnight - datetime.timedelta(days=1)
        missed_days = 1
        MarketManager.get_bulk_latest_user_stats(date_from, missed_days)
        stats = UserTradeStatus.objects.filter(updated_at__gt=midnight)
        assert stats is not None
        assert len(stats) == 3
        stats1 = UserTradeStatus.objects.get(user=self.user4)
        assert stats1.month_trades_total == Decimal('1_300_000_0')
        assert stats1.month_trades_count == Decimal('0')
        stats2 = UserTradeStatus.objects.get(user=self.user3)
        assert stats2.month_trades_total == Decimal('-8_480_000_0')
        assert stats2.month_trades_count == -1

        # test for missed_days more than 7
        missed_days = 10
        date_from = midnight - datetime.timedelta(days=missed_days)
        UserTradeStatus.objects.filter(user__in=[self.user2, self.user3, self.user4]).update(updated_at=date_from)
        MarketManager.get_bulk_latest_user_stats(date_from, missed_days)
        stats1 = UserTradeStatus.objects.get(user=self.user4)
        assert stats1.month_trades_total == Decimal('2_700_000_0')
        assert stats1.month_trades_count == Decimal('1')
        stats2 = UserTradeStatus.objects.get(user=self.user3)
        assert stats2.month_trades_total == Decimal('0')
        assert stats2.month_trades_count == 0

        # test for a user with no related record in userTradeStatus
        new_user = User.objects.create_user(username='new-user')
        create_trade(
            self.user4,
            new_user,
            src_currency=eth,
            amount=Decimal('0.1'),
            price=Decimal('1.4e8'),
            created_at=yesterday,
        )
        MarketManager.get_bulk_latest_user_stats(date_from, missed_days)
        stats = UserTradeStatus.objects.get(user=new_user)
        assert stats.month_trades_total == Decimal('1_400_000_0')
        assert stats.month_trades_count == Decimal('1')
        assert stats.updated_at > midnight

        # test for a user which with updated_at greater than midnight
        UserTradeStatus.objects.filter(user__in=[self.user2, self.user3, self.user4]).update(updated_at=date_from)
        create_trade(
            self.user2,
            new_user,
            src_currency=eth,
            amount=Decimal('0.01'),
            price=Decimal('3.8e8'),
            created_at=yesterday,
        )
        update_time = ir_now()
        MarketManager.get_bulk_latest_user_stats(date_from, missed_days)
        stats = UserTradeStatus.objects.get(user=new_user)
        assert stats.month_trades_total == Decimal('1_400_000_0')
        assert stats.month_trades_count == Decimal('1')
        assert stats.updated_at < update_time

    def test_get_latest_user_stats(self):
        stats1 = MarketManager.get_latest_user_stats(self.user1)
        assert stats1 is not None
        assert stats1.user == self.user1
        assert stats1.month_trades_count == 0
        assert stats1.month_trades_total == Decimal('0')
        assert stats1.month_trades_total_trader == Decimal('0')

        # Do a trade and check again
        # Trades after midnight shouldn't get counted
        create_trade(self.user1, self.user2, amount=Decimal('0.01'), price=Decimal('2.7e9'))
        stats1 = MarketManager.get_latest_user_stats(self.user1)
        assert stats1 is not None
        assert stats1.user == self.user1
        assert stats1.month_trades_count == 0
        assert stats1.month_trades_total == Decimal('0')
        assert stats1.month_trades_total_trader == Decimal('0')

        # Create a trade before midnight
        yesterday = ir_now() - datetime.timedelta(days=1)
        create_trade(self.user1, self.user2, amount=Decimal('0.01'), price=Decimal('2.7e9'), created_at=yesterday)
        stats1 = MarketManager.get_latest_user_stats(self.user1, force_update=True)
        assert stats1 is not None
        assert stats1.user == self.user1
        assert stats1.month_trades_count == 1
        assert stats1.month_trades_total == Decimal('2_700_000_0')
        assert stats1.month_trades_total_trader == Decimal('0')

        # USDT trades should count after new fees
        yesterday = ir_now() - datetime.timedelta(days=1)
        create_trade(
            self.user1,
            self.user2,
            dst_currency=TETHER,
            amount=Decimal('0.1'),
            price=Decimal('10500'),
            created_at=yesterday,
        )
        stats1 = MarketManager.get_latest_user_stats(self.user1, force_update=True)
        assert stats1 is not None
        assert stats1.user == self.user1
        assert stats1.month_trades_count == 2
        assert stats1.month_trades_total == Decimal('55_200_000_0')
        assert stats1.month_trades_total_trader == Decimal('0')

        # A few more trades
        btc, eth = Currencies.btc, Currencies.eth
        yesterday = ir_now() - datetime.timedelta(days=1)
        create_trade(
            self.user1,
            self.user2,
            src_currency=btc,
            amount=Decimal('0.01'),
            price=Decimal('2.7e9'),
            created_at=yesterday,
        )
        create_trade(
            self.user1,
            self.user2,
            src_currency=eth,
            amount=Decimal('0.1'),
            price=Decimal('1.4e8'),
            created_at=yesterday,
        )
        create_trade(
            self.user1,
            self.user2,
            src_currency=btc,
            amount=Decimal('0.032'),
            price=Decimal('2.65e9'),
            created_at=yesterday,
        )
        stats1 = MarketManager.get_latest_user_stats(self.user1, force_update=True)
        assert stats1 is not None
        assert stats1.user == self.user1
        assert stats1.month_trades_count == 5
        assert stats1.month_trades_total == Decimal('67_780_000_0')
        assert stats1.month_trades_total_trader == Decimal('0')

    def test_create_trade_notif(self):
        # First trade
        trade1 = create_trade(self.user1, self.user2, Currencies.btc,
                              amount=Decimal('0.0321449'), price=Decimal('2.7e9'))
        MarketManager.create_trade_notif(trade1)
        n1 = Notification.objects.filter(user=self.user1).order_by('-created_at').first()
        assert n1 is not None
        assert not n1.is_read
        assert n1.message == 'معامله انجام شد: فروش 0.032145 بیت‌کوین'
        n2 = Notification.objects.filter(user=self.user2).order_by('-created_at').first()
        assert n2 is not None
        assert not n2.is_read
        assert n2.message == 'معامله انجام شد: خرید 0.032145 بیت‌کوین'
        # Second trade
        trade2 = create_trade(self.user3, self.user1, Currencies.xrp,
                              amount=Decimal('320.4321'), price=Decimal('70999'))
        MarketManager.create_trade_notif(trade2)
        n3 = Notification.objects.filter(user=self.user3).order_by('-created_at').first()
        assert n3 is not None
        assert not n3.is_read
        assert n3.message == 'معامله انجام شد: فروش 320.43210 ریپل'
        n4 = Notification.objects.filter(user=self.user1).order_by('-created_at').first()
        assert n4 is not None
        assert not n4.is_read
        assert n4.message == 'معامله انجام شد: خرید 320.43210 ریپل'

    def test_get_market_promotion_end_date(self):
        assert MarketManager.get_market_promotion_end_date(Currencies.unknown, Currencies.rls) == MIN_DATETIME
        assert MarketManager.get_market_promotion_end_date(1000, Currencies.rls) == MIN_DATETIME
        assert (
            MarketManager.get_market_promotion_end_date(
                Currencies.api3,
                Currencies.rls,
            )
            == datetime.datetime(2023, 2, 10, 16, 30, 0, 0, pytz.utc)
        )
        assert (
            MarketManager.get_market_promotion_end_date(
                Currencies.ens,
                Currencies.usdt,
            )
            == datetime.datetime(2023, 2, 2, 12, 30, 0, 0, pytz.utc)
        )
        assert (
            MarketManager.get_market_promotion_end_date(
                Currencies.dai,
                Currencies.rls,
            )
            == datetime.datetime(2024, 3, 19, 20, 30, 0, 0, pytz.utc)
        )

    @patch('exchange.market.marketmanager.LAUNCHING_CURRENCIES', [Currencies.glm, Currencies.gmx])
    def test_is_market_in_promotion(self):
        # Test market before the launch, should be in promotion
        assert MarketManager.is_market_in_promotion(
            Currencies.glm,
            Currencies.rls,
            nw=datetime.datetime(2023, 2, 7, 16, 0, 0, 0, pytz.utc),
        )
        assert MarketManager.is_market_in_promotion(
            Currencies.gmx,
            Currencies.rls,
            nw=datetime.datetime(2023, 7, 4, 13, 0, 0, 0, pytz.utc),
        )
        assert not MarketManager.is_market_in_promotion(
            Currencies.gmx,
            Currencies.rls,
            nw=datetime.datetime(2023, 7, 6, 13, 0, 0, 0, pytz.utc),
        )
        assert not MarketManager.is_market_in_promotion(
            Currencies.btc,
            Currencies.rls,
        )
        assert MarketManager.is_market_in_promotion(
            Currencies.dai,
            Currencies.rls,
            nw=datetime.datetime(2024, 3, 1, 0, 0, 0, 0, pytz.utc),
            is_buy=True,
        )
        assert not MarketManager.is_market_in_promotion(
            Currencies.dai,
            Currencies.rls,
            nw=datetime.datetime(2024, 3, 1, 0, 0, 0, 0, pytz.utc),
        )
