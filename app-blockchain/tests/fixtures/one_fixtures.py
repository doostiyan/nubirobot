import datetime
from decimal import Decimal
from typing import List, Dict

from exchange.blockchain.models import Currencies
from pytz import UTC

import pytest


@pytest.fixture
def one_raw_block_heads():
    raw_response = [
        {
            'result': {
                'blockNumber': 61379911,
            },
        },
        {
            'result': {
                'blockNumber': 61379951,
            }
        }
    ]
    return raw_response


@pytest.fixture
def one_raw_addresses_txs() -> List[Dict]:
    raw_response = [
        {
            'result': {
                'transactions': [
                    {
                        'blockHash': '0x6f112a2ad1f7f8f99f2c0aa3dd81b3fd2008fe1721b4db4200615a7623ce0de9',
                        'blockNumber': 61379345,
                        'ethHash': '0xfa2574c01a4eeaa3e51428f87c239a6d5bcf68c1eff6c12369775c8bcacd564a',
                        'from': 'one1mtaax20fqmcwzmqdxcfu7t9h2y4hzwplct44m8',
                        'timestamp': 1723440916,
                        'to': 'one129vp4m9l7t9kp9m2zyn52xapx2wf2s6ksnxw83',
                        'value': 5013000000000000000000
                    },
                    {
                        'blockHash': '0x94d7005f8dc24f51157540bccb24380a4cdc7c4005e0945bd578c5dff597378a',
                        'blockNumber': 61379328,
                        'ethHash': '0xe7c010c321fc5d820e7de78196e72d282ae0348c5b594bedc58db32b7418d8be',
                        'from': 'one1649257ud5tphts3yj6r7xz55pjhs9tjeqklaym',
                        'timestamp': 1723440883,
                        'to': 'one1mtaax20fqmcwzmqdxcfu7t9h2y4hzwplct44m8',
                        'value': 79897879000000000000
                    },
                    {
                        'blockHash': '0x94d7005f8dc24f51157540bccb24380a4cdc7c4005e0945bd578c5dff597378a',
                        'blockNumber': 61379328,
                        'ethHash': '0x945f855dd1161b1027f33585379baa23e1deee5ccb418fbe215bdef6e4b01b55',
                        'from': 'one12888kn3c64xgsln66r0zp9mx6vmfy8t57y72zy',
                        'timestamp': 1723440883,
                        'to': 'one1mtaax20fqmcwzmqdxcfu7t9h2y4hzwplct44m8',
                        'value': 80997879000000000000
                    },
                ]
            }
        },
        {
            'result': {
                'transactions': [
                    {
                        'blockHash': '0x42aba6189a0ff69f6afa6b2274e1ba30120d1c5f98dcb430e1fef0de5af096d0',
                        'blockNumber': 61379318,
                        'ethHash': '0x9c80ce3b5160d211e005dc8f0d5f6f6a97369776b6c288e2b11943e56175ffdc',
                        'from': 'one1h6c57p0d8qrdgt4za3spzun3a3ueamcant2vcx',
                        'timestamp': 1723440862,
                        'to': 'one1mtaax20fqmcwzmqdxcfu7t9h2y4hzwplct44m8',
                        'value': 127672944340000000000
                    },
                    {
                        'blockHash': '0x83d97209b4132bcc64a069b7a1c64b8d2b6316dc9972a7feb9e998e353db1459',
                        'blockNumber': 61379132,
                        'ethHash': '0x4a969c93231a08c38fba7d36ae248e43b41d1a49bcb25aa1c3d1871beca3e910',
                        'from': 'one1qyhsqz8la4wa4zykw7rqn36u30t4ep2v2vuu5h',
                        'timestamp': 1723440490,
                        'to': 'one1h6c57p0d8qrdgt4za3spzun3a3ueamcant2vcx',
                        'value': 36675065340000000000
                    },
                    {
                        'blockHash': '0xa12366a462c3f3f382085bd8d9af50763587789d1acce56850ac94e0d7c03ab1',
                        'blockNumber': 61376399,
                        'ethHash': '0x631c01c8d248b62d17b3beef57224ac54c766f761e166c7a147bacf62c169aa6',
                        'from': 'one1qyhsqz8la4wa4zykw7rqn36u30t4ep2v2vuu5h',
                        'timestamp': 1723435022,
                        'to': 'one1h6c57p0d8qrdgt4za3spzun3a3ueamcant2vcx',
                        'value': 42000000000000000000
                    },
                ]
            }
        }
    ]
    return raw_response


@pytest.fixture
def one_raw_addresses_txs_receipt():
    raw_data = [
        {
            'receipts': [
                {
                    'id': '0xfa2574c01a4eeaa3e51428f87c239a6d5bcf68c1eff6c12369775c8bcacd564a',
                    'result': {
                        'status': 1,
                    }
                },
                {
                    'id': '0xe7c010c321fc5d820e7de78196e72d282ae0348c5b594bedc58db32b7418d8be',
                    'result': {
                        'status': 1,
                    }
                },
                {
                    'id': '0x945f855dd1161b1027f33585379baa23e1deee5ccb418fbe215bdef6e4b01b55',
                    'result': {
                        'status': 1,
                    }
                },
            ],
            'transactions': {
                'id': 1,
                'result': {
                    'transactions': [
                        {
                            'blockHash': '0x6f112a2ad1f7f8f99f2c0aa3dd81b3fd2008fe1721b4db4200615a7623ce0de9',
                            'blockNumber': 61379345,
                            'ethHash': '0xfa2574c01a4eeaa3e51428f87c239a6d5bcf68c1eff6c12369775c8bcacd564a',
                            'from': 'one1mtaax20fqmcwzmqdxcfu7t9h2y4hzwplct44m8',
                            'timestamp': 1723440916,
                            'to': 'one129vp4m9l7t9kp9m2zyn52xapx2wf2s6ksnxw83',
                            'value': 5013000000000000000000
                        },
                        {
                            'blockHash': '0x94d7005f8dc24f51157540bccb24380a4cdc7c4005e0945bd578c5dff597378a',
                            'blockNumber': 61379328,
                            'ethHash': '0xe7c010c321fc5d820e7de78196e72d282ae0348c5b594bedc58db32b7418d8be',
                            'from': 'one1649257ud5tphts3yj6r7xz55pjhs9tjeqklaym',
                            'timestamp': 1723440883,
                            'to': 'one1mtaax20fqmcwzmqdxcfu7t9h2y4hzwplct44m8',
                            'value': 79897879000000000000
                        },
                        {
                            'blockHash': '0x94d7005f8dc24f51157540bccb24380a4cdc7c4005e0945bd578c5dff597378a',
                            'blockNumber': 61379328,
                            'ethHash': '0x945f855dd1161b1027f33585379baa23e1deee5ccb418fbe215bdef6e4b01b55',
                            'from': 'one12888kn3c64xgsln66r0zp9mx6vmfy8t57y72zy',
                            'timestamp': 1723440883,
                            'to': 'one1mtaax20fqmcwzmqdxcfu7t9h2y4hzwplct44m8',
                            'value': 80997879000000000000
                        },
                    ]
                }
            }
        },
        {
            'receipts': [
                {
                    'id': '0x9c80ce3b5160d211e005dc8f0d5f6f6a97369776b6c288e2b11943e56175ffdc',
                    'result': {
                        'status': 1,
                    }
                },
                {
                    'id': '0x4a969c93231a08c38fba7d36ae248e43b41d1a49bcb25aa1c3d1871beca3e910',
                    'result': {
                        'status': 1,
                    }
                },
                {
                    'id': '0x631c01c8d248b62d17b3beef57224ac54c766f761e166c7a147bacf62c169aa6',
                    'result': {
                        'status': 1,
                    }
                },
            ],
            'transactions': {
                'id': 1,
                'result': {
                    'transactions': [
                        {
                            'blockHash': '0x42aba6189a0ff69f6afa6b2274e1ba30120d1c5f98dcb430e1fef0de5af096d0',
                            'blockNumber': 61379318,
                            'ethHash': '0x9c80ce3b5160d211e005dc8f0d5f6f6a97369776b6c288e2b11943e56175ffdc',
                            'from': 'one1h6c57p0d8qrdgt4za3spzun3a3ueamcant2vcx',
                            'timestamp': 1723440862,
                            'to': 'one1mtaax20fqmcwzmqdxcfu7t9h2y4hzwplct44m8',
                            'value': 127672944340000000000
                        },
                        {
                            'blockHash': '0x83d97209b4132bcc64a069b7a1c64b8d2b6316dc9972a7feb9e998e353db1459',
                            'blockNumber': 61379132,
                            'ethHash': '0x4a969c93231a08c38fba7d36ae248e43b41d1a49bcb25aa1c3d1871beca3e910',
                            'from': 'one1qyhsqz8la4wa4zykw7rqn36u30t4ep2v2vuu5h',
                            'timestamp': 1723440490,
                            'to': 'one1h6c57p0d8qrdgt4za3spzun3a3ueamcant2vcx',
                            'value': 36675065340000000000
                        },
                        {
                            'blockHash': '0xa12366a462c3f3f382085bd8d9af50763587789d1acce56850ac94e0d7c03ab1',
                            'blockNumber': 61376399,
                            'ethHash': '0x631c01c8d248b62d17b3beef57224ac54c766f761e166c7a147bacf62c169aa6',
                            'from': 'one1qyhsqz8la4wa4zykw7rqn36u30t4ep2v2vuu5h',
                            'timestamp': 1723435022,
                            'to': 'one1h6c57p0d8qrdgt4za3spzun3a3ueamcant2vcx',
                            'value': 42000000000000000000
                        },
                    ]
                }
            }
        }
    ]
    return raw_data


@pytest.fixture
def one_parsed_addresses_txs():
    raw_response = [
        [
            {
                Currencies.one: {
                    'amount': Decimal('5013.000000000000000000'),
                    'from_address': '0xdafbd329e906f0e16c0d3613cf2cb7512b71383f',
                    'to_address': '0x51581aecbff2cb60976a1127451ba1329c954356',
                    'hash': '0xfa2574c01a4eeaa3e51428f87c239a6d5bcf68c1eff6c12369775c8bcacd564a',
                    'block': 61379345,
                    'date': datetime.datetime(2024, 8, 12, 5, 35, 16,
                                              tzinfo=UTC),
                    'memo': None,
                    'confirmations': 566,
                    'address': '0xdafbd329e906f0e16c0d3613cf2cb7512b71383f',
                    'direction': 'outgoing',
                    'raw': None
                }
            },
            {
                Currencies.one: {
                    'amount': Decimal('79.897879000000000000'),
                    'from_address': '0xd54aaa7b8da2c375c2249687e30a940caf02ae59',
                    'to_address': '0xdafbd329e906f0e16c0d3613cf2cb7512b71383f',
                    'hash': '0xe7c010c321fc5d820e7de78196e72d282ae0348c5b594bedc58db32b7418d8be',
                    'block': 61379328,
                    'date': datetime.datetime(2024, 8, 12, 5, 34, 43,
                                              tzinfo=UTC),
                    'memo': None,
                    'confirmations': 583,
                    'address': '0xdafbd329e906f0e16c0d3613cf2cb7512b71383f',
                    'direction': 'incoming',
                    'raw': None
                }
            },
            {
                Currencies.one: {
                    'amount': Decimal('80.997879000000000000'),
                    'from_address': '0x51ce7b4e38d54c887e7ad0de209766d336921d74',
                    'to_address': '0xdafbd329e906f0e16c0d3613cf2cb7512b71383f',
                    'hash': '0x945f855dd1161b1027f33585379baa23e1deee5ccb418fbe215bdef6e4b01b55',
                    'block': 61379328,
                    'date': datetime.datetime(2024, 8, 12, 5, 34, 43,
                                              tzinfo=UTC),
                    'memo': None,
                    'confirmations': 583,
                    'address': '0xdafbd329e906f0e16c0d3613cf2cb7512b71383f',
                    'direction': 'incoming',
                    'raw': None
                }
            },
        ],
        [
            {
                Currencies.one: {
                    'amount': Decimal('127.672944340000000000'),
                    'from_address': '0xbeb14f05ed3806d42ea2ec60117271ec799eef1d',
                    'to_address': '0xdafbd329e906f0e16c0d3613cf2cb7512b71383f',
                    'hash': '0x9c80ce3b5160d211e005dc8f0d5f6f6a97369776b6c288e2b11943e56175ffdc',
                    'block': 61379318,
                    'date': datetime.datetime(2024, 8, 12, 5, 34, 22,
                                              tzinfo=UTC),
                    'memo': None,
                    'confirmations': 633,
                    'address': '0xbeb14f05ed3806d42ea2ec60117271ec799eef1d',
                    'direction': 'outgoing',
                    'raw': None
                }
            },
            {
                Currencies.one: {
                    'amount': Decimal('36.675065340000000000'),
                    'from_address': '0x012f0008ffed5dda8896778609c75c8bd75c854c',
                    'to_address': '0xbeb14f05ed3806d42ea2ec60117271ec799eef1d',
                    'hash': '0x4a969c93231a08c38fba7d36ae248e43b41d1a49bcb25aa1c3d1871beca3e910',
                    'block': 61379132,
                    'date': datetime.datetime(2024, 8, 12, 5, 28, 10,
                                              tzinfo=UTC),
                    'memo': None,
                    'confirmations': 819,
                    'address': '0xbeb14f05ed3806d42ea2ec60117271ec799eef1d',
                    'direction': 'incoming',
                    'raw': None
                }
            },
            {
                Currencies.one: {
                    'amount': Decimal('42.000000000000000000'),
                    'from_address': '0x012f0008ffed5dda8896778609c75c8bd75c854c',
                    'to_address': '0xbeb14f05ed3806d42ea2ec60117271ec799eef1d',
                    'hash': '0x631c01c8d248b62d17b3beef57224ac54c766f761e166c7a147bacf62c169aa6',
                    'block': 61376399,
                    'date': datetime.datetime(2024, 8, 12, 3, 57, 2,
                                              tzinfo=UTC),
                    'memo': None,
                    'confirmations': 3552,
                    'address': '0xbeb14f05ed3806d42ea2ec60117271ec799eef1d',
                    'direction': 'incoming',
                    'raw': None
                }
            },
        ]
    ]

    return raw_response
