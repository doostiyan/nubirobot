from unittest import TestCase
from unittest.mock import patch

from exchange.accounts.models import User
from exchange.asset_backed_credit.externals.wallet import WalletType
from exchange.asset_backed_credit.services.wallet.balance import get_total_wallet_balance
from exchange.base.models import Currencies
from tests.asset_backed_credit.helper import ABCMixins


class WalletBalanceServiceTest(TestCase, ABCMixins):

    def setUp(self):
        self.user = User.objects.get(id=201)

    @patch('exchange.asset_backed_credit.externals.price.PriceProvider.get_nobitex_price')
    def test_get_total_user_wallet_type_balance_success(self, mock_price):
        mock_price.return_value = 2
        self.charge_exchange_wallet(self.user, Currencies.usdt, 10)
        self.charge_exchange_wallet(self.user, Currencies.btc, 50)
        self.charge_exchange_wallet(self.user, Currencies.rls, 100)

        total_balance = get_total_wallet_balance(self.user.uid, self.user.id, WalletType.credit)
        assert total_balance == 2 * (10 + 50) + 100
        assert mock_price.call_count == 2
