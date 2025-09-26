from decimal import Decimal
from unittest.mock import call, patch

from django.test import TestCase

from exchange.staking.models import StakingTransaction
from exchange.staking.tasks import release_users_assets_task
from tests.staking.utils import StakingTestDataMixin


class ReleaseUserAssetsTaskTests(StakingTestDataMixin, TestCase):
    def setUp(self):
        self.plan1 = self.create_plan(**self.get_plan_kwargs())
        self.plan2 = self.create_plan(**self.get_plan_kwargs())
        self.user1 = self.create_user()
        self.user2 = self.create_user()
        self.user3 = self.create_user()
        self.user4 = self.create_user()
        self.user5 = self.create_user()
        # plan1
        self.plan1_instant_end_request1 = self.create_staking_transaction(
            user=self.user1, plan=self.plan1, amount=Decimal('100'), tp=StakingTransaction.TYPES.instant_end_request
        )
        self.create_staking_transaction(
            user=self.user1,
            plan=self.plan1,
            amount=Decimal('100'),
            tp=StakingTransaction.TYPES.unstake,
            parent=self.plan1_instant_end_request1,
        )
        self.plan1_instant_end_request5 = self.create_staking_transaction(
            user=self.user5, plan=self.plan1, amount=Decimal('100'), tp=StakingTransaction.TYPES.instant_end_request
        )
        self.create_staking_transaction(
            user=self.user5,
            plan=self.plan1,
            amount=Decimal('150'),
            tp=StakingTransaction.TYPES.unstake,
            parent=self.plan1_instant_end_request5,
        )
        # plan 2
        self.user_plan2_auto_end_transaction = self.create_staking_transaction(
            user=self.user, plan=self.plan2, amount=Decimal('0.0'), tp=StakingTransaction.TYPES.auto_end_request
        )
        self.create_staking_transaction(
            user=self.user2,
            plan=self.plan2,
            amount=Decimal('110'),
            tp=StakingTransaction.TYPES.unstake,
            parent=self.user_plan2_auto_end_transaction,
        )

        # these users released assets before
        self.create_staking_transaction(
            user=self.user3,
            plan=self.plan1,
            amount=Decimal('10'),
            tp=StakingTransaction.TYPES.release,
            parent=self.create_staking_transaction(
                user=self.user3,
                plan=self.plan1,
                amount=Decimal('10'),
                tp=StakingTransaction.TYPES.unstake,
            ),
        )

        self.create_staking_transaction(
            user=self.user4,
            plan=self.plan2,
            amount=Decimal('5'),
            tp=StakingTransaction.TYPES.release,
            parent=self.create_staking_transaction(
                user=self.user4,
                plan=self.plan2,
                amount=Decimal('5'),
                tp=StakingTransaction.TYPES.unstake,
            ),
        )

    @patch('exchange.staking.service.release_assets._release_user_asset')
    def test_release_user_assets_task_calls_release_service_successfully(self, mock_release_user_assets_service):
        release_users_assets_task(self.plan1.id)
        mock_release_user_assets_service.asset_has_calls(
            [call(self.user1.id, self.plan1.id), call(self.user5.id, self.plan1.id)], any_order=True
        )

        mock_release_user_assets_service.reset_mock()

        release_users_assets_task(self.plan2.id)
        mock_release_user_assets_service.assert_called_once_with(self.user2.id, self.plan2.id)
