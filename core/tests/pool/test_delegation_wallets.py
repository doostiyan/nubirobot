from decimal import Decimal

from django.test import TestCase
from exchange.base.calendar import ir_now

from exchange.base.models import Currencies
from exchange.pool.models import LiquidityPool, UserDelegation
from exchange.pool.tasks import task_delegate_in_pool, task_generate_deposit_address_for_nobitex_delegator
from exchange.wallet.models import Wallet


class DelegationTaskTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.pool = LiquidityPool.objects.create(currency=Currencies.btc, capacity=10, manager_id=410, is_active=True, activated_at=ir_now())

    @staticmethod
    def get_delegator_wallet(pool_id: int):
        wallet = UserDelegation.objects.get(user_id=400, pool_id=pool_id)
        return wallet.src_wallet

    def _test_successful_nobitex_delegate(self, pool_id: int, amount: str, pool_filled_capacity: str):
        Wallet.get_user_wallet(400, Currencies.btc).create_transaction('manual', amount).commit()
        success, error = task_delegate_in_pool(pool_id, amount)
        assert success
        assert not error
        assert self.get_delegator_wallet(pool_id).balance == 0
        self.pool.refresh_from_db()
        assert self.pool.filled_capacity == Decimal(pool_filled_capacity)

    def _test_unsuccessful_nobitex_delegate(self, pool_id: int, amount: str, error_message: str):
        success, error = task_delegate_in_pool(pool_id, amount)
        assert not success
        assert error == error_message
        assert not UserDelegation.objects.exists()
        self.pool.refresh_from_db()
        assert self.pool.filled_capacity == 0

    def test_nobitex_delegate(self):
        self._test_successful_nobitex_delegate(self.pool.id, '1', '1')

    def test_nobitex_delegate_no_pool(self):
        self._test_unsuccessful_nobitex_delegate(-1, '10', 'Invalid Pool')

    def test_nobitex_delegate_negative_amount(self):
        self._test_unsuccessful_nobitex_delegate(self.pool.id, '-5', 'Invalid Amount')

    def test_nobitex_delegate_exceed_capacity(self):
        self._test_unsuccessful_nobitex_delegate(self.pool.id, '15', 'Exceed Capacity')

    def test_nobitex_delegate_multiple_in_row(self):
        self._test_successful_nobitex_delegate(self.pool.id, '2', '2')
        self._test_successful_nobitex_delegate(self.pool.id, '2.5', '4.5')
        self._test_successful_nobitex_delegate(self.pool.id, '0.5', '5')

    def test_nobitex_delegator_generate_address(self):
        deposits = Wallet.get_user_wallet(400, Currencies.btc).deposit_addresses.all()
        assert not deposits.exists()
        task_generate_deposit_address_for_nobitex_delegator(self.pool.currency)
        assert len(deposits) == 1
        assert deposits[0].currency == self.pool.currency
        assert deposits[0].network == 'BTC'

        task_generate_deposit_address_for_nobitex_delegator(self.pool.currency, 'BSC')
        deposits = deposits.order_by('id')
        assert len(deposits) == 2
        assert deposits[1].currency == self.pool.currency
        assert deposits[1].network == 'BSC'
