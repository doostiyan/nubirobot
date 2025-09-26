"""Staking Service Tests"""

from decimal import Decimal
from functools import wraps
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase
from django.utils.timezone import timedelta

from exchange.base.calendar import ir_now
from exchange.staking import errors
from exchange.staking.models import ExternalEarningPlatform, Plan, StakingTransaction

_currency = 10
nw = ir_now()
a_day = timedelta(days=1)

external_earning_kwargs = dict(
    tp=ExternalEarningPlatform.TYPES.staking,
    currency=10,
    network='network',
    address='address',
    tag='tag',
)
plan_kwargs = dict(
    total_capacity=Decimal('100'),
    filled_capacity=Decimal('90'),
    announced_at=nw,
    opened_at=nw,
    request_period=a_day,
    staked_at=nw,
    staking_period=a_day,
    unstaking_period=a_day,

    initial_pool_capacity=Decimal('100'),
    is_extendable=True,
    reward_announcement_period=a_day,
    min_staking_amount=Decimal('5'),
    staking_precision=Decimal('0.1'),
)

plan = Plan(id=564654, external_platform=ExternalEarningPlatform(**external_earning_kwargs), **plan_kwargs)


def _patch_auto_end_flag_test(test):
    patch_prefix = 'exchange.staking.models.staking'

    @wraps(test)
    @patch(patch_prefix + '.Plan.get_plan_to_read')
    @patch(patch_prefix + '.StakingTransaction.get_active_transaction_by_tp')
    @patch(patch_prefix + '.StakingTransaction.objects.create')
    def decorated(*args, **kwargs):
        return test(*args, **kwargs)

    return decorated


class AutoExtendFlagTest(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        class DummyObject:
            pass

        cls.dummy_transaction = DummyObject()
        plan.staked_at = ir_now()
        cls.user_id = 124
        cls.plan_id = plan.id

    @_patch_auto_end_flag_test
    def test_non_un_extendable_plan(
        self,
        create_mock: MagicMock,
        get_active_transaction_by_tp_mock: MagicMock,
        get_plan_to_read_mock: MagicMock,
    ):
        get_plan_to_read_mock.return_value = plan
        plan.is_extendable = False
        with pytest.raises(errors.NonExtendablePlan):
            StakingTransaction.enable_auto_end(self.user_id, self.plan_id)
        create_mock.assert_not_called()
        get_active_transaction_by_tp_mock.assert_not_called()

    @_patch_auto_end_flag_test
    def test_activation(
        self,
        create_mock: MagicMock,
        get_active_transaction_by_tp_mock: MagicMock,
        get_plan_to_read_mock: MagicMock,
    ):
        get_plan_to_read_mock.return_value = plan
        get_active_transaction_by_tp_mock.side_effect = StakingTransaction.DoesNotExist
        StakingTransaction.enable_auto_end(self.user_id, self.plan_id)
        create_mock.assert_called_once_with(
            user_id=self.user_id,
            plan_id=self.plan_id,
            tp=StakingTransaction.TYPES.auto_end_request,
        )

    @_patch_auto_end_flag_test
    def test_deactivation(
        self,
        create_mock: MagicMock,
        get_active_transaction_by_tp_mock: MagicMock,
        get_plan_to_read_mock: MagicMock,
    ):
        get_plan_to_read_mock.return_value = plan
        get_active_transaction_by_tp_mock.return_value = self.dummy_transaction
        StakingTransaction.disable_auto_end(self.user_id, self.plan_id)
        create_mock.assert_called_once_with(
            user_id=self.user_id,
            plan_id=self.plan_id,
            tp=StakingTransaction.TYPES.deactivator,
            parent=self.dummy_transaction,
        )

    @_patch_auto_end_flag_test
    def test_already_activated(
        self,
        create_mock: MagicMock,
        get_active_transaction_by_tp_mock: MagicMock,
        get_plan_to_read_mock: MagicMock,
    ):
        get_plan_to_read_mock.return_value = plan
        get_active_transaction_by_tp_mock.return_value = self.dummy_transaction
        StakingTransaction.enable_auto_end(self.user_id, self.plan_id)
        create_mock.assert_not_called()

    @_patch_auto_end_flag_test
    def test_already_deactivated(
        self,
        create_mock: MagicMock,
        get_active_transaction_by_tp_mock: MagicMock,
        get_plan_to_read_mock: MagicMock,
    ):
        get_plan_to_read_mock.return_value = plan
        get_active_transaction_by_tp_mock.side_effect = StakingTransaction.DoesNotExist
        StakingTransaction.disable_auto_end(self.user_id, self.plan_id)
        create_mock.assert_not_called()

    @_patch_auto_end_flag_test
    def test_disabling_flag_for_non_un_extendable_plan(
        self,
        create_mock: MagicMock,
        get_active_transaction_by_tp_mock: MagicMock,
        get_plan_to_read_mock: MagicMock,
    ):
        get_plan_to_read_mock.return_value = plan
        plan.is_extendable = False
        with pytest.raises(errors.NonExtendablePlan):
            StakingTransaction.disable_auto_end(self.user_id, self.plan_id)
        create_mock.assert_not_called()
        get_active_transaction_by_tp_mock.assert_not_called()
