"""Plan Service Tests"""
from decimal import Decimal

from django.test import TestCase

from exchange.base.models import Currencies
from exchange.staking.models import Plan, ExternalEarningPlatform, StakingTransaction
from exchange.staking.exportables import get_balances_blocked_in_staking, _get_blocked_balances

from .utils import PlanTestDataMixin


class TestBlockedBalances(PlanTestDataMixin, TestCase):

    @classmethod
    def setUpTestData(cls) -> None:
        StakingTransaction.objects.all().delete()
        super().setUpTestData()
        cls.other_external_platform = ExternalEarningPlatform.objects.create(
            tp=ExternalEarningPlatform.TYPES.staking,
            currency=Currencies.eth,
            network='network',
            address='address',
            tag='tag',
        )
        plan_kwargs = cls.get_plan_kwargs()
        plan_kwargs['external_platform'] = cls.other_external_platform
        cls.other_plan = Plan.objects.create(**plan_kwargs)

    def setUp(self) -> None:
        _get_blocked_balances.cache_clear()

    def test_no_transaction(self):
        assert get_balances_blocked_in_staking(self.user_ids[0]) == dict()

    def test_blocked(self):
        StakingTransaction.objects.bulk_create((
            StakingTransaction(
                user_id=user_id, amount=amount, plan=plan, tp=StakingTransaction.TYPES.create_request,
            ) for user_id, amount, plan in (
                (self.user_ids[0], Decimal('10'), self.plan,),
                (self.user_ids[0], Decimal('21'), self.plan,),
                (self.user_ids[0], Decimal('43'), self.other_plan,),
                (self.user_ids[1], Decimal('80'), self.plan,),
            )
        ))
        assert get_balances_blocked_in_staking(self.user_ids[0]) == {
            self.plan.currency: Decimal('31'),
            self.other_plan.currency: Decimal('43'),
        }
        assert get_balances_blocked_in_staking(self.user_ids[1]) == {
            self.plan.currency: Decimal('80'),
        }

    def test_both_blocked_and_released(self):
        StakingTransaction.objects.bulk_create((
            StakingTransaction(
                user_id=self.user_ids[0], amount=amount, plan=plan, tp=tp,
            ) for tp, amount, plan in (
                (StakingTransaction.TYPES.create_request, Decimal('30'), self.plan,),
                (StakingTransaction.TYPES.cancel_create_request, Decimal('21'), self.plan,),
                (StakingTransaction.TYPES.create_request, Decimal('43'), self.other_plan,),
            )
        ))
        assert get_balances_blocked_in_staking(self.user_ids[0]) == {
            self.plan.currency: Decimal('9'),
            self.other_plan.currency: Decimal('43'),
        }

    def test_create_request_aggregation(self):
        StakingTransaction.objects.create(
            user_id=self.user_ids[0],
            plan=self.plan,
            tp=StakingTransaction.TYPES.create_request,
            amount=Decimal('40'),
            parent=StakingTransaction.objects.create(
                user_id=self.user_ids[0],
                plan=self.plan,
                tp=StakingTransaction.TYPES.create_request,
                amount=Decimal('20'),
            ),
        )
        assert get_balances_blocked_in_staking(self.user_ids[0]) == {
            self.plan.currency: Decimal('40'),
        }

    def test_user_on_multiple_plans(self):
        self.other_plan.external_platform.currency = self.plan.external_platform.currency
        self.other_plan.external_platform.save(update_fields=('currency',))
        StakingTransaction.objects.bulk_create((
            StakingTransaction(
                user_id=self.user_ids[0], amount=amount, plan=plan, tp=tp,
            ) for tp, amount, plan in (
                (StakingTransaction.TYPES.create_request, Decimal('30'), self.plan,),
                (StakingTransaction.TYPES.create_request, Decimal('43'), self.other_plan,),
            )
        ))
        assert get_balances_blocked_in_staking(self.user_ids[0]) == {
            self.plan.currency: Decimal('73'),
        }

    def test_released_asset(self):
        StakingTransaction.objects.bulk_create((
            StakingTransaction(
                user_id=self.user_ids[0], amount=amount, plan=plan, tp=tp,
            ) for tp, amount, plan in (
                (StakingTransaction.TYPES.create_request, Decimal('30'), self.plan,),
                (StakingTransaction.TYPES.release, Decimal('30'), self.plan,),
            )
        ))
        assert get_balances_blocked_in_staking(self.user_ids[0]) == {}
