from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from exchange.accounts.models import Notification
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.pool.crons import NotifyPendingDelegationRevokeRequestCron
from exchange.pool.models import LiquidityPool, UserDelegation, DelegationRevokeRequest


@patch.object(Notification, 'notify_admins')
class NotifyPendingDelegationRevokeRequestCronTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        pools = [
            LiquidityPool.objects.create(currency=Currencies.btc, capacity=2, manager_id=410, is_active=True, activated_at=ir_now()),
            LiquidityPool.objects.create(currency=Currencies.usdt, capacity=2000, manager_id=413, is_active=True, activated_at=ir_now()),
        ]
        cls.delegations = [
            UserDelegation.objects.create(pool=pools[0], user_id=201, balance=0.5),
            UserDelegation.objects.create(pool=pools[1], user_id=201, balance=300),
            UserDelegation.objects.create(pool=pools[0], user_id=202, balance=1.5),
            UserDelegation.objects.create(pool=pools[1], user_id=202, balance=600),
            UserDelegation.objects.create(pool=pools[1], user_id=203, balance=500),
        ]

    @staticmethod
    def _run_cron():
        NotifyPendingDelegationRevokeRequestCron().do()

    def test_no_revoke_requests(self, notify_admins):
        self._run_cron()
        notify_admins.assert_not_called()

    def test_paid_revoke_requests(self, notify_admins):
        DelegationRevokeRequest.objects.create(
            user_delegation=self.delegations[0], amount='0.3', status=DelegationRevokeRequest.STATUS.paid
        )
        self._run_cron()
        notify_admins.assert_not_called()

    def test_new_revoke_requests(self, notify_admins):
        DelegationRevokeRequest.objects.create(user_delegation=self.delegations[0], amount='0.3')
        DelegationRevokeRequest.objects.create(
            user_delegation=self.delegations[3], amount='60', created_at=timezone.now() - timezone.timedelta(hours=10)
        )
        self._run_cron()
        notify_admins.assert_not_called()

    def test_pending_new_revoke_requests(self, notify_admins):
        DelegationRevokeRequest.objects.create(
            user_delegation=self.delegations[3], amount='70', created_at=timezone.now() - timezone.timedelta(days=1),
            status=DelegationRevokeRequest.STATUS.paid,
        )
        DelegationRevokeRequest.objects.create(
            user_delegation=self.delegations[0], amount='0.3', created_at=timezone.now() - timezone.timedelta(hours=23)
        )
        DelegationRevokeRequest.objects.create(
            user_delegation=self.delegations[1], amount='40', created_at=timezone.now() - timezone.timedelta(hours=21)
        )
        DelegationRevokeRequest.objects.create(
            user_delegation=self.delegations[2], amount='0.06', created_at=timezone.now() - timezone.timedelta(hours=18)
        )
        DelegationRevokeRequest.objects.create(user_delegation=self.delegations[4], amount='100')
        self._run_cron()
        notify_admins.assert_called()
        assert notify_admins.call_args[1]['channel'] == 'pool'
        message = notify_admins.call_args[0][0]
        assert '16 hours' in message
        assert '0.36 BTC' in message
        assert '40 USDT' in message
