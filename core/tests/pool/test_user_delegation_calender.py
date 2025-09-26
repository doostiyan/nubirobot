from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import jdatetime
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now, ir_tz
from exchange.base.models import Currencies
from exchange.pool.models import DelegationTransaction, LiquidityPool, UserDelegation


@patch('exchange.pool.models.ir_today', lambda: jdatetime.date(year=1399, month=12, day=5).togregorian())
class UserDelegationCalenderTest(APITestCase):
    DELEGATION_CALENDER_URL = '/liquidity-pools/delegations/%s/current-calender'

    @patch('exchange.pool.models.DelegationTransaction.create_transaction', lambda _: None)
    @patch('exchange.pool.models.DelegationTransaction.clean', lambda _: None)
    def setUp(self):
        base_datetime = jdatetime.datetime(year=1399, month=12, day=5, tzinfo=ir_tz()).togregorian()

        self.pool1 = LiquidityPool.objects.create(
            currency=Currencies.btc, capacity=10000, manager_id=410, is_active=True, filled_capacity=5, activated_at=ir_now(),
        )
        self.pool2 = LiquidityPool.objects.create(
            currency=Currencies.eth, capacity=10000, manager_id=400, is_active=True, activated_at=ir_now(),
        )
        self.user1 = User.objects.get(pk=201)

        self.user_delegation = UserDelegation.objects.create(
            pool=self.pool1, user=self.user1, balance=Decimal(5), closed_at=None,
        )
        self.user_delegation_closed = UserDelegation.objects.create(
            pool=self.pool1, user=self.user1, balance=Decimal(5), closed_at=base_datetime,
        )

        self.user_delegation_without_tx = UserDelegation.objects.create(
            pool=self.pool2, user=self.user1, balance=Decimal(5),
        )

        DelegationTransaction.objects.create(user_delegation=self.user_delegation, amount=Decimal('-1'))
        DelegationTransaction.objects.create(user_delegation=self.user_delegation, amount=Decimal('1.5'))
        DelegationTransaction.objects.update(created_at=base_datetime + timedelta(days=1))

        tx1 = DelegationTransaction.objects.create(user_delegation=self.user_delegation, amount=Decimal('-1.5'))
        tx2 = DelegationTransaction.objects.create(user_delegation=self.user_delegation, amount=Decimal('1.5'))
        DelegationTransaction.objects.filter(pk__in=[tx1.pk, tx2.pk]).update(created_at=base_datetime + timedelta(days=2))

        tx3 = DelegationTransaction.objects.create(user_delegation=self.user_delegation, amount=Decimal('-1'))
        tx4 = DelegationTransaction.objects.create(user_delegation=self.user_delegation, amount=Decimal('-3'))
        DelegationTransaction.objects.filter(pk__in=[tx3.pk, tx4.pk]).update(created_at=base_datetime + timedelta(days=3))

        dummy_tx1 = DelegationTransaction.objects.create(user_delegation=self.user_delegation, amount=Decimal('1'))
        dummy_tx2 = DelegationTransaction.objects.create(user_delegation=self.user_delegation, amount=Decimal('6'))
        DelegationTransaction.objects.filter(pk__in=[dummy_tx1.pk, dummy_tx2.pk]).update(created_at=base_datetime - timedelta(days=31))

        self.user_delegation.balance = Decimal(5)
        self.user_delegation.save()

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user1.auth_token.key}')

    def request(self, user_delegation_id: int):
        return self.client.get(self.DELEGATION_CALENDER_URL % user_delegation_id)

    def assert_successful(self, response, dates: dict, transactions: list, balances: dict):
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert result['dates'] == dates
        assert result['transactions'] == transactions
        assert result['balances'] == balances

    def assert_unsuccessful(self, response, code: int):
        assert response.status_code == code

    def test_user_delegation_calender(self):
        response = self.request(self.user_delegation.pk)
        self.assert_successful(
            response,
            dict(
                start='2021-02-19',
                end='2021-03-20',
                profit='2021-03-21'
            ),
            [
                dict(amount='0.5', date='2021-02-24'),
                dict(amount='-4', date='2021-02-26'),
            ],
            dict(initial='8.5')
        )

    def test_user_delegation_calender_without_tx(self):
        response = self.request(self.user_delegation_without_tx.pk)
        self.assert_successful(
            response,
            dict(
                start='2021-02-19',
                end='2021-03-20',
                profit='2021-03-21'
            ),
            [],
            dict(initial='5')
        )

    def test_user_delegation_calender_not_found(self):
        response = self.request(-1)
        self.assert_unsuccessful(response, 404)

    def test_user_delegation_calender_closed(self):
        response = self.request(self.user_delegation_closed.pk)
        self.assert_unsuccessful(response, 404)

    def test_user_delegation_calender_other_user(self):
        user2 = User.objects.get(pk=202)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {user2.auth_token.key}')
        response = self.request(self.user_delegation.pk)
        self.assert_unsuccessful(response, 404)
