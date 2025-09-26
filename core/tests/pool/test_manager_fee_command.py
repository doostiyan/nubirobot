from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.pool.models import LiquidityPool
from exchange.wallet.models import Wallet


class TestUserProfit(TestCase):
    def setUp(self):
        self.user1 = User.objects.get(pk=410)
        LiquidityPool.objects.create(
            currency=Currencies.btc,
            capacity=10000,
            manager=self.user1,
            is_active=True,
        )

        self.user2 = User.objects.get(pk=411)
        LiquidityPool.objects.create(
            currency=Currencies.usdt,
            capacity=10000,
            manager=self.user2,
            is_active=True,
        )

    def test_set_fee_successfully(self):
        call_command('set_fee_for_pool_managers', exclude=f'{Currencies.usdt}', rial_fee='0.25', usdt_fee='0.112')

        self.user1.refresh_from_db()
        self.user2.refresh_from_db()

        assert self.user1.base_fee == self.user1.base_maker_fee == Decimal('0.25')
        assert self.user1.base_fee_usdt == self.user1.base_maker_fee_usdt == Decimal('0.112')
        assert not self.user2.base_fee
        assert not self.user2.base_fee_usdt
