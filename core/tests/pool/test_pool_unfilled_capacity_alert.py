from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from django.utils.timezone import now
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND, HTTP_422_UNPROCESSABLE_ENTITY

from exchange.accounts.models import User, VerificationProfile
from exchange.base.models import Currencies, Settings
from exchange.margin.services import MarginManager
from exchange.pool.crons import UnfilledCapacityAlertCron
from exchange.pool.models import LiquidityPool, PoolUnfilledCapacityAlert, UserDelegation
from exchange.pool.tasks import task_check_settle_delegation_revoke_request

from .test_delegation_revoke import DelegationRevokeTest


@patch('django.db.transaction.on_commit', lambda t: t())
@patch.object(task_check_settle_delegation_revoke_request, 'delay', task_check_settle_delegation_revoke_request)
class UnfilledCapacityAlertCreateAPITest(DelegationRevokeTest):
    DELEGATION_REVOKE_CREATE_URL = '/liquidity-pools/delegations/%s/revoke'
    CREATE_URL = '/liquidity-pools/%s/unfilled-capacity-alert/create'
    DELETE_URL = '/liquidity-pools/%s/unfilled-capacity-alert/delete'

    def tearDown(self):
        super().tearDown()
        cache.delete('orderbook_BTCIRT_best_active_buy')

    def _create_delegation_revoke(self, pool: LiquidityPool, user: User, amount: Decimal):
        user_delegation = UserDelegation.objects.get(user=user, pool=pool, closed_at=None)
        response = self._send_request_post(
            self.DELEGATION_REVOKE_CREATE_URL % user_delegation.id,
            {'amount': amount},
            user,
        )
        self._check_response(
            response=response,
            status_code=HTTP_200_OK,
            status='ok',
        )

    def _get_url(self, pool_id: int, is_create=True) -> str:
        if is_create:
            return self.CREATE_URL % pool_id
        return self.DELETE_URL % pool_id

    def _check_last_notif(self, pool: LiquidityPool, user: User, is_active: bool = False):
        notif = PoolUnfilledCapacityAlert.objects.filter(user=user, pool=pool)
        notif = notif.filter(sent_at__isnull=False).last() if not is_active else notif.filter(sent_at=None).last()
        assert notif is not None

    def test_on_not_active_pool(self):
        response = self._send_request_post(self._get_url(self.pool_usdt.id), {}, self.user1)
        self._check_response(
            response=response,
            status_code=HTTP_404_NOT_FOUND,
        )

    def test_on_not_access_pool(self):
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        self._change_activity_pool_access(self.user1_pool_access, is_active=False)
        response = self._send_request_post(self._get_url(self.pool_btc.id), {}, self.user1)
        self._check_response(
            response=response,
            status_code=HTTP_404_NOT_FOUND,
        )

    def test_on_empty_pool(self):
        self._check_pools_changes({'btc': {'hasActiveAlert': False}})

        response = self._send_request_post(self._get_url(self.pool_btc.id), {}, self.user1)
        self._check_response(
            response=response,
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            status='failed',
            code='LiquidityPoolHasNotFilled',
            message='Liquidity pool has not filled.',
        )

    @patch.dict(settings.NOBITEX_OPTIONS['minOrders'], {Currencies.rls: Decimal('1')})
    @patch('django.get_version', lambda: 'test-2')
    def test_two_request_on_active_pool(self):
        cache.set('orderbook_BTCIRT_best_active_buy', Decimal(60_000_000))
        for user_type in User.USER_TYPES:
            Settings.set(LiquidityPool.MAX_DELEGATION_SETTING_KEY % user_type[0], 100_000_000_0)
        self._change_activity_pool_access(self.user1_pool_access, is_active=True)
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        self._check_pools_changes({'btc': {'hasActiveAlert': False}})
        # 1.request alert
        response = self._send_request_post(self._get_url(self.pool_btc.id), {}, self.user1)
        self._check_response(
            response=response,
            status_code=HTTP_200_OK,
            status='ok',
        )
        self._check_pools_changes({'btc': {'hasActiveAlert': True}})
        # 2.request alert
        response = self._send_request_post(self._get_url(self.pool_btc.id), {}, self.user1)
        self._check_response(
            response=response,
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            status='failed',
            code='UnfilledCapacityAlertExist',
            message='Unfilled capacity alert exist.',
        )
        # check alert
        self._check_last_notif(self.pool_btc, self.user1, True)
        # request revoke
        self._create_delegation_revoke(self.pool_btc, self.user1, Decimal(1))
        # run cron
        UnfilledCapacityAlertCron().run()
        # check alert
        self._check_last_notif(self.pool_btc, self.user1, False)
        self._check_pools_changes({'btc': {'hasActiveAlert': False}})

    def test_email_when_unfilled_capacity_is_lower_than_threshold(self):
        cache.set('orderbook_BTCIRT_best_active_buy', Decimal(60_000_000))
        for user_type in User.USER_TYPES:
            Settings.set(LiquidityPool.MAX_DELEGATION_SETTING_KEY % user_type[0], 100_000_000_0)
        self._change_activity_pool_access(self.user1_pool_access, is_active=True)
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        self._check_pools_changes({'btc': {'hasActiveAlert': False}})
        # 1.request alert
        response = self._send_request_post(self._get_url(self.pool_btc.id), {}, self.user1)
        self._check_response(
            response=response,
            status_code=HTTP_200_OK,
            status='ok',
        )
        self._check_pools_changes({'btc': {'hasActiveAlert': True}})
        # check alert
        self._check_last_notif(self.pool_btc, self.user1, True)

        # unfilled values = 6_000_0 rls
        self._create_delegation_revoke(self.pool_btc, self.user1, Decimal(0.001))
        # run cron
        UnfilledCapacityAlertCron().run()
        # check alert
        self._check_last_notif(self.pool_btc, self.user1, True)
        self._check_pools_changes({'btc': {'hasActiveAlert': True}})

    def test_state_alerts(self):
        self._check_pools_changes({'btc': {'hasActiveAlert': False}})
        _ = self._send_request_post(self._get_url(self.pool_btc.id), {}, self.user1)
        self._check_pools_changes({'btc': {'hasActiveAlert': True}})
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        self._check_pools_changes({'btc': {'hasActiveAlert': True}})

    @patch.dict(settings.NOBITEX_OPTIONS['positionLimits'], {46: Decimal('1')})
    @patch.dict(settings.NOBITEX_OPTIONS['minOrders'], {Currencies.rls: Decimal('1')})
    @patch('django.get_version', lambda: 'test-1')
    def test_on_active_pool_after_delegation_revoke(self):
        cache.set('orderbook_BTCIRT_best_active_buy', Decimal(60_000_000))
        for user_type in User.USER_TYPES:
            Settings.set(LiquidityPool.MAX_DELEGATION_SETTING_KEY % user_type[0], 100_000_000_0)
        # create delegation
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        # request alert
        response = self._send_request_post(self._get_url(self.pool_btc.id), {}, self.user1)
        self._check_response(
            response=response,
            status_code=HTTP_200_OK,
            status='ok',
        )
        self._check_last_notif(self.pool_btc, self.user1, True)
        # create position
        max_amount = MarginManager.get_user_pool_delegation_limit(user=self.user2, currency=Currencies.btc)
        self._create_position(self.user2, Decimal('1_000_0'), max_amount, src='btc', dst='rls')
        # request revoke
        self._create_delegation_revoke(self.pool_btc, self.user1, Decimal(2))
        # run cron
        UnfilledCapacityAlertCron().run()
        # check alert
        self._check_last_notif(self.pool_btc, self.user1, False)

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    @patch.dict(settings.NOBITEX_OPTIONS['minOrders'], {Currencies.rls: Decimal('1')})
    def test_email(self):
        cache.set('orderbook_BTCIRT_best_active_buy', Decimal(60_000_000))
        for user_type in User.USER_TYPES:
            Settings.set(LiquidityPool.MAX_DELEGATION_SETTING_KEY % user_type[0], 100_000_000_0)
        Settings.set_dict('email_whitelist', [self.user1.email])
        call_command('update_email_templates')
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        self._send_request_post(self._get_url(self.pool_btc.id), {}, self.user1)
        self._create_delegation_revoke(self.pool_btc, self.user1, Decimal(2))
        UnfilledCapacityAlertCron().run()

        with patch('django.db.connection.close'):
            call_command('send_queued_mail')

    def test_delete_old_alerts(self):
        # create old alert
        old_time = now() - timedelta(days=7)
        PoolUnfilledCapacityAlert.objects.create(
            user=self.user1,
            pool=self.pool_btc,
            created_at=old_time,
            sent_at=old_time,
        )
        UnfilledCapacityAlertCron().run()
        assert not PoolUnfilledCapacityAlert.objects.filter(
            user=self.user1,
            pool=self.pool_btc,
            created_at=old_time,
        ).exists()

    def test_delete_on_not_active_pool(self):
        response = self._send_request_post(self._get_url(self.pool_usdt.id, False), {}, self.user1)
        self._check_response(
            response=response,
            status_code=HTTP_404_NOT_FOUND,
        )

    def test_delete_on_not_access_pool(self):
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        self._change_activity_pool_access(self.user1_pool_access, is_active=False)
        response = self._send_request_post(self._get_url(self.pool_btc.id, False), {}, self.user1)
        self._check_response(
            response=response,
            status_code=HTTP_404_NOT_FOUND,
        )

    def test_delete_on_empty_pool(self):
        self._check_pools_changes({'btc': {'hasActiveAlert': False}})

        response = self._send_request_post(self._get_url(self.pool_btc.id, False), {}, self.user1)
        self._check_response(
            response=response,
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            status='failed',
            code='UnfilledCapacityAlertDoesNotExist',
            message='Unfilled capacity alert does not exist.',
        )

    @patch.dict(settings.NOBITEX_OPTIONS['minOrders'], {Currencies.rls: Decimal('1')})
    def test_delete_request_on_active_pool(self):
        self._change_activity_pool_access(self.user1_pool_access, is_active=True)
        self._create_delegation(self.pool_btc, self.user1, Decimal(2), Decimal(2))
        self._check_pools_changes({'btc': {'hasActiveAlert': False}})
        # 1.request alert
        response = self._send_request_post(self._get_url(self.pool_btc.id), {}, self.user1)
        self._check_pools_changes({'btc': {'hasActiveAlert': True}})
        self._check_last_notif(self.pool_btc, self.user1, True)
        # 2.request alert
        response = self._send_request_post(self._get_url(self.pool_btc.id, False), {}, self.user1)
        self._check_response(
            response=response,
            status_code=HTTP_200_OK,
            status='ok',
        )
        self._check_pools_changes({'btc': {'hasActiveAlert': False}})
        assert PoolUnfilledCapacityAlert.objects.all().count() == 0

    def test_user_has_no_email(self):
        VerificationProfile.objects.filter(id=self.user1.get_verification_profile().id).update(email_confirmed=False)
        self._change_activity_pool_access(self.user2_pool_access, is_active=True)
        self._create_delegation(self.pool_btc, self.user2, Decimal(2), Decimal(2))
        # 1.request alert
        response = self._send_request_post(self._get_url(self.pool_btc.id), {}, self.user1)
        self._check_response(
            response=response,
            status_code=HTTP_400_BAD_REQUEST,
            status='failed',
            code='UnverifiedEmail',
            message='User does not have a verified email.',
        )
