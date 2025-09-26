from decimal import Decimal
from unittest.mock import patch

import pytest
import responses
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.crons import ABCMarginCallManagementCron, ABCMarginCallManagementHourlyCron
from exchange.asset_backed_credit.externals.wallet import WalletListAPI
from exchange.asset_backed_credit.models import AssetToDebtMarginCall, Service
from exchange.asset_backed_credit.services.margin_call import (
    MarginCallAdjustAction,
    MarginCallNotifyAction,
    MarginCallResolveAction,
    fetch_raw_candidates,
    send_margin_call_notification,
)
from exchange.asset_backed_credit.types import MarginCallCandidate
from exchange.base.models import Currencies, Settings
from tests.asset_backed_credit.helper import ABCMixins


class MarginCallTest(TestCase, ABCMixins):
    fixtures = ('test_data',)

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user.mobile = '09151234567'
        self.user.save()
        self.internal_user = self.create_internal_user(self.user)
        vp = self.user.get_verification_profile()
        vp.email_confirmed = True
        vp.save()
        self.set_usdt_mark_price(50_000_0)

    def test_margin_call_nothing_to_handle(self):
        ABCMarginCallManagementCron().run()
        assert not AssetToDebtMarginCall.objects.all()

    @patch('sentry_sdk.start_transaction')
    def test_margin_call_check_sentry_transaction_monitoring(self, sentry_transaction_mock):
        Settings.set('abc_margin_call_sentry_transaction_enabled', 'yes')

        ABCMarginCallManagementCron().run()
        assert not AssetToDebtMarginCall.objects.all()

        sentry_transaction_mock.assert_called_with(op='function', name='abc_margin_call')

    def test_margin_call_nothing_to_notif(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        self.create_user_service(self.user, initial_debt=25000000)  # $50 * 500000
        ABCMarginCallManagementCron().run()
        assert not AssetToDebtMarginCall.objects.all()

    def test_margin_call_just_under_collateral_ratio_but_no_notif(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        self.create_user_service(self.user, initial_debt=38500000)  # $77 * 500000
        ABCMarginCallManagementCron().run()
        assert not AssetToDebtMarginCall.objects.all()

    @patch('sentry_sdk.start_transaction')
    @patch('exchange.asset_backed_credit.tasks.task_margin_call_notify.delay')
    def test_margin_call_send_notification_multiple_times(self, notif_mock_delay, sentry_transaction_mock):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        self.create_user_service(self.user, initial_debt=45500000)  # $91 * 500000

        # first time check ratio -> create margin call -> send notification
        ABCMarginCallManagementCron().run()

        margin_call = AssetToDebtMarginCall.objects.all().first()
        assert margin_call
        assert margin_call.internal_user_id
        assert margin_call.total_debt == Decimal('45500000')
        assert margin_call.total_assets == Decimal('50000000')
        assert not margin_call.is_solved
        assert not margin_call.is_margin_call_sent

        # second time check ratio -> find existing margin call -> last sent notification failed -> send again!
        ABCMarginCallManagementCron().run()
        margin_call.refresh_from_db()
        assert margin_call.total_debt == Decimal('45500000')
        assert margin_call.total_assets == Decimal('50000000')
        assert not margin_call.is_solved
        assert not margin_call.is_margin_call_sent

        send_margin_call_notification(margin_call.id)

        # second time check ratio -> find existing margin call -> margin call notification sent before -> do nothing!
        ABCMarginCallManagementCron().run()
        margin_call.refresh_from_db()
        assert margin_call.total_debt == Decimal('45500000')
        assert margin_call.total_assets == Decimal('50000000')
        assert not margin_call.is_solved
        assert margin_call.is_margin_call_sent

        assert notif_mock_delay.call_count == 2
        notif_mock_delay.assert_called_with(margin_call.id)

        sentry_transaction_mock.assert_not_called()

    @patch('exchange.asset_backed_credit.tasks.task_margin_call_notify')
    @patch('exchange.asset_backed_credit.tasks.task_margin_call_adjust')
    def test_margin_call_dispatch_to_adjust(self, liquidate_mock, notif_mock):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        self.create_user_service(self.user, initial_debt=48000000)  # $96 * 500000

        ABCMarginCallManagementCron().run()
        margin_call = AssetToDebtMarginCall.objects.all().first()
        assert margin_call
        assert margin_call.internal_user_id
        assert margin_call.total_debt == Decimal('48000000')
        assert margin_call.total_assets == Decimal('50000000')
        assert not margin_call.is_solved
        assert not margin_call.is_margin_call_sent

        notif_mock.delay.assert_not_called()
        liquidate_mock.delay.assert_called_once_with(margin_call.id)

    @responses.activate
    @patch('exchange.asset_backed_credit.tasks.task_margin_call_notify')
    @patch('exchange.asset_backed_credit.tasks.task_margin_call_adjust')
    def test_margin_call_dispatch_to_adjust_when_wallet_internal_api_is_enabled(self, liquidate_mock, notif_mock):
        Settings.set('abc_use_wallet_list_internal_api', 'yes')
        responses.post(
            url=WalletListAPI.url,
            json={
                str(self.user.uid): [
                    {
                        "activeBalance": "100",
                        "balance": "100",
                        "blockedBalance": "0",
                        "currency": "usdt",
                        "type": "credit",
                        "userId": str(self.user.uid),
                    },
                ]
            },
            status=status.HTTP_200_OK,
        )

        self.create_user_service(self.user, initial_debt=48000000)  # $96 * 500000

        ABCMarginCallManagementCron().run()
        margin_call = AssetToDebtMarginCall.objects.all().first()
        assert margin_call
        assert margin_call.internal_user_id
        assert margin_call.total_debt == Decimal('48000000')
        assert margin_call.total_assets == Decimal('50000000')
        assert not margin_call.is_solved
        assert not margin_call.is_margin_call_sent

        notif_mock.delay.assert_not_called()
        liquidate_mock.delay.assert_called_once_with(margin_call.id)

    @patch('exchange.asset_backed_credit.tasks.task_margin_call_notify')
    def test_margin_call_dispatch_to_resolve(self, notif_mock):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        user_service = self.create_user_service(self.user, initial_debt=45500000)

        ABCMarginCallManagementCron().run()
        margin_call = AssetToDebtMarginCall.objects.all().first()
        assert margin_call
        assert margin_call.internal_user_id
        assert margin_call.total_debt == Decimal('45500000')
        assert margin_call.total_assets == Decimal('50000000')
        assert not margin_call.is_solved
        assert not margin_call.is_margin_call_sent

        notif_mock.delay.assert_called_once_with(margin_call.id)

        user_service.current_debt = 35500000
        user_service.save()

        ABCMarginCallManagementCron().run()

        margin_call.refresh_from_db()
        assert margin_call.is_solved

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_margin_call_cleanup_resolved_candidates(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        user_service = self.create_user_service(self.user, initial_debt=45500000)
        user_service.current_debt = 0
        user_service.save(update_fields=('current_debt',))

        self.user2 = User.objects.get(pk=202)
        self.user2.mobile = '09111235566'
        self.user2.save()
        vp1 = self.user2.get_verification_profile()
        vp1.email_confirmed = True
        vp1.save()

        user_service1 = self.create_user_service(self.user2, initial_debt=45500000)
        user_service1.current_debt = 0
        user_service1.save(update_fields=('current_debt',))

        service = self.create_service(provider=Service.PROVIDERS.wepod)
        self.create_user_service(self.user2, initial_debt=90000000, service=service)

        AssetToDebtMarginCall.objects.create(user=self.user, total_debt=0, total_assets=0)
        AssetToDebtMarginCall.objects.create(user=self.user2, total_debt=0, total_assets=0)

        ABCMarginCallManagementCron().run()

        margin_calls = AssetToDebtMarginCall.objects.all().order_by('created_at')
        assert margin_calls
        assert margin_calls[0].is_solved
        assert not margin_calls[1].is_solved
        assert not margin_calls[0].is_margin_call_sent

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    def test_margin_call_email(self):
        Settings.set_dict('email_whitelist', [self.user.email])
        call_command('update_email_templates')
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        self.create_user_service(self.user, initial_debt=45500000)

        ABCMarginCallManagementCron().run()
        margin_call = AssetToDebtMarginCall.objects.all().first()
        assert margin_call
        assert margin_call.internal_user_id
        assert margin_call.total_debt == Decimal('45500000')
        assert margin_call.total_assets == Decimal('50000000')
        assert not margin_call.is_solved
        assert not margin_call.is_margin_call_sent

        margin_call.send_margin_call()

        margin_call.refresh_from_db()
        assert margin_call.is_margin_call_sent

        with patch('django.db.connection.close'):
            call_command('send_queued_mail')

    def test_margin_call_exclude_rial_only_assets(self):
        # user with coin assets
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        self.charge_exchange_wallet(self.user, Currencies.rls, Decimal('100'))
        self.create_user_service(self.user, initial_debt=45500000)  # $91 * 500000

        # user with rial only assets
        self.user1 = User.objects.get(pk=202)
        self.user1.mobile = '09111235566'
        self.user1.save()
        vp1 = self.user1.get_verification_profile()
        vp1.email_confirmed = True
        vp1.save()
        self.charge_exchange_wallet(self.user1, Currencies.rls, Decimal('10000'))
        self.create_user_service(self.user1, initial_debt=45500000)

        # user with rial only assets and near zero coin assets
        self.user2 = User.objects.get(pk=203)
        self.user2.mobile = '09111235566'
        self.user2.save()
        vp2 = self.user2.get_verification_profile()
        vp2.email_confirmed = True
        vp2.save()
        self.charge_exchange_wallet(self.user2, Currencies.usdt, Decimal('0.000000008'))
        self.charge_exchange_wallet(self.user2, Currencies.rls, Decimal('10000'))
        self.create_user_service(self.user2, initial_debt=45500000)

        ABCMarginCallManagementCron().run()

        margin_call = AssetToDebtMarginCall.objects.all()
        assert len(margin_call) == 1
        assert margin_call[0].user == self.user
        assert margin_call[0].internal_user == self.internal_user

    def test_margin_call_not_exclude_rial_only_assets_in_hourly_task(self):
        # user with coin assets
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('100'))
        self.charge_exchange_wallet(self.user, Currencies.rls, Decimal('100'))
        self.create_user_service(self.user, initial_debt=45500000)  # $91 * 500000

        # user with rial only assets
        self.user1 = User.objects.get(pk=202)
        self.user1.mobile = '09111235566'
        self.user1.save()
        vp1 = self.user1.get_verification_profile()
        vp1.email_confirmed = True
        vp1.save()
        self.charge_exchange_wallet(self.user1, Currencies.rls, Decimal('10000'))
        self.create_user_service(self.user1, initial_debt=45500000)

        # user with rial only assets and near zero coin assets
        self.user2 = User.objects.get(pk=203)
        self.user2.mobile = '09111235566'
        self.user2.save()
        vp2 = self.user2.get_verification_profile()
        vp2.email_confirmed = True
        vp2.save()
        self.charge_exchange_wallet(self.user2, Currencies.usdt, Decimal('0.000000008'))
        self.charge_exchange_wallet(self.user2, Currencies.rls, Decimal('10000'))
        self.create_user_service(self.user2, initial_debt=45500000)

        ABCMarginCallManagementHourlyCron().run()

        margin_call = AssetToDebtMarginCall.objects.all()
        assert len(margin_call) == 3
        assert list(margin_call.values_list('user_id', flat=True).order_by('user_id')) == [
            self.user.id,
            self.user1.id,
            self.user2.id,
        ]

    def test_margin_call_prepare_candidates_excludes_debit_services(self):
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('10'))
        self.charge_exchange_wallet(self.user, Currencies.rls, Decimal('100'))
        self.create_user_service(self.user, initial_debt=50000000)

        self.user1 = User.objects.get(pk=202)
        self.user1.mobile = '09111235566'
        self.user1.save()
        vp1 = self.user1.get_verification_profile()
        vp1.email_confirmed = True
        vp1.save()
        self.charge_exchange_wallet(self.user1, Currencies.rls, Decimal('10000'))

        service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit, is_active=True
        )
        self.create_user_service(self.user1, initial_debt=1000000, service=service)

        candidates = fetch_raw_candidates()
        assert len(candidates) == 1
        assert candidates[self.user.id].internal_user_id == self.internal_user.id
        assert candidates[self.user.id].total_debt == Decimal(50000000)
        assert candidates[self.user.id].margin_call_id is None

    def test_margin_call_resolve_idempotent(self):
        # Create resolved margin call
        margin_call = AssetToDebtMarginCall.objects.create(
            user_id=self.user.id, total_debt=0, total_assets=0, is_solved=True
        )
        action = MarginCallResolveAction(ratios={'margin_call': Decimal('1.2')})
        # Add resolved margin call id
        candidate = MarginCallCandidate(
            user_id=self.user.id,
            internal_user_id=self.internal_user.id,
            total_debt=Decimal('1'),
            total_assets=None,
            margin_call_id=margin_call.id,
            is_rial_only=False,
            ratio=Decimal('1.3'),
        )
        action.collect(candidate)
        # Should not update anything (should not error)
        action.execute()
        margin_call.refresh_from_db()
        assert margin_call.is_solved

    @patch('exchange.asset_backed_credit.tasks.task_margin_call_adjust.delay')
    def test_margin_call_adjust_new_and_existing(self, adjust_task_mock):
        # No existing margin call
        action = MarginCallAdjustAction(ratios={'liquidation': Decimal('1.0')})
        candidate_new = MarginCallCandidate(
            user_id=self.user.id,
            internal_user_id=self.internal_user.id,
            total_debt=Decimal('1000'),
            total_assets=type('TA', (), {'total_mark_price': Decimal('900')})(),
            margin_call_id=None,
            is_rial_only=False,
            ratio=Decimal('0.9'),
        )
        action.collect(candidate_new)
        action.execute()
        assert adjust_task_mock.called
        margin_call = AssetToDebtMarginCall.objects.get(user_id=self.user.id)
        adjust_task_mock.assert_called_with(margin_call.id)

        # Existing margin call, should use fetch_existing
        action = MarginCallAdjustAction(ratios={'liquidation': Decimal('1.0')})
        candidate_existing = MarginCallCandidate(
            user_id=self.user.id,
            internal_user_id=self.internal_user.id,
            total_debt=Decimal('1000'),
            total_assets=type('TA', (), {'total_mark_price': Decimal('900')})(),
            margin_call_id=margin_call.id,
            is_rial_only=False,
            ratio=Decimal('0.9'),
        )
        action.collect(candidate_existing)
        action.execute()
        assert adjust_task_mock.call_count == 2  # called for both

    @patch('exchange.asset_backed_credit.tasks.task_margin_call_notify.delay')
    def test_notify_action_new_and_existing(self, notify_task_mock):
        # New margin call
        action = MarginCallNotifyAction(ratios={'liquidation': Decimal('1.0'), 'margin_call': Decimal('1.2')})
        candidate = MarginCallCandidate(
            user_id=self.user.id,
            internal_user_id=self.internal_user.id,
            total_debt=Decimal('2000'),
            total_assets=type('TA', (), {'total_mark_price': Decimal('2200')})(),
            margin_call_id=None,
            is_rial_only=False,
            ratio=Decimal('1.1'),
        )
        action.collect(candidate)
        action.execute()
        assert notify_task_mock.called
        margin_call = AssetToDebtMarginCall.objects.get(user_id=self.user.id)
        notify_task_mock.assert_called_with(margin_call.id)

        # Existing margin call, not sent
        margin_call.is_margin_call_sent = False
        margin_call.save()
        action = MarginCallNotifyAction(ratios={'liquidation': Decimal('1.0'), 'margin_call': Decimal('1.2')})
        candidate_existing = MarginCallCandidate(
            user_id=self.user.id,
            internal_user_id=self.internal_user.id,
            total_debt=Decimal('2000'),
            total_assets=type('TA', (), {'total_mark_price': Decimal('2200')})(),
            margin_call_id=margin_call.id,
            is_rial_only=False,
            ratio=Decimal('1.1'),
        )
        action.collect(candidate_existing)
        action.execute()
        assert notify_task_mock.call_count == 2
