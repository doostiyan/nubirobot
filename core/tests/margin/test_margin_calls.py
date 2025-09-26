import datetime
from decimal import Decimal
from typing import Optional
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from exchange.accounts.models import Notification
from exchange.base.calendar import get_earliest_time, ir_now, ir_today
from exchange.base.models import Currencies, Settings
from exchange.base.templatetags.nobitex import shamsidateformat
from exchange.margin.crons import MarginCallManagementCron, MarginCallSendingCron, NotifyUpcomingPositionsExpirationCron
from exchange.margin.models import MarginCall, Position
from exchange.market.models import Market, MarketCandle


class MarginCallManageTest(TestCase):

    market: Market

    @classmethod
    def setUpTestData(cls):
        cls.market = Market.by_symbol('BTCUSDT')
        cls.positions = [
            # Normal sell
            Position.objects.create(
                user_id=201,
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Position.SIDES.sell,
                collateral='213',
                earned_amount='212.6805',
                delegated_amount='0.01',
                liquidation_price='38640.18',
                status=Position.STATUS.open,
            ),
            # Normal buy
            Position.objects.create(
                user_id=201,
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Position.SIDES.buy,
                collateral='106',
                earned_amount='-212',
                delegated_amount='0.00999',
                liquidation_price='11671.67',
                status=Position.STATUS.open,
            ),
            # High liquidation price
            Position.objects.create(
                user_id=202,
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Position.SIDES.sell,
                collateral='213',
                earned_amount='106.34025',
                delegated_amount='0.005',
                liquidation_price='57974.77',
                status=Position.STATUS.open,
            ),
            # Low liquidation price
            Position.objects.create(
                user_id=201,
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Position.SIDES.buy,
                leverage='2',
                collateral='106',
                earned_amount='-61.4',
                delegated_amount='0.003',
                liquidation_price='6669.53',
                status=Position.STATUS.open,
            ),
            # Mid leverage
            Position.objects.create(
                user_id=201,
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Position.SIDES.sell,
                leverage='3',
                collateral='107',
                earned_amount='319.2604',
                delegated_amount='0.01',
                liquidation_price='38692.82',
                status=Position.STATUS.open,
            ),
            # High leverage
            Position.objects.create(
                user_id=201,
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Position.SIDES.sell,
                leverage='5',
                collateral='72',
                earned_amount='354.7338',
                delegated_amount='0.01',
                liquidation_price='38735.79',
                status=Position.STATUS.open,
            ),
            # Different market
            Position.objects.create(
                user_id=201,
                src_currency=Currencies.ltc,
                dst_currency=Currencies.usdt,
                side=Position.SIDES.sell,
                collateral='55',
                earned_amount='55',
                delegated_amount='1',
                liquidation_price='100',
                status=Position.STATUS.open,
            ),
            Position.objects.create(
                user_id=201,
                src_currency=Currencies.ltc,
                dst_currency=Currencies.usdt,
                side=Position.SIDES.buy,
                leverage='2',
                collateral='27.5',
                earned_amount='-55',
                delegated_amount='1',
                liquidation_price='29',
                status=Position.STATUS.open,
            ),
            # Not opened
            Position.objects.create(
                user_id=203,
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Position.SIDES.sell,
                collateral='21.22',
            ),
            Position.objects.create(
                user_id=203,
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Position.SIDES.buy,
                leverage='2',
                collateral='10.6',
            ),
            # Expired
            Position.objects.create(
                user_id=201,
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Position.SIDES.sell,
                collateral='21.3',
                earned_amount='0.5432',
                liquidation_price='38640.18',
                status=Position.STATUS.expired,
            ),
            Position.objects.create(
                user_id=201,
                src_currency=Currencies.btc,
                dst_currency=Currencies.usdt,
                side=Position.SIDES.sell,
                collateral='10.6',
                leverage='2',
                earned_amount='0.6543',
                liquidation_price='11671.67',
                status=Position.STATUS.expired,
            ),
        ]

    def setUp(self):
        self.changed_positions = set()

    def tearDown(self):
        for position in self.changed_positions:
            position.refresh_from_db()

    def change_collateral(self, position: Position, new_collateral: str):
        position.collateral = Decimal(new_collateral)
        position.set_liquidation_price()
        position.save(update_fields=('collateral', 'liquidation_price'))
        self.changed_positions.add(position)

    def set_market_prices(self, high_price: int, low_price: int, dt: Optional[datetime.datetime] = None, **kwargs):
        resolution = MarketCandle.RESOLUTIONS.minute
        start_time = MarketCandle.get_start_time(dt or timezone.now(), resolution)
        mid_price = (high_price + low_price) // 2
        defaults = {
            'open_price': mid_price,
            'high_price': high_price,
            'low_price': low_price,
            'close_price': mid_price,
            'trade_amount': 4,
        }
        defaults.update(kwargs)
        MarketCandle.objects.update_or_create(
            market=self.market, resolution=resolution, start_time=start_time, defaults=defaults
        )

    @staticmethod
    def run_margin_call_cron():
        MarginCallManagementCron().run()

    def test_margin_call_with_market_price_between_thresholds(self):
        self.set_market_prices(25000, 24970)
        self.run_margin_call_cron()
        assert not MarginCall.objects.exists()

    def test_margin_call_with_market_price_rise_above_upper_threshold_1st_time(self):
        self.set_market_prices(35450, 35420)
        self.run_margin_call_cron()
        margin_calls = MarginCall.objects.all()
        assert len(margin_calls) == 1
        assert margin_calls[0].position_id == self.positions[0].id
        assert margin_calls[0].liquidation_price == Decimal(self.positions[0].liquidation_price)
        assert margin_calls[0].market_price == 35450
        assert not margin_calls[0].is_sent
        assert not margin_calls[0].is_solved

    def test_margin_call_with_market_price_fall_below_lower_threshold_1st_time(self):
        self.set_market_prices(12720, 12690)
        self.run_margin_call_cron()
        margin_calls = MarginCall.objects.all()
        assert len(margin_calls) == 1
        assert margin_calls[0].position_id == self.positions[1].id
        assert margin_calls[0].liquidation_price == Decimal(self.positions[1].liquidation_price)
        assert margin_calls[0].market_price == 12690
        assert not margin_calls[0].is_sent
        assert not margin_calls[0].is_solved

    def test_margin_call_with_market_price_rise_and_stay_above_upper_threshold(self):
        self.set_market_prices(35450, 35420)
        self.run_margin_call_cron()
        self.set_market_prices(35460, 35430)
        self.run_margin_call_cron()
        margin_calls = MarginCall.objects.all()
        assert len(margin_calls) == 1
        assert margin_calls[0].market_price == 35450
        assert not margin_calls[0].is_solved

    def test_margin_call_with_market_price_fall_and_stay_below_lower_threshold(self):
        self.set_market_prices(12720, 12690)
        self.run_margin_call_cron()
        self.set_market_prices(12710, 12680)
        self.run_margin_call_cron()
        margin_calls = MarginCall.objects.all()
        assert len(margin_calls) == 1
        assert margin_calls[0].market_price == 12690
        assert not margin_calls[0].is_solved

    def test_margin_call_with_market_price_rise_above_upper_threshold_and_mild_fall(self):
        start_time = timezone.now()
        self.set_market_prices(35450, 35420, dt=start_time)
        self.run_margin_call_cron()
        self.set_market_prices(35300, 35270, dt=start_time)
        self.run_margin_call_cron()
        margin_calls = MarginCall.objects.all()
        assert len(margin_calls) == 1
        assert margin_calls[0].market_price == 35450
        assert not margin_calls[0].is_solved

    def test_margin_call_with_market_price_fall_below_lower_threshold_and_mild_rise(self):
        start_time = timezone.now()
        self.set_market_prices(12720, 12690, dt=start_time)
        self.run_margin_call_cron()
        self.set_market_prices(12800, 12770, dt=start_time)
        self.run_margin_call_cron()
        margin_calls = MarginCall.objects.all()
        assert len(margin_calls) == 1
        assert margin_calls[0].market_price == 12690
        assert not margin_calls[0].is_solved

    def test_margin_call_with_market_price_rise_above_upper_threshold_and_significant_fall(self):
        start_time = timezone.now()
        self.set_market_prices(35450, 35420, dt=start_time)
        self.run_margin_call_cron()
        self.set_market_prices(34000, 33970, dt=start_time)
        self.run_margin_call_cron()
        margin_calls = MarginCall.objects.all()
        assert len(margin_calls) == 1
        assert margin_calls[0].market_price == 35450
        assert margin_calls[0].is_solved

    def test_margin_call_with_market_price_fall_below_lower_threshold_and_significant_rise(self):
        start_time = timezone.now()
        self.set_market_prices(12720, 12690, dt=start_time)
        self.run_margin_call_cron()
        self.set_market_prices(13500, 13470, dt=start_time)
        self.run_margin_call_cron()
        margin_calls = MarginCall.objects.all()
        assert len(margin_calls) == 1
        assert margin_calls[0].market_price == 12690
        assert margin_calls[0].is_solved

    def test_margin_call_with_market_price_rise_above_upper_threshold_and_mild_fall_the_next_day(self):
        with patch.object(timezone, 'now', return_value=timezone.now() - datetime.timedelta(minutes=1)):
            self.set_market_prices(35450, 35420)
            self.run_margin_call_cron()
        with patch.object(timezone, 'now', return_value=timezone.now() + datetime.timedelta(days=1)):
            self.set_market_prices(35000, 34970)
            self.run_margin_call_cron()
        margin_calls = MarginCall.objects.all()
        assert len(margin_calls) == 1
        assert margin_calls[0].market_price == 35450
        assert margin_calls[0].is_solved

    def test_margin_call_with_market_price_fall_below_lower_threshold_and_mild_rise_the_next_day(self):
        with patch.object(timezone, 'now', return_value=timezone.now() - datetime.timedelta(minutes=1)):
            self.set_market_prices(12720, 12690)
            self.run_margin_call_cron()
        with patch.object(timezone, 'now', return_value=timezone.now() + datetime.timedelta(days=1)):
            self.set_market_prices(12800, 12770)
            self.run_margin_call_cron()
        margin_calls = MarginCall.objects.all()
        assert len(margin_calls) == 1
        assert margin_calls[0].market_price == 12690
        assert margin_calls[0].is_solved

    def test_margin_call_with_market_price_rise_then_fall_again_rise_above_upper_threshold(self):
        start_time = timezone.now()
        self.set_market_prices(35450, 35420, dt=start_time)
        self.run_margin_call_cron()
        self.set_market_prices(34000, 33970, dt=start_time)
        self.run_margin_call_cron()
        self.set_market_prices(35460, 35430, dt=start_time)
        self.run_margin_call_cron()
        margin_calls = MarginCall.objects.all().order_by('id')
        assert len(margin_calls) == 2
        assert margin_calls[0].market_price == 35450
        assert margin_calls[0].is_solved
        assert margin_calls[1].market_price == 35460
        assert not margin_calls[1].is_solved

    def test_margin_call_with_market_price_fall_then_rise_again_fall_below_lower_threshold(self):
        start_time = timezone.now()
        self.set_market_prices(12720, 12690, dt=start_time)
        self.run_margin_call_cron()
        self.set_market_prices(13500, 13470, dt=start_time)
        self.run_margin_call_cron()
        self.set_market_prices(12710, 12680, dt=start_time)
        self.run_margin_call_cron()
        margin_calls = MarginCall.objects.all().order_by('id')
        assert len(margin_calls) == 2
        assert margin_calls[0].market_price == 12690
        assert margin_calls[0].is_solved
        assert margin_calls[1].market_price == 12680
        assert not margin_calls[1].is_solved

    def test_margin_call_solve_on_user_actions_sell(self):
        self.set_market_prices(36000, 35970)
        self.run_margin_call_cron()
        margin_call = MarginCall.objects.select_related('position').last()
        threshold = margin_call.market_price * Decimal('1.2')
        assert margin_call.position.liquidation_price < threshold
        self.change_collateral(margin_call.position, '300')
        assert margin_call.position.liquidation_price > threshold
        self.run_margin_call_cron()
        margin_call.refresh_from_db()
        assert margin_call.is_solved

    def test_margin_call_solve_on_user_actions_buy(self):
        self.set_market_prices(12700, 12670)
        self.run_margin_call_cron()
        margin_call = MarginCall.objects.select_related('position').last()
        threshold = margin_call.market_price / Decimal('1.2')
        assert margin_call.position.liquidation_price > threshold
        self.change_collateral(margin_call.position, '150')
        assert margin_call.position.liquidation_price < threshold
        self.run_margin_call_cron()
        margin_call.refresh_from_db()
        assert margin_call.is_solved

    def test_margin_call_on_various_leverages(self):
        # Make margin call for L1
        self.set_market_prices(35450, 35420)
        self.run_margin_call_cron()
        assert MarginCall.objects.count() == 1

        # Make margin call for L3
        self.set_market_prices(35470, 35440)
        self.run_margin_call_cron()
        margin_calls = MarginCall.objects.order_by('id')
        assert len(margin_calls) == 2
        assert margin_calls[1].market_price == 35470
        assert margin_calls[1].liquidation_price == Decimal('38692.82')
        assert margin_calls[1].position.leverage == 3

        # Pass 1.2 margin ratio for L5
        self.set_market_prices(37000, 36970)
        self.run_margin_call_cron()
        assert MarginCall.objects.count() == 2

        # Make margin call for L3
        self.set_market_prices(37100, 37070)
        self.run_margin_call_cron()
        margin_calls = MarginCall.objects.order_by('id')
        assert len(margin_calls) == 3
        assert margin_calls[2].market_price == 37100
        assert margin_calls[2].liquidation_price == Decimal('38735.79')
        assert margin_calls[2].position.leverage == 5


class MarginCallSendTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.sell_position = Position.objects.create(
            user_id=201,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            collateral='213',
            earned_amount='212.6805',
            delegated_amount='0.01',
            liquidation_price='38640.18',
            status=Position.STATUS.open,
        )
        cls.buy_position = Position.objects.create(
            user_id=202,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.buy,
            collateral='106',
            earned_amount='-212',
            delegated_amount='0.00999',
            liquidation_price='11671.67',
            status=Position.STATUS.open,
        )
        Notification.objects.all().delete()

    @staticmethod
    def run_margin_call_cron():
        MarginCallSendingCron().run()

    def test_margin_call_send_not_sent(self):
        margin_calls = [
            MarginCall.objects.create(position=self.sell_position, market_price=36000, liquidation_price='38295.52'),
            MarginCall.objects.create(position=self.buy_position, market_price=12720, liquidation_price='11892.13'),
        ]
        self.run_margin_call_cron()
        notifications = Notification.objects.order_by('user_id')
        assert len(notifications) == 2
        assert notifications[0].user_id == 201
        assert notifications[0].message == 'موقعیت فروش شما بر روی BTC-USDT نزدیک به نقطه لیکوئید شدن است'
        assert notifications[1].user_id == 202
        assert notifications[1].message == 'موقعیت خرید شما بر روی BTC-USDT نزدیک به نقطه لیکوئید شدن است'
        for margin_call in margin_calls:
            margin_call.refresh_from_db()
            assert margin_call.is_sent

    def test_margin_call_send_already_sent(self):
        MarginCall.objects.create(
            position=self.sell_position, market_price=36000, liquidation_price='38295.52', is_sent=True
        )
        MarginCall.objects.create(
            position=self.buy_position, market_price=12720, liquidation_price='11892.13', is_sent=True
        )
        self.run_margin_call_cron()
        assert not Notification.objects.exists()

    @pytest.mark.slow
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_margin_call_email(self):
        Settings.set_dict('email_whitelist', [self.sell_position.user.email, self.buy_position.user.email])
        call_command('update_email_templates')
        MarginCall.objects.create(position=self.sell_position, market_price=36000, liquidation_price='38295.52')
        MarginCall.objects.create(position=self.buy_position, market_price=12720, liquidation_price='11892.13')
        self.run_margin_call_cron()
        with patch('django.db.connection.close'):
            call_command('send_queued_mail')


class MarginUpcomingExpirationsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        soon_to_be_expired_start_date = get_earliest_time(ir_now()) - timezone.timedelta(
            days=settings.POSITION_EXTENSION_LIMIT + 1 - 3
        )
        # Expire in expected expiration date
        cls.position = Position.objects.create(
            user_id=201,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            collateral='213',
            earned_amount='212.6805',
            delegated_amount='0.01',
            liquidation_price='38640.18',
            status=Position.STATUS.open,
            created_at=soon_to_be_expired_start_date,
        )
        # Expires 1 day before expected date
        Position.objects.create(
            user_id=201,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.buy,
            collateral='106',
            earned_amount='-212',
            delegated_amount='0.00999',
            liquidation_price='11671.67',
            status=Position.STATUS.open,
            created_at=soon_to_be_expired_start_date - timezone.timedelta(days=1),
        )
        # Expire after expected date
        Position.objects.create(
            user_id=201,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            collateral='213',
            earned_amount='106.34025',
            delegated_amount='0.005',
            liquidation_price='57974.77',
            status=Position.STATUS.open,
            created_at=soon_to_be_expired_start_date + timezone.timedelta(days=4),
        ),
        # Expired
        Position.objects.create(
            user_id=201,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            collateral='21.3',
            earned_amount='0.5432',
            liquidation_price='38640.18',
            status=Position.STATUS.expired,
            created_at=soon_to_be_expired_start_date + timezone.timedelta(days=4),
        )

    def test_positions_upcoming_expirations_notif(self):
        Notification.objects.all().delete()
        NotifyUpcomingPositionsExpirationCron().run()

        notifications = Notification.objects.filter(user_id=self.position.user_id)
        assert len(notifications) == 1
        assert notifications[0].message == (
            'موقعیت فروش شما در بازار BTC-USDT در تاریخ {} منقضی خواهد شد. '
            'لطفاً اقدامات لازم را جهت بستن موقعیت خود انجام دهید.'
        ).format(shamsidateformat(ir_today() + timezone.timedelta(days=3)))

    @pytest.mark.slow
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_positions_upcoming_expirations_email(self):
        Settings.set_dict('email_whitelist', [self.position.user.email])
        call_command('update_email_templates')
        NotifyUpcomingPositionsExpirationCron().run()
        with patch('django.db.connection.close'):
            call_command('send_queued_mail')
