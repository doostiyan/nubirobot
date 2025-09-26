import datetime
from decimal import Decimal

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import RIAL, Currencies, get_currency_codename
from exchange.margin.models import Position
from exchange.market.models import UserTradeStatus
from exchange.socialtrade.models import SocialTradeSubscription
from tests.socialtrade.helpers import SocialTradeBaseAPITest


class LeaderboardAPITest(SocialTradeBaseAPITest):
    URL = '/social-trade/leaders'

    def setUp(self) -> None:
        self.user_1 = User.objects.get(id=201)
        self.charge_wallet(self.user_1, RIAL, 10000000)

        self.user_2 = User.objects.get(id=202)
        self.user_3 = User.objects.get(id=203)
        self.user_4 = User.objects.get(id=204)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user_1.auth_token.key}')
        self.leader = self.create_leader()
        UserTradeStatus.objects.update_or_create(
            user=self.leader.user, defaults=dict(month_trades_total=Decimal('1234.56'))
        )

        position_data = dict(
            user=self.leader.user,
            created_at=ir_now() - datetime.timedelta(seconds=1),
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            delegated_amount='0.001',
            earned_amount='21',
            collateral='43.1',
            entry_price='123',
            exit_price='123.45',
            status=Position.STATUS.closed,
        )
        Position.objects.bulk_create(
            [
                Position(
                    **position_data,
                    pnl=1,
                    closed_at=ir_now() - datetime.timedelta(seconds=1),
                ),
                Position(
                    **position_data,
                    pnl=-1,
                    closed_at=ir_now() - datetime.timedelta(days=6),
                ),
                Position(
                    **position_data,
                    pnl=-1,
                    closed_at=ir_now() - datetime.timedelta(days=10),
                ),
                Position(
                    **position_data,
                    pnl=-1,
                    closed_at=ir_now() - datetime.timedelta(days=40),
                ),
                Position(
                    **position_data,
                    pnl=-1,
                    closed_at=ir_now() - datetime.timedelta(days=100),
                ),
            ]
        )

    def test_get_all_leaders_successfully(self):
        response = self.client.get(path=self.URL)
        assert response.status_code == 200
        output = response.json()
        assert output['status'] == 'ok'
        assert not output['hasNext']
        assert len(output['data']) == 1
        assert output['data'][0]['avatar']
        assert output['data'][0]['createdAt']
        assert output['data'][0]['id'] == self.leader.id
        assert output['data'][0]['nickname'] == self.leader.nickname
        assert output['data'][0]['subscriptionCurrency'] == get_currency_codename(self.leader.subscription_currency)
        assert output['data'][0]['subscriptionFee'] == str(self.leader.subscription_fee)
        assert output['data'][0]['lastMonthProfitPercentage'] == '0'
        assert output['data'][0]['numberOfSubscribers'] == 0
        assert output['data'][0]['isTrialAvailable'] is True
        assert output['data'][0]['winrate7'] == 50
        assert output['data'][0]['winrate30'] == 33
        assert output['data'][0]['winrate90'] == 25
        assert output['data'][0]['lastMonthTradeVolume'] == '1234.56'

    def test_get_all_leaders_successfully_public(self):
        self.client.credentials()
        response = self.client.get(path=self.URL)
        assert response.status_code == 200
        output = response.json()
        assert output['status'] == 'ok'
        assert not output['hasNext']
        assert len(output['data']) == 1
        assert output['data'][0]['avatar']
        assert output['data'][0]['createdAt']
        assert output['data'][0]['id'] == self.leader.id
        assert output['data'][0]['nickname'] == self.leader.nickname
        assert output['data'][0]['subscriptionCurrency'] == get_currency_codename(self.leader.subscription_currency)
        assert output['data'][0]['subscriptionFee'] == str(self.leader.subscription_fee)
        assert output['data'][0]['lastMonthProfitPercentage'] == '0'
        assert output['data'][0]['numberOfSubscribers'] == 0
        assert output['data'][0]['winrate7'] == 50
        assert output['data'][0]['winrate30'] == 33
        assert output['data'][0]['winrate90'] == 25
        assert output['data'][0]['lastMonthTradeVolume'] == '1234.56'

    def test_get_all_leaders_exclude_request_user_leader(self):
        self.leader = self.create_leader(self.user_1)

        response = self.client.get(path=self.URL)
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
        assert len(response.json()['data']) == 1

        self.client.credentials()
        response = self.client.get(path=self.URL)
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
        assert len(response.json()['data']) == 2

    def test_get_all_leaders_with_subscriber_sort_successfully(self):
        leader = self.create_leader(user=self.user_3)
        leader.last_month_profit_percentage = 1000000
        leader.save()

        SocialTradeSubscription.objects.create(
            leader=leader,
            subscriber=self.user_4,
            expires_at=ir_now() + datetime.timedelta(days=4),
            starts_at=ir_now(),
            is_trial=True,
            fee_amount=1000,
            fee_currency=2,
        )

        response = self.client.get(path=self.URL + '?order=mostSubscriber')
        assert response.status_code == 200
        output = response.json()
        assert output['data'][0]['id'] == leader.id
        assert output['data'][0]['numberOfSubscribers'] == 1
        assert output['data'][1]['id'] == self.leader.id
        assert output['data'][1]['numberOfSubscribers'] == 0

        response = self.client.get(path=self.URL + '?order=leastSubscriber')
        assert response.status_code == 200
        output = response.json()
        assert output['data'][0]['id'] == self.leader.id
        assert output['data'][0]['numberOfSubscribers'] == 0
        assert output['data'][1]['id'] == leader.id
        assert output['data'][1]['numberOfSubscribers'] == 1

        response = self.client.get(path=self.URL + '?order=newest')
        assert response.status_code == 200
        output = response.json()
        assert output['data'][0]['id'] == leader.id
        assert output['data'][1]['id'] == self.leader.id

        response = self.client.get(path=self.URL + '?order=mostProfit')
        assert response.status_code == 200
        output = response.json()
        assert output['data'][0]['id'] == leader.id
        assert output['data'][1]['id'] == self.leader.id

        response = self.client.get(path=self.URL + '?order=mostVolume')
        assert response.status_code == 200
        output = response.json()
        assert output['data'][0]['id'] == self.leader.id
        assert output['data'][1]['id'] == leader.id

    def test_get_all_leaders_with_profit_sort_successfully(self):
        leader = self.create_leader(user=self.user_3)
        leader.last_month_profit_percentage = '-10.12'
        leader.save()

        self.leader.last_month_profit_percentage = '34.12'
        self.leader.save()

        response = self.client.get(path=self.URL + '?order=mostProfit')
        assert response.status_code == 200
        output = response.json()
        assert output['data'][0]['id'] == self.leader.id
        assert output['data'][0]['lastMonthProfitPercentage'] == '34.12'
        assert output['data'][1]['id'] == leader.id
        assert output['data'][1]['lastMonthProfitPercentage'] == '-10.12'

        response = self.client.get(path=self.URL + '?order=leastProfit')
        assert response.status_code == 200
        output = response.json()
        assert output['data'][0]['id'] == leader.id
        assert output['data'][0]['lastMonthProfitPercentage'] == '-10.12'
        assert output['data'][1]['id'] == self.leader.id
        assert output['data'][1]['lastMonthProfitPercentage'] == '34.12'

    def test_get_all_leaders_with_only_subscribed_leader_successfully(self):
        leader = self.create_leader(user=self.user_3)
        SocialTradeSubscription.objects.create(
            leader=leader,
            subscriber=self.user_1,
            expires_at=ir_now() + datetime.timedelta(days=4),
            starts_at=ir_now(),
            is_trial=True,
            fee_amount=1000,
            fee_currency=2,
        )
        response = self.client.get(path=self.URL + '?onlySubscribed=true')
        assert response.status_code == 200
        output = response.json()
        assert len(output['data']) == 1
        assert output['data'][0]['id'] == leader.id

    def test_get_all_leaders_trial_available(self):
        leader_1 = self.create_leader(user=self.user_3)
        leader_2 = self.create_leader(user=self.user_4)
        self.create_subscription(user=self.user_1, leader=leader_1, is_trial=True)
        self.create_subscription(user=self.user_1, leader=leader_2, is_trial=False)

        response = self.client.get(path=self.URL)
        assert response.status_code == 200
        output = response.json()['data']
        output = sorted(output, key=lambda item: item['id'])

        assert len(output) == 3

        assert output[0]['id'] == self.leader.id
        assert output[0]['isTrialAvailable'] is True

        assert output[1]['id'] == leader_1.id
        assert output[1]['isTrialAvailable'] is False

        assert output[2]['id'] == leader_2.id
        assert output[2]['isTrialAvailable'] is True

    def test_get_all_leaders_is_subscribed(self):
        leader_1 = self.create_leader(user=self.user_3)
        leader_2 = self.create_leader(user=self.user_4)
        self.create_subscription(user=self.user_1, leader=leader_2)
        self.create_subscription(user=self.user_2, leader=leader_1)

        response = self.client.get(path=self.URL)
        assert response.status_code == 200
        output = response.json()['data']
        output = sorted(output, key=lambda item: item['id'])

        assert len(output) == 3

        assert output[0]['id'] == self.leader.id
        assert output[0]['isSubscribed'] is False

        assert output[1]['id'] == leader_1.id
        assert output[1]['isSubscribed'] is False

        assert output[2]['id'] == leader_2.id
        assert output[2]['isSubscribed'] is True


    def test_get_leaderboard_with_deleted_leader_when_subscribed(self):
        subscription = SocialTradeSubscription.objects.create(
            leader=self.leader,
            subscriber=self.user_1,
            expires_at=ir_now() + datetime.timedelta(days=4),
            starts_at=ir_now(),
            is_trial=True,
            fee_amount=1000,
            fee_currency=2,
        )
        subscription.is_trial = False
        subscription.save()
        self.leader.delete_leader(1)
        response = self.client.get(self.URL)
        assert response.status_code == 200
        output = response.json()
        assert output['status'] == 'ok'
        assert not output['hasNext']
        assert len(output['data']) == 1

    def test_get_leaderboard_with_deleted_leader_when_unsubscribed(self):
        self.leader.delete_leader(1)
        response = self.client.get(self.URL)
        assert response.status_code == 200
        output = response.json()
        assert output['status'] == 'ok'
        assert not output['hasNext']
        assert len(output['data']) == 0

    def test_get_leaderboard_with_inactive_leader(self):
        inactive_leader = self.create_leader()
        inactive_leader.activates_at = ir_now() + datetime.timedelta(minutes=1)
        inactive_leader.save()

        response = self.client.get(self.URL)
        assert response.status_code == 200
        output = response.json()
        assert output['status'] == 'ok'
        assert not output['hasNext']
        assert len(output['data']) == 1
