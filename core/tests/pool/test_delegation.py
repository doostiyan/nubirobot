from decimal import Decimal
from typing import Optional
from unittest.mock import patch

from django.core.cache import cache
from django.db.models import Sum
from django.utils.timezone import now
from rest_framework.test import APITestCase

from exchange.accounts.models import Notification, User, VerificationProfile
from exchange.base.calendar import ir_now
from exchange.base.models import AMOUNT_PRECISIONS_V2, Currencies, Settings
from exchange.base.serializers import serialize
from exchange.market.models import Market
from exchange.pool.models import (
    DelegationRevokeRequest,
    DelegationTransaction,
    LiquidityPool,
    PoolAccess,
    UserDelegation,
)
from exchange.wallet.models import Wallet


class DelegationTest(APITestCase):
    DELEGATION_URL = '/liquidity-pools/%s/delegations'

    def setUp(self):
        self.pool = self._create_pool(currency=Currencies.btc, capacity=10000, manager_id=410, is_active=True)
        self.user1 = User.objects.get(pk=201)
        self.user1.user_type = User.USER_TYPES.level2
        self.user1.save()
        VerificationProfile.objects.filter(id=self.user1.get_verification_profile().id).update(email_confirmed=True)

        self.wallet1 = Wallet.get_user_wallet(self.user1.id, Currencies.btc)
        self.initial_balance = 10
        self.wallet1.create_transaction('manual', self.initial_balance).commit()
        self.wallet1.refresh_from_db()

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user1.auth_token.key}')

    @classmethod
    def _create_pool(
            cls, currency: int, manager_id: int, capacity=Decimal(10000), filled_capacity=Decimal(0),
            is_active=True, is_private=False
    ) -> LiquidityPool:

        pool = LiquidityPool.objects.create(
            currency=currency,
            capacity=capacity,
            filled_capacity=filled_capacity,
            manager_id=manager_id,
            is_active=is_active,
            is_private=is_private,
            activated_at=ir_now(),
        )
        Settings.set(LiquidityPool.MIN_DELEGATION_SETTING_KEY, 1_000_0)
        for user_type in User.USER_TYPES:
            Settings.set(LiquidityPool.MAX_DELEGATION_SETTING_KEY % user_type[0], 1_000_000_0)

        market = Market.get_for(pool.currency, Currencies.rls)
        cache.set(f'orderbook_{market.symbol}_best_active_buy', Decimal(1_000_0))

        return pool

    def assert_successful(self, response, amount: Decimal, pool=None, wallet=None, user=None):
        pool = pool or self.pool
        wallet = wallet or self.wallet1
        user = user or self.user1

        assert response.status_code == 200
        result = response.json()

        user_delegation = UserDelegation.objects.filter(user=user, pool=pool, closed_at=None).first()
        sum_of_all_delegations = DelegationTransaction.objects.filter(
            user_delegation__user=user, user_delegation__pool=pool,
        ).aggregate(sum=Sum('amount'))

        assert result['status'] == 'ok'
        assert Decimal(result['userDelegation']['balance']) == sum_of_all_delegations['sum']
        assert result['userDelegation']['createdAt'] == serialize(user_delegation.created_at)
        assert result['userDelegation']['closedAt'] is None

        assert user_delegation is not None
        assert user_delegation.closed_at is None
        assert user_delegation.balance == sum_of_all_delegations['sum']

        delegation_tx = DelegationTransaction.objects.filter(
            user_delegation__user=user, user_delegation__pool=pool or pool,
        ).last()
        assert delegation_tx.amount == amount

        prev_pool_filled_capacity = pool.filled_capacity
        pool.refresh_from_db()
        assert pool.filled_capacity == amount + prev_pool_filled_capacity
        assert pool.unfilled_capacity == pool.capacity - amount - prev_pool_filled_capacity + pool.revoked_capacity

        prev_wallet_balance = wallet.balance
        wallet.refresh_from_db()
        assert prev_wallet_balance - wallet.balance == amount

    def assert_unsuccessful(
            self,
            response,
            status_code: int,
            code: str,
            message: str,
            user=None,
            dirty=False,
            before_balance: Optional[Decimal] = None,
    ):
        user = user or self.user1

        assert response.status_code == status_code
        result = response.json()

        assert result['status'] == 'failed'
        assert result['code'] == code
        assert result['message'] == message

        delegation_tx = DelegationTransaction.objects.filter(
            user_delegation__user=user, user_delegation__pool=self.pool,
        ).first()

        assert delegation_tx is None

        user_delegation = UserDelegation.objects.filter(user=user, pool=self.pool, closed_at=None).first()
        if dirty:
            assert user_delegation.balance == before_balance
        else:
            assert user_delegation is None

        self.pool.refresh_from_db()
        assert self.pool.filled_capacity == 0
        assert self.pool.unfilled_capacity == self.pool.capacity

        prev_wallet_balance = self.wallet1.balance
        self.wallet1.refresh_from_db()
        assert prev_wallet_balance - self.wallet1.balance == 0

    def request(self, amount: Decimal):
        return self.client.post(self.DELEGATION_URL % self.pool.id, dict(amount=amount))

    def test_successful_delegation(self):
        amount = self.pool.min_delegation
        response = self.request(amount)
        self.assert_successful(response, amount)

        response = self.request(amount * 2)
        self.assert_successful(response, amount * 2)

    def test_delegation_with_unverified_email(self):
        VerificationProfile.objects.filter(id=self.user1.get_verification_profile().id).update(email_confirmed=False)
        amount = self.pool.min_delegation
        response = self.request(amount)
        self.assert_unsuccessful(
            response,
            400,
            'UnverifiedEmail',
            'User does not have a verified email.',
        )

    def test_delegate_capacity_lower_than_min_limit(self):
        pool = self._create_pool(
            currency=Currencies.eth,
            capacity=10,
            filled_capacity=Decimal('9.9999'),
            manager_id=400,
            is_active=True,
            is_private=False,
        )
        wallet = Wallet.get_user_wallet(self.user1.id, Currencies.eth)
        wallet.create_transaction('manual', Decimal('10')).commit()
        wallet.refresh_from_db()

        amount = pool.capacity - pool.filled_capacity
        response = self.client.post(self.DELEGATION_URL % pool.id, dict(amount=amount))
        self.assert_successful(response, amount, pool, wallet)

    def test_delegation_higher_than_max_limit(self):
        amount = self.pool.get_max_delegation(self.user1.user_type) + 1
        response = self.request(amount)
        self.assert_unsuccessful(response, 422, 'HighDelegationAmount', 'Amount is greater than the max delegation.')

        # When user already has an active delegation
        UserDelegation.objects.get_or_create(
            pool=self.pool, user_id=self.user1.id, closed_at=None, balance=2,
        )
        amount = self.pool.get_max_delegation(self.user1.user_type) - 1
        response = self.request(amount)
        self.assert_unsuccessful(
            response,
            422,
            'HighDelegationAmount',
            'Amount is greater than the max delegation.',
            dirty=True,
            before_balance=2,
        )

    def test_delegation_lower_than_min_limit(self):
        amount = self.pool.min_delegation * Decimal('0.99')
        response = self.request(amount)
        self.assert_unsuccessful(response, 422, 'LowDelegationAmount', 'Amount is lower than the min delegation.')

    def test_delegation_low_wallet_balance(self):
        amount = self.wallet1.balance * Decimal('1.01')
        response = self.request(amount)
        self.assert_unsuccessful(response, 422, 'InsufficientWalletBalance', 'Amount is greater than unlocked wallet balance.')

    def test_delegation_low_capacity(self):
        self.pool.capacity = Decimal('1')
        self.pool.save()
        amount = Decimal('1.01')
        response = self.request(amount)
        self.assert_unsuccessful(response, 422, 'ExceedPoolCapacity', 'Amount is greater than unfilled capacity of the pool')

    def test_delegation_invalid_amount(self):
        response = self.request(Decimal('-1'))
        self.assert_unsuccessful(response, 400, 'ParseError', 'Only positive values are allowed for monetary values.')

        response = self.request(Decimal('0'))
        self.assert_unsuccessful(response, 400, 'ParseError', 'Only positive values are allowed for monetary values.')

        response = self.request(Decimal('0.000000000001'))
        self.assert_unsuccessful(response, 400, 'ParseError', 'Only positive values are allowed for monetary values.')

    def test_delegation_pool_not_found(self):
        amount = self.pool.min_delegation
        response = self.client.post(self.DELEGATION_URL % -1, dict(amount=amount))
        assert response.status_code == 404

    def test_delegation_pool_inactive(self):
        amount = self.pool.min_delegation
        pool = LiquidityPool.objects.create(currency=Currencies.eth, capacity=10000, manager_id=400, is_active=False, activated_at=ir_now())
        response = self.client.post(self.DELEGATION_URL % pool.id, dict(amount=amount))
        assert response.status_code == 404

    def test_delegation_pool_is_private(self):
        pool = self._create_pool(
            currency=Currencies.eth, capacity=10000, manager_id=400, is_active=True, is_private=True,
        )
        amount = Decimal(1)
        response = self.client.post(self.DELEGATION_URL % pool.id, dict(amount=amount))
        assert response.status_code == 404

        # Grant Access
        PoolAccess.objects.create(
            liquidity_pool=pool,
            user=self.user1,
            is_active=True,
            access_type=PoolAccess.ACCESS_TYPES.liquidity_provider,
        )
        wallet = Wallet.get_user_wallet(self.user1.id, Currencies.eth)
        wallet.create_transaction('manual', Decimal('10')).commit()
        wallet.refresh_from_db()

        response = self.client.post(self.DELEGATION_URL % pool.id, dict(amount=amount))
        self.assert_successful(response, amount, pool, wallet)

    def test_delegation_user_types(self):
        user = User.objects.get(pk=202)
        VerificationProfile.objects.filter(id=user.get_verification_profile().id).update(email_confirmed=True)
        wallet = Wallet.get_user_wallet(user.id, Currencies.btc)
        wallet.create_transaction('manual', 20).commit()
        wallet.refresh_from_db()

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {user.auth_token.key}')

        allowed_types = [type for type in User.USER_TYPES._db_values if type >= 44]
        denied_types = User.USER_TYPES._db_values - set(allowed_types)

        for user_type in denied_types:
            user.user_type = user_type
            user.save()
            amount = Decimal('1')
            response = self.request(amount)
            self.assert_unsuccessful(response, 422, 'PermissionDenied', 'User is not allowed.', user=user)

        for user_type in allowed_types:
            user.user_type = user_type
            user.save()
            amount = Decimal('1')
            response = self.request(amount)
            self.assert_successful(response=response, amount=amount, wallet=wallet, user=user)

    def test_delegation_user_delegation_closed(self):
        closed_user_delegation = UserDelegation.objects.create(user=self.user1, pool=self.pool, closed_at=now())
        amount = self.pool.min_delegation
        response = self.request(amount)
        self.assert_successful(response, amount)
        new_user_delegation = UserDelegation.objects.get(user=self.user1, pool=self.pool, closed_at=None)
        assert new_user_delegation.id != closed_user_delegation.id

    def test_delegation_when_already_revoking(self):
        amount = self.pool.min_delegation
        response = self.request(amount)
        self.assert_successful(response, amount)

        user_delegation = UserDelegation.objects.get(user=self.user1, pool=self.pool, closed_at=None)
        drr = DelegationRevokeRequest.objects.create(user_delegation=user_delegation, amount=user_delegation.balance)

        response = self.request(amount)
        assert response.status_code == 422
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == 'DelegateWhenRevokeInProgress'
        assert result['message'] == 'Cannot delegate when an active revoke is exists.'

        drr.status = DelegationRevokeRequest.STATUS.paid
        drr.save()

        response = self.request(amount)
        self.assert_successful(response, amount)

    @patch.dict(AMOUNT_PRECISIONS_V2, {Currencies.btc: 1})
    def test_delegation_rounding(self):
        amounts = [Decimal('1.0'), Decimal('1.1'), Decimal('1.5'), Decimal('1.99')]
        for amount in amounts:
            response = self.request(amount)
            self.assert_successful(response, 1)

    def test_delegation_notification(self):
        Notification.objects.all().delete()

        amount = Decimal('1.234')
        response = self.request(amount)
        self.assert_successful(response, amount)

        notification = Notification.objects.filter(user=self.user1).first()
        assert notification is not None
        assert notification.message == 'درخواست مشارکت شما در استخر بیت‌کوین به میزان 1.234 ثبت شد.'
