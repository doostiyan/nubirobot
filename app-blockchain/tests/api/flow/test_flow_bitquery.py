import datetime
from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

import pytest
from django.conf import settings
from django.core.cache import cache
from pytz import UTC

from exchange.base.models import Currencies
from exchange.blockchain.api.flow.flow_explorer_interface import FlowExplorerInterface
from exchange.blockchain.api.flow.flow_bitquery import FlowBitqueryApi
from exchange.blockchain.explorer_original import BlockchainExplorer
from exchange.blockchain.utils import BlockchainUtilsMixin


@pytest.mark.slow
class TestFlowBitqueryFlowApiCalls(TestCase):
    api = FlowBitqueryApi
    addresses = ['f919ee77447b7497',
                 '0x6c36d50dd512ef8e',
                 'ecfad18ba9582d4f',
                 '0xecfad18ba9582d4f']
    txs_hash = ['c7851221b77faa84c78fabbb237c3de7f38b49d1f08880b2bcaca9976649e331',
                'c3105df17a70fdf075e411e3377867668fb0c94044dbd18d56f9338ec0449d61',
                '73603f93e5081ba05ee1cd319e9ce410898f19e9972f2b71641f04338a5d5546'
                ]
    address_txs = ['0xecfad18ba9582d4f',
                   '0xf919ee77447b7497']

    @classmethod
    def check_general_response(cls, response):
        if set(response.keys()) != {'data'}:
            return False
        if set(response.get('data').keys()) != {'flow'}:
            return False
        return True

    def assert_keys(self, response, keys):
        if set(response.keys()).issubset(keys):
            return True
        return False

    def test_get_balance_api(self):
        for address in self.addresses:
            get_balance_result = self.api.get_balance(address)
            assert self.check_general_response(get_balance_result)
            needed_response = get_balance_result.get('data').get('flow')
            assert self.assert_keys(needed_response, {'address'})
            assert isinstance(needed_response.get('address'), list)
            assert isinstance(needed_response.get('address')[0].get('balance'), float)

    def test_get_block_head_api(self):
        get_block_head_response = self.api.get_block_head()
        assert self.check_general_response(get_block_head_response)
        needed_response = get_block_head_response.get('data').get('flow')
        assert self.assert_keys(needed_response, {'blocks'})
        assert isinstance(needed_response.get('blocks'), list)
        assert isinstance(needed_response.get('blocks')[0].get('height'), str)

    def test_get_address_txs_api(self):
        address_txs_keys = {'inputs', 'outputs'}
        transaction_keys = {'block', 'type', 'amountDecimal', 'currency', 'transferReason', 'transaction', 'time',
                            'address'}
        for address in self.address_txs:
            get_address_txs_response = self.api.get_address_txs(address)
            assert self.check_general_response(get_address_txs_response)
            needed_response = get_address_txs_response.get('data').get('flow')
            assert self.assert_keys(needed_response, address_txs_keys)
            transactions = needed_response.get('inputs') + needed_response.get('outputs')
            for transaction in transactions:
                assert self.assert_keys(transaction, transaction_keys)
                assert self.assert_keys(transaction.get('transaction'), {'id', 'statusCode'})

    def test_get_blocks_txs_api(self):
        blocks_txs_keys = {'inputs', 'outputs'}
        transaction_keys = {'block', 'type', 'amountDecimal', 'currency', 'transferReason', 'transaction', 'time',
                            'address'}
        get_blocks_txs_response = self.api.get_batch_block_txs(36030228, 36030230)
        assert self.check_general_response(get_blocks_txs_response)
        needed_response = get_blocks_txs_response.get('data').get('flow')
        assert self.assert_keys(needed_response, blocks_txs_keys)
        transactions = needed_response.get('inputs') + needed_response.get('outputs')
        for transaction in transactions:
            assert self.assert_keys(transaction, transaction_keys)
            assert self.assert_keys(transaction.get('transaction'), {'id', 'statusCode'})


class TestFlowBitqueryFlowFromExplorer(TestCase):
    api = FlowBitqueryApi
    # test for balances in order of normal, address with 0x, over 1000 with other asset
    addresses = [
        'f919ee77447b7497',
        '0x6c36d50dd512ef8e',
        '0xae3ed2533120533c',
        '0xecfad18ba9582d4f']
    address_txs = ['0xecfad18ba9582d4f',
                   '0xf919ee77447b7497',
                   '0x27ebe9e8b2072681']

    def test_get_balance(self):
        balance_mock_responses = [{'data': {'flow': {'address': [{'balance': 1.639999}]}}},
                                  {'data': {'flow': {'address': [{'balance': 0.00106329}]}}},
                                  {'data': {'flow': {'address': [{'balance': 0.101}]}}},
                                  {'data': {'flow': {'address': [{'balance': 2374.47318143}]}}}]
        self.api.request = Mock(side_effect=balance_mock_responses)
        FlowExplorerInterface.balance_apis[0] = self.api
        balances = BlockchainExplorer.get_wallets_balance({'FLOW': self.addresses}, Currencies.flow)
        expected_balances = [
            {'address': 'f919ee77447b7497', 'balance': Decimal('1.639999'), 'received': Decimal('1.639999'),
             'rewarded': Decimal('0'), 'sent': Decimal('0')},
            {'address': '0x6c36d50dd512ef8e', 'balance': Decimal('0.00106329'), 'received': Decimal('0.00106329'),
             'rewarded': Decimal('0'), 'sent': Decimal('0')},
            {'address': '0xae3ed2533120533c', 'balance': Decimal('0.101'), 'received': Decimal('0.101'),
             'rewarded': Decimal('0'), 'sent': Decimal('0')},
            {'address': '0xecfad18ba9582d4f', 'balance': Decimal('2374.47318143'), 'received': Decimal('2374.47318143'),
             'rewarded': Decimal('0'), 'sent': Decimal('0')}
        ]
        for balance, expected_balance in zip(balances.get(Currencies.flow), expected_balances):
            assert balance == expected_balance

    def test_get_address_txs(self):
        address_txs_mock_responses = [
            {'data': {'flow': {'blocks': [{'height': '67845488'}], 'inputs': [], 'outputs': []}}},
            {'data': {'flow': {'blocks': [{'height': '67845528'}], 'inputs': [
                {'block': {'height': '67845528'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00002979',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': '48c568f797cc92897c06378325d954bfcff79a3b985cd7128280247d2882f220',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:58'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845527'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00001652',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': '8978dc7aa6a298e32aff592af7f7c621f2ab04cbabb5b04a4edcbd2c0454abb2',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:57'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845527'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00001552',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': '82e987443b111dfbeedf0baf73a8f23ca483b136310cb7e49fa40121f55c14eb',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:57'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845527'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00000858',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': 'd8363108cb93dcca8113209725a8a9cd97a85b89c7ea9882ab61e03f1879c1ec',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:57'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845526'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00000948',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': 'd79096d95266ef0cbe2d3422f6bee5121b3d667072f86165645dd1750a3ca9d9',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:55'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845526'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00002874',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': '81d64c0fc979a1ff24bb9a0f8929afab6ea443b429995501ba00ea65edb408b2',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:55'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845525'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00002176',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': 'b9496f6817a0d6a692542e952dc874a831344593e419a85a15f6bc639c56e514',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:54'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845522'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00002949',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': 'b050befd85bc31e01f4af4f9edf18bebb43bddd1031709c8a86d91ac1b2338f4',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:50'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845520'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00002196',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': 'fbbadd5d062f80db7918ba972316254e8817d9c51f6c62688d3f5e3a3605df73',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:48'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845519'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00003099',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': '8485c1f1d9ba64e1c8b260dc4a2f8f3cf71b4602e7473202c7ef864677795863',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:47'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845519'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00000818',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': 'f31a0d82ab4cdc853de942bb22fd39b98f4705ba73fa51049ecfb2fe3786d704',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:47'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845518'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00001377',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': 'bf956e36e21e53713df14a830cb3dc0682304e45602682f1e15a63c0510ca691',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:46'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845515'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00006328',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': 'd2cd7df03df985e9b42849d1090d75727a5c77f0e097a57a5b5353ce66dd4f31',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:42'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845513'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00000404',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': '0505d0a3a8d5a48d830602ef30b7538851dca1290c37727077f0e74b2ccf814a',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:40'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845513'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00000983',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': '99be25a017787d4bcfb824d479433e1e75a0091f510093c68b8fb90b8fbfd221',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:40'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845510'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00001587',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': 'c0de8e047fb21dfbea10af5c3b05ad5a1407045d24fe173a84c8ad8fb7e41743',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:35'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845509'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00002949',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': '9ea718803fdda315e1107e485fb79a0b5e2eb2517fb3bff69d060d94c39605be',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:34'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845509'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00002225',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': 'b387c7f2ed7c9a2af8cfb80e3edd642f5bdfcf2075991270450c7b6c1612d998',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:34'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845508'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00001896',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': 'b9d8f0b81b0ccc85dcaf6912912c69a7b314d1a22756f08867a32fc9f32f68bb',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:32'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845506'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00002824',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': '0299582a53cfed49534064631afb71868ffc99f6191922ed4026cbf4da426cbc',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:31'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845506'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00002106',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': 'b336d4fd403d4fa243b9c3609e1d03d2314be48042b3ed66c4ea24f46a1d8c3f',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:31'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845506'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00000174',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': 'b8171c0b6eb68b1a0a89fa982cfe2c4d9557a892474becbb66a4a1c626da396c',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:31'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845504'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00001103',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': 'b55cb5cf659d321a898381b63f61efd07567c63d39701c07a34ba6bb77fd4fff',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:28'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845503'}, 'type': 'TokensDeposited', 'amountDecimal': '0.0000221',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': '9dbaac59013462471b9e59d189706f0db6a7037bc191f27d3854f52e1a1ff4c5',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:27'},
                 'address': {'address': '0xf919ee77447b7497'}},
                {'block': {'height': '67845503'}, 'type': 'TokensDeposited', 'amountDecimal': '0.00001876',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': '913e1c1bd2b4a2a1f2a39ce98bf9f0eeb6691d17cf36287add7a4984a00e7eed',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 07:53:27'},
                 'address': {'address': '0xf919ee77447b7497'}}], 'outputs': []}}},
            {'data': {'flow': {'blocks': [{'height': '67845566'}], 'inputs': [
                {'block': {'height': '67839613'}, 'type': 'TokensDeposited', 'amountDecimal': '2793.99999',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': '887af6ae89deb52a73db3cd3f0228ef56920df5607e47436bb1392d81ebd506c',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 05:50:31'},
                 'address': {'address': '0x27ebe9e8b2072681'}},
                {'block': {'height': '67837693'}, 'type': 'TokensDeposited', 'amountDecimal': '54.4743511',
                 'currency': {'name': 'FlowToken', 'address': 'A.1654653399040a61.FlowToken'},
                 'transferReason': 'fungible_token_transfer',
                 'transaction': {'id': 'b588d31f30d6fc99f2eb2a38c986c714c3df5619d5d4ee68b4250a15de2934c9',
                                 'statusCode': 0}, 'time': {'time': '2023-12-16 05:10:25'},
                 'address': {'address': '0x27ebe9e8b2072681'}}], 'outputs': []}}}
        ]

        self.api.request = Mock(side_effect=address_txs_mock_responses)
        FlowExplorerInterface.address_txs_apis[0] = self.api
        expected_addresses_txs = [[],
                                  [{'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': '48c568f797cc92897c06378325d954bfcff79a3b985cd7128280247d2882f220',
                                    'block': 67845528,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 58, tzinfo=UTC),
                                    'value': Decimal('0.00002979'), 'confirmations': 1, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': '8978dc7aa6a298e32aff592af7f7c621f2ab04cbabb5b04a4edcbd2c0454abb2',
                                    'block': 67845527,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 57, tzinfo=UTC),
                                    'value': Decimal('0.00001652'), 'confirmations': 2, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': '82e987443b111dfbeedf0baf73a8f23ca483b136310cb7e49fa40121f55c14eb',
                                    'block': 67845527,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 57, tzinfo=UTC),
                                    'value': Decimal('0.00001552'), 'confirmations': 2, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': 'd8363108cb93dcca8113209725a8a9cd97a85b89c7ea9882ab61e03f1879c1ec',
                                    'block': 67845527,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 57, tzinfo=UTC),
                                    'value': Decimal('0.00000858'), 'confirmations': 2, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': 'd79096d95266ef0cbe2d3422f6bee5121b3d667072f86165645dd1750a3ca9d9',
                                    'block': 67845526,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 55, tzinfo=UTC),
                                    'value': Decimal('0.00000948'), 'confirmations': 3, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': '81d64c0fc979a1ff24bb9a0f8929afab6ea443b429995501ba00ea65edb408b2',
                                    'block': 67845526,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 55, tzinfo=UTC),
                                    'value': Decimal('0.00002874'), 'confirmations': 3, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': 'b9496f6817a0d6a692542e952dc874a831344593e419a85a15f6bc639c56e514',
                                    'block': 67845525,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 54, tzinfo=UTC),
                                    'value': Decimal('0.00002176'), 'confirmations': 4, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': 'b050befd85bc31e01f4af4f9edf18bebb43bddd1031709c8a86d91ac1b2338f4',
                                    'block': 67845522,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 50, tzinfo=UTC),
                                    'value': Decimal('0.00002949'), 'confirmations': 7, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': 'fbbadd5d062f80db7918ba972316254e8817d9c51f6c62688d3f5e3a3605df73',
                                    'block': 67845520,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 48, tzinfo=UTC),
                                    'value': Decimal('0.00002196'), 'confirmations': 9, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': '8485c1f1d9ba64e1c8b260dc4a2f8f3cf71b4602e7473202c7ef864677795863',
                                    'block': 67845519,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 47, tzinfo=UTC),
                                    'value': Decimal('0.00003099'), 'confirmations': 10, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': 'f31a0d82ab4cdc853de942bb22fd39b98f4705ba73fa51049ecfb2fe3786d704',
                                    'block': 67845519,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 47, tzinfo=UTC),
                                    'value': Decimal('0.00000818'), 'confirmations': 10, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': 'bf956e36e21e53713df14a830cb3dc0682304e45602682f1e15a63c0510ca691',
                                    'block': 67845518,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 46, tzinfo=UTC),
                                    'value': Decimal('0.00001377'), 'confirmations': 11, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': 'd2cd7df03df985e9b42849d1090d75727a5c77f0e097a57a5b5353ce66dd4f31',
                                    'block': 67845515,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 42, tzinfo=UTC),
                                    'value': Decimal('0.00006328'), 'confirmations': 14, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': '0505d0a3a8d5a48d830602ef30b7538851dca1290c37727077f0e74b2ccf814a',
                                    'block': 67845513,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 40, tzinfo=UTC),
                                    'value': Decimal('0.00000404'), 'confirmations': 16, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': '99be25a017787d4bcfb824d479433e1e75a0091f510093c68b8fb90b8fbfd221',
                                    'block': 67845513,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 40, tzinfo=UTC),
                                    'value': Decimal('0.00000983'), 'confirmations': 16, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': 'c0de8e047fb21dfbea10af5c3b05ad5a1407045d24fe173a84c8ad8fb7e41743',
                                    'block': 67845510,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 35, tzinfo=UTC),
                                    'value': Decimal('0.00001587'), 'confirmations': 19, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': '9ea718803fdda315e1107e485fb79a0b5e2eb2517fb3bff69d060d94c39605be',
                                    'block': 67845509,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 34, tzinfo=UTC),
                                    'value': Decimal('0.00002949'), 'confirmations': 20, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': 'b387c7f2ed7c9a2af8cfb80e3edd642f5bdfcf2075991270450c7b6c1612d998',
                                    'block': 67845509,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 34, tzinfo=UTC),
                                    'value': Decimal('0.00002225'), 'confirmations': 20, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': 'b9d8f0b81b0ccc85dcaf6912912c69a7b314d1a22756f08867a32fc9f32f68bb',
                                    'block': 67845508,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 32, tzinfo=UTC),
                                    'value': Decimal('0.00001896'), 'confirmations': 21, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': '0299582a53cfed49534064631afb71868ffc99f6191922ed4026cbf4da426cbc',
                                    'block': 67845506,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 31, tzinfo=UTC),
                                    'value': Decimal('0.00002824'), 'confirmations': 23, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': 'b336d4fd403d4fa243b9c3609e1d03d2314be48042b3ed66c4ea24f46a1d8c3f',
                                    'block': 67845506,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 31, tzinfo=UTC),
                                    'value': Decimal('0.00002106'), 'confirmations': 23, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': 'b8171c0b6eb68b1a0a89fa982cfe2c4d9557a892474becbb66a4a1c626da396c',
                                    'block': 67845506,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 31, tzinfo=UTC),
                                    'value': Decimal('0.00000174'), 'confirmations': 23, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': 'b55cb5cf659d321a898381b63f61efd07567c63d39701c07a34ba6bb77fd4fff',
                                    'block': 67845504,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 28, tzinfo=UTC),
                                    'value': Decimal('0.00001103'), 'confirmations': 25, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': '9dbaac59013462471b9e59d189706f0db6a7037bc191f27d3854f52e1a1ff4c5',
                                    'block': 67845503,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 27, tzinfo=UTC),
                                    'value': Decimal('0.0000221'), 'confirmations': 26, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0xf919ee77447b7497', 'from_address': [],
                                    'hash': '913e1c1bd2b4a2a1f2a39ce98bf9f0eeb6691d17cf36287add7a4984a00e7eed',
                                    'block': 67845503,
                                    'timestamp': datetime.datetime(2023, 12, 16, 7, 53, 27, tzinfo=UTC),
                                    'value': Decimal('0.00001876'), 'confirmations': 26, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None}
                                   ],
                                  [{'contract_address': None, 'address': '0x27ebe9e8b2072681', 'from_address': [],
                                    'hash': '887af6ae89deb52a73db3cd3f0228ef56920df5607e47436bb1392d81ebd506c',
                                    'block': 67839613,
                                    'timestamp': datetime.datetime(2023, 12, 16, 5, 50, 31, tzinfo=UTC),
                                    'value': Decimal('2793.99999'), 'confirmations': 5954, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None},
                                   {'contract_address': None, 'address': '0x27ebe9e8b2072681', 'from_address': [],
                                    'hash': 'b588d31f30d6fc99f2eb2a38c986c714c3df5619d5d4ee68b4250a15de2934c9',
                                    'block': 67837693,
                                    'timestamp': datetime.datetime(2023, 12, 16, 5, 10, 25, tzinfo=UTC),
                                    'value': Decimal('54.4743511'), 'confirmations': 7874, 'is_double_spend': False,
                                    'details': {}, 'tag': None, 'huge': False, 'invoice': None}
                                   ]
                                  ]
        for address, expected_address_txs in zip(self.address_txs, expected_addresses_txs):
            address_txs = BlockchainExplorer.get_wallet_transactions(address, Currencies.flow, 'FLOW')
            assert len(expected_address_txs) == len(address_txs.get(Currencies.flow))
            for expected_address_tx, address_tx in zip(expected_address_txs, address_txs.get(Currencies.flow)):
                assert address_tx.confirmations >= expected_address_tx.get('confirmations')
                address_tx.confirmations = expected_address_tx.get('confirmations')
                assert address_tx.__dict__ == expected_address_tx

    def test_get_blocks_txs(self):
        blocks_txs_mock_response = [
            {'data': {'flow': {'blocks': [{'height': '60331509'}]}}},
            {'data': {'flow': {'inputs': [], 'outputs': [{'time': {'time': '2023-09-05 18:38:06'}, 'transaction': {
                'id': '6866ea62edbce43296f1d3839becb96705d1a37d866454c7fcedeb28b915d718', 'statusCode': 0},
                                                          'transferReason': 'fungible_token_transfer',
                                                          'currency': {'name': 'FlowToken',
                                                                       'address': 'A.1654653399040a61.FlowToken'},
                                                          'type': 'TokensWithdrawn', 'amountDecimal': '0.00002041',
                                                          'address': {'address': '0x18eb4ee6b3c026d2'},
                                                          'block': {'height': '60331505'}},
                                                         {'time': {'time': '2023-09-05 18:38:06'}, 'transaction': {
                                                             'id': '8d3d8febd186b008726c001497e504ae76e85e4ad4b49859f2bb38f35dc1b448',
                                                             'statusCode': 0},
                                                          'transferReason': 'fungible_token_transfer',
                                                          'currency': {'name': 'FlowToken',
                                                                       'address': 'A.1654653399040a61.FlowToken'},
                                                          'type': 'TokensWithdrawn', 'amountDecimal': '0.0000252',
                                                          'address': {'address': '0xecfad18ba9582d4f'},
                                                          'block': {'height': '60331505'}},
                                                         {'time': {'time': '2023-09-05 18:38:06'}, 'transaction': {
                                                             'id': 'b6b6e41777daa22d29f7a4cd9e4e0dae0795e545efe07be51cf84ec76125daa7',
                                                             'statusCode': 0},
                                                          'transferReason': 'fungible_token_transfer',
                                                          'currency': {'name': 'FlowToken',
                                                                       'address': 'A.1654653399040a61.FlowToken'},
                                                          'type': 'TokensWithdrawn', 'amountDecimal': '0.00000728',
                                                          'address': {'address': '0x18eb4ee6b3c026d2'},
                                                          'block': {'height': '60331505'}},
                                                         {'time': {'time': '2023-09-05 18:38:11'}, 'transaction': {
                                                             'id': '396c170a128069cf6eb0ebeee8b8cb7ee440b7a187292fefe89ec75c11a8cf6f',
                                                             'statusCode': 0},
                                                          'transferReason': 'fungible_token_transfer',
                                                          'currency': {'name': 'FlowToken',
                                                                       'address': 'A.1654653399040a61.FlowToken'},
                                                          'type': 'TokensWithdrawn', 'amountDecimal': '0.000025',
                                                          'address': {'address': '0xecfad18ba9582d4f'},
                                                          'block': {'height': '60331508'}},
                                                         {'time': {'time': '2023-09-05 18:38:11'}, 'transaction': {
                                                             'id': 'be702d03b7897537a0346c233dfc966524195a7bfb7056200bd61f278da716c0',
                                                             'statusCode': 0},
                                                          'transferReason': 'fungible_token_transfer',
                                                          'currency': {'name': 'FlowToken',
                                                                       'address': 'A.1654653399040a61.FlowToken'},
                                                          'type': 'TokensWithdrawn', 'amountDecimal': '0.00000274',
                                                          'address': {'address': '0x1b65c33d7a352c61'},
                                                          'block': {'height': '60331509'}}]}}}
        ]
        cache.delete('latest_block_height_processed_flow')
        settings.USE_TESTNET_BLOCKCHAINS = False
        FlowExplorerInterface.block_txs_apis[0] = self.api
        self.api.request = Mock(side_effect=blocks_txs_mock_response)
        txs_addresses, txs_info, _ = BlockchainExplorer.get_latest_block_addresses('FLOW', None, None, True, True)
        expected_txs_addresses = {
            'output_addresses': set(),
            'input_addresses': {'0x18eb4ee6b3c026d2', '0x1b65c33d7a352c61', '0xecfad18ba9582d4f'}}
        expected_txs_info = {
            'outgoing_txs': {
                '0x18eb4ee6b3c026d2': {Currencies.flow: [{
                    'symbol': 'FLOW',
                    'block_height': 60331505,
                    'contract_address': None,
                    'tx_hash': '6866ea62edbce43296f1d3839becb96705d1a37d866454c7fcedeb28b915d718',
                    'value': Decimal('0.00002041')},
                    {
                        'symbol': 'FLOW',
                        'block_height': 60331505,
                        'contract_address': None,
                        'tx_hash': 'b6b6e41777daa22d29f7a4cd9e4e0dae0795e545efe07be51cf84ec76125daa7',
                        'value': Decimal(
                            '0.00000728')}]},
                '0xecfad18ba9582d4f': {Currencies.flow: [{
                    'symbol': 'FLOW',
                    'block_height': 60331505,
                    'contract_address': None,
                    'tx_hash': '8d3d8febd186b008726c001497e504ae76e85e4ad4b49859f2bb38f35dc1b448',
                    'value': Decimal('0.0000252')},
                    {'symbol': 'FLOW',
                     'block_height': 60331508,
                     'contract_address': None,
                     'tx_hash': '396c170a128069cf6eb0ebeee8b8cb7ee440b7a187292fefe89ec75c11a8cf6f',
                     'value': Decimal(
                         '0.000025')}]},
                '0x1b65c33d7a352c61': {Currencies.flow: [{
                    'symbol': 'FLOW',
                    'block_height': 60331509,
                    'contract_address': None,
                    'tx_hash': 'be702d03b7897537a0346c233dfc966524195a7bfb7056200bd61f278da716c0',
                    'value': Decimal('0.00000274')}]}

            },
            'incoming_txs': {
            }
        }
        assert BlockchainUtilsMixin.compare_dicts_without_order(expected_txs_addresses, txs_addresses)
        for key, value in txs_info.get('outgoing_txs').items():
            for pair in expected_txs_info.get('outgoing_txs'):
                if key == pair:
                    assert value.get(Currencies.flow) == expected_txs_info.get('outgoing_txs').get(pair).get(
                        Currencies.flow)
        for key, value in txs_info.get('incoming_txs').items():
            for pair in expected_txs_info.get('incoming_txs'):
                if key == pair:
                    assert value.get(Currencies.flow) == expected_txs_info.get('incoming_txs').get(pair).get(
                        Currencies.flow)
