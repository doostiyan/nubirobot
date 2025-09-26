import datetime
from unittest.mock import patch

from django.test import TestCase
from django_cron.models import CronJobLog

from exchange.accounts.models import Notification, User
from exchange.base.calendar import ir_tz
from exchange.base.models import Currencies
from exchange.margin.models import Position
from exchange.market.models import Order
from exchange.socialtrade.crons import SendLeadersTradesNotifCron
from exchange.socialtrade.models import SocialTradeSubscription
from exchange.socialtrade.tasks import task_send_mass_notifications
from tests.socialtrade.helpers import SocialTradeMixin


@patch.object(task_send_mass_notifications, 'delay', task_send_mass_notifications)
@patch('exchange.base.calendar.ir_now', lambda: datetime.datetime(year=2024, month=1, day=1).astimezone(ir_tz()))
@patch(
    'exchange.socialtrade.leaders.trades.ir_now',
    lambda: datetime.datetime(year=2024, month=1, day=1).astimezone(ir_tz()),
)
class SendLeaderTradesAPITest(SocialTradeMixin, TestCase):
    def setUp(self) -> None:
        ir_now = datetime.datetime(year=2024, month=1, day=1).astimezone(ir_tz())
        self.from_dt = ir_now - datetime.timedelta(minutes=1)
        self.to_dt = ir_now

        self.user1 = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)
        self.leader1 = self.create_leader()
        self.charge_wallet(self.user1, currency=self.leader1.subscription_currency, amount=10000)
        self.charge_wallet(self.user2, currency=self.leader1.subscription_currency, amount=10000)

        # To mock prev_success_cron.start_time in the SendLeadersTradesNotifCron
        CronJobLog.objects.create(
            code=SendLeadersTradesNotifCron.code,
            is_success=True,
            start_time=self.from_dt,
            end_time=ir_now,
        )

        #### User 2 ####

        # Expired
        expired_subs_user_2 = SocialTradeSubscription.objects.create(
            leader=self.leader1,
            subscriber=self.user2,
            expires_at=ir_now + datetime.timedelta(weeks=400000),
            starts_at=ir_now,
            is_trial=False,
            fee_amount=1000,
            fee_currency=2,
        )
        expired_subs_user_2.expires_at = ir_now - datetime.timedelta(days=4)
        expired_subs_user_2.save()

        # Canceled
        canceled_sub_user_2 = SocialTradeSubscription.objects.create(
            leader=self.leader1,
            subscriber=self.user2,
            expires_at=ir_now + datetime.timedelta(weeks=400000),
            starts_at=ir_now - datetime.timedelta(microseconds=1),
            is_trial=False,
            fee_amount=1000,
            fee_currency=2,
        )
        canceled_sub_user_2.canceled_at = ir_now - datetime.timedelta(days=4)
        canceled_sub_user_2.save()

        #### User 1 ####

        self.subscription = SocialTradeSubscription.objects.create(
            leader=self.leader1,
            subscriber=self.user1,
            expires_at=ir_now + datetime.timedelta(weeks=400000),
            starts_at=ir_now - datetime.timedelta(microseconds=2),
            is_trial=True,
            fee_amount=1000,
            fee_currency=2,
        )

        # Expired
        expired_subs = SocialTradeSubscription.objects.create(
            leader=self.leader1,
            subscriber=self.user1,
            expires_at=ir_now + datetime.timedelta(weeks=400000),
            starts_at=ir_now - datetime.timedelta(microseconds=3),
            is_trial=False,
            fee_amount=1000,
            fee_currency=2,
        )
        expired_subs.expires_at = ir_now - datetime.timedelta(days=4)
        expired_subs.save()

        # Canceled
        canceled_sub = SocialTradeSubscription.objects.create(
            leader=self.leader1,
            subscriber=self.user1,
            expires_at=ir_now + datetime.timedelta(weeks=400000),
            starts_at=ir_now - datetime.timedelta(microseconds=4),
            is_trial=False,
            fee_amount=1000,
            fee_currency=2,
        )
        canceled_sub.canceled_at = ir_now - datetime.timedelta(days=4)
        canceled_sub.save()

        self.order_market1 = Order.objects.create(
            user=self.leader1.user,
            src_currency=Currencies.eth,
            dst_currency=Currencies.rls,
            order_type=Order.ORDER_TYPES.buy,
            execution_type=Order.EXECUTION_TYPES.market,
            trade_type=Order.TRADE_TYPES.margin,
            price=20000,
            amount=1000,
        )
        self.order_market1.created_at = ir_now - datetime.timedelta(seconds=1)
        self.order_market1.save(update_fields=('created_at',))

        self.order_market2 = Order.objects.create(
            user=self.leader1.user,
            src_currency=Currencies.eth,
            dst_currency=Currencies.rls,
            order_type=Order.ORDER_TYPES.buy,
            execution_type=Order.EXECUTION_TYPES.market,
            trade_type=Order.TRADE_TYPES.margin,
            price=15000,
            amount=1000,
        )
        self.order_market2.created_at = ir_now - datetime.timedelta(seconds=1)
        self.order_market2.save(update_fields=('created_at',))

        self.order_market3 = Order.objects.create(
            user=self.leader1.user,
            src_currency=Currencies.eth,
            dst_currency=Currencies.rls,
            order_type=Order.ORDER_TYPES.sell,
            execution_type=Order.EXECUTION_TYPES.market,
            trade_type=Order.TRADE_TYPES.margin,
            price=15000,
            amount=1000,
        )
        self.order_market3.created_at = ir_now - datetime.timedelta(seconds=1)
        self.order_market3.save(update_fields=('created_at',))

        self.open_position = Position.objects.create(
            user=self.leader1.user,
            opened_at=ir_now - datetime.timedelta(seconds=1),
            src_currency=Currencies.eth,
            dst_currency=Currencies.rls,
            side=Position.SIDES.buy,
            delegated_amount='0.001',
            earned_amount='21',
            collateral='43.1',
            entry_price='1230',
            status=Position.STATUS.open,
        )
        self.open_position.orders.add(self.order_market1)

        self.closed_position = Position.objects.create(
            user=self.leader1.user,
            opened_at=ir_now - datetime.timedelta(seconds=1),
            closed_at=ir_now - datetime.timedelta(seconds=1),
            src_currency=Currencies.eth,
            dst_currency=Currencies.rls,
            side=Position.SIDES.sell,
            delegated_amount='0.001',
            earned_amount='21',
            collateral='43.1',
            entry_price='123',
            exit_price='123.45',
            status=Position.STATUS.closed,
        )
        self.closed_position.orders.add(self.order_market2)

        self.liquidated_position = Position.objects.create(
            user=self.leader1.user,
            opened_at=ir_now - datetime.timedelta(seconds=1),
            closed_at=ir_now - datetime.timedelta(seconds=1),
            src_currency=Currencies.eth,
            dst_currency=Currencies.rls,
            side=Position.SIDES.sell,
            delegated_amount='0.001',
            earned_amount='21',
            collateral='43.1',
            entry_price='123.45',
            liquidation_price='455.45',
            status=Position.STATUS.liquidated,
        )
        self.liquidated_position.orders.add(self.order_market3)

        self.oco1 = Order.objects.create(
            user=self.leader1.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            order_type=Order.ORDER_TYPES.buy,
            execution_type=Order.EXECUTION_TYPES.market,
            trade_type=Order.TRADE_TYPES.margin,
            price=20000,
            amount=1000,
        )
        self.oco1.created_at = ir_now - datetime.timedelta(seconds=1)
        self.oco1.save(update_fields=('created_at',))

        self.oco1_pair = Order.objects.create(
            user=self.leader1.user,
            src_currency=Currencies.btc,
            dst_currency=Currencies.rls,
            order_type=Order.ORDER_TYPES.buy,
            execution_type=Order.EXECUTION_TYPES.market,
            trade_type=Order.TRADE_TYPES.margin,
            price=20000,
            amount=1000,
            pair=self.oco1,
        )
        self.oco1_pair.created_at = ir_now - datetime.timedelta(seconds=1)
        self.oco1_pair.save(update_fields=('created_at',))
        self.oco1.pair = self.oco1_pair
        self.oco1.save(update_fields=('pair',))

        # Dummies
        # new position
        Position.objects.create(
            user=self.leader1.user,
            created_at=ir_now - datetime.timedelta(seconds=1),
            opened_at=ir_now - datetime.timedelta(seconds=1),
            closed_at=ir_now - datetime.timedelta(seconds=1),
            src_currency=Currencies.eth,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            delegated_amount='0.001',
            earned_amount='21',
            leverage=2,
            collateral='43.1',
            status=Position.STATUS.new,
        )

        # canceled position
        Position.objects.create(
            user=self.leader1.user,
            closed_at=ir_now - datetime.timedelta(seconds=1),
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            delegated_amount='0.001',
            earned_amount='21',
            entry_price='123.45',
            collateral='43.1',
            status=Position.STATUS.canceled,
        )

        Notification.objects.all().delete()

    def test_send_leaders_trades_task(self):
        SendLeadersTradesNotifCron().run()

        user_2_notifications = Notification.objects.filter(user=self.user2)
        assert user_2_notifications.count() == 0

        notifications = Notification.objects.filter(user=self.user1).order_by('-pk')
        assert notifications.count() == 7
        assert {notification.message for notification in notifications} == {
            (
                f'تریدر انتخابی شما {self.leader1.nickname} سفارش جدیدی برای باز کردن موقعیت خرید '
                f'تعهدی در بازار ETH-RLS ثبت کرده است.\n'
                f'زمان ثبت سفارش: 1402/10/10 23:59:59'
            ),
            (
                f'تریدر انتخابی شما {self.leader1.nickname} سفارش جدیدی برای باز کردن موقعیت فروش '
                f'تعهدی در بازار ETH-RLS ثبت کرده است.\n'
                f'زمان ثبت سفارش: 1402/10/10 23:59:59'
            ),
            (
                f'تریدر انتخابی شما {self.leader1.nickname} سفارش جدیدی برای بستن موقعیت فروش تعهدی در '
                f'بازار ETH-RLS ثبت کرده است.\n'
                f'زمان ثبت سفارش: 1402/10/10 23:59:59'
            ),
            (
                f'موقعیت خرید تعهدی تریدر انتخابی شما {self.leader1.nickname} در بازار ETH-RLS باز '
                f'شد.\n'
                f'زمان باز شدن موقعیت: 1402/10/10 23:59:59'
            ),
            (
                f'موقعیت فروش تعهدی تریدر انتخابی شما {self.leader1.nickname} در بازار ETH-RLS بسته '
                f'شد.\n'
                f'زمان بسته شدن موقعیت: 1402/10/10 23:59:59'
            ),
            (
                f'هشدار! یک موقعیت فروش تعهدی تریدر انتخابی شما {self.leader1.nickname} در بازار '
                f'ETH-RLS لیکویید شده است.\n'
                f'زمان لیکویید شدن موقعیت: 1402/10/11 00:00:00'
            ),
            (
                f'تریدر انتخابی شما {self.leader1.nickname} سفارش جدیدی برای بستن موقعیت فروش تعهدی در '
                f'بازار BTC-RLS ثبت کرده است.\n'
                f'زمان ثبت سفارش: 1402/10/10 23:59:59'
            ),
        }

    def test_send_leaders_trades_task_is_notif_enabled_false(self):
        self.subscription.is_notif_enabled = False
        self.subscription.save()

        SendLeadersTradesNotifCron().run()

        notifications = Notification.objects.filter(user=self.user1)
        assert notifications.count() == 0
