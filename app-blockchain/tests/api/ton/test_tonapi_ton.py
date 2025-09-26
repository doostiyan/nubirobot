from unittest import TestCase
import pytest
from decimal import Decimal

from exchange.blockchain.api.ton.tonapi_ton import TonApi

from exchange.blockchain.api.ton.ton_explorer_interface import TonExplorerInterface

from exchange.blockchain.explorer_original import BlockchainExplorer

from exchange.base.models import Currencies
from unittest.mock import Mock


class TestTonApiTonApiCalls(TestCase):
    api = TonApi
    addresses = ['EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N',
                 'EQC9gfdnZesicH7aqqe9dajUMigvPqADBTcLFS3IP_w8dDu5']

    @pytest.mark.slow
    def test_get_balance_api(self):
        for address in self.addresses:
            get_balance_result = self.api.get_balance(address)
            assert {'balance'}.issubset(set(get_balance_result.keys()))


class TestDtonTonFromExplorer(TestCase):
    api = TonApi

    addresses = ['EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N']

    def test_get_balance(self):
        balance_mock_responses = [
            {
                "balance": 35956359013517665,
                "code": "b5ee9c720101010100710000deff0020dd2082014c97ba218201339cbab19f71b0ed44d0d31fd31f31d70bffe304e0a4f2608308d71820d31fd31fd31ff82313bbf263ed44d0d31fd31fd3ffd15132baf2a15144baf2a204f901541055f910f2a3f8009320d74a96d307d402fb00e8d101a4c8cb1fcb1fcbffc9ed54",
                "code_hash": "84dafa449f98a6987789ba232358072bc0f76dc4524002a5d0918b9a75d2d599",
                "data": "b5ee9c7201010101002a000050000000e129a9a31772c9ed6b62a6e2eba14a93b90462e7a367777beb8a38fb15b9f33844d22ce2ff",
                "status": "active"
            }
        ]
        self.api.request = Mock(side_effect=balance_mock_responses)
        TonExplorerInterface.balance_apis[0] = self.api
        balances = BlockchainExplorer.get_wallets_balance({'TON': self.addresses}, Currencies.ton)
        expected_balances = [
            {'address': 'EQCD39VS5jcptHL8vMjEXrzGaRcCVYto7HUn4bpAOg8xqB2N', 'balance': Decimal('35956359.013517665'),
             'received': Decimal('35956359.013517665'), 'sent': Decimal('0'), 'rewarded': Decimal('0')}]
        for balance, expected_balance in zip(balances.get(Currencies.ton), expected_balances):
            assert balance == expected_balance
