from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from unittest.mock import Mock, PropertyMock, patch

import pytest
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.http import HttpResponse
from django.test import override_settings
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_422_UNPROCESSABLE_ENTITY,
)
from rest_framework.test import APITestCase

from exchange.accounts.models import Notification, User, VerificationProfile
from exchange.base.calendar import ir_now
from exchange.base.models import AMOUNT_PRECISIONS_V2, Currencies, Settings, get_market_symbol
from exchange.margin.models import Position
from exchange.margin.services import MarginManager
from exchange.margin.tasks import task_bulk_update_position_on_order_change
from exchange.market.models import Market, Order
from exchange.pool.crons import CheckDelegationRevokeRequestCron
from exchange.pool.models import (
    DelegationRevokeRequest,
    DelegationTransaction,
    LiquidityPool,
    PoolAccess,
    UserDelegation,
)
from exchange.pool.tasks import task_check_settle_delegation_revoke_request
from exchange.wallet.models import Wallet
from tests.base.utils import create_order, do_matching_round


class DelegationRevokeTest(APITestCase):
    DELEGATION_REVOKE_URL = "/liquidity-pools"
    DELEGATION_URL = "/liquidity-pools/%s/delegations"

    def setUp(self):
        self.pool_btc = self._create_pool(
            currency=Currencies.btc, capacity=2, manager_id=410, is_active=True, is_private=True
        )
        self.pool_usdt = self._create_pool(currency=Currencies.usdt, capacity=2, manager_id=413, is_active=False)

        self.user1 = self._set_user(201)
        self.user2 = self._set_user(202)

        # Grant Access
        self.user1_pool_access = self._create_pool_access(
            pool=self.pool_btc,
            user=self.user1,
            access_type=PoolAccess.ACCESS_TYPES.liquidity_provider,
            is_active=True,
        )
        self.user2_pool_access = self._create_pool_access(
            pool=self.pool_btc,
            user=self.user2,
            access_type=PoolAccess.ACCESS_TYPES.liquidity_provider,
            is_active=True,
        )
        self.user2_margin_access = self._create_pool_access(
            pool=self.pool_btc,
            user=self.user2,
            access_type=PoolAccess.ACCESS_TYPES.trader,
            is_active=True,
        )
        VerificationProfile.objects.filter(id=self.user1.get_verification_profile().id).update(email_confirmed=True)
        VerificationProfile.objects.filter(id=self.user2.get_verification_profile().id).update(email_confirmed=True)

        self._set_client(self.user1)

        for user in [self.user1, self.user2]:
            self._charge_wallet(user, Currencies.btc)
            self._charge_wallet(user, Currencies.usdt)
            self._charge_wallet(user, Currencies.rls, 10000000, Wallet.WALLET_TYPE.margin)

    @classmethod
    def _create_pool(
        cls,
        currency: int,
        manager_id: int,
        capacity=Decimal(10000),
        filled_capacity=Decimal(0),
        is_active=True,
        is_private=False,
        min_available_ratio: Decimal = Decimal("0.2"),
    ) -> "LiquidityPool":
        pool = LiquidityPool.objects.create(
            currency=currency,
            capacity=capacity,
            filled_capacity=filled_capacity,
            manager_id=manager_id,
            is_active=is_active,
            is_private=is_private,
            min_available_ratio=min_available_ratio,
            activated_at=ir_now(),
        )
        Settings.set(LiquidityPool.MIN_DELEGATION_SETTING_KEY, 1_000_0)
        for user_type in User.USER_TYPES:
            Settings.set(LiquidityPool.MAX_DELEGATION_SETTING_KEY % user_type[0], 1_000_000_0)

        symbol = get_market_symbol(pool.currency, Currencies.rls)
        cache.set(f"orderbook_{symbol}_best_active_buy", Decimal(1_000_0))

        return pool

    @classmethod
    def _set_user(cls, pk: int):
        user = User.objects.get(pk=pk)
        user.user_type = User.USER_TYPES.level2
        user.email = "%s@test.com" % pk
        user.save()
        return user

    def _set_client(self, user: User):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {user.auth_token.key}")

    @classmethod
    def _create_pool_access(
        cls,
        pool: LiquidityPool,
        user: User = None,
        user_type=None,
        access_type: int = PoolAccess.ACCESS_TYPES.trader,
        is_active: bool = True,
    ) -> "PoolAccess":
        pool_access = PoolAccess.objects.create(
            liquidity_pool=pool,
            user=user,
            user_type=user_type,
            access_type=access_type,
            is_active=is_active,
        )
        return pool_access

    @classmethod
    def _change_activity_pool_access(
        cls,
        pool_access: PoolAccess,
        is_active: bool = True,
    ) -> "PoolAccess":
        pool_access.is_active = is_active
        pool_access.save(update_fields=["is_active"])
        return pool_access

    @classmethod
    def _charge_wallet(cls, user: User, currency: int, initial_balance: int = 10, tp=Wallet.WALLET_TYPE.spot) -> Wallet:
        wallet = Wallet.get_user_wallet(user, currency, tp)
        wallet.create_transaction("manual", initial_balance).commit()
        wallet.refresh_from_db()
        return wallet

    def _check_response(
        self, response: HttpResponse, status_code: int, status: str = None, code: str = None, message: str = None
    ) -> Any:
        assert response.status_code == status_code
        data = response.json()
        if status:
            assert data["status"] == status
        if code:
            assert data["code"] == code
        if message:
            assert data["message"] == message
        return data

    def _create_delegation(
        self, pool: LiquidityPool, user: User, amount: Decimal = Decimal(1), balance: Decimal = None
    ):
        response = self._send_request_post(self.DELEGATION_URL % pool.id, {"amount": amount}, user)
        assert response.status_code == HTTP_200_OK
        if balance:
            user_delegation = UserDelegation.objects.get(user=user, pool=pool, closed_at=None)
            assert user_delegation.balance == balance

    def _create_position(
        self,
        user: User,
        price: str,
        amount: Decimal = Decimal(1),
        src: Optional[str] = None,
        dst: Optional[str] = None,
    ):
        self._set_client(user)
        request_data = {
            "srcCurrency": src or "btc",
            "dstCurrency": dst or "usdt",
            "type": "sell",
            "amount": amount,
            "price": price,
        }
        response = self._send_request_post("/margin/orders/add", request_data, user)
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"

    def _close_position(
        self,
        user: User,
        position_id: int,
        price: str,
        amount: Decimal,
    ):
        self._set_client(user)
        request_data = {
            "amount": amount,
            "price": price,
        }
        response = self._send_request_post("/positions/%s/close" % position_id, request_data, user)
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"

    def _send_request_post(self, url: str, data: Dict, user: User = None) -> Any:
        if user:
            self._set_client(user)
        return self.client.post(url, data)

    def _send_request_get(self, url: str, data: Dict, user: User = None) -> Any:
        if user:
            self._set_client(user)
        return self.client.get(url, data)

    def _create_match(self, user: User, amount: str, order: Order, price: Optional[str] = None):
        create_order(
            user=user,
            src=order.src_currency,
            dst=order.dst_currency,
            amount=Decimal(amount),
            price=price or order.price,
            sell=order.is_buy,
        )
        do_matching_round(Market.get_for(order.src_currency, order.dst_currency))

    def _check_pools_changes(self, pool_dict: Dict, user: User = None):
        if user:
            self._set_client(user)

        response = self.client.get("/liquidity-pools/list")
        assert response.status_code == HTTP_200_OK

        data = response.json()
        assert data["status"] == "ok"

        data = data["pools"]
        for key, value in pool_dict.items():
            if data[key]:
                for k, v in value.items():
                    if data[key][k]:
                        assert data[key][k] == v


@patch.object(task_bulk_update_position_on_order_change, "delay", task_bulk_update_position_on_order_change)
@patch("django.db.transaction.on_commit", lambda t: t())
@patch.object(task_check_settle_delegation_revoke_request, "delay", task_check_settle_delegation_revoke_request)
class DelegationRevokeCreateAPITest(DelegationRevokeTest):
    CREATE_URL = "/delegations/%s/revoke"

    def _get_url(self, pool: LiquidityPool, user: User) -> str:
        user_delegation = UserDelegation.objects.filter(user=user, pool=pool, closed_at=None).first()
        if user_delegation is None:
            user_delegation_id = 1
        else:
            user_delegation_id = user_delegation.id
        return (self.DELEGATION_REVOKE_URL + self.CREATE_URL) % user_delegation_id

    def _check_revoke_delegation_response(
        self,
        data: Dict,
        user: User,
        pool: LiquidityPool,
        pool_res: LiquidityPool,
        check_status=False,
        closed_at: datetime = None,
    ):
        assert "delegationRevokeRequest" in data
        user_delegation = UserDelegation.objects.get(user=user, pool=pool, closed_at=closed_at)
        # check revoke request
        revoke_request = (
            DelegationRevokeRequest.objects.filter(user_delegation=user_delegation).order_by("-created_at").first()
        )
        assert revoke_request.amount == Decimal(data["delegationRevokeRequest"]["amount"])
        assert revoke_request.created_at == datetime.fromisoformat(data["delegationRevokeRequest"]["createdAt"])
        if check_status:
            assert revoke_request.get_status_display() == data["delegationRevokeRequest"]["status"]
        # check pool revoke capacity
        pool = LiquidityPool.objects.get(id=pool.id)
        assert pool.revoked_capacity == pool_res.revoked_capacity
        assert pool.unfilled_capacity == pool_res.unfilled_capacity

    def test_create_delegation_revoke_request_without_user_delegation(self):
        response = self.client.post(self._get_url(self.pool_btc, self.user1), {"amount": 2})
        self._check_response(
            response=response,
            status_code=HTTP_404_NOT_FOUND,
        )

    def test_create_delegation_revoke_request_without_delegation(self):
        UserDelegation.objects.create(user=self.user1, pool=self.pool_btc)
        response = self.client.post(self._get_url(self.pool_btc, self.user1), {"amount": 2})
        self._check_response(
            response=response,
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            status="failed",
            code="InvalidDelegationAmount",
            message="More than participation.",
        )

    def test_create_delegation_revoke_request_under_min_order(self):
        user_delegation = UserDelegation.objects.create(user=self.user1, pool=self.pool_btc)
        DelegationTransaction.objects.create(user_delegation=user_delegation, amount=Decimal(0.9))
        response = self.client.post(self._get_url(self.pool_btc, self.user1), {"amount": 0.1})
        self._check_response(
            response=response,
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            status="failed",
            code="LowDelegationAmount",
            message="Amount is lower than the min delegation.",
        )
        response = self.client.post(self._get_url(self.pool_btc, self.user1), {"amount": 0.99})
        self._check_response(
            response=response,
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            status="failed",
            code="InvalidDelegationAmount",
            message="More than participation.",
        )
        response = self.client.post(self._get_url(self.pool_btc, self.user1), {"amount": 0.9})
        data = self._check_response(response=response, status_code=HTTP_200_OK, status="ok")
        user_delegation.refresh_from_db()
        assert user_delegation.closed_at is not None
        self._check_revoke_delegation_response(
            data,
            self.user1,
            self.pool_btc,
            LiquidityPool(capacity=self.pool_btc.capacity, revoked_capacity=Decimal("0"), filled_capacity=Decimal(0)),
            False,
            user_delegation.closed_at,
        )

    def test_create_delegation_revoke_request_min(self):
        self._create_delegation(self.pool_btc, self.user1, Decimal(1), Decimal(1))
        response = self.client.post(self._get_url(self.pool_btc, self.user1), {"amount": 0.9})
        self._check_response(
            response=response,
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            status="failed",
            code="LowDelegationAmount",
            message="Amount is lower than the min delegation.",
        )

    def test_create_delegation_revoke_request_over_balance(self):
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        response = self._send_request_post(self._get_url(self.pool_btc, self.user1), {"amount": 2.1})
        self._check_response(
            response=response,
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            status="failed",
            code="InvalidDelegationAmount",
            message="More than participation.",
        )

    def test_create_delegation_revoke_request_with_access(self):
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        response = self._send_request_post(self._get_url(self.pool_btc, self.user1), {"amount": 1})
        data = self._check_response(
            response=response,
            status_code=HTTP_200_OK,
            status="ok",
        )
        self._check_revoke_delegation_response(
            data,
            self.user1,
            self.pool_btc,
            LiquidityPool(capacity=self.pool_btc.capacity, revoked_capacity=Decimal(0), filled_capacity=Decimal(1)),
        )

    def test_create_delegation_revoke_request_without_pool_access(self):
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        self._change_activity_pool_access(self.user1_pool_access, is_active=False)
        response = self._send_request_post(self._get_url(self.pool_btc, self.user1), {"amount": 1})
        data = self._check_response(response=response, status_code=HTTP_200_OK, status="ok")
        self._check_revoke_delegation_response(
            data,
            self.user1,
            self.pool_btc,
            LiquidityPool(capacity=self.pool_btc.capacity, revoked_capacity=Decimal(0), filled_capacity=Decimal(1)),
        )

    @patch.dict(settings.NOBITEX_OPTIONS["positionLimits"], {46: Decimal("0.03")})
    @patch.dict(settings.NOBITEX_OPTIONS["minOrders"], {Currencies.rls: Decimal("1")})
    def test_create_delegation_revoke_request_not_enough_resource(self):
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        max_amount = MarginManager.get_user_pool_delegation_limit(user=self.user2, currency=Currencies.btc)
        self._create_position(self.user2, Decimal("1_000_0"), max_amount, src="btc", dst="rls")
        response = self._send_request_post(self._get_url(self.pool_btc, self.user1), {"amount": 2}, self.user1)
        data = self._check_response(response=response, status_code=HTTP_200_OK, status="ok")
        self._check_revoke_delegation_response(
            data,
            self.user1,
            self.pool_btc,
            LiquidityPool(capacity=self.pool_btc.capacity, revoked_capacity=Decimal(2), filled_capacity=Decimal(2)),
            check_status=True,
        )

    @patch("django.get_version", lambda: "test-1")
    @patch.dict(settings.NOBITEX_OPTIONS["positionLimits"], {46: Decimal("0.03")})
    @patch.dict(settings.NOBITEX_OPTIONS["minOrders"], {Currencies.rls: Decimal("1")})
    def test_create_delegation_revoke_request_enough_resource(self):
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        max_amount = MarginManager.get_user_pool_delegation_limit(user=self.user2, currency=Currencies.btc)
        self._create_position(self.user2, Decimal("1_000_0"), max_amount, src="btc", dst="rls")
        response = self._send_request_post(
            self._get_url(self.pool_btc, self.user1), {"amount": Decimal("1.94")}, self.user1
        )
        data = self._check_response(response=response, status_code=HTTP_200_OK, status="ok")
        self._check_revoke_delegation_response(
            data,
            self.user1,
            self.pool_btc,
            LiquidityPool(capacity=self.pool_btc.capacity, revoked_capacity=Decimal(0), filled_capacity=max_amount),
            check_status=False,
        )

    # check positions and revoke pool
    @patch("django.get_version", lambda: "test-2")
    @patch.dict(settings.NOBITEX_OPTIONS["positionLimits"], {46: Decimal("0.5")})
    @patch.dict(settings.NOBITEX_OPTIONS["minOrders"], {Currencies.rls: Decimal("1_000_0")})
    def test_create_delegation_revoke_request_before_delegation_and_run_cron(self):
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        max_amount = MarginManager.get_user_pool_delegation_limit(user=self.user2, currency=Currencies.btc)
        self._create_position(self.user2, Decimal("1_000_0"), max_amount, src="btc", dst="rls")
        response = self._send_request_post(self._get_url(self.pool_btc, self.user1), {"amount": 1.10000001}, self.user1)

        data = self._check_response(response=response, status_code=HTTP_200_OK, status="ok")
        self._check_revoke_delegation_response(
            data,
            self.user1,
            self.pool_btc,
            LiquidityPool(
                capacity=self.pool_btc.capacity, revoked_capacity=Decimal("1.1"), filled_capacity=Decimal("2")
            ),
            check_status=False,
        )
        self._check_pools_changes({"btc": {"filledCapacity": "0.9"}})
        self._create_delegation(self.pool_btc, self.user2, Decimal(1), Decimal(1))
        CheckDelegationRevokeRequestCron().run()
        assert (
            DelegationRevokeRequest.objects.get(id=data["delegationRevokeRequest"]["id"]).status
            == DelegationRevokeRequest.STATUS.paid
        )

    @patch("django.get_version", lambda: "test-3")
    @patch.dict(settings.NOBITEX_OPTIONS["positionLimits"], {46: Decimal("0.03")})
    @patch.dict(settings.NOBITEX_OPTIONS["minOrders"], {Currencies.rls: Decimal("1")})
    def test_create_delegation_revoke_request_cancel_position(self):
        self._check_pools_changes({"btc": {"hasDelegate": False}})
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        self._check_pools_changes({"btc": {"hasDelegate": True}})

        max_amount = MarginManager.get_user_pool_delegation_limit(user=self.user2, currency=Currencies.btc)
        self._create_position(self.user2, Decimal("1_000_0"), max_amount, src="btc", dst="rls")
        response = self._send_request_post(self._get_url(self.pool_btc, self.user1), {"amount": 2}, self.user1)
        data = self._check_response(response=response, status_code=HTTP_200_OK, status="ok")
        CheckDelegationRevokeRequestCron().run()
        assert (
            DelegationRevokeRequest.objects.get(id=data["delegationRevokeRequest"]["id"]).status
            == DelegationRevokeRequest.STATUS.new
        )
        position = Position.objects.last()
        order = position.orders.last()
        order.do_cancel()
        CheckDelegationRevokeRequestCron().run()
        assert (
            DelegationRevokeRequest.objects.get(id=data["delegationRevokeRequest"]["id"]).status
            == DelegationRevokeRequest.STATUS.paid
        )
        self._check_pools_changes({"btc": {"hasDelegate": False}})

    @patch("django.get_version", lambda: "test-4")
    @patch.dict(settings.NOBITEX_OPTIONS["positionLimits"], {46: Decimal("0.5")})
    @patch.dict(settings.NOBITEX_OPTIONS["minOrders"], {Currencies.rls: Decimal("1")})
    def test_create_delegation_revoke_request_complete_position(self):
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        max_amount = MarginManager.get_user_pool_delegation_limit(user=self.user2, currency=Currencies.btc)
        self._create_position(self.user2, Decimal("1_000_0"), max_amount, src="btc", dst="rls")
        response = self._send_request_post(self._get_url(self.pool_btc, self.user1), {"amount": 2}, self.user1)
        data = self._check_response(response=response, status_code=HTTP_200_OK, status="ok")
        position = Position.objects.last()
        self._create_match(self.user1, max_amount, position.orders.last(), "10000")
        position.refresh_from_db()
        self._close_position(self.user2, position.id, "9000", position.liability)
        self._create_match(self.user1, position.liability + Decimal('0.1'), position.orders.last(), "9000")
        CheckDelegationRevokeRequestCron().run()
        assert (
            DelegationRevokeRequest.objects.get(id=data["delegationRevokeRequest"]["id"]).status
            == DelegationRevokeRequest.STATUS.paid
        )
        assert UserDelegation.objects.filter(user=self.user1, pool=self.pool_btc, closed_at__isnull=False).count() == 1

    @patch("django.get_version", lambda: "test-5")
    @patch.dict(settings.NOBITEX_OPTIONS["minOrders"], {Currencies.rls: Decimal("1")})
    @patch.dict("exchange.base.models.AMOUNT_PRECISIONS_V2", {Currencies.btc: Decimal("1e-10")})
    @patch("exchange.pool.models.LiquidityPool.min_delegation", new_callable=PropertyMock, return_value=Decimal(0))
    def test_precision_delegation_revoke(self, _):
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        response = self._send_request_post(
            self._get_url(self.pool_btc, self.user1), {"amount": "0.00000000100000000000000000"}, self.user1
        )
        data = self._check_response(response=response, status_code=HTTP_200_OK, status="ok")
        revoke_delegation = DelegationRevokeRequest.objects.get(id=data["delegationRevokeRequest"]["id"])
        assert revoke_delegation.amount == Decimal("0.00000000100000000000000000")
        notif = Notification.objects.filter(user=self.user1).last()
        assert " 0.000000001 " in notif.message

    @pytest.mark.slow
    @override_settings(POST_OFFICE={"BACKENDS": {"default": "django.core.mail.backends.smtp.EmailBackend"}})
    @patch.dict(settings.NOBITEX_OPTIONS["minOrders"], {Currencies.rls: Decimal("1")})
    def test_email(self):
        Settings.set_dict("email_whitelist", [self.user1.email])
        call_command("update_email_templates")

        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        _ = self._send_request_post(self._get_url(self.pool_btc, self.user1), {"amount": Decimal("1")}, self.user1)
        with patch("django.db.connection.close"):
            call_command("send_queued_mail")

    def test_create_delegation_revoke_request_on_inactive_pool(self):
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        self.pool_btc.is_active = False
        self.pool_btc.save()
        response = self._send_request_post(self._get_url(self.pool_btc, self.user1), {"amount": 1})
        data = self._check_response(
            response=response,
            status_code=HTTP_403_FORBIDDEN,
            code="PermissionDenied",
            message="استخر بیت‌کوین غیرفعال است و امکان ثبت درخواست وجود ندارد.",
            status="failed",
        )


@patch("django.db.transaction.on_commit", lambda t: t())
@patch.object(task_check_settle_delegation_revoke_request, "delay", task_check_settle_delegation_revoke_request)
class DelegationRevokeListAPITest(DelegationRevokeTest):
    LIST_URL = "/delegation-revoke-requests/list"
    CREATE_URL = DelegationRevokeTest.DELEGATION_REVOKE_URL + DelegationRevokeCreateAPITest.CREATE_URL

    def _get_url(self, user_delegation_id: Optional[int] = None) -> str:
        if user_delegation_id is None:
            return self.DELEGATION_REVOKE_URL + self.LIST_URL
        return self.CREATE_URL % user_delegation_id

    def _check_revoke_delegation_response(self, data: Dict, user: User, pool: LiquidityPool, status: int = None):
        user_delegation = UserDelegation.objects.get(user=user, pool=pool, closed_at=None)
        # check revoke request
        revoke_requests = DelegationRevokeRequest.objects.filter(user_delegation=user_delegation)
        if status is not None:
            revoke_requests = revoke_requests.filter(status=status)
        revoke_requests = revoke_requests.order_by("-created_at")

        assert "delegationRevokeRequests" in data
        assert len(revoke_requests) == len(data["delegationRevokeRequests"])

        for res, expected in zip(data["delegationRevokeRequests"], revoke_requests):
            assert res["createdAt"] == expected.created_at.isoformat()
            assert Decimal(res["amount"]) == expected.amount
            assert res["status"] == expected.get_status_display()

    def test_delegation_revoke_request_empty_list(self):
        response = self._send_request_get(self._get_url(), {}, self.user1)
        self._check_response(
            response=response,
            status_code=HTTP_200_OK,
            status="ok",
        )

    @patch("django.get_version", lambda: "test-6")
    @patch.dict(settings.NOBITEX_OPTIONS["positionLimits"], {46: Decimal("0.5")})
    @patch.dict(settings.NOBITEX_OPTIONS["minOrders"], {Currencies.rls: Decimal("1")})
    @patch("exchange.base.emailmanager.EmailManager.send_email")
    def test_delegation_revoke_request_list(self, mock_send_email: Mock):
        # fill pool
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        user_delegation = UserDelegation.objects.get(user=self.user1, pool=self.pool_btc.id, closed_at=None)
        # create position
        max_amount = MarginManager.get_user_pool_delegation_limit(user=self.user2, currency=Currencies.btc)
        self._create_position(self.user2, Decimal("1_000_0"), max_amount, src="btc", dst="rls")
        # 2 request revoke
        response = self._send_request_post(self._get_url(user_delegation.id), {"amount": Decimal("1")}, self.user1)
        _ = self._check_response(response=response, status_code=HTTP_200_OK, status="ok")
        response = self._send_request_post(self._get_url(user_delegation.id), {"amount": Decimal("1")}, self.user1)
        _ = self._check_response(response=response, status_code=HTTP_200_OK, status="ok")

        # get list
        response = self._send_request_get(self._get_url(), {}, self.user1)
        data = self._check_response(
            response=response,
            status_code=HTTP_200_OK,
            status="ok",
        )
        self._check_revoke_delegation_response(data, self.user1, self.pool_btc)

        # get list new
        response = self._send_request_get(self._get_url(), {"status": "new"}, self.user1)
        data = self._check_response(
            response=response,
            status_code=HTTP_200_OK,
            status="ok",
        )
        self._check_revoke_delegation_response(data, self.user1, self.pool_btc, DelegationRevokeRequest.STATUS.new)

        # incorrect status
        response = self._send_request_get(self._get_url(), {"status": "nothing"}, self.user1)
        data = self._check_response(response=response, status_code=HTTP_400_BAD_REQUEST, status="failed")

    @patch.dict(AMOUNT_PRECISIONS_V2, {Currencies.btc: Decimal("1")})
    def test_revoke_rounding(self):
        self.pool_btc.capacity = 20
        self.pool_btc.save()

        self._create_delegation(self.pool_btc, self.user1, Decimal(10), Decimal(10))
        user_delegation = UserDelegation.objects.get(user=self.user1, pool=self.pool_btc.id, closed_at=None)
        amounts = [Decimal("1.1"), Decimal("1.1"), Decimal("1.5"), Decimal("1.99")]

        for amount in amounts:
            response = self._send_request_post(self._get_url(user_delegation.id), {"amount": amount}, self.user1)
            data = self._check_response(response=response, status_code=HTTP_200_OK, status="ok")
            assert data["delegationRevokeRequest"]["amount"] == "1"


class DelegationRevokeCommandTest(DelegationRevokeTest):
    @patch("django.get_version", lambda: "test-7")
    @patch.dict(settings.NOBITEX_OPTIONS["positionLimits"], {46: Decimal("0.5")})
    @patch.dict(settings.NOBITEX_OPTIONS["minOrders"], {Currencies.rls: Decimal("1")})
    def test_revoke_pool_delegations(self):
        # fill pool
        self.pool_btc.capacity = 4
        self.pool_btc.save()
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        user1_delegation = UserDelegation.objects.get(user=self.user1, pool=self.pool_btc.id, closed_at=None)
        self._create_delegation(self.pool_btc, self.user2, Decimal(1), Decimal(1))
        user2_delegation = UserDelegation.objects.get(user=self.user2, pool=self.pool_btc.id, closed_at=None)
        # create position
        max_amount = MarginManager.get_user_pool_delegation_limit(user=self.user2, currency=Currencies.btc)
        self._create_position(self.user2, Decimal("1_000_0"), max_amount, src="btc", dst="rls")

        self.user1_margin_access = self._create_pool_access(
            pool=self.pool_btc,
            user=self.user1,
            access_type=PoolAccess.ACCESS_TYPES.trader,
            is_active=True,
        )
        max_amount = MarginManager.get_user_pool_delegation_limit(user=self.user1, currency=Currencies.btc)
        self._create_position(self.user1, Decimal("1_000_0"), max_amount, src="btc", dst="rls")

        assert self.pool_btc.revoked_capacity == Decimal('0')
        call_command("revoke_pool_delegations", currency="btc")
        self.pool_btc.refresh_from_db()
        assert self.pool_btc.revoked_capacity == Decimal('3')
        user_delegations = UserDelegation.objects.filter(pool=self.pool_btc, closed_at=None)
        assert user_delegations.count() == 2
        revoke_requests = DelegationRevokeRequest.objects.all()
        assert revoke_requests.count() == 2
        user1_revoke_request = revoke_requests.get(user_delegation=user1_delegation)
        user2_revoke_request = revoke_requests.get(user_delegation=user2_delegation)
        assert user1_revoke_request.status == DelegationRevokeRequest.STATUS.new
        assert user1_revoke_request.delegation_transaction is None
        assert user1_revoke_request.amount == Decimal('2')

        assert user2_revoke_request.status == DelegationRevokeRequest.STATUS.new
        assert user2_revoke_request.delegation_transaction is None
        assert user2_revoke_request.amount == Decimal('1')
