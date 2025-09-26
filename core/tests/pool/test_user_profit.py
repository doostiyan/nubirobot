import datetime
from datetime import timedelta
from decimal import Decimal
from random import randrange
from unittest.mock import MagicMock, PropertyMock, patch

import jdatetime
import pytest
from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.constants import SYSTEM_USER_IDS
from exchange.accounts.models import Notification, User
from exchange.base.calendar import as_ir_tz, ir_now, ir_tz
from exchange.base.crypto import random_string
from exchange.base.models import RIAL, TETHER, Currencies
from exchange.margin.models import Position
from exchange.pool.crons import DistributeUsersProfitCron
from exchange.pool.errors import NullAmountUDPExists
from exchange.pool.functions import (
    calculate_user_score,
    distribute_user_profit_on_target_pools,
    effective_days,
    populate_users_delegation_score_on_target_pools,
    populate_users_profit_on_target_pools,
)
from exchange.pool.models import DelegationTransaction, LiquidityPool, PoolProfit, UserDelegation, UserDelegationProfit
from exchange.wallet.constants import TRANSACTION_MAX
from exchange.wallet.models import Wallet
from tests.base.utils import mock_on_commit


class TestUserProfit(TestCase):
    def setUp(self):
        self.user1 = User.objects.get(pk=201)
        self.pool = LiquidityPool.objects.create(
            currency=Currencies.btc,
            capacity=10000,
            manager_id=410,
            is_active=True,
        )
        self.wallet1 = Wallet.get_user_wallet(self.user1.id, Currencies.btc)
        self.initial_balance = 10
        self.wallet1.create_transaction('manual', self.initial_balance).commit()
        self.wallet1.refresh_from_db()
        self.user_delegation = UserDelegation.objects.create(
            pool=self.pool,
            user=self.user1,
            balance=Decimal(0),
            closed_at=None,
        )
        self.user_delegation.created_at = ir_now() - timedelta(days=100)
        self.user_delegation.save()

        self.user_delegation.pool.src_wallet.create_transaction('manual', self.initial_balance).commit()
        self.from_date = ir_now() - timedelta(days=10)
        self.to_date = ir_now()

        self.profit_wallet = Wallet.get_user_wallet(SYSTEM_USER_IDS.system_pool_profit, Currencies.rls)

    def create_delegation_tx(self, amount: Decimal, created_at=None, user_delegation=None):
        return DelegationTransaction.objects.create(
            amount=amount,
            created_at=created_at or ir_now(),
            user_delegation=user_delegation or self.user_delegation,
        )

    def test_calculate_user_score_simple1(self):
        #  amount
        #   ^
        #   |
        # 1.23   +-------
        #   |    |xxxxxxx
        #   |    |xxxxxxx
        #   +----+--days->
        #        4       10

        amount = Decimal('1.23')
        self.user_delegation.created_at = self.from_date + timedelta(days=4)
        self.user_delegation.save()

        assert calculate_user_score(self.user_delegation, self.from_date.date(), self.to_date.date()) == 0

        self.create_delegation_tx(amount, created_at=self.from_date + timedelta(days=4))
        assert calculate_user_score(
            self.user_delegation, self.from_date.date(), self.to_date.date()
        ) == amount * effective_days(7)

    def test_calculate_user_score_simple2(self):
        #  amount
        #    ^
        #    |
        # 1.2 -------+
        #    |xxxxxxx|
        #    +--days-+--->
        #            6

        amount = Decimal('1.23')
        self.user_delegation.created_at = self.from_date - timedelta(days=11)
        self.user_delegation.save()

        self.create_delegation_tx(amount, created_at=self.from_date - timedelta(days=11))
        self.create_delegation_tx(-amount, created_at=self.from_date + timedelta(days=6))
        assert calculate_user_score(self.user_delegation, self.from_date.date(), self.to_date.date()) == 0

    def test_calculate_user_score_simple3(self):
        #    amount
        #      ^
        #      |
        # 1.23 +-----------
        #      |xxxxxxxxxxx
        #      +---days---->
        #                 10

        amount = Decimal('1.23')

        self.create_delegation_tx(amount, created_at=self.from_date - timedelta(days=11))
        self.user_delegation.created_at = self.from_date - timedelta(days=11)
        self.user_delegation.save()
        assert calculate_user_score(
            self.user_delegation, self.from_date.date(), self.to_date.date()
        ) == amount * effective_days(11)

    def test_calculate_user_score_complex1(self):
        #    amount
        #      ^
        # 2    |     +-----
        #      |     |xxxxx
        # 1.23 | +---+- - -
        #      | |yyyyyyyyy
        #      +-+----------> days
        #        2   5    10

        amount1 = Decimal('1.23')
        amount2 = Decimal('0.77')
        self.user_delegation.created_at = self.from_date + timedelta(days=2)
        self.user_delegation.save()
        self.create_delegation_tx(amount1, created_at=self.from_date + timedelta(days=2))
        self.create_delegation_tx(amount2, created_at=self.from_date + timedelta(days=5))
        assert calculate_user_score(self.user_delegation, self.from_date.date(), self.to_date.date()) == sum(
            [
                amount1 * effective_days(9),
                amount2 * effective_days(6),
            ]
        )

    def test_calculate_user_score_complex2(self):
        #     amount
        #       ^
        #       |
        # 2     |    +---------
        #       |    |yyyyyyyyy
        # 1.23  +----+- - - - -
        #       |xxxxxxxxxxxxxx
        #       +-------------> days
        #            3       10

        amount1 = Decimal('1.23')
        amount2 = Decimal('0.77')

        self.user_delegation.created_at = self.from_date - timedelta(days=1)
        self.user_delegation.save()

        self.create_delegation_tx(amount1, created_at=self.from_date - timedelta(days=1))
        self.create_delegation_tx(amount2, created_at=self.from_date + timedelta(days=3))
        assert calculate_user_score(self.user_delegation, self.from_date.date(), self.to_date.date()) == sum(
            [
                amount1 * effective_days(11),
                amount2 * effective_days(8),
            ]
        )

    def test_calculate_user_score_complex3(self):
        #    amount
        #      ^
        #      |
        # 2    | +-----+
        #      | |     |
        # 1.23 | | - - +-----
        #      | |xxxxxxxxxxx
        #      +-+----------> days
        #        1     5    10

        amount1 = Decimal('2')
        amount2 = Decimal('-0.77')

        self.user_delegation.created_at = self.from_date + timedelta(days=1)
        self.user_delegation.save()

        self.create_delegation_tx(amount1, created_at=self.from_date + timedelta(days=1))
        self.create_delegation_tx(amount2, created_at=self.from_date + timedelta(days=5))
        assert calculate_user_score(self.user_delegation, self.from_date.date(), self.to_date.date()) == Decimal(
            '1.23'
        ) * effective_days(10)

    def test_calculate_user_score_complex4(self):
        #    amount
        #      ^
        #      |
        # 2    +---+
        # 1.23 |- -+---------
        #      |xxxxxxxxxxxxx
        #      +-------------> days
        #          3        10

        amount1 = Decimal('2')
        amount2 = Decimal('-0.77')

        self.user_delegation.created_at = self.from_date - timedelta(days=1)
        self.user_delegation.save()

        self.create_delegation_tx(amount1, created_at=self.from_date - timedelta(days=1))
        self.create_delegation_tx(amount2, created_at=self.from_date + timedelta(days=5))
        assert calculate_user_score(self.user_delegation, self.from_date.date(), self.to_date.date()) == Decimal(
            '1.23'
        ) * effective_days(11)

    def test_calculate_user_score_complex5(self):
        #    amount
        #      ^
        # 3    +---+
        # 2    |   +--+
        # 1.23 | - -  +-----
        #      |xxxxxxxxxxxx
        #      +------------> days
        #          3  5    10

        amount1 = Decimal('3')
        amount2 = Decimal('-1')
        amount3 = Decimal('-0.77')

        self.user_delegation.created_at = self.from_date - timedelta(days=1)
        self.user_delegation.save()

        self.create_delegation_tx(amount1, created_at=self.from_date - timedelta(days=1))
        self.create_delegation_tx(amount2, created_at=self.from_date + timedelta(days=3))
        self.create_delegation_tx(amount3, created_at=self.from_date + timedelta(days=5))
        assert calculate_user_score(self.user_delegation, self.from_date.date(), self.to_date.date()) == Decimal(
            '1.23'
        ) * effective_days(11)

    def test_calculate_user_score_complex6(self):
        #    amount
        #      ^
        # 3    | +-+
        # 2    | | +--+
        # 1.23 | |- - +-----
        #      | |xxxxxxxxxx
        #      +-+----------> days
        #        2 3  5    10

        amount1 = Decimal('3')
        amount2 = Decimal('-1')
        amount3 = Decimal('-0.77')

        self.user_delegation.created_at = self.from_date + timedelta(days=2)
        self.user_delegation.save()

        self.create_delegation_tx(amount1, created_at=self.from_date + timedelta(days=2))
        self.create_delegation_tx(amount2, created_at=self.from_date + timedelta(days=3))
        self.create_delegation_tx(amount3, created_at=self.from_date + timedelta(days=5))
        assert calculate_user_score(self.user_delegation, self.from_date.date(), self.to_date.date()) == Decimal(
            '1.23'
        ) * effective_days(9)

    def test_calculate_user_score_complex7(self):
        #    amount
        #       ^
        # 3     |        +--------
        #       |        |xxxxxxxx
        # 2     |   +----+--------
        #       |   |yyyyyyyyyyyyy
        # 1.23  +---+-------------
        #       |zzzzzzzzzzzzzzzzz
        #       +---------------->  days
        #           3    6      10

        amount1 = Decimal('1.23')
        amount2 = Decimal('0.77')
        amount3 = Decimal('1')

        self.user_delegation.created_at = self.from_date - timedelta(days=1)
        self.user_delegation.save()

        self.create_delegation_tx(amount1, created_at=self.from_date - timedelta(days=1))
        self.create_delegation_tx(amount2, created_at=self.from_date + timedelta(days=3))
        self.create_delegation_tx(amount3, created_at=self.from_date + timedelta(days=6))
        assert calculate_user_score(self.user_delegation, self.from_date.date(), self.to_date.date()) == sum(
            [
                Decimal('1.23') * effective_days(11),
                Decimal('0.77') * effective_days(8),
                Decimal('1') * effective_days(5),
            ]
        )

    def test_calculate_user_score_complex8(self):
        #    amount
        #       ^
        # 3     |        +--------
        #       |        |xxxxxxxx
        # 2     |   +----+--------
        #       |   |yyyyyyyyyyyyy
        # 1.23  | +-+-------------
        #       | |zzzzzzzzzzzzzzz
        #       +-+-------------->  days
        #         2 3    6      10

        amount1 = Decimal('1.23')
        amount2 = Decimal('0.77')
        amount3 = Decimal('1')

        self.user_delegation.created_at = self.from_date + timedelta(days=2)
        self.user_delegation.save()

        self.create_delegation_tx(amount1, created_at=self.from_date + timedelta(days=2))
        self.create_delegation_tx(amount2, created_at=self.from_date + timedelta(days=3))
        self.create_delegation_tx(amount3, created_at=self.from_date + timedelta(days=6))
        assert calculate_user_score(self.user_delegation, self.from_date.date(), self.to_date.date()) == sum(
            [
                Decimal('1.23') * effective_days(9),
                Decimal('0.77') * effective_days(8),
                Decimal('1') * effective_days(5),
            ]
        )

    def test_calculate_user_score_complex9(self):
        #      ^
        # 3    |   +----+
        #      |   |    |
        # 2    |   |----+-------
        #      |   |xxxxxxxxxxxx
        # 1.23 +---+------------
        #      |yyyyyyyyyyyyyyyy
        #      +--------------->
        #          3    6

        amount1 = Decimal('1.23')
        amount2 = Decimal('1.77')
        amount3 = Decimal('-1')

        self.user_delegation.created_at = self.from_date - timedelta(days=1)
        self.user_delegation.save()

        self.create_delegation_tx(amount1, created_at=self.from_date - timedelta(days=1))
        self.create_delegation_tx(amount2, created_at=self.from_date + timedelta(days=3))
        self.create_delegation_tx(amount3, created_at=self.from_date + timedelta(days=6))
        assert calculate_user_score(self.user_delegation, self.from_date.date(), self.to_date.date()) == sum(
            [
                Decimal('0.77') * effective_days(8),
                Decimal('1.23') * effective_days(11),
            ]
        )

    def test_calculate_user_score_complex10(self):
        #      ^
        # 3    |   +----+
        #      |   |    |
        # 2    |   |----+-------
        #      |   |xxxxxxxxxxxx
        # 1.23 | +-+------------
        #      | |yyyyyyyyyyyyyy
        #      +-+------------->
        #        2 3    6

        amount1 = Decimal('1.23')
        amount2 = Decimal('1.77')
        amount3 = Decimal('-1')

        self.user_delegation.created_at = self.from_date + timedelta(days=2)
        self.user_delegation.save()

        self.create_delegation_tx(amount1, created_at=self.from_date + timedelta(days=2))
        self.create_delegation_tx(amount2, created_at=self.from_date + timedelta(days=3))
        self.create_delegation_tx(amount3, created_at=self.from_date + timedelta(days=6))
        assert calculate_user_score(self.user_delegation, self.from_date.date(), self.to_date.date()) == sum(
            [
                Decimal('0.77') * effective_days(8),
                Decimal('1.23') * effective_days(9),
            ]
        )

    def test_calculate_user_score_complex11(self):
        #      ^
        #      |
        # 3    +---+
        #      |   |
        # 2    |   |     +-----------
        #      |   |     |xxxxxxxxxxx
        # 1.23 |---+-----+-----------
        #      |yyyyyyyyyyyyyyyyyyyyy
        #      +-------------------->
        #          2     6          10

        amount1 = Decimal('3')
        amount2 = Decimal('-1.77')
        amount3 = Decimal('0.77')

        self.user_delegation.created_at = self.from_date - timedelta(days=1)
        self.user_delegation.save()

        self.create_delegation_tx(amount1, created_at=self.from_date - timedelta(days=1))
        self.create_delegation_tx(amount2, created_at=self.from_date + timedelta(days=2))
        self.create_delegation_tx(amount3, created_at=self.from_date + timedelta(days=6))
        self.create_delegation_tx(amount3, created_at=self.from_date + timedelta(days=11))  # Dummy
        assert calculate_user_score(self.user_delegation, self.from_date.date(), self.to_date.date()) == sum(
            [
                Decimal('0.77') * effective_days(5),
                Decimal('1.23') * effective_days(11),
            ]
        )

    def test_calculate_user_score_complex12(self):
        #      ^
        #      |
        # 3    + +-+
        #      | | |
        # 2    | | |     +-----------
        #      | | |     |xxxxxxxxxxx
        # 1.23 | |-+-----+ - - - - -
        #      | |yyyyyyyyyyyyyyyyyyy
        #      +-+------------------>
        #        1 2     6          10

        amount1 = Decimal('3')
        amount2 = Decimal('-1.77')
        amount3 = Decimal('0.77')

        self.user_delegation.created_at = self.from_date + timedelta(days=1)
        self.user_delegation.save()

        self.create_delegation_tx(amount1, created_at=self.from_date + timedelta(days=1))
        self.create_delegation_tx(amount2, created_at=self.from_date + timedelta(days=2))
        self.create_delegation_tx(amount3, created_at=self.from_date + timedelta(days=6))
        self.create_delegation_tx(amount3, created_at=self.from_date + timedelta(days=11))  # Dummy
        assert calculate_user_score(self.user_delegation, self.from_date.date(), self.to_date.date()) == sum(
            [
                Decimal('0.77') * effective_days(5),
                Decimal('1.23') * effective_days(10),
            ]
        )

    def test_calculate_user_score_complex13(self):
        # 4     ^             +--+
        #       |             |  |
        # 3     |     +--+    |  |
        #       |     |  |    |  |
        # 2     |  +--+  |    |  +-------
        # 1.5   |  | - - +----+xxxxxxxxxx
        # 1.23  +--+yyyyyyyyyyyyyyyyyyyyy
        #       |zzzzzzzzzzzzzzzzzzzzzzzz
        #       +----------------------->
        #          1  3  5    7  8

        amount1 = Decimal('1.23')
        amount2 = Decimal('0.77')
        amount3 = Decimal('1')
        amount4 = Decimal('-1.5')
        amount5 = Decimal('2.5')
        amount6 = Decimal('-2')

        self.user_delegation.created_at = self.from_date - timedelta(days=1)
        self.user_delegation.save()

        self.create_delegation_tx(amount1, created_at=self.from_date - timedelta(days=1))
        self.create_delegation_tx(amount2, created_at=self.from_date + timedelta(days=1))
        self.create_delegation_tx(amount3, created_at=self.from_date + timedelta(days=3))
        self.create_delegation_tx(amount4, created_at=self.from_date + timedelta(days=5))
        self.create_delegation_tx(amount5, created_at=self.from_date + timedelta(days=7))
        self.create_delegation_tx(amount6, created_at=self.from_date + timedelta(days=8))
        self.create_delegation_tx(amount3, created_at=self.from_date + timedelta(days=11))  # Dummy
        assert calculate_user_score(self.user_delegation, self.from_date.date(), self.to_date.date()) == sum(
            [
                Decimal('0.5') * effective_days(4),
                Decimal('0.27') * effective_days(10),
                Decimal('1.23') * effective_days(11),
            ]
        )

    def test_calculate_user_score_complex14(self):
        #  4    ^ +-+ +-+           +----
        #       | | | | |           |xxxx
        #  3    | | +-+ |  +--+     |xxxx
        #  2.5  | |     |  |  +-----+ - -
        #  2    | | - - +--+yyyyyyyyyyyyy
        #       | |zzzzzzzzzzzzzzzzzzzzzz
        #       +-+--------------------->
        #         1 2 3 4  5  6      8

        amount1 = Decimal('4')
        amount2 = Decimal('-1')
        amount3 = Decimal('1')
        amount4 = Decimal('-2')
        amount5 = Decimal('1')
        amount6 = Decimal('-0.5')
        amount7 = Decimal('1.5')

        self.user_delegation.created_at = self.from_date + timedelta(days=1)
        self.user_delegation.save()

        self.create_delegation_tx(amount1, created_at=self.from_date + timedelta(days=1))
        self.create_delegation_tx(amount2, created_at=self.from_date + timedelta(days=2))
        self.create_delegation_tx(amount3, created_at=self.from_date + timedelta(days=3))
        self.create_delegation_tx(amount4, created_at=self.from_date + timedelta(days=4))
        self.create_delegation_tx(amount5, created_at=self.from_date + timedelta(days=5))
        self.create_delegation_tx(amount6, created_at=self.from_date + timedelta(days=6))
        self.create_delegation_tx(amount7, created_at=self.from_date + timedelta(days=8))
        self.create_delegation_tx(amount3, created_at=self.from_date + timedelta(days=11))  # Dummy
        assert calculate_user_score(self.user_delegation, self.from_date.date(), self.to_date.date()) == sum(
            [
                Decimal('1.5') * effective_days(3),
                Decimal('0.5') * effective_days(6),
                Decimal('2') * effective_days(10),
            ]
        )

    def test_calculate_user_score_complex15(self):
        #   ▲
        #   │
        # 3 │   ┌───────────────
        #   │   │ xxxxxxxxxxxxxx
        # 2 ├───┤ xxxxxxxxxxxxxx
        #   │   │ xxxxxxxxxxxxxxx
        #   │   │ xxxxxxxxxxxxxxx  x
        #   └───┴───────────────►
        #       4
        amount1 = Decimal('2')
        amount2 = Decimal('-2')
        amount3 = Decimal('3')

        self.user_delegation.created_at = self.from_date + timedelta(days=1)
        self.user_delegation.save()

        self.create_delegation_tx(amount1, created_at=self.from_date - timedelta(days=1))
        self.create_delegation_tx(amount2, created_at=self.from_date + timedelta(days=4))
        self.create_delegation_tx(amount3, created_at=self.from_date + timedelta(days=4, seconds=1))
        assert calculate_user_score(self.user_delegation, self.from_date.date(), self.to_date.date()) == sum(
            [
                Decimal('3') * effective_days(7),
            ]
        )

    def test_populate_users_profit(self):
        from_date = ir_now().date() - timedelta(days=2)
        to_date = ir_now().date() - timedelta(days=1)

        user2 = User.objects.get(pk=202)
        user3 = User.objects.get(pk=203)

        PoolProfit.objects.create(
            from_date=from_date,
            to_date=to_date,
            currency=RIAL,
            pool=self.pool,
            position_profit=100,
            rial_value=100,
        )
        PoolProfit.objects.create(
            from_date=from_date,
            to_date=to_date,
            currency=TETHER,
            pool=self.pool,
            position_profit=50,
            rial_value=200,
        )

        user_delegation2 = UserDelegation.objects.create(
            pool=self.pool,
            user=user2,
            balance=Decimal(0),
            closed_at=None,
        )
        user_delegation3 = UserDelegation.objects.create(
            pool=self.pool,
            user=user3,
            balance=Decimal(0),
            closed_at=None,
        )
        udp1 = UserDelegationProfit.objects.create(
            user_delegation=self.user_delegation,
            delegation_score=5,
            from_date=from_date,
            to_date=to_date,
        )
        udp2 = UserDelegationProfit.objects.create(
            user_delegation=user_delegation2,
            delegation_score=10,
            from_date=from_date,
            to_date=to_date,
        )
        udp3 = UserDelegationProfit.objects.create(
            user_delegation=user_delegation3,
            delegation_score=15,
            from_date=from_date,
            to_date=to_date,
            amount=150,
        )
        all_pools = LiquidityPool.objects.all()
        populate_users_profit_on_target_pools(from_date, all_pools)
        udp1.refresh_from_db()
        udp2.refresh_from_db()
        udp3.refresh_from_db()

        assert udp1.amount == 50
        assert udp2.amount == 100
        assert udp3.amount == 150

        udp3.delegation_score = Decimal(100)
        udp3.save()
        for udp in [udp1, udp2, udp3]:
            udp.amount = None
            udp.save()

        populate_users_profit_on_target_pools(from_date, all_pools)

        udp1.refresh_from_db()
        udp2.refresh_from_db()
        udp3.refresh_from_db()

        assert udp1.amount == 13  # round(300 / 115 * 5)
        assert udp2.amount == 26  # round(300 / 115 * 10)
        assert udp3.amount == 260  # round(300 / 115 * 100)

    def test_populate_users_profit_idempotent(self):
        from_date = ir_now().date() - timedelta(days=2)
        to_date = ir_now().date() - timedelta(days=1)

        PoolProfit.objects.create(
            from_date=from_date,
            to_date=to_date,
            currency=RIAL,
            pool=self.pool,
            position_profit=100,
            rial_value=100,
        )
        PoolProfit.objects.create(
            from_date=from_date,
            to_date=to_date,
            currency=TETHER,
            pool=self.pool,
            position_profit=50,
            rial_value=200,
        )

        udp1 = UserDelegationProfit.objects.create(
            user_delegation=self.user_delegation,
            delegation_score=5,
            from_date=from_date,
            to_date=to_date,
            amount=-1,
        )

        populate_users_profit_on_target_pools(from_date, LiquidityPool.objects.all())
        udp1.refresh_from_db()

        assert udp1.amount == -1

    def test_distribute_user_profit(self):
        from_date = ir_now().date() - timedelta(days=2)
        to_date = ir_now().date() - timedelta(days=1)

        user2 = User.objects.get(pk=202)
        user3 = User.objects.get(pk=203)

        # test allow_negative_balance
        rial_wallet_user2 = Wallet.get_user_wallet(user2, RIAL)
        assert rial_wallet_user2.balance == 0
        rial_wallet_user2.create_transaction(tp='manual', amount=Decimal('-1000'), allow_negative_balance=True).commit(
            allow_negative_balance=True
        )
        rial_wallet_user2.refresh_from_db()
        assert rial_wallet_user2.balance == -1000

        user_delegation2 = UserDelegation.objects.create(
            pool=self.pool,
            user=user2,
            balance=Decimal(0),
            closed_at=None,
            total_profit=400,
        )
        user_delegation3 = UserDelegation.objects.create(
            pool=self.pool,
            user=user3,
            balance=Decimal(0),
            closed_at=None,
            total_profit=700,
        )

        pool_profit_rial = PoolProfit.objects.create(
            from_date=from_date,
            to_date=to_date,
            currency=RIAL,
            pool=self.pool,
            position_profit=100,
            rial_value=100,
        )
        pool_profit_usdt = PoolProfit.objects.create(
            from_date=from_date,
            to_date=to_date,
            currency=TETHER,
            pool=self.pool,
            position_profit=50,
            rial_value=200,
        )

        udp1 = UserDelegationProfit.objects.create(
            user_delegation=self.user_delegation,
            delegation_score=5,
            from_date=from_date,
            to_date=to_date,
        )
        udp2 = UserDelegationProfit.objects.create(
            user_delegation=user_delegation2,
            delegation_score=10,
            from_date=from_date,
            to_date=to_date,
        )
        udp3 = UserDelegationProfit.objects.create(
            user_delegation=user_delegation3,
            delegation_score=15,
            from_date=from_date,
            to_date=to_date,
        )

        pool_profit_tx = self.profit_wallet.create_transaction(
            tp='delegate',
            amount=250,
        )
        pool_profit_tx.commit()
        all_pools = LiquidityPool.objects.all()
        populate_users_profit_on_target_pools(from_date, all_pools)
        with pytest.raises(ValueError):
            distribute_user_profit_on_target_pools(from_date, all_pools)

        self.profit_wallet.refresh_from_db()
        udp1.refresh_from_db()
        udp2.refresh_from_db()
        udp3.refresh_from_db()
        pool_profit_rial.refresh_from_db()
        pool_profit_usdt.refresh_from_db()

        assert udp1.transaction is None
        assert udp2.transaction is None
        assert udp3.transaction is None
        assert pool_profit_rial.transaction is None
        assert pool_profit_usdt.transaction is None

        assert self.profit_wallet.balance == 250

        pool_profit_tx = self.profit_wallet.create_transaction(tp='delegate', amount=50)
        pool_profit_tx.commit()

        # To test idempotence
        udp3.create_transaction()
        udp3.save()

        distribute_user_profit_on_target_pools(from_date, all_pools)

        udp1.refresh_from_db()
        udp2.refresh_from_db()
        udp3.refresh_from_db()
        self.profit_wallet.refresh_from_db()
        pool_profit_rial.refresh_from_db()
        pool_profit_usdt.refresh_from_db()

        assert udp1.transaction is not None
        assert udp2.transaction is not None
        assert udp3.transaction is not None
        assert pool_profit_rial.transaction is not None
        assert pool_profit_usdt.transaction is None

        udp1.user_delegation.refresh_from_db()
        assert udp1.user_delegation.total_profit == 50

        udp2.user_delegation.refresh_from_db()
        assert udp2.user_delegation.total_profit == 500  # 400 + 100

        udp3.user_delegation.refresh_from_db()
        assert udp3.user_delegation.total_profit == 850  # 700 + 150

        assert udp1.transaction.amount == 50
        assert udp2.transaction.amount == 100
        assert udp3.transaction.amount == 150
        assert pool_profit_rial.transaction.amount == -300

        assert self.profit_wallet.balance == 0
        assert udp1.transaction.wallet.balance == 50
        assert udp2.transaction.wallet.balance == -900  # -1000 + 100  --> allow_negative_balance
        assert udp3.transaction.wallet.balance == 150
        assert pool_profit_rial.transaction.wallet.balance == 0

        for udp in [udp1, udp2, udp3]:
            assert udp.transaction.wallet.currency == RIAL

    def test_distribute_very_large_profit(self):
        from_date = ir_now().date() - timedelta(days=2)
        to_date = from_date + timedelta(days=1)

        user2 = User.objects.get(pk=202)
        user_delegation2 = UserDelegation.objects.create(
            pool=self.pool,
            user=user2,
            balance=Decimal(0),
            closed_at=None,
        )
        udp1 = UserDelegationProfit.objects.create(
            user_delegation=self.user_delegation,
            delegation_score=8,
            from_date=from_date,
            to_date=to_date,
        )
        udp2 = UserDelegationProfit.objects.create(
            user_delegation=user_delegation2,
            delegation_score=8,
            from_date=from_date,
            to_date=to_date,
        )

        pool_profit_rial = PoolProfit.objects.create(
            from_date=from_date,
            to_date=to_date,
            currency=RIAL,
            pool=self.pool,
            position_profit=int(TRANSACTION_MAX),
            rial_value=int(TRANSACTION_MAX),
        )
        pool_profit_usdt = PoolProfit.objects.create(
            from_date=from_date,
            to_date=to_date,
            currency=TETHER,
            pool=self.pool,
            position_profit=10000,
            rial_value=int(TRANSACTION_MAX),
        )
        for _ in range(2):
            self.profit_wallet.create_transaction(tp='manual', amount=int(TRANSACTION_MAX)).commit()
        all_pools = LiquidityPool.objects.all()
        populate_users_profit_on_target_pools(from_date, all_pools)
        distribute_user_profit_on_target_pools(from_date, all_pools)

        udp1.refresh_from_db()
        udp2.refresh_from_db()
        assert udp1.transaction is not None and udp2.transaction is not None
        assert udp1.transaction.amount == int(TRANSACTION_MAX)
        assert udp2.transaction.amount == int(TRANSACTION_MAX)

        self.profit_wallet.refresh_from_db()
        assert self.profit_wallet.balance == 0
        transactions = self.profit_wallet.transactions.order_by('id')[2:]
        assert len(transactions) == 2
        assert transactions[0].amount == -TRANSACTION_MAX
        assert transactions[1].amount == -(2 * int(TRANSACTION_MAX) - TRANSACTION_MAX)

        pool_profit_rial.refresh_from_db()
        assert pool_profit_rial.transaction == transactions[1]
        pool_profit_usdt.refresh_from_db()
        assert pool_profit_usdt.transaction is None

    def test_distribute_user_profit_null_udp_amount(self):
        from_date = ir_now().date() - timedelta(days=2)
        to_date = ir_now().date() - timedelta(days=1)

        UserDelegationProfit.objects.create(
            user_delegation=self.user_delegation,
            delegation_score=5,
            from_date=from_date,
            to_date=to_date,
        )
        with pytest.raises(NullAmountUDPExists):
            distribute_user_profit_on_target_pools(from_date, LiquidityPool.objects.all())

    def test_populate_users_profit_batching(self):
        total_count = 1002
        users = [
            User(
                username=random_string(12),
                email=random_string(12) + '@gmail.com',
                first_name='first_name',
                birthday=datetime.datetime(year=1993, month=11, day=15),
                gender=User.GENDER.female,
                city='Tehran',
                requires_2fa=True,
                mobile=str(9980000001 + randrange(1, 10 ** 6)),
            )
            for i in range(total_count)
        ]
        users = User.objects.bulk_create(users)
        user_delegations = [
            UserDelegation(
                pool=self.pool,
                user=user,
                balance=Decimal(1),
                closed_at=None,
            )
            for user in users
        ]
        user_delegations = UserDelegation.objects.bulk_create(user_delegations)
        UserDelegation.objects.update(created_at=ir_now() - timedelta(days=100))
        udps = [
            UserDelegationProfit(
                from_date=self.from_date.date(),
                to_date=self.to_date.date(),
                delegation_score=100,
                user_delegation=user_delegation,
            )
            for user_delegation in user_delegations
        ]
        udps = UserDelegationProfit.objects.bulk_create(udps)

        populate_users_profit_on_target_pools(self.from_date.date(), LiquidityPool.objects.all())

        user_delegation_profits = UserDelegationProfit.objects.filter(from_date=self.from_date.date())
        assert user_delegation_profits.count() == total_count
        for user_delegation_profit in user_delegation_profits:
            assert user_delegation_profit.delegation_score is not None
            assert user_delegation_profit.from_date == self.from_date.date()
            assert user_delegation_profit.to_date == self.to_date.date()
            assert user_delegation_profit.transaction is None
            assert user_delegation_profit.amount is not None

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_profit_notification(self, _):
        from_date = ir_now().date() - timedelta(days=2)
        to_date = ir_now().date() - timedelta(days=1)

        UserDelegationProfit.objects.create(
            user_delegation=self.user_delegation,
            delegation_score=5,
            from_date=from_date,
            to_date=to_date,
        )
        PoolProfit.objects.create(
            from_date=from_date,
            to_date=to_date,
            currency=RIAL,
            pool=self.pool,
            position_profit=55550,
            rial_value=55550,
        )
        pool_profit_tx = self.profit_wallet.create_transaction(
            tp='delegate',
            amount=55550,
        )
        pool_profit_tx.commit()

        Notification.objects.all().delete()
        all_pools = LiquidityPool.objects.all()
        populate_users_profit_on_target_pools(from_date, all_pools)
        distribute_user_profit_on_target_pools(from_date, all_pools)

        notification = Notification.objects.filter(user=self.user1).first()
        assert notification is not None
        assert (
            notification.message
            == 'سود مشارکت در استخر بیت‌کوین به میزان 5,555 تومان به کیف پول شما در نوبیتکس واریز شد.'
        )

    def test_populate_users_delegation_score(self):
        amount = Decimal('1.23')

        self.user_delegation.created_at = self.from_date - timedelta(days=100)
        self.user_delegation.save()

        self.create_delegation_tx(amount, created_at=self.from_date + timedelta(days=4))
        self.create_delegation_tx(amount, created_at=self.from_date - timedelta(days=100))

        # dummy
        UserDelegationProfit.objects.create(
            user_delegation=self.user_delegation,
            from_date=self.from_date.date() - timedelta(days=1),
            to_date=self.to_date.date(),
            delegation_score=1,
        )

        populate_users_delegation_score_on_target_pools(
            self.from_date.date(), self.to_date.date(), target_pools=LiquidityPool.objects.all()
        )
        user_delegation_profit = UserDelegationProfit.objects.get(
            user_delegation=self.user_delegation, from_date=self.from_date.date()
        )
        assert user_delegation_profit.delegation_score == sum(
            [
                Decimal('1.23') * effective_days(7),
                Decimal('1.23') * effective_days(11),
            ]
        )
        assert user_delegation_profit.from_date == self.from_date.date()
        assert user_delegation_profit.to_date == self.to_date.date()
        assert user_delegation_profit.transaction is None
        assert user_delegation_profit.amount is None

    def test_populate_users_delegation_score_batching(self):
        amount = Decimal('1.23')

        self.user_delegation.created_at = self.from_date - timedelta(days=100)
        self.user_delegation.save()
        total_count = 1002
        users = [
            User(
                username=random_string(12),
                email=random_string(12) + '@gmail.com',
                first_name='first_name',
                birthday=datetime.datetime(year=1993, month=11, day=15),
                gender=User.GENDER.female,
                city='Tehran',
                requires_2fa=True,
                mobile=str(9980000001 + randrange(1, 10 ** 6)),
            )
            for i in range(total_count)
        ]
        users = User.objects.bulk_create(users)
        user_delegations = [
            UserDelegation(
                pool=self.pool,
                user=user,
                balance=Decimal(1),
                closed_at=None,
            )
            for user in users
        ]
        user_delegations = UserDelegation.objects.bulk_create(user_delegations)
        UserDelegation.objects.update(created_at=ir_now() - timedelta(days=100))
        delegation_txs = [
            DelegationTransaction(
                amount=amount,
                created_at=ir_now(),
                user_delegation=user_delegation,
            )
            for user_delegation in user_delegations
        ]
        DelegationTransaction.objects.bulk_create(delegation_txs)

        populate_users_delegation_score_on_target_pools(
            self.from_date.date(), self.to_date.date(), target_pools=LiquidityPool.objects.all()
        )

        user_delegation_profits = UserDelegationProfit.objects.filter(from_date=self.from_date.date())
        assert user_delegation_profits.count() == total_count + 1
        for user_delegation_profit in user_delegation_profits:
            assert user_delegation_profit.delegation_score is not None
            assert user_delegation_profit.from_date == self.from_date.date()
            assert user_delegation_profit.to_date == self.to_date.date()
            assert user_delegation_profit.transaction is None
            assert user_delegation_profit.amount is None

    def test_populate_users_delegation_score_closed_at_midnight(self):
        amount = Decimal('1.23')
        self.create_delegation_tx(amount, created_at=self.from_date + timedelta(days=4))
        self.create_delegation_tx(amount, created_at=self.from_date - timedelta(days=100))

        self.user_delegation.closed_at = datetime.datetime.combine(
            self.to_date, datetime.time.max, ir_tz()
        ) + timedelta(hours=1)
        self.user_delegation.created_at = self.from_date - timedelta(days=100)
        self.user_delegation.save()

        populate_users_delegation_score_on_target_pools(
            self.from_date.date(), self.to_date.date(), target_pools=LiquidityPool.objects.all()
        )
        user_delegation_profit = UserDelegationProfit.objects.get(user_delegation=self.user_delegation)
        assert user_delegation_profit.delegation_score == sum(
            [
                Decimal('1.23') * effective_days(7),
                Decimal('1.23') * effective_days(11),
            ]
        )
        assert user_delegation_profit.from_date == self.from_date.date()
        assert user_delegation_profit.to_date == self.to_date.date()
        assert user_delegation_profit.transaction is None
        assert user_delegation_profit.amount is None

    def test_populate_users_delegation_score_already_done(self):
        amount = Decimal('1.23')
        self.create_delegation_tx(amount, created_at=self.from_date + timedelta(days=4))

        self.user_delegation.created_at = self.from_date - timedelta(days=100)
        self.user_delegation.save()
        udp = UserDelegationProfit.objects.create(
            user_delegation=self.user_delegation,
            from_date=self.from_date.date(),
            to_date=self.to_date.date(),
            delegation_score=1,
        )

        populate_users_delegation_score_on_target_pools(
            self.from_date.date(), self.to_date.date(), target_pools=LiquidityPool.objects.all()
        )
        user_delegation_profit = UserDelegationProfit.objects.get(
            user_delegation=self.user_delegation, from_date=self.from_date.date()
        )
        assert user_delegation_profit.id == udp.id
        assert user_delegation_profit.from_date == self.from_date.date()
        assert user_delegation_profit.to_date == self.to_date.date()
        assert user_delegation_profit.delegation_score == udp.delegation_score
        assert user_delegation_profit.transaction is None
        assert user_delegation_profit.amount is None

    @patch('jdatetime.date.today', lambda: jdatetime.date(1397, 2, 1))
    @patch('exchange.pool.functions.create_or_update_pool_stat')
    @patch('exchange.pool.functions.populate_apr_of_target_pools')
    @patch('exchange.pool.functions.populate_realized_profits_for_target_pools')
    @patch('exchange.pool.functions.populate_users_delegation_score_on_target_pools')
    @patch('exchange.pool.functions.populate_users_profit_on_target_pools')
    @patch('exchange.pool.functions.distribute_user_profit_on_target_pools')
    def test_users_profit_cron_on_first_of_month(
        self,
        _distribute_user_profit,
        _populate_users_profit,
        _populate_users_delegation_score,
        _populate_realized_pool_profits,
        _populate_apr_all_pools,
        _create_or_update_pool_stat,
    ):

        LiquidityPool.objects.create(
            currency=Currencies.eth,
            capacity=10000,
            manager_id=411,
            is_active=True,
            activated_at=ir_now(),
        )
        LiquidityPool.objects.create(
            currency=Currencies.shib,
            capacity=10000,
            manager_id=412,
            is_active=False,
            activated_at=ir_now(),
        )

        DistributeUsersProfitCron().run()
        from_date = datetime.date(2018, 3, 21)
        to_date = datetime.date(2018, 4, 20)
        _populate_users_delegation_score.assert_called_once()
        _populate_users_profit.assert_called_once()
        _distribute_user_profit.assert_called_once()
        _populate_realized_pool_profits.assert_called_once()
        _populate_apr_all_pools.assert_called_once()
        assert _create_or_update_pool_stat.call_count == 3

    @patch('jdatetime.date.today', lambda: jdatetime.date(1397, 2, 2))
    @patch('exchange.pool.functions.create_or_update_pool_stat')
    @patch('exchange.pool.functions.populate_apr_of_target_pools')
    @patch('exchange.pool.functions.populate_realized_profits_for_target_pools')
    @patch('exchange.pool.functions.populate_users_delegation_score_on_target_pools')
    @patch('exchange.pool.functions.populate_users_profit_on_target_pools')
    @patch('exchange.pool.functions.distribute_user_profit_on_target_pools')
    def test_users_profit_cron_on_rest_of_month(self, *args):
        DistributeUsersProfitCron().run()
        for fn in args:
            fn.assert_not_called()

    @patch('exchange.pool.functions.ir_today', lambda: jdatetime.date(year=1403, month=11, day=20).togregorian())
    @patch('exchange.pool.models.PoolProfit.unmatched_amount', new_callable=PropertyMock, return_value=Decimal('0'))
    @patch('exchange.pool.models.PoolProfit.orders')
    @patch('exchange.pool.functions.PriceEstimator.get_rial_value_by_best_price')
    def test_pay_pool_profit_command(self, mock_get_rial_value, mock_orders_manager, mock_unmatched_amount):
        """
        test paying profit for ETH pool
        compute profits from: 1403/11/10
                        to: 1403/11/15
        consider positions' closed_at <= 1403/11/20
        """
        mock_get_rial_value.return_value = Decimal('5')
        mock_orders = [MagicMock(matched_total_price=4), MagicMock(matched_total_price=2)]
        mock_orders_manager.all.return_value = mock_orders
        base_date = as_ir_tz(jdatetime.datetime(year=1403, month=11, day=20, hour=10).togregorian())
        self.eth_pool = LiquidityPool.objects.create(
            currency=Currencies.eth,
            capacity=1000,
            manager_id=411,
            is_active=True,
        )
        self.eth_user_delegation = UserDelegation.objects.create(
            pool=self.eth_pool,
            user=self.user1,
            balance=Decimal(0),
            closed_at=None,
        )
        self.eth_user_delegation.created_at = base_date - timedelta(days=100)
        self.eth_user_delegation.save()

        self.eth_user_delegation.pool.src_wallet.create_transaction('manual', self.initial_balance).commit()
        user1_eth_wallet = Wallet.get_user_wallet(self.user1, Currencies.eth)
        user1_eth_wallet.create_transaction('manual', self.initial_balance).commit()
        amount = Decimal('8')
        from_date = base_date - timedelta(days=10)
        to_date = base_date
        self.eth_user_delegation.created_at = from_date - timedelta(days=1)
        self.eth_user_delegation.save()
        self.create_delegation_tx(
            amount,
            created_at=from_date - timedelta(days=1),
            user_delegation=self.eth_user_delegation,
        )
        self.create_delegation_tx(
            -amount,
            created_at=from_date + timedelta(days=6),
            user_delegation=self.eth_user_delegation,
        )
        self.eth_user_delegation.closed_at = from_date + timedelta(days=6)
        self.eth_user_delegation.save()
        self.eth_user_delegation.refresh_from_db()
        profit_wallet = Wallet.get_user_wallet(LiquidityPool.get_profit_collector(), Currencies.usdt)
        profit_wallet.create_transaction(tp='pnl', amount=10).commit()
        Position.objects.create(
            user=self.user1,
            src_currency=Currencies.eth,
            dst_currency=Currencies.usdt,
            side=Position.SIDES.sell,
            collateral=213,
            earned_amount=2,
            pnl=1,
            closed_at=to_date - timedelta(days=1),
        )
        Position.objects.create(
            user=self.user1,
            src_currency=Currencies.eth,
            dst_currency=Currencies.rls,
            side=Position.SIDES.sell,
            collateral=213,
            earned_amount=5,
            pnl=2,
            closed_at=to_date - timedelta(days=1),
        )
        pool_profit_tx = self.profit_wallet.create_transaction(
            tp='delegate',
            amount=100,
        )
        pool_profit_tx.commit()
        call_command(
            "pay_pool_profits",
            currency="eth",
            from_date=from_date.strftime('%Y-%m-%d'),
            to_date=(from_date + timedelta(days=5)).strftime('%Y-%m-%d'),
            positions_to_date=to_date.strftime('%Y-%m-%d'),
        )
        self.eth_pool.refresh_from_db()
        self.eth_user_delegation.refresh_from_db()
        pool_profits = PoolProfit.objects.filter(pool=self.eth_pool, to_date=to_date)
        assert pool_profits.count() == 2
        rls_profit = pool_profits.get(currency=Currencies.rls)
        assert rls_profit.transaction is not None
        assert rls_profit.position_profit == Decimal('3')
        assert rls_profit.rial_value == Decimal('5')
        usdt_profit = pool_profits.get(currency=Currencies.usdt)
        assert usdt_profit.position_profit == Decimal('1')
        assert usdt_profit.rial_value == Decimal('6')
        udps = UserDelegationProfit.objects.filter(user_delegation__pool=self.eth_pool)
        assert udps.count() == 1
        udp = udps.first()
        assert udp.transaction is not None
        assert udp.to_date == (as_ir_tz(self.eth_user_delegation.closed_at) - timedelta(days=1)).date()
        assert udp.delegation_score == Decimal('72')
        assert udp.amount == Decimal('11')
        assert self.eth_pool.current_profit == Decimal('10')
