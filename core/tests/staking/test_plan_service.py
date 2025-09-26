"""Plan Service Tests"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

import pytest
from django.test import TestCase

from exchange.base.calendar import ir_now
from exchange.base.money import money_is_zero
from exchange.staking import errors
from exchange.staking.helpers import get_asset_collector_user, get_fee_collector_user, get_nobitex_reward_collector
from exchange.staking.models import Plan, PlanTransaction, StakingTransaction
from exchange.staking.service.announce_reward import (
    _create_users_announce_reward_transactions,
    _edit_users_announce_reward_transactions,
)
from exchange.wallet.helpers import RefMod
from exchange.wallet.models import Transaction, Wallet

from .utils import PlanTestDataMixin


class PlanServiceTest(PlanTestDataMixin, TestCase):

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.plan.opened_at = ir_now() - timedelta(days=2)
        cls.plan.staked_at = ir_now() + timedelta(days=2)
        cls.plan.save()

    def setUp(self) -> None:
        self.plan = Plan.get_plan_to_update(self.plan.id)

    # Block Capacity Tests
    # # # # # # # # # # # #
    def test_block_success(self):
        amount = Decimal('7')
        initial_filled_capacity = self.plan.filled_capacity
        self.plan.block_capacity(amount)
        assert initial_filled_capacity + amount == Plan.objects.get(pk=self.plan.id).filled_capacity

    def test_over_blocking(self):
        amount = Decimal('11')
        with pytest.raises(errors.LowPlanCapacity):
            assert self.plan.block_capacity(amount) is None
        assert self.plan.filled_capacity == Plan.objects.get(pk=self.plan.id).filled_capacity

    # UnBlock Capacity Tests
    # # # # # # # # # # # #
    def test_unblock_success(self):
        amount = Decimal('7')
        initial_filled_capacity = self.plan.filled_capacity
        self.plan.unblock_capacity(amount)
        assert initial_filled_capacity - amount == Plan.objects.get(pk=self.plan.id).filled_capacity

    def test_over_unblocking(self):
        amount = Decimal('91')
        with pytest.raises(errors.LowPlanCapacity):
            assert self.plan.block_capacity(amount) is None
        assert self.plan.filled_capacity == Plan.objects.get(pk=self.plan.id).filled_capacity

    # Quantize Amount Tests
    # # # # # # # # # # # #
    def test_quantize_success(self):
        amount = Decimal('7.12')
        assert self.plan.quantize_amount(amount) == Decimal('7.1')

    def test_round_down(self):
        amount = Decimal('7.19')
        assert self.plan.quantize_amount(amount) == Decimal('7.1')

    def test_negative_amount(self):
        amount = Decimal('-1.1')
        with pytest.raises(errors.InvalidAmount):
            self.plan.quantize_amount(amount)
        assert self.plan.filled_capacity == Plan.objects.get(pk=self.plan.id).filled_capacity

    def test_small_amount(self):
        amount = Decimal('4.9999')
        with pytest.raises(errors.InvalidAmount):
            self.plan.quantize_amount(amount)
        assert self.plan.filled_capacity == Plan.objects.get(pk=self.plan.id).filled_capacity

    # Validate Create Request Time Tests
    # # # # # # # # # # # #
    def test_ok_create_request_time(self):
        self.plan.opened_at = ir_now() - timedelta(days=1)
        self.plan.request_period = timedelta(days=2)
        self.plan.save(update_fields=('opened_at', 'request_period',))
        assert self.plan.check_if_plan_is_open_to_accepting_requests() is None

    def test_late_create_request(self):
        self.plan.opened_at = ir_now() - timedelta(days=2)
        self.plan.request_period = timedelta(days=1)
        self.plan.save(update_fields=('opened_at', 'request_period',))
        with pytest.raises(errors.TooLate):
            self.plan.check_if_plan_is_open_to_accepting_requests()

    def test_early_create_request(self):
        self.plan.opened_at = ir_now() + timedelta(days=1)
        self.plan.request_period = timedelta(days=1)
        self.plan.save(update_fields=('opened_at', 'request_period',))
        with pytest.raises(errors.TooSoon):
            self.plan.check_if_plan_is_open_to_accepting_requests()

    # `system_approve_stake_amount` Tests
    # # # # # # # # # # # #
    def test_ok_system_approve_stake_amount(self):
        self.plan.opened_at = ir_now() - timedelta(days=3)
        self.plan.request_period = timedelta(days=2)
        self.plan.save(update_fields=('opened_at', 'request_period',))
        StakingTransaction.objects.bulk_create([StakingTransaction(
            user_id=user_id,
            plan_id=self.plan.id,
            tp=StakingTransaction.TYPES.create_request,
            amount=Decimal('10'),
        ) for user_id in self.user_ids])
        StakingTransaction.objects.create(
            user_id=self.user_ids[0],
            plan_id=self.plan.id,
            tp=StakingTransaction.TYPES.create_request,
            amount=Decimal('45'),
            parent=StakingTransaction.objects.filter(user_id=self.user_ids[0], plan_id=self.plan.id).first()
        )

        Plan.system_approve_stake_amount(self.plan.id)
        assert self.plan.transactions.filter(
            tp=PlanTransaction.TYPES.system_stake_amount_approval,
        ).first().amount == Decimal('45') + (len(self.user_ids) - 1) * Decimal('10')

    def test_soon_system_approve_stake_amount(self):
        self.plan.opened_at = ir_now() - timedelta(days=1)
        self.plan.request_period = timedelta(days=2)
        self.plan.save(update_fields=('opened_at', 'request_period',))
        with pytest.raises(errors.TooSoon):
            Plan.system_approve_stake_amount(self.plan.id)

    def test_duplicate_system_approve_stake_amount(self):
        self.plan.opened_at = ir_now() - timedelta(days=3)
        self.plan.request_period = timedelta(days=2)
        self.plan.save(update_fields=('opened_at', 'request_period',))
        Plan.system_approve_stake_amount(self.plan.id)
        with pytest.raises(errors.AlreadyCreated):
            Plan.system_approve_stake_amount(self.plan.id)

    # `stake_assets` Tests
    # # # # # # # # # # # #
    def test_ok_stake_assets(self):
        self.plan.staked_at = ir_now() - timedelta(.1)
        self.plan.save(update_fields=('staked_at',),)
        self.setUp()
        self.plan.transactions.create(
            tp=PlanTransaction.TYPES.system_stake_amount_approval,
            amount=Decimal('245'),
        )
        Plan.stake_assets(self.plan.id)
        assert self.plan.transactions.get(tp=PlanTransaction.TYPES.stake).amount == Decimal('245')

    def test_early_stake_assets(self):
        self.plan.staked_at = ir_now() + timedelta(.1)
        self.plan.save(update_fields=('staked_at',),)
        self.setUp()
        self.plan.transactions.create(
            tp=PlanTransaction.TYPES.system_stake_amount_approval,
            amount=Decimal('245'),
        )
        with pytest.raises(errors.TooSoon):
            Plan.stake_assets(self.plan.id)

    def test_duplicate_stake_assets(self):
        self.plan.staked_at = ir_now() - timedelta(.1)
        self.plan.save(update_fields=('staked_at',),)
        self.setUp()
        self.plan.transactions.create(
            tp=PlanTransaction.TYPES.system_stake_amount_approval,
            amount=Decimal('245'),
        )
        Plan.stake_assets(self.plan.id)
        with pytest.raises(errors.AlreadyCreated):
            Plan.stake_assets(self.plan.id)

    def test_no_approval_stake_assets(self):
        self.plan.staked_at = ir_now() - timedelta(.1)
        self.plan.save(update_fields=('staked_at',),)
        self.setUp()
        with pytest.raises(errors.ParentIsNotCreated):
            Plan.stake_assets(self.plan.id)

    # `get_fetched_reward_amount_until` Tests
    # # # # # # # # # # # #
    def test_no_fetched_reward_test(self):
        assert self.plan.get_fetched_reward_amount_until(ir_now()) == Decimal('0')

    def test_last_fetched_reward_order(self):
        self.plan.transactions.create(
            tp=PlanTransaction.TYPES.fetched_reward,
            created_at=ir_now() - timedelta(minutes=30),
            amount=Decimal('30'),
        )
        self.plan.transactions.create(
            tp=PlanTransaction.TYPES.fetched_reward,
            created_at=ir_now() - timedelta(minutes=10),
            amount=Decimal('10'),
        )
        self.plan.transactions.create(
            tp=PlanTransaction.TYPES.fetched_reward,
            created_at=ir_now() - timedelta(minutes=20),
            amount=Decimal('20'),
        )
        assert self.plan.get_fetched_reward_amount_until(ir_now()) == Decimal('10')

    def test_last_fetched_reward_filter(self):
        self.plan.transactions.create(
            tp=PlanTransaction.TYPES.fetched_reward,
            created_at=ir_now() - timedelta(minutes=10),
            amount=Decimal('10'),
        )
        self.plan.transactions.create(
            tp=PlanTransaction.TYPES.fetched_reward,
            created_at=ir_now() + timedelta(minutes=20),
            amount=Decimal('20'),
        )
        assert self.plan.get_fetched_reward_amount_until(ir_now()) == Decimal('10')

    # `_create_users_announce_reward_transactions` Tests
    # # # # # # # # # # # #
    def test_user_announced_reward_amount(self):
        for user_id, staking_amount in zip(self.user_ids, (
            Decimal('10'), Decimal('20'), Decimal('3'),
        )):
            StakingTransaction.objects.create(
                user_id=user_id, plan=self.plan, tp=StakingTransaction.TYPES.stake, amount=staking_amount,
            )
        self.plan.transactions.create(
            tp=PlanTransaction.TYPES.system_stake_amount_approval,
            amount=Decimal('90'),
        )
        plan_reward_transaction = self.plan.transactions.create(
            tp=PlanTransaction.TYPES.announce_reward,
            amount=Decimal('4'),
        )
        _create_users_announce_reward_transactions(self.plan, plan_reward_transaction)
        for user_id, staking_amount in zip(
            self.user_ids,
            (
                Decimal('10'),
                Decimal('20'),
                Decimal('3'),
            ),
        ):
            assert money_is_zero(
                StakingTransaction.objects.get(
                    user_id=user_id,
                    plan=self.plan,
                    tp=StakingTransaction.TYPES.announce_reward,
                ).amount
                - Decimal('4') * (staking_amount / Decimal('90'))
            )

        plan_reward_transaction.amount = Decimal('7')
        _edit_users_announce_reward_transactions(self.plan, plan_reward_transaction)
        for user_id, staking_amount in zip(
            self.user_ids,
            (
                Decimal('10'),
                Decimal('20'),
                Decimal('3'),
            ),
        ):
            assert money_is_zero(
                StakingTransaction.objects.get(
                    user_id=user_id,
                    plan=self.plan,
                    tp=StakingTransaction.TYPES.announce_reward,
                ).amount
                - Decimal('7') * (staking_amount / Decimal('90'))
            )


class GetRewardAnnouncementTimestampTest(PlanTestDataMixin, TestCase):

    @classmethod
    def setUpTestData(cls,) -> None:
        super().setUpTestData()
        cls.plan.opened_at = ir_now() - timedelta(days=2)
        cls.plan.staked_at = ir_now() - timedelta(days=1)
        cls.plan.staking_period = timedelta(days=4)
        cls.plan.reward_announcement_period = timedelta(days=0.7)
        cls.plan.save()

    def setUp(self) -> None:
        self.plan = Plan.get_plan_to_read(self.plan.id,)

    def test_badly_configured_plan(self,):
        self.plan.reward_announcement_period = timedelta(minutes=0.9)
        self.plan.get_reward_announcement_timestamp()
        self.plan.refresh_from_db()
        assert self.plan.reward_announcement_period == timedelta(days=1)

    def test_early_call(self,):
        self.plan.staked_at = ir_now() + timedelta(minutes=1)
        with pytest.raises(errors.TooSoon):
            self.plan.get_reward_announcement_timestamp()

    def test_first_announcement(self,):
        self.plan.staked_at = ir_now() - 0.9 * self.plan.reward_announcement_period
        assert self.plan.get_reward_announcement_timestamp() == self.plan.staked_at

    def test_an_announcement_in_middle(self,):
        self.plan.staked_at = ir_now() - 1.1 * self.plan.reward_announcement_period
        assert self.plan.get_reward_announcement_timestamp() == self.plan.staked_at \
            + self.plan.reward_announcement_period

    def test_last_announcement(self,):
        self.plan.staked_at = ir_now() - timedelta(days=1000)
        assert self.plan.get_reward_announcement_timestamp() == self.plan.staked_at + self.plan.staking_period


class WithdrawUsersRewardFromPlanTest(PlanTestDataMixin, TestCase):

    @classmethod
    def setUpTestData(cls,) -> None:
        super().setUpTestData()
        cls.plan.transactions.create(
            tp=PlanTransaction.TYPES.announce_reward,
            amount=Decimal('100'),
            created_at=cls.plan.staked_at + cls.plan.staking_period,
        )
        cls.plan.transactions.create(
            tp=PlanTransaction.TYPES.fetched_reward,
            amount=Decimal('125'),
        )
        wallet = Wallet.get_user_wallet(get_asset_collector_user(), cls.currency)
        wallet.balance = Decimal('200')
        wallet.save()
        cls.system_wallet = Wallet.get_user_wallet(cls.system_user.id, cls.currency)

    def setUp(self) -> None:
        super().setUp()
        self.system_wallet.create_transaction('manual', '1000').commit()

    def test_system_user_low_balance(self):
        self.system_wallet.balance = 0
        self.system_wallet.save()
        with pytest.raises(errors.FailedAssetTransfer):
            Plan.withdraw_users_reward_from_plan(self.plan.id)

    def test_already_created(self):
        self.plan.transactions.all().delete()
        self.plan.transactions.create(
            tp=PlanTransaction.TYPES.give_reward,
            amount=-Decimal('100'),
        )
        with pytest.raises(errors.AlreadyCreated):
            Plan.withdraw_users_reward_from_plan(self.plan.id)

    def test_no_reward_announcement(self):
        self.plan.transactions.filter(
            tp=PlanTransaction.TYPES.announce_reward,
        ).delete()
        with pytest.raises(errors.ParentIsNotCreated):
            Plan.withdraw_users_reward_from_plan(self.plan.id)

    @patch('exchange.staking.models.plan.PlanTransaction.objects.create')
    @patch('exchange.staking.models.plan.create_and_commit_transaction')
    def test_wallet_transaction_creations(self, create_and_commit_mock: MagicMock, create_mock: MagicMock,):
        dummy_trx = PlanTransaction.objects.first()
        dummy_w_trx = Transaction.objects.first()
        create_mock.side_effect = (dummy_trx, dummy_trx, dummy_trx, dummy_trx, dummy_trx,)
        create_and_commit_mock.side_effect = (dummy_w_trx, dummy_w_trx, dummy_w_trx, dummy_w_trx, dummy_w_trx,)
        Plan.withdraw_users_reward_from_plan(self.plan.id)
        currency = self.plan.external_platform.currency
        create_and_commit_mock.assert_has_calls(calls=(call(
            user_id=get_fee_collector_user().id,
            currency=currency,
            amount=Decimal('25'),
            ref_id=dummy_trx.id,
            ref_module=RefMod.staking_fee,
            description=f'reward fee, planId: {self.plan.id}',
        ), call(
            user_id=get_asset_collector_user().id,
            currency=currency,
            amount=Decimal('-25'),
            ref_id=dummy_trx.id,
            ref_module=RefMod.staking_fee,
            description=f'reward fee, planId: {self.plan.id}',
        ), call(
            user_id=get_asset_collector_user().id,
            currency=currency,
            amount=Decimal('-90'),
            ref_id=dummy_trx.id,
            ref_module=RefMod.staking_reward,
            description=f'rewards withdrawn to be paid to users, planId: {self.plan.id}',
        ), call(
            user_id=get_asset_collector_user().id,
            currency=currency,
            amount=Decimal('-10'),
            ref_id=dummy_trx.id,
            ref_module=RefMod.staking_reward,
            description=f'system rewards for unfilled capacity, planId: {self.plan.id}',
        ), call(
            user_id=get_nobitex_reward_collector().id,
            currency=currency,
            amount=Decimal('10'),
            ref_id=dummy_trx.id,
            ref_module=RefMod.staking_reward,
            description=f'system rewards for unfilled capacity, planId: {self.plan.id}',
        ),), any_order=True,)

    def test_last_reward_announcement_has_not_been_created(self):
        self.plan.transactions.filter(
            tp=PlanTransaction.TYPES.announce_reward,
        ).update(
            created_at=self.plan.staked_at + self.plan.staking_period - timedelta(hours=1),
        )
        with pytest.raises(errors.TooSoon):
            Plan.withdraw_users_reward_from_plan(self.plan.id)


class CreateExtendOutTransactionTest(PlanTestDataMixin, TestCase):

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.plan.staked_at = ir_now() - cls.plan.staking_period
        cls.plan.save()
        cls.stake_transaction = cls.plan.transactions.create(tp=PlanTransaction.TYPES.stake)

    def test_a_success(self):
        StakingTransaction.objects.bulk_create((StakingTransaction(
            plan=self.plan, user_id=self.user_ids[0], amount=Decimal('22'), tp=StakingTransaction.TYPES.extend_out,
        ), StakingTransaction(
            plan=self.plan, user_id=self.user_ids[0], amount=Decimal('50'), tp=StakingTransaction.TYPES.unstake,
        ), StakingTransaction(
            plan=self.plan, user_id=self.user_ids[1], amount=Decimal('61'), tp=StakingTransaction.TYPES.extend_out,
        ), StakingTransaction(
            plan=self.plan, user_id=self.user_ids[2], amount=Decimal('9'), tp=StakingTransaction.TYPES.unstake,
        ),))
        Plan.create_extend_out_transaction(self.plan.id)
        assert PlanTransaction.objects.filter(
            plan=self.plan, tp=PlanTransaction.TYPES.unstake, amount=Decimal('59'), parent=self.stake_transaction,
        ).exists()
        assert PlanTransaction.objects.filter(
            plan=self.plan, tp=PlanTransaction.TYPES.extend_out, amount=Decimal('83'), parent=self.stake_transaction,
        ).exists()

    def test_early_call(self):
        self.plan.staked_at += timedelta(hours=1)
        self.plan.save()
        with pytest.raises(errors.TooSoon):
            Plan.create_extend_out_transaction(self.plan.id)

    def test_extend_out_creation_even_with_zero_values(self):
        Plan.create_extend_out_transaction(self.plan.id)
        assert PlanTransaction.objects.filter(
            plan=self.plan, tp=PlanTransaction.TYPES.unstake, amount=Decimal('0'), parent=self.stake_transaction,
        ).exists()
        assert PlanTransaction.objects.filter(
            plan=self.plan, tp=PlanTransaction.TYPES.extend_out, amount=Decimal('0'), parent=self.stake_transaction,
        ).exists()

    def test_user_in_stake_state_existence(self):
        StakingTransaction.objects.create(
            plan=self.plan, user_id=self.user_ids[0], amount=Decimal('10'), tp=StakingTransaction.TYPES.stake,
        ),
        with pytest.raises(errors.TooSoon):
            Plan.create_extend_out_transaction(self.plan.id)


class CreateExtendInTransactionTest(PlanTestDataMixin, TestCase):

    def setUp(self) -> None:
        plan_kwargs = self.get_plan_kwargs()
        plan_kwargs['extended_from_id'] = self.plan.id
        self.extension = Plan.objects.create(**plan_kwargs)
        self.transaction = self.plan.transactions.create(tp=PlanTransaction.TYPES.extend_out, amount=Decimal('51354'))

    def test_non_extendable_plan(self):
        self.plan.is_extendable = False
        self.plan.save()
        with pytest.raises(errors.NonExtendablePlan):
            Plan.create_extend_in_transaction(self.plan.id)

    def test_no_extension_plan(self):
        self.extension.delete()
        with pytest.raises(errors.AdminMistake):
            Plan.create_extend_in_transaction(self.plan.id)

    def test_no_extend_out_transaction(self):
        self.transaction.delete()
        with pytest.raises(errors.ParentIsNotCreated):
            Plan.create_extend_in_transaction(self.plan.id)

    def test_already_created(self):
        Plan.create_extend_in_transaction(self.plan.id)
        with pytest.raises(errors.AlreadyCreated):
            Plan.create_extend_in_transaction(self.plan.id)

    def test_success(self):
        assert not self.extension.transactions.filter(tp=PlanTransaction.TYPES.extend_in,).exists()
        assert not self.extension.transactions.filter(tp=PlanTransaction.TYPES.stake,).exists()
        Plan.create_extend_in_transaction(self.plan.id)
        assert self.extension.transactions.filter(tp=PlanTransaction.TYPES.extend_in,).exists()
        assert self.extension.transactions.get(tp=PlanTransaction.TYPES.extend_in,).amount == self.transaction.amount
        assert self.extension.transactions.filter(tp=PlanTransaction.TYPES.stake,).exists()
        assert self.extension.transactions.get(tp=PlanTransaction.TYPES.stake,).amount == self.transaction.amount

    def test_success_with_already_staked_assets(self):
        self.extension.transactions.create(tp=PlanTransaction.TYPES.stake, amount=Decimal('2513'),)
        assert not self.extension.transactions.filter(tp=PlanTransaction.TYPES.extend_in,).exists()
        Plan.create_extend_in_transaction(self.plan.id)
        assert self.extension.transactions.filter(tp=PlanTransaction.TYPES.extend_in,).exists()
        assert self.extension.transactions.get(tp=PlanTransaction.TYPES.extend_in,).amount == self.transaction.amount
        assert self.extension.transactions.filter(tp=PlanTransaction.TYPES.stake,).exists()
        assert self.extension.transactions.get(
            tp=PlanTransaction.TYPES.stake,
        ).amount == self.transaction.amount + Decimal('2513')


class CreateReleaseTransactionTests(PlanTestDataMixin, TestCase):

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.wallet = Wallet.get_user_wallet(995, cls.plan.currency,)
        cls.wallet.balance = Decimal('11')
        cls.wallet.save(update_fields=('balance',))
        cls.system_wallet = Wallet.get_user_wallet(cls.system_user.id, cls.currency)

    def setUp(self) -> None:
        self.plan.staked_at = ir_now() - timedelta(days=10)
        self.plan.staking_period = timedelta(days=8)
        self.plan.unstaking_period = timedelta(days=1.9)
        self.plan.save(update_fields=('staked_at', 'staking_period', 'unstaking_period',))
        self.plan.transactions.create(tp=PlanTransaction.TYPES.unstake, amount=Decimal('10'))
        self.wallet.balance = Decimal('11')
        self.wallet.save(update_fields=('balance',))
        self.system_wallet.balance = 1000
        self.system_wallet.save()

    def test_early_release(self):
        self.plan.unstaking_period = timedelta(days=2.1)
        self.plan.save(update_fields=('unstaking_period',))
        with pytest.raises(errors.TooSoon):
            Plan.create_release_transaction(self.plan.id)
        self.plan.refresh_from_db(fields=('released_capacity',))
        assert self.plan.released_capacity == Decimal('0')

    def test_re_releasing(self):
        Plan.create_release_transaction(self.plan.id)
        with pytest.raises(errors.AlreadyCreated):
            Plan.create_release_transaction(self.plan.id)
        assert self.plan.released_capacity == Decimal('0')

    def test_releasing_non_staked(self):
        self.plan.transactions.all().delete()
        with pytest.raises(errors.ParentIsNotCreated):
            Plan.create_release_transaction(self.plan.id)
        assert self.plan.released_capacity == Decimal('0')

    def test_system_user_low_balance(self):
        self.system_wallet.balance = 0
        self.system_wallet.save()
        with pytest.raises(errors.FailedAssetTransfer):
            Plan.create_release_transaction(self.plan.id)

    def test_a_successful_call(self):
        assert self.plan.transactions.filter(tp=PlanTransaction.TYPES.release).first() is None
        assert self.plan.released_capacity == Decimal('0')
        Plan.create_release_transaction(self.plan.id)
        self.plan.refresh_from_db(fields=('released_capacity',))
        assert self.plan.released_capacity == Decimal('10')
        assert self.plan.transactions.filter(tp=PlanTransaction.TYPES.release).first().amount == Decimal('10')


class PlanServiceQueriesTest(PlanTestDataMixin, TestCase):

    def test_get_plan_ids_to_stake(self):
        plans = []
        plan_kwargs = self.get_plan_kwargs()
        plans.append(Plan(**plan_kwargs))  # 0: A plan which its staked time is in the future
        plan_kwargs['staked_at'] = ir_now() - timedelta(.1)
        plans.append(Plan(**plan_kwargs))  # 1: A plan to stake
        plans.append(Plan(**plan_kwargs))  # 2: An already staked plan
        plans.append(Plan(**plan_kwargs))  # 3: A plan with no admin approval
        Plan.objects.bulk_create(plans)
        PlanTransaction.objects.bulk_create((PlanTransaction(
            plan=plans[1], tp=PlanTransaction.TYPES.system_stake_amount_approval,
        ), PlanTransaction(
            plan=plans[2], tp=PlanTransaction.TYPES.stake,
        ),))
        ids = list(Plan.get_plan_ids_to_stake())
        assert len(ids) == 1
        assert ids[0] == plans[1].id

    def test_get_plan_ids_to_assign_staking_to_users(self):
        plans = []
        plan_kwargs = self.get_plan_kwargs()
        plans.append(Plan(**plan_kwargs))  # 0: A plan with un-assigned staking
        plans.append(Plan(**plan_kwargs))  # 1: A plan with no un-assigned staking
        plans.append(Plan(**plan_kwargs))  # 2: A plan with no staking transaction.
        Plan.objects.bulk_create(plans)
        PlanTransaction.objects.bulk_create((PlanTransaction(
            plan=plans[0], tp=PlanTransaction.TYPES.stake, amount=Decimal('10'),
        ), PlanTransaction(
            plan=plans[1], tp=PlanTransaction.TYPES.stake, amount=Decimal('0'),
        ),))
        assert set(Plan.get_plan_ids_to_assign_staking_to_users()) == {plans[0].id}

    def test_get_plan_ids_to_end_its_user_staking(self):
        plans = []
        plan_kwargs = self.get_plan_kwargs()
        plans.append(Plan(**plan_kwargs))  # 0: A plan in staking period
        plan_kwargs['staked_at'] = ir_now() - timedelta(days=2)
        plans.append(Plan(**plan_kwargs))  # 1: A plan with user in staking state
        plans.append(Plan(**plan_kwargs))  # 2: A plan with user in unstake state
        plans.append(Plan(**plan_kwargs))  # 3: A plan with no user
        Plan.objects.bulk_create(plans)
        user_id = 201
        StakingTransaction.objects.create(
            user_id=user_id, plan=plans[0], tp=StakingTransaction.TYPES.stake, amount=Decimal('10'),
        )
        StakingTransaction.objects.create(
            user_id=user_id, plan=plans[1], tp=StakingTransaction.TYPES.stake, amount=Decimal('10'),
        )
        StakingTransaction.objects.create(
            user_id=user_id,
            plan=plans[2],
            tp=StakingTransaction.TYPES.unstake,
            amount=Decimal('10'),
            parent=StakingTransaction.objects.create(
                user_id=user_id, plan=plans[2], tp=StakingTransaction.TYPES.stake, amount=Decimal('10'),
            )
        )
        ids = list(Plan.get_plan_ids_to_end_its_user_staking())
        assert len(ids) == 1
        assert ids == [plans[i].id for i in (1,)]

    def test_get_plan_ids_to_release_its_user_assets(self):
        plans = []
        plan_kwargs = self.get_plan_kwargs()
        plan_kwargs['staked_at'] = ir_now() - timedelta(days=1.5)
        plans.append(Plan(**plan_kwargs))  # 0: A plan in unstaking period
        plan_kwargs['staked_at'] = ir_now() - timedelta(days=2.5)
        plans.append(Plan(**plan_kwargs))  # 1: A plan with user in unstaking state, but no release plan transaction
        plans.append(Plan(**plan_kwargs))  # 2: A plan with user in released assets
        plans.append(Plan(**plan_kwargs))  # 3: A plan with no user
        plans.append(Plan(**plan_kwargs))  # 4: A plan with user in unstaking state
        Plan.objects.bulk_create(plans)
        plans[1].transactions.create(tp=PlanTransaction.TYPES.release)

        user_id = 201
        StakingTransaction.objects.create(
            user_id=user_id, plan=plans[0], tp=StakingTransaction.TYPES.unstake, amount=Decimal('10'),
        )
        StakingTransaction.objects.create(
            user_id=user_id, plan=plans[1], tp=StakingTransaction.TYPES.unstake, amount=Decimal('10'),
        )
        StakingTransaction.objects.create(
            user_id=user_id,
            plan=plans[2],
            tp=StakingTransaction.TYPES.release,
            amount=Decimal('10'),
            parent=StakingTransaction.objects.create(
                user_id=user_id, plan=plans[2], tp=StakingTransaction.TYPES.unstake, amount=Decimal('10'),
            )
        )
        ids = list(Plan.get_plan_ids_to_release_its_user_assets())
        assert ids == [plans[i].id for i in (0, 1)]

    def test_get_plan_ids_to_fetch_rewards(self):
        Plan.objects.all().delete()
        plans = []
        plan_kwargs = self.get_plan_kwargs()

        plan_kwargs['staking_period'] = timedelta(days=3)
        plan_kwargs['reward_announcement_period'] = timedelta(days=.4)
        plan_kwargs['staked_at'] = ir_now() + timedelta(days=.5)
        plans.append(Plan(**plan_kwargs))  # 0: A plan in operation period
        plan_kwargs['staked_at'] = ir_now() - timedelta(days=.5)
        plans.append(Plan(**plan_kwargs))  # 1: A plan with no fetched reward
        plans.append(Plan(**plan_kwargs))  # 2: A plan with no recent fetched reward
        plans.append(Plan(**plan_kwargs))  # 3: A plan with a recent fetched reward
        plans.append(Plan(**plan_kwargs))  # 4: A plan with both recent and non recent fetched rewards
        plan_kwargs['staked_at'] = ir_now() - timedelta(days=3.1)
        plans.append(Plan(**plan_kwargs))  # 5: A plan after its staking period
        plan_kwargs['staked_at'] = ir_now() - timedelta(days=3.5)
        plans.append(Plan(**plan_kwargs))  # 6: A plan enough time has passed after its staking period
        Plan.objects.bulk_create(plans)
        PlanTransaction.objects.bulk_create((PlanTransaction(
            plan=plans[2], tp=PlanTransaction.TYPES.fetched_reward, created_at=ir_now() - timedelta(hours=1.1),
        ), PlanTransaction(
            plan=plans[3], tp=PlanTransaction.TYPES.fetched_reward, created_at=ir_now() - timedelta(hours=0.9),
        ), PlanTransaction(
            plan=plans[4], tp=PlanTransaction.TYPES.fetched_reward, created_at=ir_now() - timedelta(hours=1.1),
        ), PlanTransaction(
            plan=plans[4], tp=PlanTransaction.TYPES.fetched_reward, created_at=ir_now() - timedelta(hours=0.9),
        ),),)
        assert set(Plan.get_plan_ids_to_fetch_rewards()) == {plans[i].id for i in (1, 2, 5,)}

    def test_get_plan_ids_to_announce_rewards(self):
        Plan.objects.all().delete()
        plans = []
        plan_kwargs = self.get_plan_kwargs()

        plan_kwargs['staking_period'] = timedelta(days=3)
        plan_kwargs['reward_announcement_period'] = timedelta(days=1)
        plan_kwargs['staked_at'] = ir_now() + timedelta(days=.5)
        plans.append(Plan(**plan_kwargs))  # 0: A plan in operation period
        plan_kwargs['staked_at'] = ir_now() - timedelta(days=1.5)
        plans.append(Plan(**plan_kwargs))  # 1: A plan with no announced reward
        plans.append(Plan(**plan_kwargs))  # 2: A plan with no recent announced reward
        plans.append(Plan(**plan_kwargs))  # 3: A plan with a recent announced reward
        plans.append(Plan(**plan_kwargs))  # 4: A plan with both recent and non recent announced rewards
        Plan.objects.bulk_create(plans)
        PlanTransaction.objects.bulk_create((PlanTransaction(
            plan=plans[2], tp=PlanTransaction.TYPES.announce_reward, created_at=ir_now() - timedelta(days=1.1),
        ), PlanTransaction(
            plan=plans[3], tp=PlanTransaction.TYPES.announce_reward, created_at=ir_now() - timedelta(days=0.9),
        ), PlanTransaction(
            plan=plans[4], tp=PlanTransaction.TYPES.announce_reward, created_at=ir_now() - timedelta(days=1.1),
        ), PlanTransaction(
            plan=plans[4], tp=PlanTransaction.TYPES.announce_reward, created_at=ir_now() - timedelta(days=0.9),
        ),),)
        assert set(Plan.get_plan_ids_to_announce_rewards()) == {plans[i].id for i in (1, 2,)}

    def test_get_plan_ids_to_pay_rewards(self):
        Plan.objects.all().delete()
        plans = []
        plan_kwargs = self.get_plan_kwargs()

        plans.append(Plan(**plan_kwargs))  # 0: A plan with not withdrawn reward
        plans.append(Plan(**plan_kwargs))  # 1: A plan with paid rewards
        plans.append(Plan(**plan_kwargs))  # 2: A plan to pay reward
        Plan.objects.bulk_create(plans)
        PlanTransaction.objects.bulk_create((PlanTransaction(
            plan=plans[2], tp=PlanTransaction.TYPES.give_reward, amount=Decimal('10'),
        ), PlanTransaction(
            plan=plans[1], tp=PlanTransaction.TYPES.give_reward, amount=Decimal('0'),
        ),),)
        assert set(Plan.get_plan_ids_to_pay_rewards()) == {plans[2].id}

    def test_get_plan_ids_to_approve_stake_amount(self):
        Plan.objects.all().delete()
        plans = []
        plan_kwargs = self.get_plan_kwargs()
        plan_kwargs['opened_at'] = ir_now() - 0.9 * plan_kwargs['request_period']
        plans.append(Plan(**plan_kwargs))  # 0: A plan which is in its request period
        plan_kwargs['opened_at'] = ir_now() - 1.1 * plan_kwargs['request_period']
        plans.append(Plan(**plan_kwargs))  # 1: A Plan to approve
        plans.append(Plan(**plan_kwargs))  # 2: Already approved plan
        Plan.objects.bulk_create(plans)
        PlanTransaction.objects.create(
            plan=plans[2], tp=PlanTransaction.TYPES.system_stake_amount_approval,
        )
        assert list(Plan.get_plan_ids_to_approve_stake_amount()) == [plans[1].id]

    def test_get_plan_ids_to_extend_staking(self):
        Plan.objects.all().delete()
        plans = []
        plan_kwargs = self.get_plan_kwargs()
        plans.append(Plan(**plan_kwargs))  # 0: A Plan to extend
        plan_kwargs['is_extendable'] = False
        plans.append(Plan(**plan_kwargs))  # 1: A non extendable Plan
        plan_kwargs['is_extendable'] = True
        plans.append(Plan(**plan_kwargs))  # 2: A plan that its end method hasn't been call yet
        plans.append(Plan(**plan_kwargs))  # 3: Already extended
        Plan.objects.bulk_create(plans)
        transactions = PlanTransaction.objects.bulk_create((PlanTransaction(
            plan=plans[0], tp=PlanTransaction.TYPES.extend_out,
        ), PlanTransaction(
            plan=plans[1], tp=PlanTransaction.TYPES.extend_out,
        ), PlanTransaction(
            plan=plans[3], tp=PlanTransaction.TYPES.extend_out,
        ),),)
        PlanTransaction.objects.create(
            plan=Plan.objects.create(**plan_kwargs),
            tp=PlanTransaction.TYPES.extend_in,
            parent_id=transactions[-1].id,
        )
        assert list(Plan.get_plan_ids_to_extend_staking()) == [plans[0].id]

    def test_get_plan_ids_create_extend_out_transaction(self):
        Plan.objects.all().delete()
        plans = []
        plan_kwargs = self.get_plan_kwargs()
        plan_kwargs['staked_at'] -= plan_kwargs['staking_period']
        plans.append(Plan(**plan_kwargs))  # 0: A Plan to end staking
        plan_kwargs['staked_at'] += plan_kwargs['staking_period']
        plans.append(Plan(**plan_kwargs))  # 1: A In its staking period
        plan_kwargs['staked_at'] -= plan_kwargs['staking_period']
        plans.append(Plan(**plan_kwargs))  # 2: Already ended
        Plan.objects.bulk_create(plans)
        transactions = PlanTransaction.objects.bulk_create((PlanTransaction(
            plan=plans[0], tp=PlanTransaction.TYPES.stake,
        ), PlanTransaction(
            plan=plans[1], tp=PlanTransaction.TYPES.stake,
        ), PlanTransaction(
            plan=plans[2], tp=PlanTransaction.TYPES.stake,
        ),),)
        PlanTransaction.objects.create(
            plan=Plan.objects.create(**plan_kwargs),
            tp=PlanTransaction.TYPES.extend_out,
            parent_id=transactions[-1].id,
        )
        assert list(Plan.get_plan_ids_create_extend_out_transaction()) == [plans[0].id]

    def test_get_plan_ids_to_extend_users_assets(self):
        Plan.objects.all().delete()
        plans = []
        plan_kwargs = self.get_plan_kwargs()
        plan_kwargs['staked_at'] -= plan_kwargs['staking_period']
        plans.append(Plan(**plan_kwargs))  # 0: A Plan to end staking
        plan_kwargs['staked_at'] += plan_kwargs['staking_period']
        plans.append(Plan(**plan_kwargs))  # 1: A In its staking period
        plan_kwargs['staked_at'] -= plan_kwargs['staking_period']
        plans.append(Plan(**plan_kwargs))  # 2: Already ended
        Plan.objects.bulk_create(plans)
        transactions = PlanTransaction.objects.bulk_create((PlanTransaction(
            plan=plans[0], tp=PlanTransaction.TYPES.stake,
        ), PlanTransaction(
            plan=plans[1], tp=PlanTransaction.TYPES.stake,
        ), PlanTransaction(
            plan=plans[2], tp=PlanTransaction.TYPES.stake,
        ),),)
        PlanTransaction.objects.create(
            plan=Plan.objects.create(**plan_kwargs),
            tp=PlanTransaction.TYPES.extend_out,
            parent_id=transactions[-1].id,
        )
        assert list(Plan.get_plan_ids_create_extend_out_transaction()) == [plans[0].id]

    def test_get_plan_user_ids(self):
        plan_kwargs = self.get_plan_kwargs()
        plan_id = Plan.objects.create(**plan_kwargs).id
        StakingTransaction.objects.bulk_create((StakingTransaction(
            user_id=self.user_ids[0], plan_id=plan_id, tp=StakingTransaction.TYPES.create_request,
        ), StakingTransaction(
            user_id=self.user_ids[0], plan_id=plan_id, tp=StakingTransaction.TYPES.cancel_create_request,
        ), StakingTransaction(
            user_id=self.user_ids[1], plan_id=plan_id, tp=StakingTransaction.TYPES.create_request,
        ),))
        assert set(Plan.get_plan_user_ids(plan_id)) == {self.user_ids[0], self.user_ids[1]}

    def test_get_user_ids_to_extend(self):
        plan_kwargs = self.get_plan_kwargs()
        plan_id = Plan.objects.create(**plan_kwargs).id

        extendable_user_plans = [
            StakingTransaction(
                user_id=self.user_ids[0],
                plan_id=plan_id,
                tp=StakingTransaction.TYPES.extend_out,
            ),
            StakingTransaction(
                user_id=self.user_ids[3],
                plan_id=plan_id,
                tp=StakingTransaction.TYPES.extend_out,
            ),
        ]
        none_extendable_user_plans = [
            StakingTransaction(
                user_id=self.user_ids[1],
                plan_id=plan_id,
                tp=StakingTransaction.TYPES.stake,
                parent=StakingTransaction.objects.create(
                    user_id=self.user_ids[1],
                    plan_id=plan_id,
                    tp=StakingTransaction.TYPES.extend_out,
                ),
            ),
            StakingTransaction(
                user_id=self.user_ids[2],
                plan_id=Plan.objects.create(**plan_kwargs).id,
                tp=StakingTransaction.TYPES.extend_out,
            ),
        ]

        StakingTransaction.objects.bulk_create(extendable_user_plans + none_extendable_user_plans)
        assert list(Plan.get_user_ids_to_extend(plan_id)) == [self.user_ids[0], self.user_ids[3]]

    def test_get_plan_user_ids_of_users_with_staked_assets(self):
        plan_kwargs = self.get_plan_kwargs()
        plan_id = Plan.objects.create(**plan_kwargs).id
        StakingTransaction.objects.bulk_create((StakingTransaction(
            user_id=self.user_ids[0], plan_id=plan_id, tp=StakingTransaction.TYPES.stake,
        ), StakingTransaction(
            user_id=self.user_ids[1],
            plan_id=plan_id,
            tp=StakingTransaction.TYPES.unstake,
            parent=StakingTransaction.objects.create(
                user_id=self.user_ids[1], plan_id=plan_id, tp=StakingTransaction.TYPES.stake,
            ),
        ), StakingTransaction(
            user_id=self.user_ids[2], plan_id=Plan.objects.create(**plan_kwargs).id, tp=StakingTransaction.TYPES.stake,
        ),))
        assert set(Plan.get_plan_user_ids_of_users_with_staked_assets(plan_id)) == {self.user_ids[0]}

    def test_get_plan_user_ids_of_users_with_unreleased_assets(self):
        plan_kwargs = self.get_plan_kwargs()
        plan_id = Plan.objects.create(**plan_kwargs).id
        StakingTransaction.objects.bulk_create((StakingTransaction(
            user_id=self.user_ids[0], plan_id=plan_id, tp=StakingTransaction.TYPES.unstake,
        ), StakingTransaction(
            user_id=self.user_ids[1],
            plan_id=plan_id,
            tp=StakingTransaction.TYPES.release,
            parent=StakingTransaction.objects.create(
                user_id=self.user_ids[1], plan_id=plan_id, tp=StakingTransaction.TYPES.unstake,
            ),
        ), StakingTransaction(user_id=self.user_ids[2], plan_id=Plan.objects.create(
            **plan_kwargs
        ).id, tp=StakingTransaction.TYPES.unstake,),))
        assert set(Plan.get_plan_user_ids_of_users_with_unreleased_assets(plan_id)) == {self.user_ids[0]}

    def test_get_plan_user_ids_to_pay_reward(self):
        plan_kwargs = self.get_plan_kwargs()
        plan_id = Plan.objects.create(**plan_kwargs).id
        StakingTransaction.objects.bulk_create((StakingTransaction(
            user_id=self.user_ids[0], plan_id=plan_id, tp=StakingTransaction.TYPES.stake, amount=Decimal('1'),
        ), StakingTransaction(
            user_id=self.user_ids[1], plan_id=plan_id, tp=StakingTransaction.TYPES.stake, amount=Decimal('0'),
        ), StakingTransaction(
            user_id=self.user_ids[2], plan_id=plan_id, tp=StakingTransaction.TYPES.stake, amount=Decimal('1'),
        ), StakingTransaction(
            user_id=self.user_ids[2], plan_id=plan_id, tp=StakingTransaction.TYPES.give_reward,
        ), ))
        assert set(Plan.get_plan_user_ids_to_pay_reward(plan_id)) == {self.user_ids[0]}

    def test_get_plan_ids_to_create_release_transaction(self):
        Plan.objects.all().delete()
        plans = []
        plan_kwargs = self.get_plan_kwargs()

        plan_kwargs['staking_period'] = timedelta(days=3)
        plan_kwargs['unstaking_period'] = timedelta(days=3)
        plan_kwargs['staked_at'] = ir_now() - timedelta(days=2)
        plans.append(Plan(**plan_kwargs))  # 0: A plan in staking period
        plan_kwargs['staked_at'] = ir_now() - timedelta(days=4)
        plans.append(Plan(**plan_kwargs))  # 1: A plan in unstaking period
        plan_kwargs['staked_at'] = ir_now() - timedelta(days=7)
        plans.append(Plan(**plan_kwargs))  # 2: A plan in to release
        plans.append(Plan(**plan_kwargs))  # 3: A plan with no unstake transaction
        plans.append(Plan(**plan_kwargs))  # 4: An already released planassed after its staking period
        Plan.objects.bulk_create(plans)
        PlanTransaction.objects.bulk_create((PlanTransaction(
            plan=plans[2], tp=PlanTransaction.TYPES.unstake,
        ), PlanTransaction(plan=plans[4], tp=PlanTransaction.TYPES.release, parent=PlanTransaction.objects.create(
                plan=plans[4], tp=PlanTransaction.TYPES.unstake,
        ),),),)
        assert set(Plan.get_plan_ids_to_create_release_transaction()) == {plans[2].id}

    def test_get_open_plan_ids(self):
        Plan.objects.all().delete()
        plans = []
        plan_kwargs = self.get_plan_kwargs()

        plan_kwargs['staking_period'] = timedelta(days=3)
        plan_kwargs['unstaking_period'] = timedelta(days=3)
        plan_kwargs['staked_at'] = ir_now() - timedelta(days=2)
        plans.append(Plan(**plan_kwargs))  # 0: A plan in staking period
        plan_kwargs['staked_at'] = ir_now() - timedelta(days=4)
        plans.append(Plan(**plan_kwargs))  # 1: A plan in unstaking period
        plan_kwargs['staked_at'] = ir_now() - timedelta(days=7)
        plans.append(Plan(**plan_kwargs))  # 2: A plan in to release
        plans.append(Plan(**plan_kwargs))  # 3: A plan with no unstake transaction
        plans.append(Plan(**plan_kwargs))  # 4: An already released planassed after its staking period
        Plan.objects.bulk_create(plans)
        PlanTransaction.objects.bulk_create((PlanTransaction(
            plan=plans[2], tp=PlanTransaction.TYPES.unstake,
        ), PlanTransaction(plan=plans[4], tp=PlanTransaction.TYPES.release, parent=PlanTransaction.objects.create(
                plan=plans[4], tp=PlanTransaction.TYPES.unstake,
        ),),),)
        assert set(Plan.get_plan_ids_to_create_release_transaction()) == {plans[2].id}

    def test_get_user_ids_to_apply_instant_end_requests(self):
        plan_kwargs = self.get_plan_kwargs()
        plan_id = Plan.objects.create(**plan_kwargs).id
        StakingTransaction.objects.bulk_create(
            [
                StakingTransaction(
                    user_id=self.user_ids[0],
                    plan_id=plan_id,
                    tp=StakingTransaction.TYPES.instant_end_request,
                ),
                StakingTransaction(
                    user_id=self.user_ids[1],
                    plan_id=plan_id,
                    tp=StakingTransaction.TYPES.unstake,
                    parent=StakingTransaction.objects.create(
                        user_id=self.user_ids[1],
                        plan_id=plan_id,
                        tp=StakingTransaction.TYPES.instant_end_request,
                    ),
                ),
                StakingTransaction(
                    user_id=self.user_ids[2],
                    plan_id=Plan.objects.create(**plan_kwargs).id,
                    tp=StakingTransaction.TYPES.instant_end_request,
                ),
            ]
        )
        assert set(Plan.get_user_ids_to_apply_instant_end_requests(plan_id)) == {self.user_ids[0]}
