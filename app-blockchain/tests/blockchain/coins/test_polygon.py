from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock

import pytz

from exchange.base.models import Currencies
from exchange.blockchain.api.polygon.polygon_covalent import PolygonCovalenthqAPI
from exchange.blockchain.api.polygon.polyganscan import PolygonScanAPI
from exchange.blockchain.api.polygon.polygon_web3 import PolygonWeb3API
from exchange.blockchain.models import Transaction
from exchange.blockchain.polygon import PolygonBlockchainInspector


def test_get_wallets_balance_polygonscan():
    addresses = ['0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae']
    expected_result = [
        {
            'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
            'balance': Decimal('353318.436783144397866641'),
            'received': Decimal('353318.436783144397866641'),
            'sent': Decimal('0'),
            'rewarded': Decimal('0'),
        },
        {
            'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
            'balance': Decimal('353318.436783144397866641'),
            'received': Decimal('353318.436783144397866641'),
            'sent': Decimal('0'),
            'rewarded': Decimal('0'),
        }
    ]
    api = PolygonScanAPI.get_api()
    api.request = Mock()
    api.request.return_value = test_data.get('balance').get('polygonscan')
    result = PolygonBlockchainInspector.get_wallets_balance_polygonscan(addresses)
    assert result == expected_result


def test_get_wallets_balance_covalent():
    addresses = ['0xc1393866edc1201121e3c786f238bfdebd179562']
    expected_result = [
        {
            'address': '0xc1393866edc1201121e3c786f238bfdebd179562',
            'balance': Decimal('0.009739707496339517'),
            'received': Decimal('0.009739707496339517'),
            'sent': Decimal('0'),
            'rewarded': Decimal('0'),
        },
    ]
    api = PolygonCovalenthqAPI.get_api()
    api.request = Mock()
    api.request.return_value = test_data.get('balance').get('covalenth')
    result = PolygonBlockchainInspector.get_wallets_balance_covalent(addresses)
    assert result == expected_result


def test_get_wallets_balance_web3():
    addresses = ['0xc1393866edc1201121e3c786f238bfdebd179562']
    expected_result = [
        {
            'address': '0xc1393866edc1201121e3c786f238bfdebd179562',
            'balance': Decimal('0.009739707496339517'),
            'received': Decimal('0.009739707496339517'),
            'sent': Decimal('0'),
            'rewarded': Decimal('0'),
        },
    ]
    api = PolygonWeb3API.get_api()
    api.w3.eth.get_balance = Mock()
    api.w3.eth.get_balance.return_value = 9739707496339517
    result = PolygonBlockchainInspector.get_wallets_balance_web3(addresses)
    assert result == expected_result


def test_get_wallet_transactions_polygonscan():
    expected_result = [
        Transaction(
            address='0x9d067c0fc83091bb80f9f56cc5076db8ac95318e',
            from_address=['0x5448f6f3b11afbfb4a73f67bf0c37ac04a8c6d84'],
            block=13977683,
            hash='0x47435e33ea2194d1ef1077122f23fc6d4e7aa0183650d6db5ab08b6ebd256535',
            timestamp=datetime(2022, 1, 10, 12, 10, 32, tzinfo=pytz.UTC),
            value=Decimal('0.015'),
            confirmations=84313,
            details=test_data.get('transaction').get('polygonscan'),
            is_double_spend=False
        )
    ]
    api = PolygonScanAPI.get_api()
    api.request = Mock()
    api.request.return_value = {
        'status': '1', 'message': 'OK',
        'result': [test_data.get('transaction').get('polygonscan')]
    }
    PolygonBlockchainInspector.USE_EXPLORER_TRANSACTION_POLYGON = 'polygonscan'
    result = PolygonBlockchainInspector.get_wallet_transactions_polygon('0x9d067c0fc83091bb80f9f56cc5076db8ac95318e')
    assert vars(expected_result[0]) == vars(result[0])


def test_get_wallet_transactions_covalenthq():
    expected_results = [
        Transaction(
            address='0xec3f4f97f11486cdde8dfcad20e0a62d83ddbc74',
            from_address=['0xec3f4f97f11486cdde8dfcad20e0a62d83ddbc74'],
            block=24333449,
            hash='0xa3581c183db120a0aeda3b1ee1dc19ff273e0e0bd7834c3682f874dcc29b8557',
            timestamp=datetime(2022, 1, 30, 6, 56, 8, tzinfo=pytz.UTC),
            value=Decimal('-184.990000000000000000'),
            confirmations=75008,
            details=test_data.get('transaction').get('covalenth')[0],
            is_double_spend=False
        ),
        Transaction(
            address='0xec3f4f97f11486cdde8dfcad20e0a62d83ddbc74',
            from_address=['0xb2d11bd09c74076f0c071c7b0fd0c8ed03071f6a'],
            block=24308357,
            hash='0x816a43a55a36927a751a02384f1f9b9b1e1151810a2bf0e3ea00356fa9718deb',
            timestamp=datetime(2022, 1, 29, 15, 30, 13, tzinfo=pytz.UTC),
            value=Decimal('185'),
            confirmations=100100,
            details=test_data.get('transaction').get('covalenth')[1],
            is_double_spend=False
        )
    ]
    api = PolygonCovalenthqAPI.get_api()
    api.request = Mock()
    api.request.side_effect = [
        {
            'data': {
                'address': '0xec3f4f97f11486cdde8dfcad20e0a62d83ddbc74',
                'updated_at': '2022-01-30T10:32:23.637869409Z',
                'next_update_at': '2022-01-30T10:37:23.637869679Z',
                'quote_currency': 'USD',
                'chain_id': 137,
                'items': [test_data.get('transaction').get('covalenth')[0],
                          test_data.get('transaction').get('covalenth')[1]],
                'pagination': {
                    'has_more': False,
                    'page_number': 0,
                    'page_size': 100,
                    'total_count': None
                }
            },
            'error': False,
            'error_message': None,
            'error_code': None
        },
        {
            'data': {
                'items': [
                    {
                        'height': 24408457
                    }
                ]
            }
        }
    ]
    PolygonBlockchainInspector.USE_EXPLORER_TRANSACTION_POLYGON = 'covalent'
    results = PolygonBlockchainInspector.get_wallet_transactions_polygon('0xec3f4f97f11486cdde8dfcad20e0a62d83ddbc74')
    for result, expected_result in zip(results, expected_results):
        assert vars(expected_result) == vars(result)


test_data = {
    'balance': {
        'polygonscan': {
            'status': '1',
            'message': 'OK',
            'result': [
                {'account': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'balance': '353318436783144397866641'},
                {'account': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'balance': '353318436783144397866641'},
            ]
        },
        'covalenth': {
            'data': {
                'address': '0xc1393866edc1201121e3c786f238bfdebd179562',
                'updated_at': '2022-01-30T06:57:05.568012551Z',
                'next_update_at': '2022-01-30T07:02:05.568012842Z',
                'quote_currency': 'USD',
                'chain_id': 137,
                'items': [
                    {
                        'contract_decimals': 18,
                        'contract_name': 'AeFX.io',
                        'contract_ticker_symbol': 'AeFX.io',
                        'contract_address': '0x2744861accb5bd435017c1cfee789b6ebab42082',
                        'supports_erc': ['erc20'],
                        'logo_url': 'https://logos.covalenthq.com/tokens/137/0x2744861accb5bd435017c1c',
                        'last_transferred_at': '2021-11-14T16:26:50Z',
                        'type': 'cryptocurrency',
                        'balance': '800000000000000000000000',
                        'balance_24h': None,
                        'quote_rate': 0.3297093,
                        'quote_rate_24h': 0.3346554,
                        'quote': 263767.44,
                        'quote_24h': None,
                        'nft_data': None
                    },
                    {
                        'contract_decimals': 18,
                        'contract_name': 'Matic Token',
                        'contract_ticker_symbol': 'MATIC',
                        'contract_address': '0x0000000000000000000000000000000000001010',
                        'supports_erc': ['erc20'],
                        'logo_url': 'https://logos.covalenthq.com/tokens/1/0x7d1afa7b718fb893db30a3abc',
                        'last_transferred_at': None,
                        'type': 'cryptocurrency',
                        'balance': '9739707496339517',
                        'balance_24h': '9739707496339517',
                        'quote_rate': 1.6729163,
                        'quote_rate_24h': 1.6975287,
                        'quote': 0.016293716,
                        'quote_24h': 0.016533433,
                        'nft_data': None
                    },
                ],
                'pagination': None
            },
            'error': False,
            'error_message': None,
            'error_code': None
            }
    },
    'transaction': {
        'polygonscan': {
            'blockNumber': '13977683',
            'timeStamp': '1641816632',
            'hash': '0x47435e33ea2194d1ef1077122f23fc6d4e7aa0183650d6db5ab08b6ebd256535',
            'nonce': '27',
            'blockHash': '0xec40922a4268a46280f98d1251388beb5fc2e0ecc0fe378e6773045bd245939f',
            'transactionIndex': '19',
            'from': '0x5448f6f3b11afbfb4a73f67bf0c37ac04a8c6d84',
            'to': '0x9d067c0fc83091bb80f9f56cc5076db8ac95318e',
            'value': '15000000000000000',
            'gas': '21000',
            'gasPrice': '248956309595',
            'isError': '0',
            'txreceipt_status': '1',
            'input': '0x',
            'contractAddress': '',
            'cumulativeGasUsed': '1537170',
            'gasUsed': '21000',
            'confirmations': '84313'
        },
        'covalenth': [
            {
                'block_signed_at': '2022-01-30T06:56:08Z',
                'block_height': 24333449,
                'tx_hash': '0xa3581c183db120a0aeda3b1ee1dc19ff273e0e0bd7834c3682f874dcc29b8557',
                'tx_offset': 47,
                'successful': True,
                'from_address': '0xec3f4f97f11486cdde8dfcad20e0a62d83ddbc74',
                'from_address_label': None,
                'to_address': '0xe7804c37c13166ff0b37f5ae0bb07a3aebb6e245',
                'to_address_label': None,
                'value': '184990000000000000000',
                'value_quote': 308.0839610564709,
                'gas_offered': 312401,
                'gas_spent': 21004,
                'gas_price': 32010069206,
                'gas_quote': 0.001119720062510729,
                'gas_quote_rate': 1.665408730506897,
                'log_events': [
                    {
                        'block_signed_at': '2022-01-30T06:56:08Z',
                        'block_height': 24333449,
                        'tx_offset': 47,
                        'log_offset': 177,
                        'tx_hash': '0xa3581c183db120a0aeda3b1ee1dc19ff273e0e0bd7834c3682f874dcc29b8557',
                        '_raw_log_topics_bytes': None,
                        'raw_log_topics': [
                            '0x4dfe1bbbcf077ddc3e01291eea2d5c70c2b422b415d95645b9adcfd678cb1d63',
                            '0x0000000000000000000000000000000000000000000000000000000000001010',
                            '0x000000000000000000000000ec3f4f97f11486cdde8dfcad20e0a62d83ddbc74',
                            '0x00000000000000000000000067b94473d81d0cd00849d563c94d0432ac988b49'
                        ],
                        'sender_contract_decimals': 18,
                        'sender_name': 'Matic Token',
                        'sender_contract_ticker_symbol': 'MATIC',
                        'sender_address': '0x0000000000000000000000000000000000001010',
                        'sender_address_label': None,
                        'sender_logo_url': 'https://logos.covalenthq.com/tokens/0x7d1afa7b718fb893db30a3abc0c',
                        'raw_log_data': '0x0000000000000000000000000000000000000000000000000002637d3ca88b0c000'
                                        '00000000000000000000000000000000000000000000a076407d3f744000000000000'
                                        '000000000000000000000000000000000000013d8cf74c2083c085540000000000000'
                                        '0000000000000000000000000000000000a0761a456ba9b74f4000000000000000000'
                                        '00000000000000000000000000013d8cf9af9dc0691060',
                        'decoded': None
                    },
                    {
                        'block_signed_at': '2022-01-30T06:56:08Z',
                        'block_height': 24333449,
                        'tx_offset': 47,
                        'log_offset': 176,
                        'tx_hash': '0xa3581c183db120a0aeda3b1ee1dc19ff273e0e0bd7834c3682f874dcc29b8557',
                        '_raw_log_topics_bytes': None,
                        'raw_log_topics': [
                            '0xe6497e3ee548a3372136af2fcb0696db31fc6cf20260707645068bd3fe97f3c4',
                            '0x0000000000000000000000000000000000000000000000000000000000001010',
                            '0x000000000000000000000000ec3f4f97f11486cdde8dfcad20e0a62d83ddbc74',
                            '0x000000000000000000000000e7804c37c13166ff0b37f5ae0bb07a3aebb6e245'
                        ],
                        'sender_contract_decimals': 18,
                        'sender_name': 'Matic Token',
                        'sender_contract_ticker_symbol': 'MATIC',
                        'sender_address': '0x0000000000000000000000000000000000001010',
                        'sender_address_label': None,
                        'sender_logo_url': 'https://logos.covalenthq.com/tokens/0x7d1afa7b718fb893db30a3abc0cf',
                        'raw_log_data': '0x00000000000000000000000000000000000000000000000a074080e1878300000000'
                                        '0000000000000000000000000000000000000000000a074080e6bcddc04a0000000000'
                                        '00000000000000000000000000000000096c27b9a977473446026f0000000000000000'
                                        '0000000000000000000000000000000000000005355ac04a0000000000000000000000'
                                        '00000000000000000000096c31c0e9f828bbc9026f',
                        'decoded': None
                    }
                ]
            },
            {
                'block_signed_at': '2022-01-29T15:30:13Z',
                'block_height': 24308357,
                'tx_hash': '0x816a43a55a36927a751a02384f1f9b9b1e1151810a2bf0e3ea00356fa9718deb',
                'tx_offset': 126,
                'successful': True,
                'from_address': '0xb2d11bd09c74076f0c071c7b0fd0c8ed03071f6a',
                'from_address_label': None,
                'to_address': '0xec3f4f97f11486cdde8dfcad20e0a62d83ddbc74',
                'to_address_label': None,
                'value': '185000000000000000000',
                'value_quote': 313.4769809246063,
                'gas_offered': 21000,
                'gas_spent': 21000,
                'gas_price': 29240904311,
                'gas_quote': 0.0010405046403311855,
                'gas_quote_rate': 1.6944701671600342,
                'log_events': [
                    {
                        'block_signed_at': '2022-01-29T15:30:13Z',
                        'block_height': 24308357,
                        'tx_offset': 126,
                        'log_offset': 607,
                        'tx_hash': '0x816a43a55a36927a751a02384f1f9b9b1e1151810a2bf0e3ea00356fa9718deb',
                        '_raw_log_topics_bytes': None,
                        'raw_log_topics': [
                            '0x4dfe1bbbcf077ddc3e01291eea2d5c70c2b422b415d95645b9adcfd678cb1d63',
                            '0x0000000000000000000000000000000000000000000000000000000000001010',
                            '0x000000000000000000000000b2d11bd09c74076f0c071c7b0fd0c8ed03071f6a',
                            '0x000000000000000000000000ef46d5fe753c988606e6f703260d816af53b03eb'
                        ],
                        'sender_contract_decimals': 18,
                        'sender_name': 'Matic Token',
                        'sender_contract_ticker_symbol': 'MATIC',
                        'sender_address': '0x0000000000000000000000000000000000001010',
                        'sender_address_label': None,
                        'sender_logo_url': 'https://logos.covalenthq.com/tokens/0x7d1afa7b718fb893db30a3abc0',
                        'raw_log_data': '0x00000000000000000000000000000000000000000000000000022e534a693f200000'
                                        '0000000000000000000000000000000000000000000a87ef1dc791f6c3fe0000000000'
                                        '000000000000000000000000000000000004809b8e9c2b5c3015f30000000000000000'
                                        '0000000000000000000000000000000a87ecef74478d84de0000000000000000000000'
                                        '000000000000000000000004809b90ca7ea6995513',
                        'decoded': None
                    },
                    {
                        'block_signed_at': '2022-01-29T15:30:13Z',
                        'block_height': 24308357,
                        'tx_offset': 126,
                        'log_offset': 606,
                        'tx_hash': '0x816a43a55a36927a751a02384f1f9b9b1e1151810a2bf0e3ea00356fa9718deb',
                        '_raw_log_topics_bytes': None,
                        'raw_log_topics': [
                            '0xe6497e3ee548a3372136af2fcb0696db31fc6cf20260707645068bd3fe97f3c4',
                            '0x0000000000000000000000000000000000000000000000000000000000001010',
                            '0x000000000000000000000000b2d11bd09c74076f0c071c7b0fd0c8ed03071f6a',
                            '0x000000000000000000000000ec3f4f97f11486cdde8dfcad20e0a62d83ddbc74'
                        ],
                        'sender_contract_decimals': 18,
                        'sender_name': 'Matic Token',
                        'sender_contract_ticker_symbol': 'MATIC',
                        'sender_address': '0x0000000000000000000000000000000000001010',
                        'sender_address_label': None,
                        'sender_logo_url': 'https://logos.covalenthq.com/tokens/0x7d1afa7b718fb893db30a3abc0c',
                        'raw_log_data': '0x00000000000000000000000000000000000000000000000a076407d3f74400000000'
                                        '0000000000000000000000000000000000000000000a87ecef4bd1f652460000000000'
                                        '0000000000000000000000000000000000000000000000000000000000000000000000'
                                        '000000000000000000000000000000008088e777dab252460000000000000000000000'
                                        '0000000000000000000000000a076407d3f7440000',
                        'decoded': None
                    }
                ]
            }
        ]
    }
}


def test_get_latest_block_addresses():
    api = PolygonScanAPI.get_api()
    api.get_latest_block = Mock()
    expected_result = (
        {
            '0x59535f537c2cdb0326ef2cda332c3af561bbb0a6',
            '0x832f166799a407275500430b61b622f0058f15d6',
            '0x0296006c75fad2ed15a8f38f24aa09135ce2c8bd',
            '0xb27dd2931f9fe23cb7ecfd34b483811bc7d9a1a3',
            '0x2ef7b30995a27074e7368e5e51879690e088fb4a',
            '0x9f0836a8bada9ef1b9aaa5e544898c75ee055475',
            '0xc1a3d34d032d286cd6a17486a363b9004c6db395',
            '0x0f2d0b673d9256c13511bc2bfc059ae354cceca6',
        },
        {
            '0x0296006c75fad2ed15a8f38f24aa09135ce2c8bd': {
                Currencies.eth: [{
                    'tx_hash': '0x521bf4713f4754b9b41b4657384c0f3b89490dcb90f3d9a550353af5f18a0a31',
                    'direction': 'outgoing',
                    'value': Decimal('0.006937281412272165')
                }]
            },
            '0x0f2d0b673d9256c13511bc2bfc059ae354cceca6': {
                Currencies.eth: [{
                    'tx_hash': '0xc59c7686a8da95d0cc676f7739e3e8d4be7406d2429234378ed45e3ce4ea08d8',
                    'direction': 'incoming',
                    'value': Decimal('0.57')
                }]
            },
            '0x2ef7b30995a27074e7368e5e51879690e088fb4a': {
                Currencies.eth: [{
                    'tx_hash': '0x0e9f74231e996c337edd14ece393f16c840be76814cb4244fc4edeb74a3298fc',
                    'direction': 'outgoing',
                    'value': Decimal('1')
                }]
            },
            '0x59535f537c2cdb0326ef2cda332c3af561bbb0a6': {
                Currencies.eth: [{
                    'tx_hash': '0xfcaebeacf5d6e6ba730cdf2e8a77e702bc1519588a44b11ab170aed2b43ed414',
                    'direction': 'outgoing',
                    'value': Decimal('10.013897111978023708')
                }]
            },
            '0x832f166799a407275500430b61b622f0058f15d6': {
                Currencies.eth: [{
                    'tx_hash': '0xfcaebeacf5d6e6ba730cdf2e8a77e702bc1519588a44b11ab170aed2b43ed414',
                    'direction': 'incoming',
                    'value': Decimal('10.013897111978023708')
                }]
            },
            '0x9f0836a8bada9ef1b9aaa5e544898c75ee055475': {
                Currencies.eth: [{
                    'tx_hash': '0x0e9f74231e996c337edd14ece393f16c840be76814cb4244fc4edeb74a3298fc',
                    'direction': 'incoming',
                    'value': Decimal('1')
                }]
            },
            '0xb27dd2931f9fe23cb7ecfd34b483811bc7d9a1a3': {
                Currencies.eth: [{
                    'tx_hash': '0x521bf4713f4754b9b41b4657384c0f3b89490dcb90f3d9a550353af5f18a0a31',
                    'direction': 'incoming',
                    'value': Decimal('0.006937281412272165')
                }]
            },
            '0xc1a3d34d032d286cd6a17486a363b9004c6db395': {
                Currencies.eth: [{
                    'tx_hash': '0xc59c7686a8da95d0cc676f7739e3e8d4be7406d2429234378ed45e3ce4ea08d8',
                    'direction': 'outgoing',
                    'value': Decimal('0.57')
                }]
            },
        }
    )
    api.get_latest_block.return_value = expected_result
    PolygonBlockchainInspector.USE_EXPLORER_BLOCKS = 'polygonscan'
    result = PolygonBlockchainInspector.get_latest_block_addresses()

    assert result == expected_result
