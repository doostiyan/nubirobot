"""Staking Test Helpers """
import random
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, Union

import pytz

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.crypto import random_string
from exchange.base.models import Currencies
from exchange.staking.models import ExternalEarningPlatform, Plan, PlanTransaction, StakingTransaction
from exchange.wallet.models import Transaction, Wallet


class ExternalEarningPlatformTestDataMixin:  # pylint: disable=too-few-public-methods
    @classmethod
    def setUpTestData(cls) -> None:  # pylint: disable=invalid-name
        cls.currency = Currencies.btc
        cls.external_platform = cls.add_external_platform(cls.currency, ExternalEarningPlatform.TYPES.staking)

    @staticmethod
    def add_external_platform(currency: int, tp: int):
        return ExternalEarningPlatform.objects.create(
            tp=tp,
            currency=currency,
            network='network',
            address='address',
            tag='tag',
        )

    @classmethod
    def charge_wallet(cls, user: User, currency: int, amount: Decimal, tp=Wallet.WALLET_TYPE.spot) -> Wallet:
        wallet = Wallet.get_user_wallet(user, currency, tp=tp)
        wallet.create_transaction(tp='manual', amount=amount).commit()
        wallet.refresh_from_db()
        return wallet

    @classmethod
    def create_user(cls, is_active=True, **kwargs) -> User:
        username = 'staking_user_' + random_string(12)
        user = User.objects.create(
            username=username,
            email=username + '@gmail.com',
            first_name='staking_user',
            birthday=datetime(year=1990, month=11, day=15),
            gender=User.GENDER.female,
            city='Tehran',
            requires_2fa=True,
            is_active=is_active,
            mobile=str(9980000001 + random.randrange(1, 10 ** 6)),
            **kwargs,
        )
        return user



class PlanArgsMixin(ExternalEarningPlatformTestDataMixin):

    @classmethod
    def get_plan_kwargs(cls, external_platform: Optional[ExternalEarningPlatform] = None):
        nw = ir_now()
        a_day = timedelta(days=1)
        external_platform = external_platform or cls.external_platform
        return dict(
            external_platform=external_platform,
            total_capacity=Decimal('100'),
            filled_capacity=Decimal('90'),
            announced_at=nw,
            opened_at=nw,
            request_period=a_day,
            staked_at=nw,
            staking_period=a_day,
            unstaking_period=a_day,
            fee=Decimal('0.2'),
            estimated_annual_rate=Decimal('.44'),
            initial_pool_capacity=Decimal('100'),
            is_extendable=True,
            reward_announcement_period=a_day,
            min_staking_amount=Decimal('5'),
            staking_precision=Decimal('0.1'),
        )


class PlanTestDataMixin(PlanArgsMixin):
    plan: Plan

    @classmethod
    def setUpTestData(cls) -> None:
        PlanArgsMixin.setUpTestData()
        cls.plan = cls.create_plan(**cls.get_plan_kwargs())
        cls.user_ids = (201, 202, 203, 205)
        cls.user = User.objects.get(pk=201)
        cls.system_user = User.objects.create_user(
            username='system-staking',
            pk=995,
        )
        User.objects.create_user(
            username='system-staking-rewards',
            pk=993,
        )
        cls.wallet = Wallet.get_user_wallet(cls.user, cls.currency)

    @classmethod
    def create_plan(cls, **kwargs) -> Plan:
        return Plan.objects.create(**kwargs)

    @classmethod
    def create_plan_transaction(
        cls,
        tp: int,
        plan: Plan = None,
        parent_transaction: Optional[PlanTransaction] = None,
        amount: Optional[Decimal] = Decimal('0.0'),
        wallet_transaction: Optional[Transaction] = None,
        **kwargs,
    ) -> PlanTransaction:
        plan = plan or cls.plan

        plan_transaction = PlanTransaction.objects.create(
            plan=plan, tp=tp, parent=parent_transaction, amount=amount, wallet_transaction=wallet_transaction, **kwargs
        )
        return plan_transaction


class StakingTestDataMixin(PlanTestDataMixin):

    @classmethod
    def setUpTestData(cls) -> None:
        PlanTestDataMixin.setUpTestData()

    @classmethod
    def create_staking_transaction(
        cls,
        tp: int,
        amount: Decimal,
        parent: Optional[StakingTransaction] = None,
        user: Optional[User] = None,
        plan: Optional[Plan] = None,
        plan_transaction: Optional[PlanTransaction] = None,
        **kwargs,
    ) -> StakingTransaction:
        user = user or cls.user
        plan = plan or cls.plan
        cls.staking = StakingTransaction.objects.create(
            user=user,
            plan=plan,
            tp=tp,
            parent=parent,
            amount=amount,
            plan_transaction=plan_transaction,
            **kwargs,
        )
        return cls.staking

    @classmethod
    def to_utc_timezone(cls, value: Union[datetime, date]):
        return value.astimezone(pytz.timezone('UTC'))

    @classmethod
    def create_user(cls, is_active=True, **kwargs) -> User:
        username = random_string(12)
        user = User.objects.create(
            username=username,
            email=username + '@gmail.com',
            first_name='first_name',
            birthday=datetime(year=1993, month=11, day=15),
            gender=User.GENDER.female,
            city='Tehran',
            requires_2fa=True,
            is_active=is_active,
            mobile=str(9980000001 + random.randrange(1, 10 ** 6)),
            **kwargs,
        )
        return user
