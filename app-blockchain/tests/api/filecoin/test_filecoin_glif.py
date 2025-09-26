from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

import pytest
from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.explorer_original import BlockchainExplorer
from exchange.blockchain.api.filecoin.filecoin_explorer_interface import FilecoinExplorerInterface
from exchange.blockchain.api.filecoin.filecoin_glif import FilecoinGlifApi, FilecoinGlifNodeAPI
from exchange.blockchain.api.general.dtos.dtos import TransferTx


@pytest.mark.slow
class TestGlifFilecoinApiCalls(TestCase):
    api = FilecoinGlifApi
    api_node = FilecoinGlifNodeAPI

    addresses_of_account = ['f410f6vyzxlrug5vux6x5a7pvdl2orafibezzpbywv6y',
                            'f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy',
                            ]
    tx_hashes = ['bafy2bzaceco3rxb22d6mbifqzhn7tgk5h2aafdlbgyufz3aufhz3ph7eymkhk',
                 'bafy2bzacebrq7bbg3hv6tdpl7cdjybet5ow3j6424ihizkt4mfv5belmvdoss']

    @classmethod
    def check_general_response(cls, response, keys):
        if set(keys).issubset(response.keys()):
            return True
        return False

    def test_get_balance_api(self):

        keys = {'jsonrpc', 'result', 'id'}
        for address in self.addresses_of_account:
            get_balance_result = self.api.get_balance(address)
            assert self.check_general_response(get_balance_result, keys)
            assert isinstance(get_balance_result, dict)
            assert isinstance(get_balance_result.get('result'), str)

    def test_get_tx_details_api(self):
        keys = {'jsonrpc', 'result', 'id'}
        transaction_keys = {'CID', 'From', 'Method', 'Params', 'Value', 'To'}
        for tx_hash in self.tx_hashes:
            get_tx_details_response = self.api_node.get_tx_details(tx_hash)
            assert self.check_general_response(get_tx_details_response, keys)
            assert isinstance(get_tx_details_response, dict)
            assert isinstance(get_tx_details_response.get('result'), dict)
            assert self.check_general_response(get_tx_details_response.get('result'), transaction_keys)



class TestGlifFilecoinFromExplorer(TestCase):
    api = FilecoinGlifApi
    api_node = FilecoinGlifNodeAPI
    currency = Currencies.fil
    addresses_of_account = ['f410f6vyzxlrug5vux6x5a7pvdl2orafibezzpbywv6y',
                            'f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy'
                            ]
    tx_hashes = ['bafy2bzaceco3rxb22d6mbifqzhn7tgk5h2aafdlbgyufz3aufhz3ph7eymkhk',
                 'bafy2bzacebrq7bbg3hv6tdpl7cdjybet5ow3j6424ihizkt4mfv5belmvdoss']

    def test_get_balance(self):
        balance_mock_response = [{'id': 1, 'jsonrpc': '2.0', 'result': '350844698902389'},
                                 {'id': 1, 'jsonrpc': '2.0', 'result': '299335333566431890'}, ]
        self.api.get_balance = Mock(side_effect=balance_mock_response)
        FilecoinExplorerInterface.balance_apis[0] = self.api
        balances = BlockchainExplorer.get_wallets_balance({'FIL': self.addresses_of_account}, Currencies.fil)
        expected_balances = {Currencies.fil: [
            {'address': 'f410f6vyzxlrug5vux6x5a7pvdl2orafibezzpbywv6y', 'balance': Decimal('0.000350844698902389'),
             'received': Decimal('0.000350844698902389'), 'rewarded': Decimal('0'), 'sent': Decimal('0')},
            {'address': 'f1emm55jaulyucsuttc7a6cf62uysn5rcwd7k4qyy', 'balance': Decimal('0.299335333566431890'),
             'received': Decimal('0.299335333566431890'), 'rewarded': Decimal('0'), 'sent': Decimal('0')}]}

        assert self.currency in balances.keys()
        expected_values = expected_balances.values()
        expected_merged_list = []
        for sublist in expected_values:
            expected_merged_list.extend(sublist)
        for balance, expected_balance in zip(balances.get(Currencies.fil), expected_merged_list):
            assert balance == expected_balance

    def test_get_tx_details(self):
        tx_details_mock_responses = [{'id': 1, 'jsonrpc': '2.0', 'result': {'CID': {'/': 'bafy2bzaceazskeoxwilgvdmewr2qd7ropquimvvyt4wl3zju4zgy3ivdzzgsq'}, 'From': 'f1lsnd3toag7sqczubqfkcmadfgvmdlp6rmqmcuby', 'GasFeeCap': '407804', 'GasLimit': 3059156, 'GasPremium': '121076', 'Method': 0, 'Nonce': 0, 'Params': None, 'To': 'f1ys5qqiciehcml3sp764ymbbytfn3qoar5fo3iwy', 'Value': '52016000000000000000', 'Version': 0}},
                                     {'id': 1, 'jsonrpc': '2.0', 'result': {'CID': {'/': 'bafy2bzacebrq7bbg3hv6tdpl7cdjybet5ow3j6424ihizkt4mfv5belmvdoss'}, 'From': 'f3ui6ac5umttel2gasdn3xefipthctm5xm3oozfw7yzrroh4sp4nk37opfmtojdegfeug2qv4l76ie45ysolha', 'GasFeeCap': '125841', 'GasLimit': 36548772, 'GasPremium': '125841', 'Method': 5, 'Nonce': 13878, 'Params': 'hQaCggBAggFAgYINWQGAlwbuwngUnD38ioXqd+EDCwI0diR+AE2tgpbgch+QSmydUvQj3nC5TvSJWbeH+Ow3rVYrJSYpM8NvPfopUwAVeum1WKYw+b8zD/WYV9jQs4JGo9wsqjmnIFTvkG57lr0hC4VhmY82f/ZvYk6WSSGPGVNjrfNGLV+JVMk6KJpPryXL/I6DxgcZeq1fi1yZKQsBjJiT/DD6Auff+oovfSzIkWpl2+lR4Nz7d2N1KVBEWd68FBNNPIRHZjSUU666f9TNk1LHbJZDelzCE53fpcvy6klv/noHz2HtzQ/vSORT8MhuEfA41ok0BO0rMJFK6NS8jU8TJNdUgV6TYeD45zx7ihIyfShe1n86GHlKG95ibkIA3hxn06yG4OIAbz46G6NMFBVOE2HdvEjYbKTBex7uQyV46S8MV9Vf/NC9pW+z8QaI2P9JfrLszOdWr0Cahp26gyD99eV0HNZlCwkv015XtVhaKxRcIcKygpYCwnj3i/UWxBEO13COB2kbTix448dSGgBGBS9YIC4iabEXTzbqn7FXgEcQWO2h8o1aB1tzxzDoOwFoKP76', 'To': 'f01985775', 'Value': '0', 'Version': 0}}]
        self.api.request = Mock(side_effect=tx_details_mock_responses)
        parsed_responses = []
        for tx_hash in self.tx_hashes:
            api_response = self.api_node.get_tx_details(tx_hash)
            parsed_response = self.api.parser.parse_tx_details_response(api_response, None)
            parsed_responses.append(parsed_response)
        expected_txs_details = [[TransferTx(tx_hash='bafy2bzaceazskeoxwilgvdmewr2qd7ropquimvvyt4wl3zju4zgy3ivdzzgsq', success=True, from_address='f1lsnd3toag7sqczubqfkcmadfgvmdlp6rmqmcuby', to_address='f1ys5qqiciehcml3sp764ymbbytfn3qoar5fo3iwy', value=Decimal('52.016000000000000000'), symbol=self.api_node.symbol, confirmations=0, block_height=None, block_hash=None, date=None, memo='', tx_fee=None, token=None, index=None)],
                                []]
        for expected_tx_details, tx_details in zip(expected_txs_details, parsed_responses):
            assert tx_details == expected_tx_details

