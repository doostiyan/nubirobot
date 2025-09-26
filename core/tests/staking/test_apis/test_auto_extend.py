from decimal import Decimal
from typing import Optional

from django.test import TestCase
from django.utils.timezone import timedelta
from rest_framework import status

from exchange.accounts.models import User, VerificationProfile
from exchange.staking.models import StakingTransaction

from ..utils import StakingTestDataMixin


class EnableAutoExtendTest(StakingTestDataMixin, TestCase):
    URL = '/earn/plan/auto-extend/enable'

    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = User.objects.get(id=201)
        self.user.user_type = User.USER_TYPES.level2
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=True)
        self.user.save()
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'

    def call_api(self, plan_id: Optional[int] = None):
        plan_id = plan_id or self.plan.id
        return self.client.post(path=self.URL, data={'planId': plan_id})

    def test_with_invalid_plan_id_raises_error(self):
        response = self.call_api(plan_id=-1)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            'code': 'InvalidPlanId',
            'message': 'No plan was found with submitted plan id',
            'status': 'failed',
        }
        assert (
            StakingTransaction.objects.filter(
                plan=self.plan, user=self.user, tp=StakingTransaction.TYPES.auto_end_request
            ).exists()
            is False
        )
        assert (
            StakingTransaction.objects.filter(
                plan=self.plan, user=self.user, tp=StakingTransaction.TYPES.deactivator
            ).exists()
            is False
        )

    def test_enable_auto_extend_when_user_has_selected_not_auto_extend_in_subscription(self):
        self.create_staking_transaction(
            user=self.user, plan=self.plan, tp=StakingTransaction.TYPES.auto_end_request, amount=Decimal('0')
        )
        assert StakingTransaction.objects.filter(
            plan=self.plan,
            user=self.user,
            tp=StakingTransaction.TYPES.auto_end_request,
            child=None,
        ).exists()

        response = self.call_api()

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert data['result'] is None
        assert (
            StakingTransaction.objects.filter(
                plan=self.plan,
                user=self.user,
                tp=StakingTransaction.TYPES.auto_end_request,
                child=None,
            ).exists()
            is False
        )
        auto_end_request = StakingTransaction.objects.get(
            plan=self.plan,
            user=self.user,
            tp=StakingTransaction.TYPES.auto_end_request,
        )
        assert StakingTransaction.objects.get(
            plan=self.plan, user=self.user, tp=StakingTransaction.TYPES.deactivator, parent=auto_end_request
        )

    def test_enable_auto_extend_when_user_has_already_selected_to_auto_extend_this_plan(self):
        response = self.call_api()

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert data['result'] is None
        assert (
            StakingTransaction.objects.filter(
                plan=self.plan, user=self.user, tp=StakingTransaction.TYPES.auto_end_request
            ).exists()
            is False
        )
        assert (
            StakingTransaction.objects.filter(
                plan=self.plan, user=self.user, tp=StakingTransaction.TYPES.deactivator
            ).exists()
            is False
        )

    def test_when_staking_period_is_finished_then_too_late_error_is_raised(self):
        self.plan.staked_at -= timedelta(days=5)
        self.plan.save(update_fields=('staked_at',))

        response = self.call_api()

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {'code': 'TooLate', 'message': 'It is too late', 'status': 'failed'}
        assert (
            StakingTransaction.objects.filter(
                plan=self.plan, user=self.user, tp=StakingTransaction.TYPES.auto_end_request
            ).exists()
            is False
        )
        assert (
            StakingTransaction.objects.filter(
                plan=self.plan, user=self.user, tp=StakingTransaction.TYPES.deactivator
            ).exists()
            is False
        )

    def test_when_plan_is_not_extendable_then_error_is_raised(self):
        self.plan.is_extendable = False
        self.plan.save(update_fields=['is_extendable'])

        response = self.call_api()

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {'code': 'NonExtendablePlan', 'message': 'Plan is not extendable', 'status': 'failed'}
        assert (
            StakingTransaction.objects.filter(
                plan=self.plan, user=self.user, tp=StakingTransaction.TYPES.auto_end_request
            ).exists()
            is False
        )
        assert (
            StakingTransaction.objects.filter(
                plan=self.plan, user=self.user, tp=StakingTransaction.TYPES.deactivator
            ).exists()
            is False
        )


class DisableAutoExtendTest(StakingTestDataMixin, TestCase):
    URL = '/earn/plan/auto-extend/disable'

    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = User.objects.get(id=201)
        self.user.user_type = User.USER_TYPES.level2
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=True)
        self.user.save()
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'

    def call_api(self, plan_id: Optional[int] = None):
        plan_id = plan_id or self.plan.id
        return self.client.post(path=self.URL, data={'planId': plan_id})

    def test_with_invalid_plan_id_raises_error(self):
        response = self.call_api(plan_id=-1)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            'code': 'InvalidPlanId',
            'message': 'No plan was found with submitted plan id',
            'status': 'failed',
        }

    def test_disable_auto_extend_success_when_user_has_no_auto_end_transaction(self):
        response = self.call_api()

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert data['result'] is None
        assert StakingTransaction.objects.filter(
            plan_id=self.plan.id,
            user_id=self.user.id,
            tp=StakingTransaction.TYPES.auto_end_request,
            child=None,
        ).exists()

    def test_disable_auto_extend_success_when_user_has_auto_end_transaction(self):
        self.create_staking_transaction(
            tp=StakingTransaction.TYPES.auto_end_request, amount=Decimal('0'), plan=self.plan, user=self.user
        )

        response = self.call_api()

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert data['result'] is None
        assert StakingTransaction.objects.filter(
            plan_id=self.plan.id,
            user_id=self.user.id,
            tp=StakingTransaction.TYPES.auto_end_request,
            child=None,
        ).exists()
        assert (
            StakingTransaction.objects.filter(
                plan_id=self.plan.id, user_id=self.user.id, tp=StakingTransaction.TYPES.auto_end_request
            ).count()
            == 1
        )

    def test_when_staking_period_is_finished_then_too_late_error_is_raised(self):
        self.plan.staked_at -= timedelta(days=5)
        self.plan.save(update_fields=('staked_at',))

        response = self.call_api()

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {'code': 'TooLate', 'message': 'It is too late', 'status': 'failed'}
        assert (
            StakingTransaction.objects.filter(
                plan_id=self.plan.id,
                user_id=self.user.id,
                tp=StakingTransaction.TYPES.auto_end_request,
            ).exists()
            is False
        )

    def test_when_plan_is_not_extendable_then_error_is_raised(self):
        self.plan.is_extendable = False
        self.plan.save(update_fields=['is_extendable'])

        response = self.call_api()

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {'code': 'NonExtendablePlan', 'message': 'Plan is not extendable', 'status': 'failed'}
        assert (
            StakingTransaction.objects.filter(
                plan_id=self.plan.id,
                user_id=self.user.id,
                tp=StakingTransaction.TYPES.auto_end_request,
            ).exists()
            is False
        )
