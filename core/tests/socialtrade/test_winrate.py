from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.margin.models import Position
from exchange.socialtrade.constants import LEADER_WINRATE_CACHE_KEY
from exchange.socialtrade.enums import WinratePeriods
from exchange.socialtrade.functions import update_winrates
from tests.socialtrade.helpers import SocialTradeMixin


class TestWinrate(TestCase, SocialTradeMixin):
    def setUp(self) -> None:
        self.leader = self.create_leader()
        self.dummy_leader1 = self.create_leader()
        self.dummy_leader2 = self.create_leader()

        self.position_data = dict(
            created_at=ir_now() - timedelta(seconds=1),
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            delegated_amount='0.001',
            earned_amount='21',
            collateral='43.1',
            entry_price='123',
            exit_price='123.45',
        )
        Position.objects.bulk_create(
            [
                Position(
                    **self.position_data,
                    user=self.leader.user,
                    pnl=1,
                    closed_at=ir_now(),
                    status=Position.STATUS.closed,
                ),
                Position(
                    **self.position_data,
                    user=self.leader.user,
                    pnl=1,
                    closed_at=ir_now() - timedelta(seconds=100),
                    status=Position.STATUS.liquidated,
                ),
                Position(  #  Dummy because of status
                    **self.position_data,
                    user=self.leader.user,
                    pnl=1,
                    closed_at=ir_now() - timedelta(seconds=100),
                    status=Position.STATUS.canceled,
                ),
                Position(
                    **self.position_data,
                    user=self.leader.user,
                    pnl=-1,
                    closed_at=ir_now() - timedelta(days=2),
                    status=Position.STATUS.closed,
                ),
                Position(
                    **self.position_data,
                    user=self.leader.user,
                    pnl=0,
                    status=Position.STATUS.liquidated,
                    closed_at=ir_now() - timedelta(days=4),
                ),
                Position(
                    **self.position_data,
                    user=self.leader.user,
                    pnl=-1,
                    status=Position.STATUS.closed,
                    closed_at=ir_now() - timedelta(days=6),
                ),
                Position(
                    **self.position_data,
                    user=self.leader.user,
                    pnl=-1,
                    status=Position.STATUS.liquidated,
                    closed_at=ir_now() - timedelta(days=8),
                ),
                Position(
                    **self.position_data,
                    user=self.leader.user,
                    pnl=1,
                    closed_at=ir_now() - timedelta(days=10),
                    status=Position.STATUS.closed,
                ),
                Position(
                    **self.position_data,
                    user=self.leader.user,
                    pnl=-1,
                    closed_at=ir_now() - timedelta(days=40),
                    status=Position.STATUS.closed,
                ),
                Position(
                    **self.position_data,
                    user=self.leader.user,
                    pnl=-1,
                    closed_at=ir_now() - timedelta(days=100),
                    status=Position.STATUS.closed,
                ),
                Position(
                    **self.position_data,
                    user=self.dummy_leader1.user,
                    pnl=1,
                    closed_at=ir_now(),
                    status=Position.STATUS.closed,
                ),
            ],
        )

    def _clear_cache(self, leader):
        for period in WinratePeriods:
            cache.delete(LEADER_WINRATE_CACHE_KEY % (leader.pk, period.value))
            assert cache.get(LEADER_WINRATE_CACHE_KEY % (leader.pk, period.value)) is None

    def test_get_winrate(self):
        winrates_7 = self.leader.get_winrate(WinratePeriods.WEEK)
        assert winrates_7 == 40  # 2 * 100 // 5
        winrates_30 = self.leader.get_winrate(WinratePeriods.MONTH)
        assert winrates_30 == 42  # 3 * 100 // 7
        winrates_90 = self.leader.get_winrate(WinratePeriods.MONTH_3)
        assert winrates_90 == 37  # 3 * 100 // 7

    def test_update_winrates(self):
        self._clear_cache(self.leader)

        update_winrates()

        # leader
        assert cache.get(LEADER_WINRATE_CACHE_KEY % (self.leader.pk, WinratePeriods.WEEK.value)) == 40
        assert cache.get(LEADER_WINRATE_CACHE_KEY % (self.leader.pk, WinratePeriods.MONTH.value)) == 42
        assert cache.get(LEADER_WINRATE_CACHE_KEY % (self.leader.pk, WinratePeriods.MONTH_3.value)) == 37

        # dummy leader 1 with 1 position
        assert cache.get(LEADER_WINRATE_CACHE_KEY % (self.dummy_leader1.pk, WinratePeriods.WEEK.value)) == 100
        assert cache.get(LEADER_WINRATE_CACHE_KEY % (self.dummy_leader1.pk, WinratePeriods.MONTH.value)) == 100
        assert cache.get(LEADER_WINRATE_CACHE_KEY % (self.dummy_leader1.pk, WinratePeriods.MONTH_3.value)) == 100

        # dummy leader 2 with no position
        assert cache.get(LEADER_WINRATE_CACHE_KEY % (self.dummy_leader2.pk, WinratePeriods.WEEK.value)) == 0
        assert cache.get(LEADER_WINRATE_CACHE_KEY % (self.dummy_leader2.pk, WinratePeriods.MONTH.value)) == 0
        assert cache.get(LEADER_WINRATE_CACHE_KEY % (self.dummy_leader2.pk, WinratePeriods.MONTH_3.value)) == 0

        Position.objects.create(
            **self.position_data,
            user=self.leader.user,
            pnl=-1,
            closed_at=ir_now() - timedelta(seconds=1),
            status=Position.STATUS.closed,
        ),
        update_winrates()

        # leader
        assert cache.get(LEADER_WINRATE_CACHE_KEY % (self.leader.pk, WinratePeriods.WEEK.value)) == 33
        assert cache.get(LEADER_WINRATE_CACHE_KEY % (self.leader.pk, WinratePeriods.MONTH.value)) == 37
        assert cache.get(LEADER_WINRATE_CACHE_KEY % (self.leader.pk, WinratePeriods.MONTH_3.value)) == 33

    def test_get_winrate_uses_cache(self):
        self._clear_cache(self.leader)
        self.leader.get_winrate(WinratePeriods.WEEK)
        with patch('exchange.socialtrade.functions.update_winrates') as mock_update_winrates:
            self.leader.get_winrate(WinratePeriods.WEEK)
            assert not mock_update_winrates.called
