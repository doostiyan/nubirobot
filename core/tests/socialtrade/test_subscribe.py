from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from unittest.mock import patch

from django.conf import settings
from rest_framework.authtoken.models import Token

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, Settings, get_currency_codename
from exchange.socialtrade.models import SocialTradeSubscription
from exchange.wallet.models import Wallet
from tests.base.utils import create_order
from tests.socialtrade.helpers import SocialTradeBaseAPITest


class SocialTradeAPITest(SocialTradeBaseAPITest):
    url = '/social-trade/subscriptions'

    def setUp(self):
        self.user = User.objects.get(pk=201)

        vp = self.user.get_verification_profile()
        vp.email_confirmed = True
        vp.save()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

        self.leader = self.create_leader(subscription_currency=Currencies.usdt)
        self.leader.activates_at = ir_now()
        self.leader.save()

        self.leader_wallet = Wallet.get_user_wallet(self.leader.user.id, Currencies.usdt)
        self.system_wallet = Wallet.get_user_wallet(settings.SOCIAL_TRADE['fee_user'], Currencies.usdt)
        self.user_wallet = Wallet.get_user_wallet(self.user.id, Currencies.usdt)
        self.user_wallet.create_transaction('manual', 1000).commit()
        self.user_wallet.refresh_from_db()
        self.initial_user_balance = self.user_wallet.balance

    def request(self, leader_id: Optional[int] = None, is_auto_renewal_enabled: Optional[bool] = None):
        data = {}
        if leader_id:
            data['leaderId'] = leader_id

        if is_auto_renewal_enabled:
            data['isAutoRenewalEnabled'] = is_auto_renewal_enabled

        return self.client.post(self.url, data=data)

    def assert_ok(self, response, expected_subscription: dict):
        assert response.status_code == 200, response.json()
        result = response.json()
        assert result['status'] == 'ok'
        actual_result = result['subscription']
        for key in [
            'id',
            'createdAt',
            'subscriptionCurrency',
            'subscriptionFee',
            'isTrial',
            'startsAt',
            'expiresAt',
            'canceledAt',
            'isAutoRenewalEnabled',
            'leader',
            'isNotifEnabled',
        ]:
            assert key in actual_result

        subscription = SocialTradeSubscription.objects.filter(pk=actual_result['id']).first()
        assert subscription is not None
        assert actual_result['subscriptionCurrency'] == get_currency_codename(expected_subscription['currency'])
        assert actual_result['subscriptionFee'] == str(expected_subscription['fee'])
        assert actual_result['isTrial'] == expected_subscription['is_trial']
        assert actual_result['isAutoRenewalEnabled'] == expected_subscription['is_auto_renewal_enabled']
        assert actual_result['isNotifEnabled'] is True
        assert actual_result['startsAt'] is not None
        assert datetime.fromisoformat(
            actual_result['expiresAt'],
        ) == datetime.fromisoformat(actual_result['startsAt']) + timedelta(days=expected_subscription['period'])
        assert actual_result['canceledAt'] is None
        assert actual_result['leader']['id'] == expected_subscription['leader'].pk
        self.user_wallet.refresh_from_db()
        self.leader_wallet.refresh_from_db()
        self.system_wallet.refresh_from_db()

        if expected_subscription['is_trial']:
            assert self.user_wallet.balance == self.initial_user_balance
            assert self.leader_wallet.balance == 0
            assert self.system_wallet.balance == 0

            assert subscription.withdraw_transaction is None
            assert subscription.leader_transaction is None
            assert subscription.system_transaction is None
        else:
            assert self.user_wallet.balance == self.initial_user_balance - self.leader.subscription_fee
            assert self.leader_wallet.balance == self.leader.subscription_fee * (1 - self.leader.system_fee_rate)
            assert self.system_wallet.balance == self.leader.subscription_fee * self.leader.system_fee_rate

            assert subscription.withdraw_transaction is not None
            assert subscription.leader_transaction is not None
            assert subscription.system_transaction is not None
            assert subscription.withdraw_transaction.amount == -self.leader.subscription_fee
            assert subscription.leader_transaction.amount == self.leader_wallet.balance
            assert subscription.system_transaction.amount == self.system_wallet.balance

            assert subscription.withdraw_transaction.currency == self.leader.subscription_currency
            assert subscription.leader_transaction.currency == self.leader.subscription_currency
            assert subscription.system_transaction.currency == self.leader.subscription_currency

    def assert_failed(self, response, status_code, code, message):
        assert response.status_code == status_code
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == code
        assert result['message'] == message

        self.user_wallet.refresh_from_db()
        self.leader_wallet.refresh_from_db()
        self.system_wallet.refresh_from_db()
        assert self.user_wallet.balance == self.initial_user_balance
        assert self.leader_wallet.balance == 0
        assert self.system_wallet.balance == 0

    def assert_leader_not_found(self, response):
        self.assert_failed(response, 422, 'LeaderNotFound', 'Leader not found')

    def assert_already_subscribed(self, response):
        self.assert_failed(response, 422, 'AlreadySubscribed', 'Already subscribed to this leader')

    def test_subscribe_trial(self):
        response = self.request(self.leader.pk, is_auto_renewal_enabled=True)
        self.assert_ok(
            response,
            dict(
                leader=self.leader,
                is_auto_renewal_enabled=True,
                currency=self.leader.subscription_currency,
                fee=self.leader.subscription_fee,
                is_trial=True,
                period=settings.SOCIAL_TRADE['subscriptionTrialPeriod'],
            ),
        )

    def test_subscribe_when_no_trial_left(self):
        for _ in range(int(Settings.get('social_trade_max_trial_count', 3))):
            leader = self.create_leader()
            self.create_subscription(self.user, leader)

        response = self.request(self.leader.pk, is_auto_renewal_enabled=True)
        self.assert_ok(
            response,
            dict(
                leader=self.leader,
                is_auto_renewal_enabled=True,
                currency=self.leader.subscription_currency,
                fee=self.leader.subscription_fee,
                is_trial=False,
                period=settings.SOCIAL_TRADE['subscriptionPeriod'],
            ),
        )

    def test_subscribe_when_already_used_trial_on_leader_canceled(self):
        subscription = self.create_subscription(self.user, self.leader, is_trial=True)
        subscription.canceled_at = ir_now()
        subscription.save()

        response = self.request(self.leader.pk, is_auto_renewal_enabled=True)
        self.assert_ok(
            response,
            dict(
                leader=self.leader,
                is_auto_renewal_enabled=True,
                currency=self.leader.subscription_currency,
                fee=self.leader.subscription_fee,
                is_trial=False,
                period=settings.SOCIAL_TRADE['subscriptionPeriod'],
            ),
        )

    def test_subscribe_when_already_used_trial_on_leader_expired(self):
        subscription = self.create_subscription(self.user, self.leader, is_trial=True)
        subscription.expires_at = ir_now()
        subscription.save()

        response = self.request(self.leader.pk, is_auto_renewal_enabled=True)
        self.assert_ok(
            response,
            dict(
                leader=self.leader,
                is_auto_renewal_enabled=True,
                currency=self.leader.subscription_currency,
                fee=self.leader.subscription_fee,
                is_trial=False,
                period=settings.SOCIAL_TRADE['subscriptionPeriod'],
            ),
        )

    def test_subscribe_when_reached_limit(self):
        for _ in range(int(Settings.get('social_trade_max_subscription_count', 5))):
            leader = self.create_leader()
            self.create_subscription(self.user, leader)

        response = self.request(self.leader.pk, is_auto_renewal_enabled=True)
        self.assert_failed(response, 422, 'ReachedSubscriptionLimit', 'Reached total subscription limit')

    def test_subscribe_missing_leader_id(self):
        response = self.request(is_auto_renewal_enabled=True)
        self.assert_failed(response, 400, 'ParseError', 'Missing integer value')

    def test_subscribe_missing_auto_renewal(self):
        response = self.request(leader_id=self.leader.pk)
        self.assert_failed(response, 400, 'ParseError', 'Missing boolean value')

    def test_subscribe_leader_invalid_id(self):
        response = self.request(leader_id='not-int', is_auto_renewal_enabled=True)
        self.assert_failed(response, 400, 'ParseError', 'Invalid integer value: "not-int"')

    def test_subscribe_leader_invalid_is_auto_renewal_enabled(self):
        response = self.request(leader_id=self.leader.pk, is_auto_renewal_enabled='not-bool')
        self.assert_failed(response, 400, 'ParseError', 'Invalid boolean value: "not-bool"')

    def test_subscribe_leader_not_found(self):
        response = self.request(leader_id=-1, is_auto_renewal_enabled=True)
        self.assert_leader_not_found(response)

    def test_subscribe_leader_not_active(self):
        self.leader.activates_at = ir_now() + timedelta(seconds=1)
        self.leader.save()
        response = self.request(leader_id=self.leader.pk, is_auto_renewal_enabled=True)
        self.assert_leader_not_found(response)

    def test_subscribe_leader_deleted(self):
        self.leader.deleted_at = ir_now()
        self.leader.save()
        response = self.request(leader_id=self.leader.pk, is_auto_renewal_enabled=True)
        self.assert_leader_not_found(response)

    def test_subscribe_already_subscribed(self):
        subscription = self.create_subscription(self.user, self.leader, is_trial=True)
        response = self.request(leader_id=self.leader.pk, is_auto_renewal_enabled=True)
        self.assert_already_subscribed(response)

        subscription.is_trial = False
        subscription.save()
        response = self.request(leader_id=self.leader.pk, is_auto_renewal_enabled=True)
        self.assert_already_subscribed(response)

    @patch('exchange.socialtrade.models.SocialTradeSubscription.is_trial_available', lambda u,l: False)
    def test_subscribe_insufficient_balance(self):
        # when balance is not enough
        self.user_wallet.create_transaction('manual', -1).commit()
        response = self.request(leader_id=self.leader.pk, is_auto_renewal_enabled=True)
        self.user_wallet.create_transaction('manual', 1).commit()
        self.assert_failed(response, 422, 'InsufficientBalance', 'Wallet balance is not enough')

        # when balance is blocked
        create_order(self.user, Currencies.usdt, Currencies.rls, Decimal('0.5'), Decimal('140e7'), sell=True)
        self.charge_wallet(self.user, Currencies.usdt, Decimal('-0.5'))
        assert self.user_wallet.balance == 1000
        assert self.user_wallet.active_balance == Decimal('999.5')

        response = self.request(leader_id=self.leader.pk, is_auto_renewal_enabled=True)
        self.assert_failed(response, 422, 'InsufficientBalance', 'Wallet balance is not enough')

    def test_subscribe_to_self(self):
        leader_user = self.leader.user
        token = Token.objects.create(key=f'{leader_user.username}Token', user=leader_user)
        leader_user.auth_token = token
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {leader_user.auth_token.key}')
        response = self.request(leader_id=self.leader.pk, is_auto_renewal_enabled=True)
        self.assert_failed(response, 422, 'SelfSubscriptionImpossible', 'Subscribing oneself is not possible')
