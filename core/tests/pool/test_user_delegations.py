from decimal import Decimal

from django.utils.timezone import now
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, get_currency_codename
from exchange.base.serializers import serialize
from exchange.pool.models import LiquidityPool, UserDelegation, DelegationRevokeRequest


class UserDelegationListTest(APITestCase):
    DELEGATION_LIST_URL = '/liquidity-pools/delegations/list'

    def setUp(self):
        self.pool1 = LiquidityPool.objects.create(
            currency=Currencies.btc, capacity=10000, manager_id=410, is_active=True, activated_at=ir_now(),
        )
        self.pool2 = LiquidityPool.objects.create(
            currency=Currencies.eth, capacity=10000, manager_id=400, is_active=True, activated_at=ir_now(),
        )
        self.user1 = User.objects.get(pk=201)

        self.user_delegations = list(reversed([
            UserDelegation.objects.create(
                pool=self.pool1, user=self.user1, balance=Decimal(1), closed_at=None,
            ),
            UserDelegation.objects.create(
                pool=self.pool1, user=self.user1, balance=Decimal(2), closed_at=now(),
            ),
            UserDelegation.objects.create(
                pool=self.pool2, user=self.user1, balance=Decimal(3), closed_at=now(),
            ),
        ]))

        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user1.auth_token.key}')

    def request(self, page=None, page_size=None, pool_id=None, is_closed=None):
        query_string = {}
        query_string.update({'page': page} if page is not None else {})
        query_string.update({'pageSize': page_size} if page_size is not None else {})
        query_string.update({'poolId': pool_id} if pool_id is not None else {})
        query_string.update({'isClosed': is_closed} if is_closed is not None else {})

        return self.client.get(self.DELEGATION_LIST_URL, query_string)

    def assert_successful(self, response, expected: list, has_next=False):
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert result['hasNext'] is has_next
        assert 'userDelegations' in result
        user_delegations = result['userDelegations']
        assert len(user_delegations) == len(expected)
        for ud, actual in zip(expected, user_delegations):
            assert ud.id == actual['id']
            assert serialize(ud.pool_id) == actual['pool']['id']
            assert serialize(ud.balance) == actual['balance']
            assert serialize(ud.created_at) == actual['createdAt']
            assert serialize(ud.closed_at) == actual['closedAt']
            assert serialize(ud.total_profit) == actual['totalProfit']
            assert get_currency_codename(ud.pool.currency) == actual['currency']
            assert serialize(ud.pool.min_delegation) == actual['minRevoke']

    def assert_unsuccessful(self, response, code: int, reason: str):
        assert response.status_code == code
        result = response.json()
        assert result['status'] == 'failed'
        assert result['code'] == reason

    def test_user_delegation_with_defaults(self):
        response = self.request()
        self.assert_successful(response, self.user_delegations)

    def test_user_delegation_with_is_closed_filter(self):
        response = self.request(is_closed=False)
        self.assert_successful(
            response,
            self.user_delegations[2:],
        )

        response = self.request(is_closed=True)
        self.assert_successful(
            response,
            self.user_delegations[:2],
        )

        response = self.request(is_closed='invalid')
        self.assert_unsuccessful(response, 400, 'ParseError')

    def test_user_delegation_with_pool_id_filter(self):
        response = self.request(pool_id=self.pool1.id)
        self.assert_successful(
            response,
            self.user_delegations[1:],
        )

        response = self.request(pool_id=self.pool2.id)
        self.assert_successful(
            response,
            self.user_delegations[:1],
        )

        response = self.request(pool_id=-1)
        self.assert_successful(response, [])

        response = self.request(pool_id='invalid')
        self.assert_unsuccessful(response, 400, 'ParseError')

    def test_user_delegation_pagination(self):
        response = self.request(page_size=1)
        self.assert_successful(response, self.user_delegations[:1], has_next=True)

        response = self.request(page_size=2)
        self.assert_successful(response, self.user_delegations[:2], has_next=True)

        response = self.request(page_size=2, page=2)
        self.assert_successful(response, self.user_delegations[2:], has_next=False)

        response = self.request(page=-1)
        self.assert_successful(response, self.user_delegations, has_next=False)

    def test_user_delegation_revoking_balance(self):
        DelegationRevokeRequest.objects.create(user_delegation=self.user_delegations[0], amount='0.3')
        DelegationRevokeRequest.objects.create(user_delegation=self.user_delegations[0], amount='0.2')
        response = self.request()
        self.assert_successful(response, self.user_delegations)
        delegations = response.json()['userDelegations']
        assert delegations[0]['revokingBalance'] == '0.5'
        assert delegations[1]['revokingBalance'] == '0'
        assert delegations[2]['revokingBalance'] == '0'
