from django.test import TestCase

from exchange.base.models import Currencies
from exchange.blockchain.general_blockchain_wallets import GeneralBlockchainWallet


class TestValidateColdAddresses(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.dummy_general_blockchain_wallet_instance = GeneralBlockchainWallet()
        cls.eth_like_address = '0x7423Cc6632924434544544544544544544544544'
        cls.sol_address = 'HdY1TYDSgrCPvQYVxbKyAvd8psc1CXrRsQP3WohUfW2q'
        cls.btc_bech32_like_address = 'bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq'
        cls.btc_legacy_address = '15e15hWo6CShMgbAfo8c2Ykj4C6BLq6Not'

    def test_address_validation(self):
        # address, currency, address_type, expected result(bool)
        test_cases = [
            (self.eth_like_address, Currencies.eth, 'miner', False),
            (self.eth_like_address, Currencies.eth, 'standard', True),
            (self.eth_like_address, Currencies.btc, 'standard', False),
            (self.sol_address, Currencies.sol, 'standard', True),
            (self.btc_bech32_like_address, Currencies.btc, 'miner', True),
            (self.btc_legacy_address, Currencies.btc, 'miner', False),
            (self.btc_bech32_like_address, Currencies.btc, 'segwit', True),
            (self.btc_legacy_address, Currencies.btc, 'segwit', False),
        ]

        for address, currency, address_type, result  in test_cases:
            actual_result = self.dummy_general_blockchain_wallet_instance.validate_cold_addresses(address, currency, address_type)
            self.assertEqual(result, actual_result)
