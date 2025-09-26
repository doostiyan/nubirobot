import datetime
from decimal import Decimal
from typing import Optional

from django.test import TestCase
from rest_framework import status

from exchange.accounts.models import User, VerificationProfile
from exchange.staking.models import Plan, StakingTransaction

from ..utils import StakingTestDataMixin


class EndRequestAPITest(StakingTestDataMixin, TestCase):
    URL = '/earn/request/end'

    def setUp(self):
        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.user = User.objects.get(id=201)
        self.user.user_type = User.USER_TYPES.level2
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=True)
        self.user.save()
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'
        self.create_staking_transaction(StakingTransaction.TYPES.stake, Decimal('40'), user=self.user, plan=self.plan)

    def get_end_request_id(self, amount: Decimal):
        return StakingTransaction.objects.get(
            amount=amount,
            user_id=self.user.id,
            plan_id=self.plan.id,
            tp=StakingTransaction.TYPES.instant_end_request,
        ).id

    def call_api(
        self,
        amount: Decimal,
        plan_id: Optional[int] = None,
    ):
        plan_id = plan_id or self.plan.id
        return self.client.post(
            path=self.URL,
            data={
                'planId': plan_id,
                'type': 'end',
                'amount': amount,
            },
        )

    def assert_datetime_format(self, value):
        assert datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%f+03:30')

    def test_create_end_request_successfully(self):
        response = self.call_api(Decimal('15.7'))

        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        self.assert_datetime_format(data['result']['createdAt'])
        data['result'].pop('createdAt')
        assert data['result'] == {
            'id': self.get_end_request_id(amount=Decimal('15.7')),
            'planId': self.plan.id,
            'type': 'end',
            'amount': '15.7',
        }

    def test_create_end_request_multiple_times(
        self,
    ):
        response = self.call_api(Decimal('10'))

        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        self.assert_datetime_format(data['result']['createdAt'])
        data['result'].pop('createdAt')
        assert data['result'] == {
            'id': self.get_end_request_id(amount=Decimal('10')),
            'planId': self.plan.id,
            'type': 'end',
            'amount': '10',
        }

        response = self.call_api(Decimal('15'))

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        self.assert_datetime_format(data['result']['createdAt'])
        data['result'].pop('createdAt')
        assert data['result'] == {
            'id': self.get_end_request_id(amount=Decimal('15')),
            'planId': self.plan.id,
            'type': 'end',
            'amount': '15',
        }

    def test_when_user_has_no_staking_in_plan_then_error_is_raised(self):
        plan = self.create_plan(**self.get_plan_kwargs())

        response = self.call_api(Decimal('10'), plan_id=plan.id)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            'code': 'InvalidPlanId',
            'message': 'No plan was found with submitted plan id',
            'status': 'failed',
        }
        assert (
            StakingTransaction.objects.filter(
                tp=StakingTransaction.TYPES.instant_end_request, plan=plan, user=self.user
            ).exists()
            is False
        )

    def test_when_amount_is_more_than_staked_amount_then_error_is_raised(self):
        response = self.call_api(Decimal('45'))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {'code': 'InvalidAmount', 'message': 'amount is not acceptable.', 'status': 'failed'}
        assert (
            StakingTransaction.objects.filter(
                tp=StakingTransaction.TYPES.instant_end_request, plan=self.plan, user=self.user
            ).exists()
            is False
        )

    def test_when_multiple_calls_ends_with_amount_more_than_staked_amount_then_error_is_raised(self):
        response = self.call_api(
            Decimal('10.1'),
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()['status'] == 'ok'
        assert self.get_end_request_id(amount=Decimal('10.1'))

        response = self.call_api(Decimal('30'))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'InvalidAmount',
            'message': 'amount is not acceptable.',
            'status': 'failed',
        }
        assert (
            StakingTransaction.objects.filter(
                amount__gt=Decimal('10.1'),
                tp=StakingTransaction.TYPES.instant_end_request,
                plan=self.plan,
                user=self.user,
            ).exists()
            is False
        )

    def test_when_requested_amount_reduces_stake_amount_less_than_min_stake_amount_then_error_is_raised(self):
        self.plan.min_staking_amount = Decimal('14')
        self.plan.save(update_fields=['min_staking_amount'])

        response = self.call_api(
            Decimal('26.1'),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {'code': 'InvalidAmount', 'message': 'amount is not acceptable.', 'status': 'failed'}
        assert (
            StakingTransaction.objects.filter(
                tp=StakingTransaction.TYPES.instant_end_request, plan=self.plan, user=self.user
            ).exists()
            is False
        )

    def test_when_multiple_requests_ends_with_amount_less_than_plan_min_stake_amount_then_error_is_raised(self):
        self.plan.min_staking_amount = Decimal('14')
        self.plan.save(update_fields=['min_staking_amount'])

        response = self.call_api(
            Decimal('9.9'),
        )

        assert response.status_code == status.HTTP_200_OK
        assert self.get_end_request_id(amount=Decimal('9.9'))

        response = self.call_api(
            Decimal('16.2'),
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'InvalidAmount',
            'message': 'amount is not acceptable.',
            'status': 'failed',
        }
        assert (
            StakingTransaction.objects.filter(
                amount__gt=Decimal('9.9'),
                tp=StakingTransaction.TYPES.instant_end_request,
                plan=self.plan,
                user=self.user,
            ).exists()
            is False
        )

    def test_end_all_staked_amount_successfully(self):
        response = self.call_api(Decimal('40'))

        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        self.assert_datetime_format(data['result']['createdAt'])
        data['result'].pop('createdAt')
        assert data['result'] == {
            'id': self.get_end_request_id(Decimal('40')),
            'planId': self.plan.id,
            'type': 'end',
            'amount': '40',
        }

    def end_all_staked_amount_successfully_with_multiple_end_requests(self):
        response = self.call_api(
            Decimal('8.9'),
        )

        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        self.assert_datetime_format(data['result']['createdAt'])
        data['result'].pop('createdAt')
        assert data['result'] == {
            'id': self.get_end_request_id(Decimal('8.9')),
            'planId': self.plan.id,
            'type': 'end',
            'amount': '8.9',
        }

        response = self.call_api(Decimal('31.1'))

        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert data['status'] == 'ok'
        self.assert_datetime_format(data['result']['createdAt'])
        data['result'].pop('createdAt')
        assert data['result'] == {
            'id': self.get_end_request_id(Decimal('40')),
            'planId': self.plan.id,
            'type': 'end',
            'amount': '40',
        }

    def test_when_plan_id_is_invalid_then_error_is_raised(self):
        response = self.call_api(Decimal('1.334'), Plan.objects.latest('id').id + 10)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {
            'code': 'InvalidPlanId',
            'message': 'No plan was found with submitted plan id',
            'status': 'failed',
        }
        assert (
            StakingTransaction.objects.filter(
                tp=StakingTransaction.TYPES.instant_end_request, amount=Decimal('1.334'), user=self.user
            ).exists()
            is False
        )

    def test_when_plan_is_not_extendable_then_nothing_happens_and_request_is_created_successfully(self):
        self.plan.is_extendable = False
        self.plan.save(update_fields=['is_extendable'])

        response = self.call_api(Decimal('12'), self.plan.id)

        data = response.json()
        assert data['status'] == 'ok'
        self.assert_datetime_format(data['result']['createdAt'])
        data['result'].pop('createdAt')
        assert data['result'] == {
            'id': self.get_end_request_id(amount=Decimal('12')),
            'planId': self.plan.id,
            'type': 'end',
            'amount': '12',
        }

    def test_when_amount_is_less_than_zero_then_error_is_raised(self):
        response = self.call_api(Decimal('-11'))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'ParseError',
            'message': 'Only positive values are allowed for monetary values.',
            'status': 'failed',
        }
        assert (
            StakingTransaction.objects.filter(
                tp=StakingTransaction.TYPES.instant_end_request,
                user=self.user,
                plan=self.plan,
            ).exists()
            is False
        )
