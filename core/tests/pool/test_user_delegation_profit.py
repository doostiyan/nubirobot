from typing import Iterable, Any
from decimal import Decimal
import datetime
from django.utils.timezone import now
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.base.serializers import serialize
from exchange.pool.models import LiquidityPool, UserDelegation, UserDelegationProfit


class UserDelegationProfitListTest(APITestCase):
    DELEGATION_LIST_URL = "/liquidity-pools/delegation-profits/list"

    def setUp(self):
        # make pools
        self.pool1 = LiquidityPool.objects.create(
            currency=Currencies.btc,
            capacity=10000,
            manager_id=410,
            is_active=True,
            activated_at=ir_now(),
        )
        self.pool2 = LiquidityPool.objects.create(
            currency=Currencies.eth,
            capacity=10000,
            manager_id=400,
            is_active=True,
            activated_at=ir_now(),
        )
        # set user
        self.user1 = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)

        # make user_delegations
        self.user_delegations = [
            UserDelegation(pool=self.pool1, user=self.user1, balance=Decimal(2), closed_at=now()),
            UserDelegation(pool=self.pool2, user=self.user1, balance=Decimal(3), closed_at=now()),
            UserDelegation(pool=self.pool2, user=self.user2, balance=Decimal(3), closed_at=now()),
        ]

        UserDelegation.objects.bulk_create(self.user_delegations)

        self.transactions = []
        for user_delegation in self.user_delegations:
            trans = user_delegation.src_wallet.create_transaction("manual", Decimal(1), description="test")
            trans.commit()
            self.transactions.append(trans)

        # make profits
        self.date_now = now()
        self.delta_time = datetime.timedelta(days=1)
        self.user_profits = [
            UserDelegationProfit(
                user_delegation=self.user_delegations[0],
                amount=Decimal(1),
                from_date=self.date_now,
                to_date=self.date_now - (self.delta_time * 3),
                delegation_score=1,
                transaction=self.transactions[0],
            ),
            UserDelegationProfit(
                user_delegation=self.user_delegations[1],
                amount=Decimal(1),
                from_date=self.date_now,
                to_date=self.date_now - (self.delta_time * 4),
                delegation_score=1,
                transaction=self.transactions[1],
            ),
            UserDelegationProfit(
                user_delegation=self.user_delegations[1],
                amount=Decimal(1),
                from_date=self.date_now - (self.delta_time),
                to_date=self.date_now - (self.delta_time * 5),
                delegation_score=1,
            ),
            UserDelegationProfit(
                user_delegation=self.user_delegations[1],
                amount=Decimal(1),
                from_date=self.date_now - (self.delta_time * 2),
                to_date=self.date_now - (self.delta_time * 2),
                delegation_score=1,
                transaction=self.transactions[2],
            ),
        ]
        UserDelegationProfit.objects.bulk_create(self.user_profits)

    def request(self, user: User, page=None, page_size=None, pool_id=None, order_by=None) -> Any:
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {user.auth_token.key}")
        query_string = {}
        query_string.update({"page": page} if page is not None else {})
        query_string.update({"pageSize": page_size} if page_size is not None else {})
        query_string.update({"poolId": pool_id} if pool_id is not None else {})
        query_string.update({"order": order_by} if order_by is not None else {})

        return self.client.get(self.DELEGATION_LIST_URL, query_string)

    def assert_successful(self, response, expected, has_next=False):
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "ok"
        assert result["hasNext"] is has_next
        assert "delegationProfits" in result
        user_profits = result["delegationProfits"]
        assert len(user_profits) == len(expected)
        for user_profit, actual in zip(expected, user_profits):
            assert serialize(user_profit.user_delegation_id) == actual["userDelegationId"]
            assert serialize(user_profit.amount) == actual["amount"]
            assert serialize(user_profit.to_date) == actual["toDate"]
            assert serialize(user_profit.from_date) == actual["fromDate"]
            assert serialize(user_profit.settled_at) == actual["settledAt"]

    def _get_user_delegation_profits(
        self, user: User, pool_id: int = None, order_by: str = "-to_date"
    ) -> Iterable[UserDelegationProfit]:
        query_filter = {"user_delegation__user": user}
        if pool_id:
            query_filter.update({"user_delegation__pool": pool_id})
        return UserDelegationProfit.objects.filter(**query_filter).order_by(order_by)

    def test_user_delegation_profits_with_defaults(self):
        response = self.request(self.user1)
        self.assert_successful(response, self._get_user_delegation_profits(self.user1))

    def test_user_delegation_profits_empty(self):
        response = self.request(self.user2)
        self.assert_successful(response, [])

    def test_user_delegation_profits_with_defaults_user2(self):
        UserDelegationProfit.objects.create(
            user_delegation=self.user_delegations[2],
            amount=Decimal(1),
            from_date=self.date_now,
            to_date=self.date_now - (self.delta_time * 3),
            delegation_score=1,
        )
        response = self.request(self.user2)
        self.assert_successful(response, self._get_user_delegation_profits(self.user2))

    def test_user_delegation_profits_filter_pools(self):
        response = self.request(self.user1, pool_id=self.pool1.id)
        self.assert_successful(response, self._get_user_delegation_profits(self.user1, self.pool1.id))

    def test_user_delegation_profits_filter_order(self):
        response = self.request(self.user1, pool_id=self.pool2.id, order_by="latest")
        self.assert_successful(response, self._get_user_delegation_profits(self.user1, self.pool2, "to_date"))
