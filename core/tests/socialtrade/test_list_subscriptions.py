import datetime
from decimal import Decimal

from exchange.accounts.models import User
from exchange.base.calendar import as_ir_tz, ir_now
from exchange.base.models import Currencies
from exchange.base.serializers import serialize
from exchange.wallet.models import Wallet
from tests.socialtrade.helpers import SocialTradeBaseAPITest


class UserSubscriptionsAPITest(SocialTradeBaseAPITest):
    URL = '/social-trade/subscriptions'

    def setUp(self):
        self.user = User.objects.get(id=201)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.user2 = User.objects.get(id=203)
        self.leader1 = self.create_leader()
        self.leader2 = self.create_leader()

        user_wallet = Wallet.get_user_wallet(self.user.id, Currencies.rls)
        user_wallet.create_transaction('manual', 100000).commit()
        user_wallet.refresh_from_db()

        user2_wallet = Wallet.get_user_wallet(self.user2.id, Currencies.rls)
        user2_wallet.create_transaction('manual', 100000).commit()
        user2_wallet.refresh_from_db()

        self.subscription1 = self.create_subscription(self.user, self.leader1, is_auto_renewal_enabled=True)
        self.subscription2 = self.create_subscription(
            self.user, self.leader2, is_trial=False, is_auto_renewal_enabled=False
        )
        self.expired_subscription = self.create_subscription(
            self.user, self.leader1, is_trial=False, is_auto_renewal_enabled=True
        )
        self.expired_subscription.expires_at = ir_now() - datetime.timedelta(minutes=1)
        self.expired_subscription.save()
        self.user_2_subscription1 = self.create_subscription(
            self.user2, self.leader2, is_trial=False, is_auto_renewal_enabled=True
        )

    def test_get_subscriptions_list(self):
        response = self.client.get(self.URL)
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
        subscriptions = response.json()['subscriptions']
        assert len(subscriptions) == 2
        assert subscriptions[1]['id'] == self.subscription1.id
        assert subscriptions[0]['id'] == self.subscription2.id
        assert subscriptions[0]['subscriptionCurrency'] == 'rls'
        assert Decimal(subscriptions[0]['subscriptionFee']) == self.leader1.subscription_fee
        assert subscriptions[0]['isTrial'] is False
        assert subscriptions[0]['createdAt'] == serialize(self.subscription2.created_at)
        assert as_ir_tz(datetime.datetime.fromisoformat(subscriptions[0]['startsAt'])) == self.subscription2.starts_at
        assert as_ir_tz(datetime.datetime.fromisoformat(subscriptions[0]['expiresAt'])) == self.subscription2.expires_at
        assert subscriptions[0]['canceledAt'] is None
        assert subscriptions[0]['isAutoRenewalEnabled'] is False
        assert subscriptions[0]['leader']['id'] == self.leader2.id
        assert subscriptions[0]['leader']['nickname'] == self.leader2.nickname
        assert subscriptions[0]['leader']['subscriptionCurrency'] == 'rls'
        assert Decimal(subscriptions[0]['leader']['subscriptionFee']) == self.leader2.subscription_fee
        assert subscriptions[0]['leader']['avatar']['id'] == self.leader2.avatar.id
        assert subscriptions[0]['leader']['avatar']['image'] is not None
        assert 'isTrialAvailable' not in subscriptions[0]['leader']
        assert 'isSubscribed' not in subscriptions[0]['leader']
        assert 'gainedSubscriptionFees' not in subscriptions[0]['leader']
        assert 'assetRatios' not in subscriptions[0]['leader']
        assert 'dailyProfits' not in subscriptions[0]['leader']
        assert 'numberOfUnsubscribes' not in subscriptions[0]['leader']
