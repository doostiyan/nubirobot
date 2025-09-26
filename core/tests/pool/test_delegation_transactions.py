from datetime import timedelta
from decimal import Decimal
from typing import List

from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now, ir_today
from exchange.base.models import Currencies, get_currency_codename
from exchange.base.serializers import serialize
from exchange.pool.models import DelegationTransaction, LiquidityPool, UserDelegation, DelegationRevokeRequest
from exchange.wallet.models import Wallet


class DelegationTxsListTest(APITestCase):
    DELEGATION_TX_LIST_URL = '/liquidity-pools/delegation-transactions/list'

    def setUp(self):
        self.user1 = User.objects.get(pk=201)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user1.auth_token.key}')

        self.initial_balance = 10
        self.wallet1 = Wallet.get_user_wallet(self.user1.id, Currencies.btc)
        self.wallet1.create_transaction('manual', self.initial_balance).commit()

        self.wallet2 = Wallet.get_user_wallet(self.user1.id, Currencies.eth)
        self.wallet2.create_transaction('manual', self.initial_balance).commit()

        self.pool1 = LiquidityPool.objects.create(
            currency=Currencies.btc, capacity=10000, manager_id=410, is_active=True, activated_at=ir_now(),
        )
        self.pool2 = LiquidityPool.objects.create(
            currency=Currencies.eth, capacity=10000, manager_id=400, is_active=True, activated_at=ir_now(),
        )
        self.ud1 = UserDelegation.objects.create(pool=self.pool1, user=self.user1)
        self.ud2 = UserDelegation.objects.create(pool=self.pool2, user=self.user1)

        self.pool1.src_wallet.create_transaction('manual', Decimal(6)).commit()
        self.pool1.src_wallet.refresh_from_db()

        self.delegation_transactions = list(reversed([
            DelegationTransaction.objects.create(user_delegation=self.ud1, amount=Decimal(6)),
            DelegationTransaction.objects.create(user_delegation=self.ud1, amount=Decimal(-4)),
            DelegationTransaction.objects.create(user_delegation=self.ud2, amount=Decimal(3)),
        ]))

        DelegationRevokeRequest.objects.create(
            amount='-1',
            user_delegation=self.ud1,
            status=DelegationRevokeRequest.STATUS.paid,
            delegation_transaction=self.delegation_transactions[1],
        )


    def request(
            self, page=None, page_size=None, pool_id=None, is_revoke=None, from_date=None, to_date=None, order_by=None,
            user_delegation_id=None,
    ):
        query_string = {}
        query_string.update({'page': page} if page is not None else {})
        query_string.update({'pageSize': page_size} if page_size is not None else {})
        query_string.update({'poolId': pool_id} if pool_id is not None else {})
        query_string.update({'isRevoke': is_revoke} if is_revoke is not None else {})
        query_string.update({'fromDate': from_date} if from_date is not None else {})
        query_string.update({'toDate': to_date} if to_date is not None else {})
        query_string.update({'order': order_by} if order_by is not None else {})
        query_string.update({'userDelegationId': user_delegation_id} if user_delegation_id is not None else {})

        return self.client.get(self.DELEGATION_TX_LIST_URL, query_string)

    def assert_successful(self, response, expected: List[DelegationTransaction], has_next=False):
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert result['hasNext'] is has_next
        assert 'delegationTransactions' in result
        delegation_transactions = result['delegationTransactions']
        assert len(delegation_transactions) == len(expected)
        for dt, actual in zip(expected, delegation_transactions):
            assert serialize(dt.amount) == actual['amount']
            assert serialize(dt.created_at) == actual['createdAt']
            assert get_currency_codename(dt.user_delegation.pool.currency) == actual['currency']
            assert serialize(dt.user_delegation_id) == actual['userDelegationId']
            if dt.amount < 0:
                assert serialize(dt.delegation_revoke_request.created_at) == actual['requestedAt']
            else:
                assert 'requestedAt' not in actual

    def assert_unsuccessful(self, response, code: int, reason: str):
        assert response.status_code == code
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == reason

    def test_delegation_transaction_with_defaults(self):
        response = self.request()
        self.assert_successful(response, self.delegation_transactions)

    def test_delegation_transaction_with_pool_id_filter(self):
        response = self.request(pool_id=self.pool1.id)
        self.assert_successful(response, self.delegation_transactions[1:3])

        response = self.request(pool_id=self.pool2.id)
        self.assert_successful(response, self.delegation_transactions[:1])

        response = self.request(pool_id=-1)
        self.assert_successful(response, [])

        response = self.request(pool_id='invalid')
        self.assert_unsuccessful(response, 400, 'ParseError')

    def test_delegation_transaction_with_user_delegation_id_filter(self):
        response = self.request(user_delegation_id=self.ud1.id)
        self.assert_successful(response, self.delegation_transactions[1:3])

        response = self.request(user_delegation_id=self.ud2.id)
        self.assert_successful(response, self.delegation_transactions[:1])

        response = self.request(user_delegation_id=-1)
        self.assert_successful(response, [])

        response = self.request(user_delegation_id='invalid')
        self.assert_unsuccessful(response, 400, 'ParseError')

    def test_delegation_transaction_pagination(self):
        response = self.request(page_size=1)
        self.assert_successful(response, self.delegation_transactions[:1], has_next=True)

        response = self.request(page_size=2)
        self.assert_successful(response, self.delegation_transactions[:2], has_next=True)

        response = self.request(page_size=2, page=2)
        self.assert_successful(response, self.delegation_transactions[2:4], has_next=False)

        response = self.request(page=-1)
        self.assert_successful(response, self.delegation_transactions, has_next=False)

    def test_delegation_transaction_with_is_revoke_filter(self):
        response = self.request(is_revoke=False)
        self.assert_successful(response, [self.delegation_transactions[0], self.delegation_transactions[2]])

        response = self.request(is_revoke=True)
        self.assert_successful(response, [self.delegation_transactions[1]])

    def test_delegation_transaction_with_from_date_filter(self):
        DelegationTransaction.objects.filter(pk=self.delegation_transactions[0].pk).update(
            created_at=ir_now() - timedelta(days=2)
        )
        response = self.request(from_date=(ir_today() - timedelta(days=1)).isoformat())
        self.assert_successful(response, [self.delegation_transactions[1], self.delegation_transactions[2]])

        response = self.request(from_date=(ir_today() + timedelta(days=1)).isoformat())
        self.assert_successful(response, [])

        # Wrong format
        response = self.request(from_date='2000/10/10')
        self.assert_unsuccessful(response, 400, 'ParseError')

    def test_delegation_transaction_with_to_date_filter(self):
        response = self.request(to_date=(ir_today() - timedelta(days=1)).isoformat())
        self.assert_successful(response, [])

        DelegationTransaction.objects.filter(pk=self.delegation_transactions[2].pk).update(
            created_at=ir_now() - timedelta(days=2)
        )
        self.delegation_transactions[2].refresh_from_db()
        response = self.request(to_date=(ir_today() - timedelta(days=1)).isoformat())
        self.assert_successful(response, [self.delegation_transactions[2]])

        response = self.request(to_date=(ir_today() + timedelta(days=1)).isoformat())
        self.assert_successful(response, self.delegation_transactions)

        # Wrong format
        response = self.request(to_date='2000/10/10')
        self.assert_unsuccessful(response, 400, 'ParseError')

    def test_delegation_transaction_with_order(self):
        response = self.request(order_by='newest')
        self.assert_successful(response, self.delegation_transactions)

        response = self.request(order_by='latest')
        self.assert_successful(response, list(reversed(self.delegation_transactions)))

        response = self.request(order_by='max')
        self.assert_successful(
            response,
            sorted(self.delegation_transactions, key=lambda tx: abs(tx.amount), reverse=True),
        )
