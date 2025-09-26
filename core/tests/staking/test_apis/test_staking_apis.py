"""Staking APIs Test"""

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.utils.timezone import timedelta

from exchange.accounts.models import User, UserRestriction, VerificationProfile
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.staking import best_performing_plans
from exchange.staking.models import ExternalEarningPlatform, Plan, StakingTransaction

from ..test_best_performing_plans import OfferedPlansSelectionTest
from ..utils import PlanArgsMixin, StakingTestDataMixin


class PlansApiTest(PlanArgsMixin, TestCase):

    def fetch_plans(self, **kwargs):
        return self.client.get('/earn/plan', kwargs).json()['result']

    def test_non_announced_plans(self):
        plan_kwargs = self.get_plan_kwargs()
        plan_kwargs['announced_at'] = ir_now() + timedelta(.1)
        plan = Plan.objects.create(**plan_kwargs)
        assert len(self.fetch_plans()) == 0
        plan.announced_at = ir_now() - timedelta(.1)
        plan.save(update_fields=('announced_at',))
        plans = self.fetch_plans()
        assert len(plans) == 1
        assert plans[0]['id'] == plan.id

    def requestable_plan_kwargs(self):
        return self.get_plan_kwargs()

    def non_requestable_plan_kwargs(self):
        kwargs = self.get_plan_kwargs()
        kwargs['staking_period'] += timedelta(days=1)
        kwargs['request_period'] = timedelta(.7)
        kwargs['opened_at'] += timedelta(.1)
        return kwargs

    def test_order_against_increasing_opened_at(self):
        plan0_kwargs = self.requestable_plan_kwargs()
        plan1_kwargs = self.non_requestable_plan_kwargs()
        plan1_kwargs['request_period'] = timedelta(.7)
        plan1_kwargs['opened_at'] += timedelta(.1)
        (plan0, plan1,) = Plan.objects.bulk_create((Plan(**plan0_kwargs), Plan(**plan1_kwargs),))
        plans = self.fetch_plans()
        assert len(plans) == 2
        assert plan0.id == plans[0]['id']
        assert plan1.id == plans[1]['id']

    def test_order_against_decreasing_opened_at(self):
        plan0_kwargs = self.requestable_plan_kwargs()
        plan1_kwargs = self.non_requestable_plan_kwargs()
        plan1_kwargs['request_period'] = timedelta(.7)
        plan1_kwargs['opened_at'] -= timedelta(.1)
        (plan0, plan1,) = Plan.objects.bulk_create((Plan(**plan0_kwargs), Plan(**plan1_kwargs),))
        plans = self.fetch_plans()
        assert len(plans) == 2
        assert plan0.id == plans[0]['id']
        assert plan1.id == plans[1]['id']

    def test_order_against_increasing_creation_time(self):
        plan0_kwargs = self.get_plan_kwargs()
        plan1_kwargs = self.non_requestable_plan_kwargs()
        plan0 = Plan.objects.create(**plan0_kwargs)
        plan1 = Plan.objects.create(**plan1_kwargs)
        plans = self.fetch_plans()
        assert len(plans) == 2
        assert plan0.id == plans[0]['id']
        assert plan1.id == plans[1]['id']

    def test_order_against_decreasing_creation_time(self):
        plan0_kwargs = self.get_plan_kwargs()
        plan1_kwargs = self.non_requestable_plan_kwargs()
        plan1 = Plan.objects.create(**plan1_kwargs)
        plan0 = Plan.objects.create(**plan0_kwargs)
        plans = self.fetch_plans()
        assert len(plans) == 2
        assert plan0.id == plans[0]['id']
        assert plan1.id == plans[1]['id']

    def test_active_plans(self):
        Plan.objects.all().delete()
        Plan.objects.create(**self.get_plan_kwargs())
        Plan.objects.create(**self.get_plan_kwargs())
        plan0, plan1 = list(Plan.objects.all())
        plan1.extended_from = plan0
        plan1.save()
        plans = self.fetch_plans()
        assert len(self.fetch_plans()) == 1
        assert plan1.id == plans[0]['id']

    def test_when_external_earning_platform_is_unavailable_then_its_plans_are_filtered(self):
        Plan.objects.all().delete()

        # unavailable platform plans
        plan0_kwargs = self.get_plan_kwargs()
        plan1_kwargs = self.non_requestable_plan_kwargs()
        plan0 = Plan.objects.create(**plan1_kwargs)
        plan1 = Plan.objects.create(**plan0_kwargs)

        # unavailable platform plans
        unavailable_platform = ExternalEarningPlatform.objects.create(
            tp=101, currency=123, network='network', address='address', tag='tag', is_available=False
        )

        Plan.objects.create(**self.get_plan_kwargs(unavailable_platform))
        Plan.objects.create(**self.get_plan_kwargs(unavailable_platform))
        Plan.objects.create(**self.get_plan_kwargs(unavailable_platform))

        response_result = self.fetch_plans()
        assert len(response_result) == 2
        assert {plan0.id, plan1.id} == {response_result[0]['id'], response_result[1]['id']}

    def test_active_plan_with_filter(self):
        ya_eep = ExternalEarningPlatform.objects.create(
            tp=ExternalEarningPlatform.TYPES.yield_aggregator,
            currency=Currencies.btc,
            network='network',
            address='address',
            tag='tag',
        )
        Plan.objects.all().delete()
        Plan.objects.create(**self.get_plan_kwargs(external_platform=ya_eep))
        plan1_kwargs = self.non_requestable_plan_kwargs()
        Plan.objects.create(**plan1_kwargs)
        plans = self.fetch_plans(type="yield_aggregator")
        assert len(plans) == 1
        assert plans[0]['type'] == 'yield_aggregator'

    def test_similar_plans(self):
        plan_kwargs = self.requestable_plan_kwargs()
        Plan.objects.all().delete()
        Plan.objects.create(**plan_kwargs)
        for key in ('announced_at', 'staked_at',):
            plan_kwargs[key] -= timedelta(days=100)
        Plan.objects.create(**plan_kwargs)
        assert len(self.fetch_plans()) == 1


class UserRestrictionTest(StakingTestDataMixin, TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.user.user_type = User.USER_TYPES.level2
        VerificationProfile.objects.filter(id=cls.user.get_verification_profile().id).update(email_confirmed=True)
        cls.user.save()

    def setUp(self):
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'

    def test_enable_auto_extend(self):
        assert (
            self.client.post(path='/earn/plan/auto-extend/enable', data={'planId': self.plan.id}).json()['status']
            == 'ok'
        )
        UserRestriction.objects.create(user=self.user, restriction=UserRestriction.RESTRICTION.StakingRenewal)
        response = self.client.post(path='/earn/plan/auto-extend/enable', data={'planId': self.plan.id}).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'ActionIsRestricted'
        assert response['message'] == 'You have been restricted by admin.'

    def test_disable_auto_extend(self):
        assert (
            self.client.post(path='/earn/plan/auto-extend/disable', data={'planId': self.plan.id}).json()['status']
            == 'ok'
        )
        UserRestriction.objects.create(user=self.user, restriction=UserRestriction.RESTRICTION.StakingRenewal)
        response = self.client.post(path='/earn/plan/auto-extend/disable', data={'planId': self.plan.id}).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'ActionIsRestricted'
        assert response['message'] == 'You have been restricted by admin.'

    def test_create_request(self):
        self.wallet.balance = 1000
        self.wallet.save(update_fields=('balance',))
        assert (
            self.client.post(path='/earn/request/create', data={'planId': self.plan.id, 'amount': '10'}).json()[
                'status'
            ]
            == 'ok'
        )
        UserRestriction.objects.create(user=self.user, restriction=UserRestriction.RESTRICTION.StakingParticipation)
        response = self.client.post(path='/earn/request/create', data={'planId': self.plan.id}).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'ActionIsRestricted'
        assert response['message'] == 'You have been restricted by admin.'

    def test_instant_end(self):
        StakingTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_in,
            amount=50,
        )
        StakingTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.stake,
            amount=50,
        )
        assert (
            self.client.post(path='/earn/request/instant-end', data={'planId': self.plan.id, 'amount': 15}).json()[
                'status'
            ]
            == 'ok'
        )
        UserRestriction.objects.create(user=self.user, restriction=UserRestriction.RESTRICTION.StakingCancellation)
        response = self.client.post(path='/earn/request/instant-end', data={'planId': self.plan.id}).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'ActionIsRestricted'
        assert response['message'] == 'You have been restricted by admin.'

    def test_v1_end_request_restriction_is_like_instant_end(self):
        StakingTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.extend_in,
            amount=50,
        )
        StakingTransaction.objects.create(
            user=self.user,
            plan=self.plan,
            tp=StakingTransaction.TYPES.stake,
            amount=50,
        )
        assert (
            self.client.post(path='/earn/request/end', data={'planId': self.plan.id, 'amount': 21}).json()['status']
            == 'ok'
        )
        UserRestriction.objects.create(user=self.user, restriction=UserRestriction.RESTRICTION.StakingCancellation)
        response = self.client.post(path='/earn/request/end', data={'planId': self.plan.id}).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'ActionIsRestricted'
        assert response['message'] == 'You have been restricted by admin.'


class OfferedPlansSelectionTestApiTest(OfferedPlansSelectionTest):

    def test_success(self):
        cache.delete(best_performing_plans.BEST_PERFORMING_PLANS_CACHE_KEY_TEMPLATE.format(
            tp=ExternalEarningPlatform.TYPES.staking,
        ))

        self.create_plans(Currencies.btc, Decimal('10'))
        self.create_plans(Currencies.usdt, Decimal('20'))
        self.create_plans(Currencies.usdt, Decimal('19'))
        self.create_plans(Currencies.doge, Decimal('14'), ExternalEarningPlatform.TYPES.yield_aggregator)
        self.create_plans(Currencies.shib, Decimal('27'), ExternalEarningPlatform.TYPES.yield_aggregator)

        assert self.client.get(
            path='/earn/plan/best-performing',
        ).json()['result'] == [
            {
                'currency': 'usdt',
                'realizedAPR': '7300',
                'stakingPeriod': 86400.0,
            },
            {
                'currency': 'btc',
                'realizedAPR': '3650',
                'stakingPeriod': 86400.0,
            },
        ]
        assert self.client.get(
            path='/earn/plan/best-performing?type=yield_aggregator',
        ).json()['result'] == [
            {
                'currency': 'shib',
                'realizedAPR': '9855',
                'stakingPeriod': 86400.0,
            },
            {
                'currency': 'doge',
                'realizedAPR': '5110',
                'stakingPeriod': 86400.0,
            },
        ]

    def test_invalid_type(self):
        assert self.client.get(
            path='/earn/plan/best-performing?type=mamad',
        ).json()['code'] == 'ParseError'
