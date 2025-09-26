import datetime
from decimal import Decimal
from unittest.mock import Mock

import pytz
from django.conf import settings
from django.core.cache import cache

from exchange.blockchain.api.eth.eth_blockbook_new import EthereumBlockBookApi
from exchange.blockchain.api.eth.eth_explorer_interface import EthExplorerInterface
from exchange.blockchain.tests.api.eth.eth_blockbook_fixtures import (
    address_txs_mock_response,
    address_txs_weth_tx_mock_response,
    block_head_mock_response,
    block_txs_mock_response,
    token_tx_details_mock_response,
    token_txs_mock_response,
    tx_details_mock_response,
)

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

explorer = EthExplorerInterface()
api = EthereumBlockBookApi


def test__address_txs__successful(block_head_mock_response, address_txs_mock_response):
    explorer.address_txs_apis = [api]
    api.request = Mock(side_effect=[block_head_mock_response, address_txs_mock_response])

    result = explorer.get_txs('0xd84b7dfa43dbeb0e2f4e9daabb0326fa0ded5e3b')

    expected = [
        {
            Currencies.eth: {
                'amount': Decimal('0.041332982043186680'),
                'from_address': '0xd84b7dfa43dbeb0e2f4e9daabb0326fa0ded5e3b',
                'to_address': '0x9c89c3289bcaf3c06318a2b03584956c7349c3f9',
                'hash': '0x3a39bc06b8b44cb7f59f2291cafb8693c28c51e2aa4196856f46cc0eaafea287',
                'block': 20753635,
                'date': datetime.datetime.fromtimestamp(1726374635, tz=pytz.UTC),
                'memo': None,
                'confirmations': 12,
                'address': '0xd84b7dfa43dbeb0e2f4e9daabb0326fa0ded5e3b',
                'direction': 'outgoing',
                'raw': None,
            }
        },
        {
            Currencies.eth: {
                'amount': Decimal('0.061929458768865380'),
                'from_address': '0xd84b7dfa43dbeb0e2f4e9daabb0326fa0ded5e3b',
                'to_address': '0x3254d5cad483e329c475d4e13bf2343c578eea42',
                'hash': '0xc8eff0af35ac4cdb662cb134cc226c8f0f04af8598655cb01e3e52cd929b41a7',
                'block': 20753599,
                'date': datetime.datetime.fromtimestamp(1726374179, tz=pytz.UTC),
                'memo': None,
                'confirmations': 48,
                'address': '0xd84b7dfa43dbeb0e2f4e9daabb0326fa0ded5e3b',
                'direction': 'outgoing',
                'raw': None,
            }
        },
    ]

    assert result == expected


def test__address_txs__when_weth_tx__do_not_return(block_head_mock_response, address_txs_weth_tx_mock_response):
    explorer.address_txs_apis = [api]
    api.request = Mock(side_effect=[block_head_mock_response, address_txs_weth_tx_mock_response])

    result = explorer.get_txs('0xDb9f32E57A580889fa77De0BC294f81C486076e9')

    assert result == []


def test__token_txs__successful(block_head_mock_response, token_txs_mock_response):
    explorer.token_txs_apis = [api]
    api.request = Mock(side_effect=[block_head_mock_response, token_txs_mock_response])

    result = explorer.get_token_txs('0xdac17f958d2ee523a2206206994597c13d831ec7',
                                    api.parser.contract_info_list()[Currencies.usdt])

    expected = [
        {
            Currencies.usdt: {
                'amount': Decimal('1500.000000'),
                'from_address': '0xc1aa38477597803da4f26111a1656522e8c4c844',
                'to_address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                'hash': '0x37719d67ffd9e9e114ebb70be9889d9806ab6e4e098a2b25d5b9cc3f758ae436',
                'block': 20752954,
                'date': datetime.datetime.fromtimestamp(1726366415, tz=pytz.UTC),
                'memo': None,
                'confirmations': 721,
                'address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                'direction': 'incoming',
                'raw': None,
            }
        }
    ]

    assert result == expected


def test__block_txs__successful(block_head_mock_response, block_txs_mock_response):
    explorer.block_txs_apis = [api]
    cache.set('latest_block_height_processed_eth', 20753637)
    api.request = Mock(side_effect=[block_head_mock_response, block_txs_mock_response])

    result = explorer.get_latest_block(include_inputs=True, include_info=True)

    expected = (
        {
            'input_addresses': {
                '0x9fc3da866e7df3a1c57ade1a97c9f00a70f010c8',
            },
            'output_addresses': {
                '0x388c818ca8b9251b393131c08a736a67ccb19297',
            }
        },
        {
            'incoming_txs': {
                '0x388c818ca8b9251b393131c08a736a67ccb19297': {
                    Currencies.eth: [
                        {
                            'tx_hash': '0x0874f11f3f5d2cdd9640e9812c2179d3666a0ff3e4338e571e28c6c59ee27f80',
                            'value': Decimal('0.016519211539722639'),
                            'contract_address': None,
                            'block_height': 20753638,
                            'symbol': 'ETH',
                        }
                    ]
                },
            },
            'outgoing_txs': {
                '0x9fc3da866e7df3a1c57ade1a97c9f00a70f010c8': {
                    Currencies.eth: [
                        {
                            'tx_hash': '0x0874f11f3f5d2cdd9640e9812c2179d3666a0ff3e4338e571e28c6c59ee27f80',
                            'value': Decimal('0.016519211539722639'),
                            'contract_address': None,
                            'block_height': 20753638,
                            'symbol': 'ETH',
                        }
                    ]
                },
            }
        },
        20753638
    )

    assert result == expected


def test__tx_details__successful(tx_details_mock_response):
    explorer.tx_details_apis = [api]
    api.request = Mock(side_effect=[tx_details_mock_response])

    result = explorer.get_tx_details('0x3a39bc06b8b44cb7f59f2291cafb8693c28c51e2aa4196856f46cc0eaafea287')

    expected = {
        'hash': '0x3a39bc06b8b44cb7f59f2291cafb8693c28c51e2aa4196856f46cc0eaafea287',
        'success': True,
        'block': 20753635,
        'date': datetime.datetime.fromtimestamp(1726374635, tz=pytz.UTC),
        'fees': Decimal('0.000026556924765000'),
        'memo': None,
        'confirmations': 171,
        'raw': None,
        'inputs': [],
        'outputs': [],
        'transfers': [
            {
                'type': 'MainCoin',
                'symbol': 'ETH',
                'currency': Currencies.eth,
                'from': '0xd84B7DfA43dbEb0e2f4e9dAABb0326fa0dEd5e3b',
                'to': '0x9C89C3289bcAf3c06318A2b03584956c7349C3f9',
                'value': Decimal('0.041332982043186680'),
                'is_valid': True,
                'token': None,
                'memo': None,
            }
        ],
    }

    assert result == expected


def test__token_tx_details__successful(token_tx_details_mock_response):
    explorer.token_tx_details_apis = [api]
    api.request = Mock(side_effect=[token_tx_details_mock_response])

    result = explorer.get_token_tx_details(
        '0x7d621745c41f9a31649683da8a59f01005f48b77f841ef181ea6c49a5f9887a5')

    expected = {
        'hash': '0x7d621745c41f9a31649683da8a59f01005f48b77f841ef181ea6c49a5f9887a5',
        'success': True,
        'block': 20750598,
        'date': datetime.datetime.fromtimestamp(1726338059, tz=pytz.UTC),
        'fees': Decimal('0.000156721351494046'),
        'memo': None,
        'confirmations': 3215,
        'raw': None,
        'inputs': [],
        'outputs': [],
        'transfers': [
            {
                'type': 'Token',
                'symbol': 'USDT',
                'currency': Currencies.usdt,
                'from': '0xe718c3a32474c8448d529837a4cb31b89bc228ab',
                'to': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                'value': Decimal('1067.017891'),
                'is_valid': True,
                'token': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                'memo': None,
            }
        ],
    }

    assert result == expected
