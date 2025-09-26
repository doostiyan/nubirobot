import pytest
import datetime
from decimal import Decimal
from unittest import TestCase
from exchange.base.models import Currencies
from exchange.blockchain.api.ada.cardano_bitquery_new import BitQueryCardanoApi
from exchange.blockchain.api.ada.cardano_explorer_interface import CardanoExplorerInterface
from exchange.blockchain.apis_conf import APIS_CONF
from exchange.blockchain.tests.api.general_test.general_test_from_explorer import TestFromExplorer


class TestCardanoApiCalls(TestCase):
    api = BitQueryCardanoApi
    balance_address = ['DdzFFzCqrhszAisfe4k7wNnA8Ue4L3AyHVpdeewZkyrfScRqRptz6RxzzVdbvYNscoq7cWyz69sECE2tKwC7gKFiqu5dzLZfTs3ez1xy']
    account_address = ['addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq']
    txs_hash = ['bd45860549399c69bcb1eba0811fc6aa9dcbc88491c9950e096a0af63c9b4b75']

    blocks = [(10572331, 10572332)]

    @pytest.mark.slow
    def test_get_balance_api(self):
        for account_address in self.balance_address:
            get_balance_result = self.api.get_balance(account_address)
            assert isinstance(get_balance_result, dict)
            assert isinstance(get_balance_result.get('data'), dict)
            assert isinstance(get_balance_result.get('data').get('cardano'), dict)
            assert isinstance(get_balance_result.get('data').get('cardano').get('address'), list)
            assert isinstance(get_balance_result.get('data').get('cardano').get('address')[0], dict)
            assert isinstance(get_balance_result.get('data').get('cardano').get('address')[0].get('balance'), list)
            assert isinstance(get_balance_result.get('data').get('cardano').get('address')[0].get('balance')[0], dict)
            assert isinstance(get_balance_result.get('data').get('cardano').get('address')[0].get('balance')[0]
                              .get('currency'), dict)
            assert isinstance(get_balance_result.get('data').get('cardano').get('address')[0].get('balance')[0]
                              .get('currency').get('symbol'), str)
            assert isinstance(get_balance_result.get('data').get('cardano').get('address')[0].get('balance')[0]
                              .get('value'), float)

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_result = self.api.get_block_head()
        assert isinstance(get_block_head_result, dict)
        assert isinstance(get_block_head_result.get('data'), dict)
        assert isinstance(get_block_head_result.get('data').get('cardano'), dict)
        assert isinstance(get_block_head_result.get('data').get('cardano').get('blocks'), list)
        assert isinstance(get_block_head_result.get('data').get('cardano').get('blocks')[0], dict)
        assert isinstance(get_block_head_result.get('data').get('cardano').get('blocks')[0].get('height'), int)

    @pytest.mark.slow
    def test_get_tx_details_api(self):
        get_tx_details_result = self.api.get_tx_details_batch(self.txs_hash)
        assert isinstance(get_tx_details_result, dict)
        assert isinstance(get_tx_details_result.get('data'), dict)
        assert isinstance(get_tx_details_result.get('data').get('cardano'), dict)
        assert isinstance(get_tx_details_result.get('data').get('cardano').get('blocks'), list)
        assert isinstance(get_tx_details_result.get('data').get('cardano').get('blocks')[0].get('height'), int)

        assert isinstance(get_tx_details_result.get('data').get('cardano').get('transactions'), list)
        key2check_transaction = [('block', dict), ('hash', str), ('feeValue', float)]
        for key, value in key2check_transaction:
            for tx in get_tx_details_result.get('data').get('cardano').get('transactions'):
                assert isinstance(tx.get(key), value)

        assert isinstance(get_tx_details_result.get('data').get('cardano').get('inputs'), list)
        key2check_inputs = [('transaction', dict), ('block', dict), ('inputAddress', dict), ('currency', dict)]
        for key, value in key2check_inputs:
            for input_ in get_tx_details_result.get('data').get('cardano').get('inputs'):
                assert isinstance(input_.get(key), value)

        assert isinstance(get_tx_details_result.get('data').get('cardano').get('outputs'), list)
        key2check_inputs = [('transaction', dict), ('block', dict), ('outputAddress', dict), ('currency', dict)]
        for key, value in key2check_inputs:
            for output_ in get_tx_details_result.get('data').get('cardano').get('outputs'):
                assert isinstance(output_.get(key), value)

    @pytest.mark.slow
    def test_get_address_txs_api(self):
        for address in self.account_address:
            address_txs_result = self.api.get_address_txs(address)
            assert isinstance(address_txs_result, dict)
            assert isinstance(address_txs_result.get('data'), dict)
            assert isinstance(address_txs_result.get('data').get('cardano'), dict)
            assert isinstance(address_txs_result.get('data').get('cardano').get('blocks'), list)
            assert isinstance(address_txs_result.get('data').get('cardano').get('blocks')[0].get('height'), int)
            assert isinstance(address_txs_result.get('data').get('cardano').get('inputs'), list)
            key2check_inputs = [('transaction', dict), ('block', dict), ('inputAddress', dict)]
            for key, value in key2check_inputs:
                for input_ in address_txs_result.get('data').get('cardano').get('inputs'):
                    assert isinstance(input_.get(key), value)

            assert isinstance(address_txs_result.get('data').get('cardano').get('outputs'), list)
            key2check_inputs = [('transaction', dict), ('block', dict), ('outputAddress', dict)]
            for key, value in key2check_inputs:
                for output_ in address_txs_result.get('data').get('cardano').get('outputs'):
                    assert isinstance(output_.get(key), value)


class TestCardanoFromExplorer(TestFromExplorer):
    api = BitQueryCardanoApi
    addresses = [
        'DdzFFzCqrhszAisfe4k7wNnA8Ue4L3AyHVpdeewZkyrfScRqRptz6RxzzVdbvYNscoq7cWyz69sECE2tKwC7gKFiqu5dzLZfTs3ez1xy']
    txs_addresses = [
        'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq']
    txs_hash = ['206485c0d8e3893bc534782c3665d0bfa6f03f9c7b6d4df16fb4fe4eeb329f57']
    explorerInterface = CardanoExplorerInterface
    currencies = Currencies.ada
    symbol = 'ADA'

    @classmethod
    def test_get_balance(cls):
        APIS_CONF['ADA']['get_balances'] = 'ada_explorer_interface'
        balance_mock_responses = [{
            'data': {'cardano': {'address': [{'balance': [
                {'currency': {'address': '', 'symbol': 'ADA', 'tokenType': ''}, 'value': 79212.743262}]}]}}}]
        expected_balances = [
            {
                'address': 'DdzFFzCqrhszAisfe4k7wNnA8Ue4L3AyHVpdeewZkyrfScRqRptz6RxzzVdbvYNscoq7cWyz69sECE2tKwC7gKFiqu5dzLZfTs3ez1xy',
                'balance': Decimal('79212.743262'),
                'received': Decimal('79212.743262'),
                'rewarded': Decimal('0'),
                'sent': Decimal('0')
            }
        ]
        cls.get_balance(balance_mock_responses, expected_balances)

    @classmethod
    def test_get_tx_details(cls):
        APIS_CONF['ADA']['txs_details'] = 'ada_explorer_interface'
        cls.api.TRANSACTION_DETAILS_BATCH = True
        tx_details_mock_responses = [
            {'data': {'cardano': {'blocks': [{'height': 10570815}]}}},
            {'data': {
                'cardano': {
                    'blocks': [{'height': 10570815}],
                    'transactions': [
                        {'block': {'height': 10568207, 'timestamp': {'time': '2024-07-13T16:23:16Z'}},
                         'index': '24',
                         'hash': '206485c0d8e3893bc534782c3665d0bfa6f03f9c7b6d4df16fb4fe4eeb329f57',
                         'feeValue': 0.228785,
                         'includedAt': {
                             'time': '2024-07-13T16:23:16Z'}}],
                    'outputs': [{'outputIndex': 0, 'transaction': {
                        'hash': '206485c0d8e3893bc534782c3665d0bfa6f03f9c7b6d4df16fb4fe4eeb329f57'},
                                 'block': {'height': 10568207,
                                           'timestamp': {
                                               'time': '2024-07-13T16:23:16Z'}},
                                 'outputAddress': {
                                     'address': 'addr1q8u9r5uaa5lsl2vrd979htq6c7mslx5hsnteqz7rjnp92kr5e04vm5h6ln9pplarzjdtp8grwl5ntjk9693twyh9xzeqctht6m'},
                                 'value': 1.45247,
                                 'currency': {'symbol': 'ADA'}},
                                {'outputIndex': 1, 'transaction': {
                                    'hash': '206485c0d8e3893bc534782c3665d0bfa6f03f9c7b6d4df16fb4fe4eeb329f57'},
                                 'block': {'height': 10568207,
                                           'timestamp': {
                                               'time': '2024-07-13T16:23:16Z'}},
                                 'outputAddress': {
                                     'address': 'addr1z8d70g7c58vznyye9guwagdza74x36f3uff0eyk2zwpcpxm5e04vm5h6ln9pplarzjdtp8grwl5ntjk9693twyh9xzeq22kq5u'},
                                 'value': 102.5,
                                 'currency': {'symbol': 'ADA'}},
                                {'outputIndex': 2, 'transaction': {
                                    'hash': '206485c0d8e3893bc534782c3665d0bfa6f03f9c7b6d4df16fb4fe4eeb329f57'},
                                 'block': {'height': 10568207,
                                           'timestamp': {
                                               'time': '2024-07-13T16:23:16Z'}},
                                 'outputAddress': {
                                     'address': 'addr1q8l7hny7x96fadvq8cukyqkcfca5xmkrvfrrkt7hp76v3qvssm7fz9ajmtd58ksljgkyvqu6gl23hlcfgv7um5v0rn8qtnzlfk'},
                                 'value': 1.0,
                                 'currency': {'symbol': 'ADA'}},
                                {'outputIndex': 3, 'transaction': {
                                    'hash': '206485c0d8e3893bc534782c3665d0bfa6f03f9c7b6d4df16fb4fe4eeb329f57'},
                                 'block': {'height': 10568207,
                                           'timestamp': {
                                               'time': '2024-07-13T16:23:16Z'}},
                                 'outputAddress': {
                                     'address': 'addr1q8u9r5uaa5lsl2vrd979htq6c7mslx5hsnteqz7rjnp92kr5e04vm5h6ln9pplarzjdtp8grwl5ntjk9693twyh9xzeqctht6m'},
                                 'value': 45.323541,
                                 'currency': {'symbol': 'ADA'}}],
                    'inputs': [{'inputIndex': 0, 'transaction': {
                        'hash': '206485c0d8e3893bc534782c3665d0bfa6f03f9c7b6d4df16fb4fe4eeb329f57'},
                                'block': {'height': 10568207,
                                          'timestamp': {'time': '2024-07-13T16:23:16Z'}},
                                'inputAddress': {
                                    'address': 'addr1q8u9r5uaa5lsl2vrd979htq6c7mslx5hsnteqz7rjnp92kr5e04vm5h6ln9pplarzjdtp8grwl5ntjk9693twyh9xzeqctht6m',
                                    'annotation': None}, 'value': 54.236009,
                                'currency': {'symbol': 'ADA'}},
                               {'inputIndex': 1, 'transaction': {
                                   'hash': '206485c0d8e3893bc534782c3665d0bfa6f03f9c7b6d4df16fb4fe4eeb329f57'},
                                'block': {'height': 10568207,
                                          'timestamp': {
                                              'time': '2024-07-13T16:23:16Z'}},
                                'inputAddress': {
                                    'address': 'addr1q8u9r5uaa5lsl2vrd979htq6c7mslx5hsnteqz7rjnp92kr5e04vm5h6ln9pplarzjdtp8grwl5ntjk9693twyh9xzeqctht6m',
                                    'annotation': None}, 'value': 1.2068,
                                'currency': {'symbol': 'ADA'}},
                               {'inputIndex': 2, 'transaction': {
                                   'hash': '206485c0d8e3893bc534782c3665d0bfa6f03f9c7b6d4df16fb4fe4eeb329f57'},
                                'block': {'height': 10568207,
                                          'timestamp': {'time': '2024-07-13T16:23:16Z'}},
                                'inputAddress': {
                                    'address': 'addr1q8u9r5uaa5lsl2vrd979htq6c7mslx5hsnteqz7rjnp92kr5e04vm5h6ln9pplarzjdtp8grwl5ntjk9693twyh9xzeqctht6m',
                                    'annotation': None}, 'value': 95.061987,
                                'currency': {'symbol': 'ADA'}}]}}}
        ]
        expected_txs_details = [
            {'hash': '206485c0d8e3893bc534782c3665d0bfa6f03f9c7b6d4df16fb4fe4eeb329f57', 'success': True,
             'block': 10568207, 'date': datetime.datetime(2024, 7, 13, 16, 23, 16, tzinfo=datetime.timezone.utc),
             'fees': None,
             'memo': None, 'confirmations': 2608, 'raw': None, 'inputs': [], 'outputs': [],
             'transfers': [
                 {'type': 'MainCoin', 'symbol': 'ADA', 'currency': 21,
                  'from': 'addr1q8u9r5uaa5lsl2vrd979htq6c7mslx5hsnteqz7rjnp92kr5e04vm5h6ln9pplarzjdtp8grwl5ntjk9693twyh9xzeqctht6m',
                  'to': '',
                  'value': Decimal('103.728785'), 'is_valid': True, 'token': None, 'memo': None},
                 {'type': 'MainCoin', 'symbol': 'ADA', 'currency': 21, 'from': '',
                  'to': 'addr1z8d70g7c58vznyye9guwagdza74x36f3uff0eyk2zwpcpxm5e04vm5h6ln9pplarzjdtp8grwl5ntjk9693twyh9xzeq22kq5u',
                  'value': Decimal('102.5'), 'is_valid': True, 'token': None,  'memo': None},
                 {'type': 'MainCoin', 'symbol': 'ADA', 'currency': 21, 'from': '',
                  'to': 'addr1q8l7hny7x96fadvq8cukyqkcfca5xmkrvfrrkt7hp76v3qvssm7fz9ajmtd58ksljgkyvqu6gl23hlcfgv7um5v0rn8qtnzlfk',
                  'value': Decimal('1.0'), 'is_valid': True, 'token': None,  'memo': None}]}
        ]
        cls.get_tx_details(tx_details_mock_responses, expected_txs_details)

        cls.txs_hash = ['bd45860549399c69bcb1eba0811fc6aa9dcbc88491c9950e096a0af63c9b4b75']
        tx_details_mock_responses2 = [
            {'data': {'cardano': {'blocks': [{'height': 10570815}]}}},
            {
                'data': {
                    'cardano': {
                        'blocks': [{'height': 7088224}],
                        'transactions': [
                            {
                                'block': {
                                    'height': 7088217,
                                    'timestamp': {'time': '2022-04-06T03:14:56Z'},
                                },
                                'index': '36',
                                'hash': 'bd45860549399c69bcb1eba0811fc6aa9dcbc88491c9950e096a0af63c9b4b75',
                                'feeValue': 0.169021,
                                'includedAt': {'time': '2022-04-06T03:14:56Z'},
                            }
                        ],
                        'outputs': [
                            {
                                'outputIndex': 0,
                                'transaction': {
                                    'hash': 'bd45860549399c69bcb1eba0811fc6aa9dcbc88491c9950e096a0af63c9b4b75'
                                },
                                'block': {
                                    'height': 7088217,
                                    'timestamp': {'time': '2022-04-06T03:14:56Z'},
                                },
                                'outputAddress': {
                                    'address': 'addr1qyuztplghtqavnzc8prwnvhnsqhmtv477qmptdmwefd3gg05h3lus0z66jkpaxsy6w2vwwjs5vyj0tf4ckax4shxnkmszvvfff'
                                },
                                'value': 1999.0,
                                'currency': {'symbol': 'ADA'},
                            },
                            {
                                'outputIndex': 1,
                                'transaction': {
                                    'hash': 'bd45860549399c69bcb1eba0811fc6aa9dcbc88491c9950e096a0af63c9b4b75'
                                },
                                'block': {
                                    'height': 7088217,
                                    'timestamp': {'time': '2022-04-06T03:14:56Z'},
                                },
                                'outputAddress': {
                                    'address': 'addr1qyg8zvftl2dwtgr8xxf5dnmkune0prp243wcrkwh2t3dv8evep55nfane06hggrc2gvnpdj4gcf26kzhkd3fs874hzhs5432hv'
                                },
                                'value': 55162.94816,
                                'currency': {'symbol': 'ADA'},
                            },
                        ],
                        'inputs': [
                            {
                                'inputIndex': 0,
                                'transaction': {
                                    'hash': 'bd45860549399c69bcb1eba0811fc6aa9dcbc88491c9950e096a0af63c9b4b75'
                                },
                                'block': {
                                    'height': 7088217,
                                    'timestamp': {'time': '2022-04-06T03:14:56Z'},
                                },
                                'inputAddress': {
                                    'address': 'addr1q9n5zzvlu02xm2gfqghyq9mqj3a7mr4kv2htwv6dhh2e5lpvep55nfane06hggrc2gvnpdj4gcf26kzhkd3fs874hzhsju4lg7',
                                    'annotation': None,
                                },
                                'value': 57162.117181,
                                'currency': {'symbol': 'ADA'},
                            }
                        ],
                    }
                }
            }
        ]
        expected_txs_details2 = [
            {'hash': 'bd45860549399c69bcb1eba0811fc6aa9dcbc88491c9950e096a0af63c9b4b75',
             'success': True,
             'block': 7088217,
             'date': datetime.datetime(2022, 4, 6, 3, 14, 56, tzinfo=datetime.timezone.utc),
             'fees': None,
             'memo': None,
             'confirmations': 3482598,
             'raw': None,
             'inputs': [],
             'outputs': [],
             'transfers': [
                 {'type': 'MainCoin', 'symbol': 'ADA', 'currency': 21,
                  'from': 'addr1q9n5zzvlu02xm2gfqghyq9mqj3a7mr4kv2htwv6dhh2e5lpvep55nfane06hggrc2gvnpdj4gcf26kzhkd3fs874hzhsju4lg7',
                  'to': '',
                  'value': Decimal('57162.117181'), 'is_valid': True, 'token': None,  'memo': None},
                 {'type': 'MainCoin', 'symbol': 'ADA', 'currency': 21, 'from': '',
                  'to': 'addr1qyuztplghtqavnzc8prwnvhnsqhmtv477qmptdmwefd3gg05h3lus0z66jkpaxsy6w2vwwjs5vyj0tf4ckax4shxnkmszvvfff',
                  'value': Decimal('1999.0'), 'is_valid': True, 'token': None,  'memo': None},
                 {'type': 'MainCoin', 'symbol': 'ADA', 'currency': 21, 'from': '',
                  'to': 'addr1qyg8zvftl2dwtgr8xxf5dnmkune0prp243wcrkwh2t3dv8evep55nfane06hggrc2gvnpdj4gcf26kzhkd3fs874hzhs5432hv',
                  'value': Decimal('55162.94816'), 'is_valid': True, 'token': None,  'memo': None}]}
        ]
        cls.get_tx_details(tx_details_mock_responses2, expected_txs_details2)

    @classmethod
    def test_get_address_txs(cls):
        APIS_CONF['ADA']['get_txs'] = 'ada_explorer_interface'
        address_txs_mock_response = [
            {'data': {'cardano': {'blocks': [{'height': 10571706}]}}},
            {'data': {'cardano': {
                'outputs': [
                    {'block': {'height': 10571081, 'timestamp': {'time': '2024-07-14T08:36:17Z'}},
                     'transaction': {'hash': '13cbf66386e24fcada40d216ef95de3bd1a0fd522019e6e37665bda7725d587f'},
                     'outputAddress': {
                         'address': 'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq'},
                     'value': 999.841432},
                    {'block': {'height': 10571052, 'timestamp': {'time': '2024-07-14T08:24:23Z'}},
                     'transaction': {
                         'hash': '3f5f201912d095bd2663d0485a890cd38d4229bd6a354bc08183f0e112e137ec'},
                     'outputAddress': {
                         'address': 'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq'},
                     'value': 1002.758623}],
                'inputs': [
                    {'block': {'height': 10571084, 'timestamp': {'time': '2024-07-14T08:36:31Z'}},
                     'transaction': {'hash': '1ce151f58225c0236197a1267f1907787e58c4ae61444c0fd5815aa1d94d5c75'},
                     'inputAddress': {
                         'address': 'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq'},
                     'value': 999.841432},
                    {'block': {'height': 10571054, 'timestamp': {'time': '2024-07-14T08:24:53Z'}},
                     'transaction': {
                         'hash': '1771d7c0def86b707e81fdbc5b235570cbe70a95b9346ab97fe20b1fb80448d0'},
                     'inputAddress': {
                         'address': 'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq'},
                     'value': 1002.758623}],
                'blocks': [{'height': 10571706}]}}}
        ]
        expected_address_txs = [
            [{'contract_address': None,
             'address': 'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq',
             'from_address': [
                 'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq'],
             'hash': '1ce151f58225c0236197a1267f1907787e58c4ae61444c0fd5815aa1d94d5c75', 'block': 10571084,
             'timestamp': datetime.datetime(2024, 7, 14, 8, 36, 31, tzinfo=datetime.timezone.utc), 'value': Decimal(
                '-999.841432'), 'confirmations': 622, 'is_double_spend': False, 'details': {}, 'tag': None,
             'huge': False, 'invoice': None},
            {
                'contract_address': None,
                'address': 'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq',
                'from_address': [
                    'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq'],
                'hash': '1771d7c0def86b707e81fdbc5b235570cbe70a95b9346ab97fe20b1fb80448d0', 'block': 10571054,
                'timestamp': datetime.datetime(2024, 7, 14, 8, 24, 53, tzinfo=datetime.timezone.utc), 'value': Decimal(
                '-1002.758623'), 'confirmations': 652, 'is_double_spend': False, 'details': {}, 'tag': None,
                'huge': False, 'invoice': None},
            {
                'contract_address': None,
                'address': 'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq',
                'from_address': [], 'hash': '13cbf66386e24fcada40d216ef95de3bd1a0fd522019e6e37665bda7725d587f',
                'block': 10571081,
                'timestamp': datetime.datetime(2024, 7, 14, 8, 36, 17, tzinfo=datetime.timezone.utc), 'value': Decimal(
                '999.841432'), 'confirmations': 625, 'is_double_spend': False, 'details': {}, 'tag': None,
                'huge': False, 'invoice': None},
            {
                'contract_address': None,
                'address': 'addr1z8p79rpkcdz8x9d6tft0x0dx5mwuzac2sa4gm8cvkw5hcnxxmamn55j2l2l620dvu22rw5ag2gfdddq6sn3aqmy374rs0raldq',
                'from_address': [], 'hash': '3f5f201912d095bd2663d0485a890cd38d4229bd6a354bc08183f0e112e137ec',
                'block': 10571052,
                'timestamp': datetime.datetime(2024, 7, 14, 8, 24, 23, tzinfo=datetime.timezone.utc), 'value': Decimal(
                '1002.758623'), 'confirmations': 654, 'is_double_spend': False, 'details': {}, 'tag': None,
                'huge': False, 'invoice': None}]
        ]
        cls.get_address_txs(address_txs_mock_response, expected_address_txs)

    @classmethod
    def test_get_block_txs(cls):
        APIS_CONF[cls.symbol]['get_blocks_addresses'] = 'ada_explorer_interface'
        block_txs_mock_response = [
            {'data': {'cardano': {'blocks': [{'height': 10570815}]}}},
            {'data': {'cardano': {
                'inputs': [
                    {'transaction': {'hash': 'd3d4838783cc7be37894aa1849c10454d0d3b79f5ec575940ba632afb77b8df8'},
                     'value': 5.472407, 'inputAddress': {
                        'address': 'addr1q9trulz8kyefy4geu2y8xgrrgy954efkhh0pzm9k8408m8z8e7ycs6yf49kaydzwugmq39en0djdljmq2jv70yyz5wwqgmmhs0'},
                     'block': {'height': 10572332, 'timestamp': {'time': '2024-07-14T15:39:42Z'}}}],
                'outputs': [
                    {'transaction': {'hash': 'd3d4838783cc7be37894aa1849c10454d0d3b79f5ec575940ba632afb77b8df8'},
                     'value': 1.28737, 'outputAddress': {
                        'address': 'addr1q9trulz8kyefy4geu2y8xgrrgy954efkhh0pzm9k8408m8z8e7ycs6yf49kaydzwugmq39en0djdljmq2jv70yyz5wwqgmmhs0'},
                     'block': {'height': 10572332, 'timestamp': {'time': '2024-07-14T15:39:42Z'}}},
                    {'transaction': {'hash': 'd3d4838783cc7be37894aa1849c10454d0d3b79f5ec575940ba632afb77b8df8'},
                     'value': 4.0, 'outputAddress': {
                        'address': 'addr1zxn9efv2f6w82hagxqtn62ju4m293tqvw0uhmdl64ch8uw6j2c79gy9l76sdg0xwhd7r0c0kna0tycz4y5s6mlenh8pq6s3z70'},
                     'block': {'height': 10572332, 'timestamp': {'time': '2024-07-14T15:39:42Z'}}}],
                'blocks': [{'height': 10572635}]}}},
            {''}, {''}, {''}, {''}
        ]
        expected_txs_addresses = {
            'input_addresses': {
                'addr1q9trulz8kyefy4geu2y8xgrrgy954efkhh0pzm9k8408m8z8e7ycs6yf49kaydzwugmq39en0djdljmq2jv70yyz5wwqgmmhs0'},
            'output_addresses': {
                'addr1zxn9efv2f6w82hagxqtn62ju4m293tqvw0uhmdl64ch8uw6j2c79gy9l76sdg0xwhd7r0c0kna0tycz4y5s6mlenh8pq6s3z70'}
        }
        expected_txs_info = {
            'outgoing_txs': {
                'addr1q9trulz8kyefy4geu2y8xgrrgy954efkhh0pzm9k8408m8z8e7ycs6yf49kaydzwugmq39en0djdljmq2jv70yyz5wwqgmmhs0': {
                    Currencies.ada: [
                        {'contract_address': None,
                         'tx_hash': 'd3d4838783cc7be37894aa1849c10454d0d3b79f5ec575940ba632afb77b8df8',
                         'value': Decimal('4.185037'),
                         'block_height': 10572332,
                         'symbol': 'ADA'
                         }
                    ]
                }
            },
            'incoming_txs': {
                'addr1zxn9efv2f6w82hagxqtn62ju4m293tqvw0uhmdl64ch8uw6j2c79gy9l76sdg0xwhd7r0c0kna0tycz4y5s6mlenh8pq6s3z70': {
                    Currencies.ada: [
                        {'contract_address': None,
                         'tx_hash': 'd3d4838783cc7be37894aa1849c10454d0d3b79f5ec575940ba632afb77b8df8',
                         'value': Decimal('4.0'),
                         'block_height': 10572332,
                         'symbol': 'ADA'
                         }
                    ]
                }
            }
        }
        cls.get_block_txs(block_txs_mock_response, expected_txs_addresses, expected_txs_info)
