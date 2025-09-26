from datetime import datetime
from decimal import Decimal
from typing import Dict, List
from unittest.mock import Mock

import pytest
from django.conf import settings

from exchange.blockchain.api.ftm.ftm_covalenthq import FtmCovalenthqApi
from exchange.blockchain.api.ftm.ftm_explorer_interface import FTMExplorerInterface
from exchange.blockchain.contracts_conf import opera_ftm_contract_info
from exchange.blockchain.tests.api.general_test.base_test_case import BaseTestCase

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

BLOCK_HEAD_MOCK_RESPONSE = {
    'data': {
        'items': [
            {
                'height': 87097837
            }
        ]
    }
}

GET_BALANCES_MOCK_RESPONSE: List[Dict] = [
    {
        'data': {
            'items': [
                {
                    'contract_ticker_symbol': 'FTM',
                    'balance': '5491731466303367276'
                }
            ]
        }
    },
    {
        'data': {
            'items': [
                {
                    'contract_ticker_symbol': 'FTM',
                    'balance': '23776584000000000000'
                }
            ]
        }
    }
]

GET_TX_DETAILS_MOCK_RESPONSE: List[Dict] = [
    BLOCK_HEAD_MOCK_RESPONSE,
    {
        'data': {
            'items': [
                {
                    'block_height': 87097837,
                    'block_hash': '0x000485b70000141a7a447a79b98db9ca7cf84d2df45065a49ab825165d7155fa',
                    'tx_hash': '0x9c38c7e6c2dd73d605126aa011f23e52558d422ad3dc6945296feee26443f99e',
                    'block_signed_at': '2024-07-29T09:31:50Z',
                    'from_address': '0x2ddd6ed11400a8a1d5c4184589d9b903b1311fd8',
                    'to_address': '0xf45f0c3573c8b704bbb50fce53b4024a706d43c0',
                    'value': '15526551009239029',
                    'fees_paid': '510934823259000',
                    'successful': True
                }
            ]
        }
    }
]

GET_TXS_MOCK_RESPONSE: List[Dict] = [
    BLOCK_HEAD_MOCK_RESPONSE,
    {
        'data': {
            'items': [
                {
                    'block_height': 87097837,
                    'block_hash': '0x000485b70000141a7a447a79b98db9ca7cf84d2df45065a49ab825165d7155fa',
                    'tx_hash': '0x428a6e267704eb0c8f03478348e08c9347e69986cadeb0058d5b3357d7ce85e5',
                    'block_signed_at': '2024-07-28T09:31:50Z',
                    'from_address': '0x80427d1ee2bc9db8d2a859b057d755919d548a39',
                    'to_address': '0xa3472370b9312f757f714972e8d1d8a75f4ad999',
                    'value': '12364781633033800',
                    'fees_paid': '15833186342424',
                    'successful': True,
                },
                {
                    'block_height': 87097837,
                    'block_hash': '0x000485b70000141a7a447a79b98db9ca7cf84d2df45065a49ab825165d7155fa',
                    'tx_hash': '0x0986dcc4487aa89e164a836723d7b8a9e7082dc315c4ec3173dcec5d1cbadabd',
                    'block_signed_at': '2024-07-29T09:31:50Z',
                    'from_address': '0x80427d1ee2bc9db8d2a859b057d755919d548a39',
                    'to_address': '0xa3472370b9312f757f714972e8d1d8a75f4ad999',
                    'value': '14767646064306940',
                    'fees_paid': '1783186342424',
                    'successful': True,
                }
            ]
        }
    }
]

GET_TOKEN_BALANCE_MOCK_RESPONSE: List[Dict] = [
    {
        'data': {
            'items': [
                {
                    'balance': '2916560',
                    'contract_address': '0x321162cd933e2be498cd2267a90534a804051b11'
                }
            ]
        }
    }
]


class TestFTMCovalenthqExplorerInterface(BaseTestCase):
    explorer = FTMExplorerInterface()
    api = FtmCovalenthqApi

    def setUp(self):
        self.explorer.block_head_apis = [self.api]
        self.explorer.balance_apis = [self.api]
        self.explorer.token_balance_apis = [self.api]
        self.explorer.address_txs_apis = [self.api]
        self.explorer.tx_details_apis = [self.api]
        self.maxDiff = None

    def test_get_balances(self):
        self.api.request = Mock(side_effect=GET_BALANCES_MOCK_RESPONSE)

        balances = self.explorer.get_balances(
            [
                '0xc9bB715E2538A08aC7418A79E808B22f78415620',
                '0x52CEba41Da235Af367bFC0b0cCd3314cb901bB5F'
            ]
        )

        expected_balances = [
            {
                Currencies.ftm: {
                    'address': '0xc9bB715E2538A08aC7418A79E808B22f78415620',
                    'amount': Decimal('5.491731466303367276'),
                    'symbol': 'FTM'
                }
            },
            {
                Currencies.ftm: {
                    'address': '0x52CEba41Da235Af367bFC0b0cCd3314cb901bB5F',
                    'amount': Decimal('23.776584000000000000'),
                    'symbol': 'FTM'
                }
            }
        ]

        self.assertListEqual(balances, expected_balances)

    def test_get_txs_details(self):
        self.api.request = Mock(side_effect=GET_TX_DETAILS_MOCK_RESPONSE)

        tx_hash = '0x9c38c7e6c2dd73d605126aa011f23e52558d422ad3dc6945296feee26443f99e'

        tx_detail = self.explorer.get_tx_details(tx_hash)

        expected = {
            'hash': tx_hash,
            'success': True,
            'inputs': [],
            'outputs': [],
            'memo': None,
            'date': datetime.strptime('2024-07-29T09:31:50+00:00', '%Y-%m-%dT%H:%M:%S%z'),
            'raw': None,
            'block': 87097837,
            'fees': Decimal('0.000510934823259000'),
            'confirmations': 0,
            'transfers': [
                {
                    'type': 'MainCoin',
                    'symbol': 'FTM',
                    'currency': Currencies.ftm,
                    'from': '0x2ddd6ed11400a8a1d5c4184589d9b903b1311fd8',
                    'to': '0xf45f0c3573c8b704bbb50fce53b4024a706d43c0',
                    'value': Decimal('0.015526551009239029'),
                    'is_valid': True,
                    'token': None,
                    'memo': None
                }
            ]
        }
        self.maxDiff = None

        self.assertDictEqual(tx_detail, expected)

    def test_get_txs(self):
        self.api.request = Mock(side_effect=GET_TXS_MOCK_RESPONSE)

        address = '0xa3472370b9312f757f714972e8d1d8a75f4ad999'

        transactions = self.explorer.get_txs(address)

        expected_transactions = [
            {
                Currencies.ftm: {
                    'block': 87097837,
                    'date': datetime.strptime('2024-07-28T09:31:50+00:00', '%Y-%m-%dT%H:%M:%S%z'),
                    'hash': '0x428a6e267704eb0c8f03478348e08c9347e69986cadeb0058d5b3357d7ce85e5',
                    'from_address': '0x80427d1ee2bc9db8d2a859b057d755919d548a39',
                    'to_address': address,
                    'address': address,
                    'amount': Decimal('0.012364781633033800'),
                    'confirmations': 0,
                    'direction': 'incoming',
                    'raw': None,
                    'memo': None
                },
            },
            {
                Currencies.ftm: {
                    'block': 87097837,
                    'date': datetime.strptime('2024-07-29T09:31:50+00:00', '%Y-%m-%dT%H:%M:%S%z'),
                    'hash': '0x0986dcc4487aa89e164a836723d7b8a9e7082dc315c4ec3173dcec5d1cbadabd',
                    'from_address': '0x80427d1ee2bc9db8d2a859b057d755919d548a39',
                    'to_address': address,
                    'address': address,
                    'amount': Decimal('0.014767646064306940'),
                    'confirmations': 0,
                    'direction': 'incoming',
                    'raw': None,
                    'memo': None
                }
            }
        ]

        self.assertListEqual(transactions, expected_transactions)

    def test_get_token_balance(self):
        self.api.request = Mock(side_effect=GET_TOKEN_BALANCE_MOCK_RESPONSE)

        address = '0x000052fca55e63AaD9b0d243E5B6a9fEc9b55ff7'

        contract_info = opera_ftm_contract_info['mainnet'][Currencies.btc]

        result = self.explorer.get_token_balance(address, {
            Currencies.btc: contract_info
        })

        expected_result = {
            'address': address,
            'amount': Decimal('0.02916560'),
            'symbol': contract_info.get('symbol')
        }

        self.assertDictEqual(expected_result, result)

    def test_get_txs_notReturnTransaction_onSuccessfulFalse(self):
        self.api.request = Mock(side_effect=[
            BLOCK_HEAD_MOCK_RESPONSE,
            {
                'data': {
                    'items': [
                        {
                            'successful': False,
                            'value': 9732541,
                            'from_address': 'just not being equal to to_address',
                            'block_height': 318731,
                            'fees_paid': '326232'
                        }
                    ]
                }
            }
        ])

        result = self.explorer.get_txs('0xa3472370b9312f757f714972e8d1d8a75f4ad999')

        self.assertListEqual(result, [])

    def test_get_txs_notReturnTransaction_onNegativeValues(self):
        self.api.request = Mock(side_effect=[
            BLOCK_HEAD_MOCK_RESPONSE,
            {
                'data': {
                    'items': [
                        {
                            'successful': True,
                            'value': -9732541,
                            'from_address': 'just not being equal to to_address',
                            'block_height': 318731,
                            'fees_paid': '326232'
                        }
                    ]
                }
            }
        ])

        result = self.explorer.get_txs('0xa3472370b9312f757f714972e8d1d8a75f4ad999')

        self.assertListEqual(result, [])

@pytest.mark.slow
class TestFtmCovalenthqApi(BaseTestCase):
    api = FtmCovalenthqApi

    def test_get_balance(self):
        balance = self.api.get_balance('0x89e8fa64d576d84e0143af9ee9c94f759f1ef759')

        schema = {
            'data': {
                'items': {
                    'balance': str
                }
            }
        }

        self.assert_schema(balance, schema)

    def test_get_token_balance(self):
        schema = {
            'data': {
                'items': {
                    'contract_address': str,
                    'balance': str
                }
            }
        }
        result = self.api.get_token_balance('0x31c798ac8159568d44c7f0c8678bf6fdc4caf57c', {})
        self.assert_schema(result, schema)

    def test_get_txs(self):
        transactions = self.api.get_address_txs('0x049c1daf1c641f7a5547efbf89c32354015eccac')

        schema = {
            'data': {
                'items': {
                    'tx_hash': str,
                    'from_address': str,
                    'to_address': str,
                    'value': str,
                    'block_height': int,
                    'block_hash': str,
                    'block_signed_at': str,
                    'fees_paid': str,
                }
            }
        }

        self.assert_schema(transactions, schema)

    def test_txs_details(self):
        tx_details = self.api.get_tx_details('0x38db609e1cc36bba19acb51882e2feea5791b277ad93dd6d887d0c295e0c5a5e')
        schema = {
            'data': {
                'items': {
                    'block_height': int,
                    'block_hash': str,
                    'tx_hash': str,
                    'block_signed_at': str,
                    'from_address': str,
                    'to_address': str,
                    'value': str,
                    'fees_paid': str,
                }
            }
        }
        self.assert_schema(tx_details, schema)

    def test_block_head(self):
        block_head_response = self.api.get_block_head()

        schema = {
            'data': {
                'items': {
                    'height': int
                }
            }
        }

        self.assert_schema(block_head_response, schema)
