import random
import string
import tempfile
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List
from unittest.mock import patch

from django.core.management import call_command
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.calendar import as_ir_tz, ir_now
from exchange.base.crypto import random_string
from exchange.base.models import ACTIVE_CURRENCIES, RIAL, Currencies, Settings, get_currency_codename
from exchange.features.models import QueueItem
from exchange.margin.models import Position
from exchange.market.models import Order
from exchange.portfolio.models import UserTotalDailyProfit
from exchange.socialtrade.models import Leader, SocialTradeAvatar, SocialTradeSubscription
from exchange.socialtrade.validators import FEE_BOUNDARY_KEY
from exchange.wallet.models import Wallet
from tests.features.utils import BetaFeatureTestMixin


class SocialTradeMixin(BetaFeatureTestMixin):
    def create_user(self):
        username = random_string(12)
        user = User.objects.create(
            username=username,
            email=username + '@gmail.com',
            first_name='first_name',
            birthday=datetime(year=1993, month=11, day=15),
            gender=User.GENDER.female,
            city='Tehran',
            requires_2fa=True,
            mobile=str(9980000001 + random.randrange(1, 10**6)),
        )
        return user

    def create_avatar(self, *, is_active=True):
        return SocialTradeAvatar.objects.create(
            image=tempfile.NamedTemporaryFile(suffix='.jpg').name,
            is_active=is_active,
        )

    def create_leader(self, user=None, fee=1000, subscription_currency=RIAL):
        user = user or self.create_user()
        leader = Leader.objects.create(
            user=user,
            nickname=random_string(12),
            subscription_fee=fee,
            subscription_currency=subscription_currency,
            avatar=self.create_avatar(),
            system_fee_percentage=Decimal('10.34'),
        )
        leader.activates_at = ir_now()
        leader.save()
        return leader

    def create_subscription(
        self,
        user=None,
        leader=None,
        fee=1000,
        *,
        is_trial=True,
        is_auto_renewal_enabled=True,
        is_notif_enabled=True,
    ):
        user = user or self.create_user()
        leader = leader or self.create_leader(fee=fee)
        return SocialTradeSubscription.objects.create(
            subscriber=user,
            leader=leader,
            is_trial=is_trial,
            is_auto_renewal_enabled=is_auto_renewal_enabled,
            is_notif_enabled=is_notif_enabled,
        )

    def charge_wallet(self, user: User, currency: int, amount: Decimal, tp=Wallet.WALLET_TYPE.spot) -> Wallet:
        wallet = Wallet.get_user_wallet(user.id, currency, tp=tp)
        wallet.create_transaction('manual', amount).commit()
        wallet.refresh_from_db()
        return wallet

    def set_fee_boundary(self, currency: int, max_fee: Decimal, min_fee: Decimal):
        currency_codename = get_currency_codename(currency)
        Settings.set_dict(
            FEE_BOUNDARY_KEY,
            {'max': {currency_codename: str(max_fee)}, 'min': {currency_codename: str(min_fee)}},
        )

class SocialTradeBaseAPITest(SocialTradeMixin, APITestCase):
    pass


class SocialTradeTestDataMixin(BetaFeatureTestMixin):
    """
    Overall, this class can create the following test data:
    1- Two leaders on users 201 and 202 named as self.leader and self.leader_two
    2- A default of 8 users named as 'user_n' with confirmed email and mobile, to be used as subscribers to leaders
       'user_n' is the self.subscribers[n-1]
    3- Subscriptions will be as follows:
        users user_1 and user_5 will be the active subscribers of self.leader and self.leader_two
        users user_2 and user_6 will have expired subscriptions of self.leader and self.leader_two
        users user_3 and user_7 will have cancelled subscriptions of self.leader and self.leader_two
        users user_4 and user_8 will have waiting subscriptions of self.leader and self.leader_two
        users user_1, user_2, user_3, and user_4 are on paid subscriptions to self.leader and self.leader_two
        users user_5, user_6, user_7, and user_8 are on trial subscriptions to self.leader and self.leader_two
        subscriptions to self.leader are called self.subscriptions and self.trials
        subscriptions to self.leader_two are called self.leader_two_subscriptions and self.leader_two_trials
    4- Trades will be as follows:
        4 orders for both leaders with created_at as 4 hours ago, 3 days ago, 10 days ago, and 50 days ago
        4 positions for both leaders with created_at as 1 hour ago, 4 days ago, 9 days ago, and 51 days ago
        4 exchange_trades for both leaders with created_at as 3 hours ago, 2 days ago, 12 days ago, and 52 days ago
        self.orders[i] where i%2==0 belongs to self.leader, self.orders[i] where i%2==1 belongs to self.leader_two
        self.positions[i] where i%2==0 belongs to self.leader, self.positions[i] where i%2==1 belongs to self.leader_two
        self.xchanges[i] where i%2==0 belongs to self.leader, self.xchanges[i] where i%2==1 belongs to self.leader_two
        All subscribers of self.leader and self.leader_two should see all the first 3 trades (self.orders[0:3] etc)
        All non-subscribers of self.leader and self.leader_two should only see the second trades (self.orders[1] etc)
    5- Portfolio data will be as follows:
        self.leader will have 4 days worth of portfolio data
        self.leader_two will have 2 days worth of portfolio data
        self.leader_three will not have any portfolio data
    """

    def create_test_data(self):
        self.user_one = User.objects.get(pk=201)
        self.user_two = User.objects.get(pk=202)
        self.user_three = User.objects.get(pk=203)

        self.user_one.mobile = '09012345678'
        self.user_one.save()
        vp = self.user_one.get_verification_profile()
        vp.mobile_confirmed = True
        vp.email_confirmed = True
        vp.save()

        for user in [self.user_one, self.user_two, self.user_three]:
            Wallet.create_user_wallets(user)

        self.leaders = self._create_leaders([self.user_one, self.user_two])
        self.leaders.sort(key=lambda leader: leader.id)
        self.leader, self.leader_two = self.leaders[0], self.leaders[1]
        self.leader_three = self._create_leaders([self.user_three])[0]
        (
            self.subscribers,
            self.subscriptions,
            self.trials,
            self.leader_two_subscriptions,
            self.leader_two_trials,
        ) = self._create_subscribers_with_subscriptions()

    def _create_leaders(self, users: [User]) -> [Leader]:
        for user in users:
            leader = Leader.objects.create(
                user=user,
                nickname=f'test_{user.username}',
                avatar=SocialTradeAvatar.objects.create(
                    image=tempfile.NamedTemporaryFile(suffix='.jpg').name,
                ),
                subscription_fee=10,
                subscription_currency=Currencies.usdt,
                system_fee_percentage=10,
                gained_subscription_fees=0,
                last_month_profit_percentage=5 + round(random.random(), 2),
            )
            leader.activates_at = ir_now()
            leader.save()
        return list(Leader.objects.filter(user_id__in=[user.id for user in users]))

    def _create_subscribers_with_subscriptions(self, num_of_users: int = 8, num_of_subs: int = 4):
        users = self._create_subscribers(num=num_of_users)
        SocialTradeSubscription.objects.all().delete()
        subscriptions = self._create_subscriptions(
            users=users[:num_of_subs],
            is_trial=False,
            activeness_info=[{}, {'expired': True}, {'canceled': True}, {'waiting': True}],
        )
        trials = self._create_subscriptions(
            users=users[num_of_subs:],
            is_trial=True,
            activeness_info=[{}, {'expired': True}, {'canceled': True}, {'waiting': True}],
        )
        leader_two_subscriptions = self._create_subscriptions(
            users=users[:num_of_subs],
            is_trial=False,
            leader=self.leader_two,
            activeness_info=[{}, {'expired': True}, {'canceled': True}, {'waiting': True}],
        )
        leader_two_trials = self._create_subscriptions(
            users=users[num_of_subs:],
            is_trial=True,
            leader=self.leader_two,
            activeness_info=[{}, {'expired': True}, {'canceled': True}, {'waiting': True}],
        )
        return users, subscriptions, trials, leader_two_subscriptions, leader_two_trials

    def _create_subscribers(self, num: int) -> [User]:
        User.objects.filter(username__contains='user_').delete()
        users = [
            User.objects.create_user(
                username=f'user_{i+1}',
                email=f'user_{i+1}@example.com',
                mobile=''.join(random.choices(string.digits, k=10)),
            )
            for i in range(num)
        ]
        for user in users:
            vp = user.get_verification_profile()
            vp.email_confirmed = True
            vp.mobile_confirmed = True
            vp.save()
        return users

    def _create_subscriptions(
        self, users: [User], is_trial: bool, leader: Leader = None, activeness_info: [dict] = None
    ) -> [SocialTradeSubscription]:
        if not leader:
            leader = self.leader
        if not activeness_info:
            activeness_info = []
        right_now = ir_now()
        non_waiting_subscriptions = []
        waiting_subscriptions = []
        for user, activeness in zip(users, activeness_info):
            if activeness.get('waiting', False):
                waiting_subscriptions.append(
                    SocialTradeSubscription(
                        leader=leader,
                        is_trial=is_trial,
                        fee_amount=leader.subscription_fee,
                        fee_currency=leader.subscription_currency,
                        subscriber=user,
                        starts_at=right_now + timedelta(days=1),
                        expires_at=right_now + timedelta(days=2),
                    )
                )
            else:
                if not is_trial:
                    # Added so that annotate_is_trial_available works correctly.
                    subscription = SocialTradeSubscription.objects.create(
                        leader=leader,
                        is_trial=True,
                        fee_amount=leader.subscription_fee,
                        fee_currency=leader.subscription_currency,
                        subscriber=user,
                        starts_at=right_now - timedelta(days=35),
                    )
                    subscription.expires_at = right_now - timedelta(days=30)
                self._charge_wallet(user, leader.subscription_currency, leader.subscription_fee)
                subscription = SocialTradeSubscription.objects.create(
                    leader=leader,
                    is_trial=is_trial,
                    fee_amount=leader.subscription_fee,
                    fee_currency=leader.subscription_currency,
                    subscriber=user,
                    starts_at=right_now,
                )
                if activeness.get('expired', False):
                    subscription.expires_at = right_now
                    subscription.save()
                if activeness.get('canceled', False):
                    subscription.canceled_at = right_now
                    subscription.save()
                non_waiting_subscriptions.append(subscription)

        return [*non_waiting_subscriptions, *SocialTradeSubscription.objects.bulk_create(waiting_subscriptions)]

    def _charge_wallet(self, user: User, currency: int, amount: Decimal, tp=Wallet.WALLET_TYPE.spot) -> Wallet:
        wallet = Wallet.get_user_wallet(user.id, currency, tp=tp)
        wallet.create_transaction('manual', amount).commit()
        wallet.refresh_from_db()
        return wallet

    def _create_trades(self):
        Order.objects.all().delete()
        Position.objects.all().delete()

        self.order_timedeltas = [timedelta(hours=4), timedelta(days=3), timedelta(days=10), timedelta(days=50)]
        self.position_timedeltas = [timedelta(hours=1), timedelta(days=4), timedelta(days=9), timedelta(days=51)]
        self.current_time = ir_now()

        self.orders, self.positions, self.xchanges = [], [], []
        for order_timedelta in self.order_timedeltas:
            for leader in self.leaders:
                order = Order.objects.create(
                    user=leader.user,
                    src_currency=Currencies.btc,
                    dst_currency=Currencies.usdt,
                    order_type=1,
                    trade_type=Order.TRADE_TYPES.margin,
                    execution_type=1,
                    price=1000,
                    amount=1000,
                )
                order.created_at = self.current_time - order_timedelta
                order.save()
                self.orders.append(order)

        for position_timedelta in self.position_timedeltas:
            for leader in self.leaders:
                self.positions.append(
                    Position.objects.create(
                        user=leader.user,
                        opened_at=self.current_time - position_timedelta,
                        created_at=self.current_time - position_timedelta,
                        src_currency=Currencies.btc,
                        dst_currency=Currencies.usdt,
                        side=Position.SIDES.sell,
                        delegated_amount=Decimal('0.001'),
                        earned_amount=Decimal('21'),
                        collateral=Decimal('43.1'),
                        status=Position.STATUS.closed,
                        entry_price=29000,
                    )
                )

    def _create_leader_portfolios_without_withdraw_and_deposit(
        self, full_portfo_leader: Leader, one_day_portfo_leader: Leader
    ):
        self.report_day_count = 4
        first_balance = Decimal(1_000_000_0)
        daily_profits = [Decimal(0), Decimal(500_000_0), Decimal(-300_000_0), Decimal(600_000_0)]
        daily_profit_percentage = [Decimal(0), Decimal(50), Decimal(-20), Decimal(50)]
        today = ir_now().replace(hour=23, minute=59, second=59)
        self.report_dates = [(today - timedelta(days=i)).date() for i in range(self.report_day_count, 0, -1)]

        for i in range(self.report_day_count):
            UserTotalDailyProfit.objects.create(
                report_date=self.report_dates[i],
                user=full_portfo_leader.user,
                total_balance=first_balance + sum(daily_profits[: i + 1]),
                profit=daily_profits[i],
                profit_percentage=daily_profit_percentage[i],
                total_withdraw=Decimal(0),
                total_deposit=Decimal(0),
            )
        full_portfo_leader.update_profits()

        for i in range(self.report_day_count - 2):
            UserTotalDailyProfit.objects.create(
                report_date=self.report_dates[i + 2],
                user=one_day_portfo_leader.user,
                total_balance=first_balance + sum(daily_profits[: i + 1]),
                profit=daily_profits[i],
                profit_percentage=daily_profit_percentage[i],
                total_withdraw=Decimal(0),
                total_deposit=Decimal(0),
            )
        one_day_portfo_leader.update_profits()

    def _create_leader_portfolios_with_withdraw_and_deposit(
        self, full_portfo_leader: Leader, one_day_portfo_leader: Leader
    ):
        self.report_day_count = 4
        first_balance = Decimal(1_000_000_0)
        daily_profits = [Decimal(0), Decimal(400_000_0), Decimal(300_000_0), Decimal(-100_000_0)]
        daily_profit_percentage = [Decimal(0), Decimal(40), Decimal(20), Decimal(-14.286)]
        withdraws = [Decimal(0), Decimal(100_000_0), Decimal(100_000_0), Decimal(400_000_0)]
        deposits = [Decimal(0), Decimal(200_000_0), Decimal(400_000_0), Decimal(200_000_0)]
        today = ir_now().replace(hour=23, minute=59, second=59)
        self.report_dates = [(today - timedelta(days=i)).date() for i in range(self.report_day_count, 0, -1)]

        for i in range(self.report_day_count):
            UserTotalDailyProfit.objects.create(
                report_date=self.report_dates[i],
                user=full_portfo_leader.user,
                total_balance=first_balance
                + sum(daily_profits[: i + 1])
                + sum(deposits[: i + 1])
                - sum(withdraws[: i + 1]),
                profit=daily_profits[i],
                profit_percentage=daily_profit_percentage[i],
                total_withdraw=withdraws[i],
                total_deposit=deposits[i],
            )
        full_portfo_leader.update_profits()

        for i in range(self.report_day_count - 2):
            UserTotalDailyProfit.objects.create(
                report_date=self.report_dates[i + 2],
                user=one_day_portfo_leader.user,
                total_balance=first_balance
                + sum(daily_profits[: i + 1])
                + sum(deposits[: i + 1])
                - sum(withdraws[: i + 1]),
                profit=daily_profits[i],
                profit_percentage=daily_profit_percentage[i],
                total_withdraw=withdraws[i],
                total_deposit=deposits[i],
            )
        one_day_portfo_leader.update_profits()

    def create_user_wallets(self, user: User, currecies: List[int] = ACTIVE_CURRENCIES):
        for currency in currecies:
            Wallet.get_user_wallet(user, currency)

    def charge_user_wallet(self, user: User, currency: int, amount: Decimal):
        wallet = Wallet.get_user_wallet(user, currency)
        wallet.balance = amount
        wallet.save()

    def enable_feature_for_user(self, user: User, feature: int):
        QueueItem.objects.create(feature=feature, user=user, status=QueueItem.STATUS.done)


@contextmanager
def enable_email(users):
    if not isinstance(users, list):
        users = [users]

    Settings.set_dict('email_whitelist', [user.email for user in users])
    call_command('update_email_templates')
    yield
    with patch('django.db.connection.close'):
        call_command('send_queued_mail')


def to_dt_irantz(str_dt: str):
    return as_ir_tz(datetime.fromisoformat(str_dt))
