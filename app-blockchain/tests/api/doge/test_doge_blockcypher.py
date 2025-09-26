import datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from django.conf import settings

from exchange.blockchain.api.doge import DogeExplorerInterface
from exchange.blockchain.api.doge.doge_blockcypher_new import DogeBlockcypherApi
from exchange.blockchain.tests.api.general_test.base_test_case import BaseTestCase

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


@pytest.mark.slow
class TestDogeBlockcypherApi(BaseTestCase):
    api = DogeBlockcypherApi

    def test_get_balance(self):
        response = self.api.get_balance('D6iDd199RiVhemnFAKmdc1QFK2X5UnqWc8')
        schema = {
            'balance': int,
            'unconfirmed_balance': int
        }
        self.assert_schema(response, schema)

    def test_tx_details(self):
        response = self.api.get_tx_details('e5847a40ee0c3d2323b0e590aeeb4ff174d176946116e8694bc96fade2364e03')
        schema = {
            'block_hash': str,
            'block_height': int,
            'confirmations': int,
            'hash': str,
            'fees': int,
            'confirmed': str,
            'double_spend': bool,
            'inputs': {
                'addresses': list,
                'script_type': str,
                'output_value': int
            },
            'outputs': {
                'addresses': list,
                'script_type': str,
                'value': int
            }
        }
        self.assert_schema(response, schema)


GET_BALANCE_MOCK_RESPONSE = {'address': 'D6iDd199RiVhemnFAKmdc1QFK2X5UnqWc8', 'total_received': 52260135240,
                             'total_sent': 0, 'balance': 52260135240, 'unconfirmed_balance': 0,
                             'final_balance': 52260135240, 'n_tx': 1, 'unconfirmed_n_tx': 0, 'final_n_tx': 1, 'txs': [
        {'block_hash': 'd39eb2c6f348872845f06295eaf719758204a69b700a53a8a3d9ef1b8d3d1eeb', 'block_height': 5354516,
         'block_index': 3, 'hash': 'e5847a40ee0c3d2323b0e590aeeb4ff174d176946116e8694bc96fade2364e03',
         'addresses': ['D6iDd199RiVhemnFAKmdc1QFK2X5UnqWc8', 'DDz1H7AcqPgmKzFEP3pBHW5b1GWuWEoAAP'],
         'total': 68776794176014, 'fees': 11615496, 'size': 226, 'preference': 'high',
         'relayed_by': '108.239.67.42:22556', 'confirmed': '2024-08-28T07:01:15Z',
         'received': '2024-08-28T06:58:54.452Z', 'ver': 2, 'double_spend': False, 'vin_sz': 1, 'vout_sz': 2,
         'confirmations': 4, 'confidence': 1, 'inputs': [
            {'prev_hash': '444aa8fcebf6158aeb8a6fab540e5cd72d28fd0d581c02c2764e235d9ccb3658', 'output_index': 1,
             'script': '483045022100f6fb86e6df1138fd3a98f53e7cb2c583fec60aa64cf2ffe5b10266b10468520102204175a9de36a706305b8065fc488a909b058274c4adf654f56b2a65fc75a06d5501210308ada4ff67c25f87296d82f236ddeeb994f17cbb5428516e1b62a34078758b40',
             'output_value': 68776805791510, 'sequence': 4294967295,
             'addresses': ['DDz1H7AcqPgmKzFEP3pBHW5b1GWuWEoAAP'], 'script_type': 'pay-to-pubkey-hash', 'age': 5354473}],
         'outputs': [{'value': 52260135240, 'script': '76a914113bc39d343c808d092f9af92361e05a1dc647ce88ac',
                      'addresses': ['D6iDd199RiVhemnFAKmdc1QFK2X5UnqWc8'], 'script_type': 'pay-to-pubkey-hash'},
                     {'value': 68724534040774, 'script': '76a9146100ff1d8c47cbaae0fc96957aea720568657bf188ac',
                      'addresses': ['DDz1H7AcqPgmKzFEP3pBHW5b1GWuWEoAAP'], 'script_type': 'pay-to-pubkey-hash'}]}]}

GET_TX_DETAILS_MOCK_RESPONSE = {'block_hash': 'd39eb2c6f348872845f06295eaf719758204a69b700a53a8a3d9ef1b8d3d1eeb',
                                'block_height': 5354516, 'block_index': 3,
                                'hash': 'e5847a40ee0c3d2323b0e590aeeb4ff174d176946116e8694bc96fade2364e03',
                                'addresses': ['D6iDd199RiVhemnFAKmdc1QFK2X5UnqWc8',
                                              'DDz1H7AcqPgmKzFEP3pBHW5b1GWuWEoAAP'], 'total': 68776794176014,
                                'fees': 11615496, 'size': 226, 'preference': 'high',
                                'relayed_by': '108.239.67.42:22556', 'confirmed': '2024-08-28T07:01:15Z',
                                'received': '2024-08-28T06:58:54.452Z', 'ver': 2, 'double_spend': False, 'vin_sz': 1,
                                'vout_sz': 2, 'confirmations': 4, 'confidence': 1, 'inputs': [
        {'prev_hash': '444aa8fcebf6158aeb8a6fab540e5cd72d28fd0d581c02c2764e235d9ccb3658', 'output_index': 1,
         'script': '483045022100f6fb86e6df1138fd3a98f53e7cb2c583fec60aa64cf2ffe5b10266b10468520102204175a9de36a706305b8065fc488a909b058274c4adf654f56b2a65fc75a06d5501210308ada4ff67c25f87296d82f236ddeeb994f17cbb5428516e1b62a34078758b40',
         'output_value': 68776805791510, 'sequence': 4294967295, 'addresses': ['DDz1H7AcqPgmKzFEP3pBHW5b1GWuWEoAAP'],
         'script_type': 'pay-to-pubkey-hash', 'age': 5354473}], 'outputs': [
        {'value': 52260135240, 'script': '76a914113bc39d343c808d092f9af92361e05a1dc647ce88ac',
         'addresses': ['D6iDd199RiVhemnFAKmdc1QFK2X5UnqWc8'], 'script_type': 'pay-to-pubkey-hash'},
        {'value': 68724534040774, 'script': '76a9146100ff1d8c47cbaae0fc96957aea720568657bf188ac',
         'addresses': ['DDz1H7AcqPgmKzFEP3pBHW5b1GWuWEoAAP'], 'script_type': 'pay-to-pubkey-hash'}]}


class TestDogeBlockcypher(BaseTestCase):
    explorer = DogeExplorerInterface()
    api = DogeBlockcypherApi

    def setUp(self):
        self.explorer.balance_apis = [self.api]
        self.explorer.tx_details_apis = [self.api]
        self.maxDiff = None

    def test_get_balance(self):
        self.api.request = Mock(side_effect=[GET_BALANCE_MOCK_RESPONSE])

        address = 'D6iDd199RiVhemnFAKmdc1QFK2X5UnqWc8'

        result = self.explorer.get_balance(address)

        expected = {
            Currencies.doge: {
                'address': address,
                'balance': Decimal('522.60135240'),
                'symbol': 'DOGE',
                'unconfirmed_balance': Decimal('0.0')
            }
        }

        self.assertDictEqual(result, expected)

    def test_get_tx_details(self):
        self.api.request = Mock(side_effect=[GET_TX_DETAILS_MOCK_RESPONSE])

        result = self.explorer.get_tx_details('e5847a40ee0c3d2323b0e590aeeb4ff174d176946116e8694bc96fade2364e03')

        expected = {
            'block': 5354516,
            'confirmations': 4,
            'date': datetime.datetime.strptime('2024-08-28T07:01:15+00:00', '%Y-%m-%dT%H:%M:%S%z'),
            'fees': Decimal('0.11615496'),
            'hash': 'e5847a40ee0c3d2323b0e590aeeb4ff174d176946116e8694bc96fade2364e03',
            'inputs': [],
            'memo': None,
            'outputs': [],
            'raw': None,
            'success': True,
            'transfers': [
                {
                    'currency': Currencies.doge,
                    'from': 'DDz1H7AcqPgmKzFEP3pBHW5b1GWuWEoAAP',
                    'is_valid': True,
                    'memo': None,
                    'symbol': 'DOGE',
                    'to': '',
                    'token': None,
                    'type': 'MainCoin',
                    'value': Decimal('522.71750736')
                }, {
                    'currency': Currencies.doge,
                    'from': '',
                    'is_valid': True,
                    'memo': None,
                    'symbol': 'DOGE',
                    'to': 'D6iDd199RiVhemnFAKmdc1QFK2X5UnqWc8',
                    'token': None,
                    'type': 'MainCoin',
                    'value': Decimal('522.60135240')
                }
            ]
        }

        self.assertDictEqual(result, expected)
