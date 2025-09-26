from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from django.db.models import Q
from django.test import TestCase

from exchange.accounts.models import User, VerificationProfile
from exchange.base.models import Currencies
from exchange.staking.models import ExternalEarningPlatform, Plan, StakingTransaction

from ..utils import StakingTestDataMixin


class InstantEndRequestTest(StakingTestDataMixin, TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.external_platform = cls.add_external_platform(Currencies.btc, ExternalEarningPlatform.TYPES.staking)
        cls.user = User.objects.get(pk=201)
        cls.user.user_type = User.USER_TYPES.level2
        VerificationProfile.objects.filter(id=cls.user.get_verification_profile().id).update(email_confirmed=True)
        cls.user.save()

    def setUp(self):
        self.plan = Plan.objects.create(**self.get_plan_kwargs())
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'
        self.staking = self.create_staking_transaction(StakingTransaction.TYPES.stake, Decimal('40'), plan=self.plan)

    def get_transaction(
        self, trx_amount: Decimal = None, tp=StakingTransaction.TYPES.instant_end_request
    ) -> StakingTransaction:
        q = Q()
        if trx_amount:
            q = Q(amount=trx_amount)
        return (
            StakingTransaction.objects.filter(
                q,
                user_id=self.user.id,
                plan_id=self.plan.id,
                tp=tp,
            )
            .order_by('-id')
            .first()
        )

    def call_api(self, amount: Decimal, plan_id: Optional[int] = None):
        plan_id = plan_id or self.plan.id
        return self.client.post(path='/earn/request/instant-end', data={'planId': plan_id, 'amount': amount}).json()

    def test_create_instant_end_request_success(self):
        response = self.call_api(Decimal('3'))

        assert response['status'] == 'ok'
        datetime.strptime(response['result']['createdAt'], '%Y-%m-%dT%H:%M:%S.%f+03:30')
        response['result'].pop('createdAt')
        assert response['result'] == {
            'id': self.get_transaction(trx_amount=Decimal(3), tp=StakingTransaction.TYPES.instant_end_request).id,
            'planId': self.plan.id,
            'type': 'instant_end',
            'amount': '3',
        }
        assert self.get_transaction(trx_amount=Decimal(3), tp=StakingTransaction.TYPES.unstake)

    def test_create_and_request_aggregation(self):
        response = self.call_api(Decimal('10'))

        assert response['status'] == 'ok'
        response['result'].pop('createdAt')
        assert response['result'] == {
            'id': self.get_transaction(trx_amount=Decimal(10), tp=StakingTransaction.TYPES.instant_end_request).id,
            'planId': self.plan.id,
            'type': 'instant_end',
            'amount': '10',
        }
        assert self.get_transaction(trx_amount=Decimal(10), tp=StakingTransaction.TYPES.unstake)

        response = self.call_api(Decimal('11'))

        assert response['status'] == 'ok'
        response['result'].pop('createdAt')
        assert response['result'] == {
            'id': self.get_transaction(trx_amount=Decimal(11), tp=StakingTransaction.TYPES.instant_end_request).id,
            'planId': self.plan.id,
            'type': 'instant_end',
            'amount': '11',
        }
        assert self.get_transaction(trx_amount=Decimal(11), tp=StakingTransaction.TYPES.unstake)

    def test_no_staking(self):
        self.staking.delete()

        response = self.call_api(
            Decimal('10'),
        )

        assert response['status'] == 'failed'
        assert response['code'] == 'InvalidPlanId'
        assert self.get_transaction(tp=StakingTransaction.TYPES.instant_end_request) is None
        assert self.get_transaction(tp=StakingTransaction.TYPES.unstake) is None

    def test_over_ending(self):
        response = self.call_api(Decimal('45'))

        assert response['status'] == 'failed'
        assert response['code'] == 'InvalidAmount'
        assert self.get_transaction(tp=StakingTransaction.TYPES.instant_end_request) is None
        assert self.get_transaction(Decimal('45'), tp=StakingTransaction.TYPES.unstake) is None

    def test_aggregated_over_ending(self):
        response = self.call_api(Decimal('10'))

        assert response['status'] == 'ok'
        assert self.get_transaction(trx_amount=Decimal(10), tp=StakingTransaction.TYPES.instant_end_request)
        assert self.get_transaction(trx_amount=Decimal(10), tp=StakingTransaction.TYPES.unstake)

        response = self.call_api(Decimal('35'))

        assert response['status'] == 'failed'
        assert response['code'] == 'InvalidAmount'
        assert self.get_transaction(Decimal('35'), tp=StakingTransaction.TYPES.unstake) is None

    def test_plan_min_amount(self):
        response = self.call_api(Decimal('36'))

        assert response['status'] == 'failed'
        assert response['code'] == 'InvalidAmount'
        assert self.get_transaction(tp=StakingTransaction.TYPES.instant_end_request) is None
        assert self.get_transaction(Decimal('36'), tp=StakingTransaction.TYPES.unstake) is None

    def test_aggregated_plan_min_amount(self):
        response = self.call_api(Decimal('10'))

        assert response['status'] == 'ok'
        assert self.get_transaction(Decimal('10'), tp=StakingTransaction.TYPES.instant_end_request)
        assert self.get_transaction(Decimal('10'), tp=StakingTransaction.TYPES.unstake)

        response = self.call_api(Decimal('26'))

        assert response['status'] == 'failed'
        assert response['code'] == 'InvalidAmount'
        assert self.get_transaction(Decimal('26'), tp=StakingTransaction.TYPES.instant_end_request) is None
        assert self.get_transaction(Decimal('26'), tp=StakingTransaction.TYPES.unstake) is None

    def test_end_all(self):
        response = self.call_api(Decimal('40'))

        assert response['status'] == 'ok'
        response['result'].pop('createdAt')
        assert response['result'] == {
            'id': self.get_transaction(Decimal('40'), tp=StakingTransaction.TYPES.instant_end_request).id,
            'planId': self.plan.id,
            'type': 'instant_end',
            'amount': '40',
        }
        assert self.get_transaction(Decimal('40'), tp=StakingTransaction.TYPES.unstake)

    def test_aggregated_end_all(self):
        response = self.call_api(Decimal('10'))

        assert response['status'] == 'ok'
        assert self.get_transaction(Decimal(10), tp=StakingTransaction.TYPES.instant_end_request)
        assert self.get_transaction(Decimal(10), tp=StakingTransaction.TYPES.unstake)

        response = self.call_api(Decimal('30'))

        assert response['status'] == 'ok'
        assert self.get_transaction(Decimal(30), tp=StakingTransaction.TYPES.instant_end_request)
        assert self.get_transaction(Decimal(30), tp=StakingTransaction.TYPES.unstake)
        response['result'].pop('createdAt')
        assert response['result'] == {
            'id': self.get_transaction(Decimal(30), tp=StakingTransaction.TYPES.instant_end_request).id,
            'planId': self.plan.id,
            'type': 'instant_end',
            'amount': '30',
        }

    def test_invalid_plan_id(self):
        response = self.call_api(Decimal('30'), self.plan.id + 1)

        assert response['status'] == 'failed'
        assert response['code'] == 'InvalidPlanId'
        assert self.get_transaction(tp=StakingTransaction.TYPES.instant_end_request) is None
        assert self.get_transaction(Decimal(30), tp=StakingTransaction.TYPES.unstake) is None

    def test_when_staking_is_already_ended(self):
        self.plan.staked_at -= timedelta(days=self.plan.staking_period.days + 1)
        self.plan.save()

        response = self.call_api(Decimal('10'))

        assert response['status'] == 'failed'
        assert response['code'] == 'UnexpectedError'  # fixme to AlreadyEnded
        assert self.get_transaction(tp=StakingTransaction.TYPES.instant_end_request) is None
        assert self.get_transaction(Decimal(10), tp=StakingTransaction.TYPES.unstake) is None
