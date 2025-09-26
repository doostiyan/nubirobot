from datetime import datetime, timedelta, timezone
from decimal import Decimal
from functools import wraps
from unittest.mock import MagicMock, call, patch

import pytest
from django.test import TestCase

from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.blockchain.staking.staking_models import StakingInfo
from exchange.staking import errors
from exchange.staking.models import ExternalEarningPlatform, PlanTransaction
from exchange.staking.rewards import (
    _fetch_non_periodic_staking_reward,
    _fetch_periodic_staking_reward,
    _fetch_staking_reward,
    fetch_reward,
)

from .test_staking_service import plan


@patch('exchange.staking.rewards.Plan.get_plan_to_update', lambda *_, **__: plan)
class FetchRewardTest(TestCase):

    @classmethod
    def setUpTestData(cls) -> None:
        cls.currency = plan.external_platform.currency
        cls.plan = plan

    @patch('exchange.staking.rewards._fetch_staking_reward')
    def test_a_staking_plan(self, staking_reward_fetcher_mock: MagicMock):
        plan.external_platform.tp = ExternalEarningPlatform.TYPES.staking
        fetch_reward(plan.id)
        staking_reward_fetcher_mock.assert_called_once()

    @patch('exchange.staking.rewards._fetch_yield_aggregator_reward')
    def test_a_yield_aggregator(self, yield_aggregator_reward_fetcher_mock: MagicMock):
        plan.external_platform.tp = ExternalEarningPlatform.TYPES.yield_aggregator
        fetch_reward(plan.id)
        yield_aggregator_reward_fetcher_mock.assert_called_once()

    def test_invalid_plan_type(self,):
        plan.external_platform.tp = -1
        with pytest.raises(NotImplementedError):
            fetch_reward(plan.id)
        plan.external_platform.tp = 101


@patch('exchange.staking.rewards.Plan.get_plan_to_update', lambda *_, **__: plan)
class FetchStakingRewardTest(TestCase):

    @patch('exchange.staking.rewards._fetch_non_periodic_staking_reward')
    @patch('exchange.staking.rewards._fetch_periodic_staking_reward')
    def test_coins_with_periodic_rewards(self, periodic_mock: MagicMock, non_periodic_mock: MagicMock,):
        currencies = (
            Currencies.bnb,
        )
        for currency in currencies:
            plan.external_platform.currency = currency
            _fetch_staking_reward(plan,)
        periodic_mock.assert_has_calls(calls=len(currencies) * [call(plan)])
        non_periodic_mock.assert_not_called()
        plan.external_platform.currency = 10

    @patch('exchange.staking.rewards._fetch_non_periodic_staking_reward')
    @patch('exchange.staking.rewards._fetch_periodic_staking_reward')
    def test_coins_with_non_periodic_rewards(self, periodic_mock: MagicMock, non_periodic_mock: MagicMock,):
        currencies = (
            Currencies.ftm,
        )
        for currency in currencies:
            plan.external_platform.currency = currency
            _fetch_staking_reward(plan,)
        non_periodic_mock.assert_has_calls(calls=len(currencies) * [call(plan)])
        periodic_mock.assert_not_called()


_ir_now = datetime.now(timezone.utc)


def _patch_stake_asset(test):
    patch_prefix = 'exchange.staking.rewards'

    @wraps(test)
    @patch(patch_prefix + '.ir_now', lambda: _ir_now)
    @patch(patch_prefix + '.PlanTransaction.objects.create')
    @patch(patch_prefix + '._get_staking_reward_balance', lambda *_, **__: 22.12)
    @patch(patch_prefix + '.Plan.get_active_transaction_by_tp')
    def decorated(*args, **kwargs):
        return test(*args, **kwargs)
    return decorated


class FetchPeriodicStakingRewardTest(TestCase):

    def setUp(self,) -> None:
        self.transaction = PlanTransaction(
            plan=plan,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('11'),
            created_at=_ir_now - timedelta(hours=25),
        )

    @_patch_stake_asset
    def test_early_request(
        self,
        transactions_get_mock: MagicMock,
        transactions_create_mock: MagicMock,
    ):
        self.transaction.created_at = _ir_now - timedelta(hours=.8)
        transactions_get_mock.return_value = self.transaction
        with pytest.raises(errors.TooSoon):
            _fetch_periodic_staking_reward(plan)
        transactions_create_mock.assert_not_called()

    @_patch_stake_asset
    def test_first_fetched_record(
        self,
        transactions_get_mock: MagicMock,
        transactions_create_mock: MagicMock,
    ):
        transactions_get_mock.side_effect = PlanTransaction.DoesNotExist
        _fetch_periodic_staking_reward(plan)
        transactions_create_mock.assert_called_once_with(
            plan=plan,
            parent=None,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('22.12'),
            created_at=_ir_now,
        )

    @_patch_stake_asset
    def test_aggregation(
        self,
        transactions_get_mock: MagicMock,
        transactions_create_mock: MagicMock,
    ):
        transactions_get_mock.return_value = self.transaction
        _fetch_periodic_staking_reward(plan)
        transactions_create_mock.assert_called_once_with(
            plan=plan,
            parent=self.transaction,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('33.12'),
            created_at=_ir_now,
        )

    @_patch_stake_asset
    def test_repetitive_call(
        self,
        transactions_get_mock: MagicMock,
        transactions_create_mock: MagicMock,
    ):
        self.transaction.created_at = _ir_now - timedelta(hours=1.001)
        transactions_get_mock.return_value = self.transaction
        _fetch_periodic_staking_reward(plan)
        if (_ir_now - timedelta(hours=1.001)).date() == _ir_now.date():
            transactions_create_mock.assert_not_called()
        else:
            transactions_create_mock.assert_called_once_with(
                plan=plan,
                parent=self.transaction,
                tp=PlanTransaction.TYPES.fetched_reward,
                amount=Decimal('33.12'),
                created_at=_ir_now,
            )


class FetchNonPeriodicStakingRewardTest(TestCase):
    def setUp(self,) -> None:
        self.transaction = PlanTransaction(
            plan=plan,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('11'),
            created_at=_ir_now - timedelta(hours=25),
        )

    @_patch_stake_asset
    def test_early_request(
        self,
        transactions_get_mock: MagicMock,
        transactions_create_mock: MagicMock,
    ):
        self.transaction.created_at = _ir_now - timedelta(hours=.8)
        transactions_get_mock.return_value = self.transaction
        with pytest.raises(errors.TooSoon):
            _fetch_non_periodic_staking_reward(plan)
        transactions_create_mock.assert_not_called()

    @_patch_stake_asset
    def test_first_fetched_record(
        self,
        transactions_get_mock: MagicMock,
        transactions_create_mock: MagicMock,
    ):
        transactions_get_mock.side_effect = PlanTransaction.DoesNotExist
        _fetch_non_periodic_staking_reward(plan)
        transactions_create_mock.assert_called_once_with(
            plan=plan,
            parent=None,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('22.12'),
            created_at=_ir_now,
        )

    @_patch_stake_asset
    def test_dont_aggregate(
        self,
        transactions_get_mock: MagicMock,
        transactions_create_mock: MagicMock,
    ):
        transactions_get_mock.return_value = self.transaction
        _fetch_non_periodic_staking_reward(plan)
        transactions_create_mock.assert_called_once_with(
            plan=plan,
            parent=self.transaction,
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('22.12'),
            created_at=_ir_now,
        )
