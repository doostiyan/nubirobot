from django.test import TestCase

from exchange.accounts.models import User
from exchange.config.config.models import Currencies
from exchange.wallet.exceptions import TransferException
from exchange.wallet.functions import transfer_balance
from exchange.wallet.models import Wallet


class WalletTransferBalanceUnitTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(cls.user)

    def setUp(self):
        self.spot_usdt_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        self.margin_usdt_wallet = Wallet.get_user_wallet(self.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)

    def test_transfer_to_negative_balance_dst_success(self):
        self.margin_usdt_wallet.create_transaction('manual', amount='100').commit()
        self.spot_usdt_wallet.create_transaction('manual', amount='-120', allow_negative_balance=True).commit(
            allow_negative_balance=True
        )

        src_wallet, dst_wallet, _, _ = transfer_balance(
            self.user, Currencies.usdt, 100, Wallet.WALLET_TYPE.margin, Wallet.WALLET_TYPE.spot
        )

        assert src_wallet.balance == 0
        assert dst_wallet.balance == -20

    def test_transfer_src_negative_balance_failure(self):
        self.margin_usdt_wallet.create_transaction('manual', amount='50').commit()
        self.spot_usdt_wallet.create_transaction('manual', amount='-120', allow_negative_balance=True).commit(
            allow_negative_balance=True
        )

        with self.assertRaises(TransferException):
            transfer_balance(self.user, Currencies.usdt, 100, Wallet.WALLET_TYPE.margin, Wallet.WALLET_TYPE.spot)

        assert self.margin_usdt_wallet.balance == 50
        assert self.spot_usdt_wallet.balance == -120
