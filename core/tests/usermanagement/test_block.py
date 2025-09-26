from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.models import Currencies, ACTIVE_CURRENCIES
from exchange.wallet.models import Wallet
from exchange.market.models import Order
from exchange.usermanagement.block import BalanceBlockManager
from ..base.utils import create_order


class BalanceBlockManagerTest(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(self.user)

    def test_get_balance_in_order(self):
        btc, rls = Currencies.btc, Currencies.rls
        w_rls = Wallet.get_user_wallet(self.user, rls)
        w_btc = Wallet.get_user_wallet(self.user, btc)
        assert BalanceBlockManager.get_balance_in_order(w_btc) == Decimal('0')
        assert BalanceBlockManager.get_balance_in_order(w_rls) == Decimal('0')
        o1 = create_order(self.user, btc, rls, Decimal('0.0932'), Decimal('140e7'), sell=True)
        assert BalanceBlockManager.get_balance_in_order(w_btc) == Decimal('0.0932')
        assert BalanceBlockManager.get_balance_in_order(w_rls) == Decimal('0')
        o2 = create_order(self.user, btc, rls, Decimal('0.32'), Decimal('140e7'), sell=True)
        assert BalanceBlockManager.get_balance_in_order(w_btc) == Decimal('0.4132')
        assert BalanceBlockManager.get_balance_in_order(w_rls) == Decimal('0')
        o3 = create_order(self.user, btc, rls, Decimal('0.1'), Decimal('140e7'), sell=False)
        assert BalanceBlockManager.get_balance_in_order(w_btc) == Decimal('0.4132')
        assert BalanceBlockManager.get_balance_in_order(w_rls) == Decimal('14e7')
        o2.do_cancel()
        assert BalanceBlockManager.get_balance_in_order(w_btc) == Decimal('0.0932')
        assert BalanceBlockManager.get_balance_in_order(w_rls) == Decimal('14e7')
        w_rls_margin = Wallet.get_user_wallet(self.user, rls, tp=Wallet.WALLET_TYPE.margin)
        assert BalanceBlockManager.get_balance_in_order(w_rls_margin) == Decimal('0')
        o1.do_cancel()
        o3.do_cancel()
        assert BalanceBlockManager.get_balance_in_order(w_btc) == Decimal('0')
        assert BalanceBlockManager.get_balance_in_order(w_rls) == Decimal('0')
