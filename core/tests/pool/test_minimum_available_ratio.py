from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.utils.timezone import now
from rest_framework.status import HTTP_200_OK

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.margin.models import Position
from exchange.margin.services import MarginManager
from exchange.margin.tasks import task_bulk_update_position_on_order_change
from exchange.pool.crons import MinimumRatioAvailableCapacityAlertCron
from exchange.pool.models import LiquidityPool, PoolMinimumAvailableRatioAlert, UserDelegation
from exchange.pool.tasks import task_check_settle_delegation_revoke_request

from .test_delegation_revoke import DelegationRevokeTest


@patch.object(task_bulk_update_position_on_order_change, "delay", task_bulk_update_position_on_order_change)
@patch("django.db.transaction.on_commit", lambda t: t())
@patch.object(task_check_settle_delegation_revoke_request, "delay", task_check_settle_delegation_revoke_request)
class UnfilledCapacityAlertAPITest(DelegationRevokeTest):
    DELEGATION_REVOKE_CREATE_URL = "/liquidity-pools/delegations/%s/revoke"

    def _create_delegation_revoke(self, pool: LiquidityPool, user: User, amount: Decimal):
        user_delegation = UserDelegation.objects.get(user=user, pool=pool, closed_at=None)
        response = self._send_request_post(
            self.DELEGATION_REVOKE_CREATE_URL % user_delegation.id, {"amount": amount}, user
        )
        self._check_response(
            response=response,
            status_code=HTTP_200_OK,
            status="ok",
        )

    def _check_alerts(self, pool: LiquidityPool, num_active: int = 0, num_inactive: int = 0):
        alerts = PoolMinimumAvailableRatioAlert.objects.filter(pool=pool)

        assert alerts.filter(is_active=True).count() == num_active
        assert alerts.filter(is_active=False).count() == num_inactive

    def _activate_pool(self, pool: LiquidityPool):
        pool.is_active = True
        pool.activated_at=ir_now()
        pool.save(update_fields=["is_active", "activated_at"])

    def _change_capacity_pool(self, pool: LiquidityPool, capacity: Decimal):
        pool.capacity = capacity
        pool.save(update_fields=["capacity"])

    def test_empty_pool(self):
        self._check_alerts(self.pool_btc)
        self._activate_pool(self.pool_usdt)

        for _ in range(2):
            MinimumRatioAvailableCapacityAlertCron().run()
            self._check_alerts(self.pool_btc, num_active=1)
            self._check_alerts(self.pool_usdt, num_active=1)

    def test_empty_pool_delegate(self):
        self._activate_pool(self.pool_usdt)
        MinimumRatioAvailableCapacityAlertCron().run()
        self._check_alerts(self.pool_btc, num_active=1)

        self._create_delegation(self.pool_btc, self.user1, Decimal(1), Decimal(1))
        MinimumRatioAvailableCapacityAlertCron().run()
        self._check_alerts(self.pool_btc, num_inactive=1)
        self._check_alerts(self.pool_usdt, num_active=1)

    def test_pool_change_pool_capacity_and_revoke_delegate(self):
        self._create_delegation(self.pool_btc, self.user1, Decimal(1), Decimal(1))
        MinimumRatioAvailableCapacityAlertCron().run()
        self._check_alerts(self.pool_btc)

        self._change_capacity_pool(self.pool_btc, Decimal(10))
        MinimumRatioAvailableCapacityAlertCron().run()
        self._check_alerts(self.pool_btc, num_active=1)

        self._create_delegation(self.pool_btc, self.user1, Decimal(9), Decimal(10))
        MinimumRatioAvailableCapacityAlertCron().run()
        self._check_alerts(self.pool_btc, num_inactive=1)

        self._create_delegation_revoke(self.pool_btc, self.user1, Decimal("5"))
        MinimumRatioAvailableCapacityAlertCron().run()
        self._check_alerts(self.pool_btc, num_inactive=1)

        self._create_delegation_revoke(self.pool_btc, self.user1, Decimal("4"))
        MinimumRatioAvailableCapacityAlertCron().run()
        self._check_alerts(self.pool_btc, num_active=1)

    @patch.dict(settings.NOBITEX_OPTIONS["positionLimits"], {46: Decimal("0.85")})
    @patch.dict(settings.NOBITEX_OPTIONS["minOrders"], {Currencies.rls: Decimal("1")})
    def test_pool_with_cancel_position(self):
        self._create_delegation(self.pool_btc, self.user1, Decimal(1), Decimal(1))
        MinimumRatioAvailableCapacityAlertCron().run()
        self._check_alerts(self.pool_btc)
        # open position
        max_amount = MarginManager.get_user_pool_delegation_limit(user=self.user2, currency=Currencies.btc)
        self._create_position(self.user2, Decimal("1_000_0"), max_amount, src="btc", dst="rls")
        MinimumRatioAvailableCapacityAlertCron().run()
        self._check_alerts(self.pool_btc, num_active=1)
        # cancel position
        position = Position.objects.last()
        order = position.orders.last()
        order.do_cancel()
        MinimumRatioAvailableCapacityAlertCron().run()
        self._check_alerts(self.pool_btc, num_inactive=1)

    @patch("django.get_version", lambda: "test-1")
    @patch.dict(settings.NOBITEX_OPTIONS["positionLimits"], {46: Decimal("0.85")})
    @patch.dict(settings.NOBITEX_OPTIONS["minOrders"], {Currencies.rls: Decimal("1")})
    def test_pool_with_complete_position(self):
        self._create_delegation(self.pool_btc, self.user1, Decimal(1), Decimal(1))
        # open position
        max_amount = MarginManager.get_user_pool_delegation_limit(user=self.user2, currency=Currencies.btc)
        self._create_position(self.user2, Decimal("1_000_0"), max_amount, src="btc", dst="rls")
        MinimumRatioAvailableCapacityAlertCron().run()
        self._check_alerts(self.pool_btc, num_active=1)
        # open position and match
        position = Position.objects.last()
        self._create_match(self.user1, max_amount, position.orders.last(), "10000")
        position.refresh_from_db()
        MinimumRatioAvailableCapacityAlertCron().run()
        self._check_alerts(self.pool_btc, num_active=1)

        self._close_position(self.user2, position.id, "9000", position.liability)
        self._create_match(self.user1, position.liability, position.orders.last(), "9000")
        MinimumRatioAvailableCapacityAlertCron().run()
        self._check_alerts(self.pool_btc, num_inactive=1)

    def test_check_remove_old_alerts(self):
        self._activate_pool(self.pool_usdt)
        self._change_capacity_pool(self.pool_btc, Decimal(10))
        self._create_delegation(self.pool_btc, self.user1, Decimal(10), Decimal(10))
        self._create_delegation(self.pool_usdt, self.user1, Decimal(1), Decimal(1))
        old_date = now() - timedelta(days=2, hours=1)

        alerts = [
            PoolMinimumAvailableRatioAlert(pool=self.pool_btc, is_active=False, created_at=old_date),
            PoolMinimumAvailableRatioAlert(pool=self.pool_usdt, is_active=True, created_at=old_date),
        ]
        PoolMinimumAvailableRatioAlert.objects.bulk_create(alerts)
        self._check_alerts(self.pool_btc, num_inactive=1)
        self._check_alerts(self.pool_usdt, num_active=1)

        MinimumRatioAvailableCapacityAlertCron().run()
        self._check_alerts(self.pool_btc)
        self._check_alerts(self.pool_usdt, num_inactive=1)

        self._create_delegation_revoke(self.pool_btc, self.user1, Decimal("9"))
        MinimumRatioAvailableCapacityAlertCron().run()
        self._check_alerts(self.pool_btc, num_active=1)
        self._check_alerts(self.pool_usdt)
