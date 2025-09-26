from decimal import Decimal

from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.models import Currencies, Settings, get_currency_codename
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.wallet.block_processing import NobitexBlockProcessing
from exchange.wallet.models import Wallet, WithdrawRequest
from exchange.wallet.withdraw_method import AutomaticWithdrawMethod
from tests.base.utils import create_withdraw_request


class WalletGetAddressEndPointTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        Wallet.create_user_wallets(cls.user)
        cls.currency = Currencies.ondo
        cls.network = CurrenciesNetworkName.ETH
        cls.blockchain_hash = "0xa6ea4f8f40851880cf33f527d4324e37f23135e8bb378f2d4f6f4a15a48e911d"
        cls.hot_wallet_address = "0x57dd4A4AceAdBb1E1F280260DCe7724e7D0D9D1d"
        cls.destination_address = "0x7Ef6F7899eE70846cA94537b620C2e212A95cC95"
        cls.block_processor = NobitexBlockProcessing()

    def test_change_system_after_tx_creation(self):
        tx_value = Decimal('50')
        initial_fee = AutomaticWithdrawMethod.get_withdraw_fee(self.currency, self.network)
        withdraw_with_fee = create_withdraw_request(
            user=self.user,
            currency=self.currency,
            address='UQC5uTmBRojmKMGR29Eq0GNbENM3XKv_hX2fTkafy3zW',
            amount=tx_value,
            network=self.network,
            status=WithdrawRequest.STATUS.sent,
            fee=initial_fee,
            blockchain_url=self.blockchain_hash,
        )

        # changing system fee
        coin_name = get_currency_codename(self.currency)
        network_name = self.network
        withdraw_fee_key = f'withdraw_fee_{coin_name}_{network_name.lower()}'
        new_min_withdraw_fee = 7.5
        Settings.set(withdraw_fee_key, new_min_withdraw_fee)
        self.assertEqual(
            Decimal(new_min_withdraw_fee), AutomaticWithdrawMethod.get_withdraw_fee(self.currency, self.network)
        )
        txs_info = {
            self.hot_wallet_address: {
                self.currency: [{'tx_hash': self.blockchain_hash, 'value': tx_value - initial_fee}]
            }
        }

        self.block_processor.update_withdraw_status(
            updated_hot_wallet_addresses=[self.hot_wallet_address.lower()], transactions_info=txs_info
        )
        withdraw_with_fee.refresh_from_db()
        self.assertEqual(withdraw_with_fee.status, WithdrawRequest.STATUS.done)
