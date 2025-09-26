import datetime
from decimal import Decimal
from unittest import TestCase

import pytest
from exchange.base.models import Currencies
from exchange.blockchain.api.near.near_explorer_interface import NearExplorerInterface
from exchange.blockchain.api.near.nearblocks_near import NearBlocksApi
from exchange.blockchain.tests.api.general_test.general_test_from_explorer import TestFromExplorer
from pytz import UTC


class TestNearBlocksApiCalls(TestCase):
    api = NearBlocksApi
    addresses = ['eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                 '1238a90de7206e38d327195fea85d48200fd96d335053d78ec626a81a4c560cd',
                 'c3782fddeb491d6d592744aa2b9269c36105dbf9dcf36eedbb6efe79c9efe4ce']
    txs_hash = ['EYf7MFDneobGfVWXwjJGbc7gSJWsafUbPxfap5BVBVx',
                'c5R6fPNQPba3t25KHHGLT2d3hEpvu4uf9Ac9Vms1n3G',
                'BwhYAChhbNXs32dVczFNoUknKrmvxYBJgiYY3fBEDJdy']
    block_height = [99400305, 99400324]

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_response = self.api.get_block_head()
        assert len(get_block_head_response) == 1
        assert isinstance(get_block_head_response, dict)
        assert isinstance(get_block_head_response.get('blocks'), list)
        keys2check = [('block_height', str), ('block_hash', str), ('block_timestamp', str)]
        for key, value in keys2check:
            assert isinstance(get_block_head_response.get('blocks')[0].get(key), value)

    @pytest.mark.slow
    def test_get_balance_api(self):
        for address in self.addresses:
            get_balance_response = self.api.get_balance(address)
            assert len(get_balance_response) == 1
            assert isinstance(get_balance_response, dict)
            assert isinstance(get_balance_response.get('account'), list)
            keys2check = [('amount', str), ('block_hash', str), ('block_height', str), ('account_id', str)]
            for key, value in keys2check:
                assert isinstance(get_balance_response.get('account')[0].get(key), value)

    @pytest.mark.slow
    def test_get_tx_details_api(self):
        for tx_hash in self.txs_hash:
            get_tx_details_response = self.api.get_tx_details(tx_hash)
            assert len(get_tx_details_response) == 1
            assert isinstance(get_tx_details_response, dict)
            assert isinstance(get_tx_details_response.get('txns'), list)
            for tx in get_tx_details_response.get('txns'):
                keys2check = [('transaction_hash', str), ('receiver_account_id', str), ('block_timestamp', str),
                              ('actions', list), ('actions_agg', dict), ('outcomes', dict), ('block', dict),
                              ('outcomes_agg', dict)]
                for key, value in keys2check:
                    assert isinstance(tx.get(key), value)
                assert isinstance(tx.get('block').get('block_height'), int)
                assert isinstance(tx.get('actions')[0].get('action'), str)
                assert isinstance(tx.get('outcomes_agg').get('transaction_fee'), int)
                assert isinstance(tx.get('actions_agg').get('deposit'), float)

    @pytest.mark.slow
    def test_get_address_txs_api(self):
        for address in self.addresses:
            get_address_txs_response = self.api.get_address_txs(address)
            assert len(get_address_txs_response) == 1 or len(get_address_txs_response) == 2
            assert isinstance(get_address_txs_response, dict)
            assert isinstance(get_address_txs_response.get('txns'), list)
            for tx in get_address_txs_response.get('txns'):
                keys2check = [('transaction_hash', str), ('receiver_account_id', str), ('block_timestamp', str),
                              ('actions', list), ('actions_agg', dict), ('outcomes', dict), ('block', dict),
                              ('outcomes_agg', dict)]
                for key, value in keys2check:
                    assert isinstance(tx.get(key), value)
                assert isinstance(tx.get('block').get('block_height'), int)
                assert isinstance(tx.get('actions')[0].get('action'), str)
                transaction_fee = tx.get('outcomes_agg').get('transaction_fee')
                assert isinstance(transaction_fee, int) or (
                        isinstance(transaction_fee, float) and transaction_fee.is_integer())
                assert isinstance(tx.get('actions_agg').get('deposit'), int) or isinstance(
                    tx.get('actions_agg').get('deposit'), float)


class TestNearBlocksNearFromExplorer(TestFromExplorer):
    api = NearBlocksApi
    addresses = ['eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294']
    txs_addresses = ['eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294']
    txs_hash = ['EYf7MFDneobGfVWXwjJGbc7gSJWsafUbPxfap5BVBVx']
    explorerInterface = NearExplorerInterface
    currencies = Currencies.near
    symbol = 'NEAR'

    @classmethod
    def test_get_balance(cls):
        balance_mock_responses = [
            {
                "account": [
                    {
                        "amount": "5601931208170068373937391788054",
                        "block_hash": "7upTvBJb4RJr5WbVM7aMGMkrKB1pJhqkFaFo6rkdMpJg",
                        "block_height": 99688453,
                        "code_hash": "11111111111111111111111111111111",
                        "locked": "0",
                        "storage_paid_at": 0,
                        "storage_usage": 182,
                        "account_id": "eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294",
                        "created": {
                            "transaction_hash": "9H3dd3Tz6nUhvekXUFqzV4Dpk1BJ7waLXHuxJ7yZPyrd",
                            "block_timestamp": 1693037931371925000
                        },
                        "deleted": {
                            "transaction_hash": None,
                            "block_timestamp": None
                        }
                    }
                ]
            }
        ]
        expected_balances = [
            {
                'address': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                'balance': Decimal('5601931.208170068373937391788054'),
                'received': Decimal('5601931.208170068373937391788054'),
                'sent': Decimal('0'),
                'rewarded': Decimal('0')
            }
        ]
        cls.get_balance(balance_mock_responses, expected_balances)

    @classmethod
    def test_get_tx_details(cls):
        tx_details_mock_responses = [
            {
                "blocks": [
                    {
                        "block_height": "99708065",
                        "block_hash": "AX7a6F6rZMHq6J5VpfAs6Rgw4FErKZyMKVn4doN2VWU8",
                        "block_timestamp": "1693051765178255585",
                        "author_account_id": "cryptium.poolv1.near",
                        "chunks_agg": {
                            "gas_used": 40765044344602
                        },
                        "transactions_agg": {
                            "count": 5
                        }
                    }
                ]
            },
            {
                "txns": [
                    {
                        "transaction_hash": "EYf7MFDneobGfVWXwjJGbc7gSJWsafUbPxfap5BVBVx",
                        "included_in_block_hash": "BHZEPqAEg3PRZQGg1nbpEbhHbY4GXd78aHrjDFLuzfL8",
                        "block_timestamp": "1660378507566341591",
                        "signer_account_id": "eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294",
                        "receiver_account_id": "e9b2fd9f3a6280ab37f6ce6909f4487aa86e76be3627c83583c0c69a11dd0fe1",
                        "receipt_conversion_gas_burnt": "424555062500",
                        "receipt_conversion_tokens_burnt": "42455506250000000000",
                        "block": {
                            "block_height": 71902391
                        },
                        "actions": [
                            {
                                "action": "TRANSFER",
                                "method": None
                            }
                        ],
                        "actions_agg": {
                            "deposit": 9.99e+23,
                            "gas_attached": 0
                        },
                        "outcomes": {
                            "status": True
                        },
                        "outcomes_agg": {
                            "transaction_fee": 84911012500000000000,
                            "gas_used": 1273665187500
                        },
                        "receipts": [
                            {
                                "fts": [],
                                "nfts": []
                            },
                            {
                                "fts": [],
                                "nfts": []
                            }
                        ]
                    }
                ]
            }
        ]
        expected_txs_details = [
            {
                'success': True,
                'block': 71902391,
                'date': datetime.datetime(2022, 8, 13, 8, 15, 7, 566342, tzinfo=UTC),
                'raw': None,
                'inputs': [],
                'outputs': [],
                'transfers': [
                    {'type': 'MainCoin',
                     'symbol': 'NEAR',
                     'currency': 84,
                     'to': 'e9b2fd9f3a6280ab37f6ce6909f4487aa86e76be3627c83583c0c69a11dd0fe1',
                     'value': Decimal('0.999000000000000000000000'),
                     'is_valid': True,
                     'token': None,
                     'memo': None,
                     'from': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294'}
                ],
                'fees': Decimal('0.000084911012500000000000'),
                'memo': None,
                'confirmations': 27805674,
                'hash': 'EYf7MFDneobGfVWXwjJGbc7gSJWsafUbPxfap5BVBVx'
            }
        ]
        cls.get_tx_details(tx_details_mock_responses, expected_txs_details)

        # invalid
        tx_details_mock_responses2 = [
            {
                "blocks": [
                    {
                        "block_height": "99708065",
                        "block_hash": "AX7a6F6rZMHq6J5VpfAs6Rgw4FErKZyMKVn4doN2VWU8",
                        "block_timestamp": "1693051765178255585",
                        "author_account_id": "cryptium.poolv1.near",
                        "chunks_agg": {
                            "gas_used": 40765044344602
                        },
                        "transactions_agg": {
                            "count": 5
                        }
                    }
                ]
            },
            {'txns': [{'transaction_hash': '4ZEpQQTXstfzYrh2ap4MvEMafqXsXc5QFRmJ6jG9a6R1',
                       'included_in_block_hash': '3NrovZDshYtPE5wXBMXq88nEN1mxX8gJwFZMeByiZkze',
                       'block_timestamp': '1697455107768752470', 'signer_account_id': 'sweat_welcome.near',
                       'receiver_account_id': 'a002019b760b7a73fa3837be3d8f2eecc1014b8d51b2149abd7c8fa4c77709ba',
                       'receipt_conversion_gas_burnt': '4174947687500',
                       'receipt_conversion_tokens_burnt': '417494768750000000000', 'block': {'block_height': 103505850},
                       'actions': [{'action': 'TRANSFER', 'method': None}],
                       'actions_agg': {'deposit': 5e+22, 'gas_attached': 0}, 'outcomes': {'status': True},
                       'outcomes_agg': {'transaction_fee': 834989537500000000000, 'gas_used': 8573077937500},
                       'receipts': [{'fts': [], 'nfts': []}, {'fts': [], 'nfts': []}]}]}]
        expected_txs_details2 = [{'success': False}]
        cls.get_tx_details(tx_details_mock_responses2, expected_txs_details2)

        # invalid
        tx_details_mock_responses3 = [
            {
                "blocks": [
                    {
                        "block_height": "99708065",
                        "block_hash": "AX7a6F6rZMHq6J5VpfAs6Rgw4FErKZyMKVn4doN2VWU8",
                        "block_timestamp": "1693051765178255585",
                        "author_account_id": "cryptium.poolv1.near",
                        "chunks_agg": {
                            "gas_used": 40765044344602
                        },
                        "transactions_agg": {
                            "count": 5
                        }
                    }
                ]
            },
            {'txns': [{'transaction_hash': 'J6ncYMUkHKqCCoRtxgzeoBejdwuygz5F59ZP84iShWFG',
                       'included_in_block_hash': 'FRxWv56QCU9SocWcpkCVmaNMayNZVi6qdWNptMbHA5dg',
                       'block_timestamp': '1697455103848286983', 'signer_account_id': 'sweat_welcome.near',
                       'receiver_account_id': '89eda01ed1a62dabdc6d0ca87c6076de2d2f44a7523d071e6bf5f49a188ffdc3',
                       'receipt_conversion_gas_burnt': '4174947687500',
                       'receipt_conversion_tokens_burnt': '417494768750000000000', 'block': {'block_height': 103505847},
                       'actions': [{'action': 'TRANSFER', 'method': None}],
                       'actions_agg': {'deposit': 5e+22, 'gas_attached': 0}, 'outcomes': {'status': True},
                       'outcomes_agg': {'transaction_fee': 834989537500000000000, 'gas_used': 8573077937500},
                       'receipts': [{'fts': [], 'nfts': []}, {'fts': [], 'nfts': []}]}]}
        ]
        expected_txs_details3 = [{'success': False}]
        cls.get_tx_details(tx_details_mock_responses3, expected_txs_details3)

        cls.txs_hash = ['FMy4MTxATGtfxqTg5PZfGhQpRWej9Ppbttwo7FWF13wA']
        tx_details_mock_responses4 = [
            {
                "blocks": [
                    {
                        "block_height": "99708065",
                        "block_hash": "AX7a6F6rZMHq6J5VpfAs6Rgw4FErKZyMKVn4doN2VWU8",
                        "block_timestamp": "1693051765178255585",
                        "author_account_id": "cryptium.poolv1.near",
                        "chunks_agg": {
                            "gas_used": 40765044344602
                        },
                        "transactions_agg": {
                            "count": 5
                        }
                    }
                ]
            },
            {'txns': []}
        ]
        expected_txs_details4 = [{'success': False}]
        cls.get_tx_details(tx_details_mock_responses4, expected_txs_details4)

        tx_details_mock_responses5 = [
            {
                "blocks": [
                    {
                        "block_height": "99708065",
                        "block_hash": "AX7a6F6rZMHq6J5VpfAs6Rgw4FErKZyMKVn4doN2VWU8",
                        "block_timestamp": "1693051765178255585",
                        "author_account_id": "cryptium.poolv1.near",
                        "chunks_agg": {
                            "gas_used": 40765044344602
                        },
                        "transactions_agg": {
                            "count": 5
                        }
                    }
                ]
            },
            {'txns': [{'transaction_hash': '9ofcG3fDyDdpiW6e9BXdJ51cCEArDLVNvMpp3eaxAPdV',
                       'included_in_block_hash': 'FKywh8jcJARGjETBLmt5QdoS9j3WCvZ91bKAtMSBqgnJ',
                       'block_timestamp': '1691411199101642441', 'signer_account_id': 'jbouw.near',
                       'receiver_account_id': 'aurora', 'receipt_conversion_gas_burnt': '2427952303076',
                       'receipt_conversion_tokens_burnt': '242795230307600000000', 'block': {'block_height': 98274370},
                       'actions': [{'action': 'FUNCTION_CALL', 'method': 'deploy_upgrade'}],
                       'actions_agg': {'deposit': 0, 'gas_attached': 300000000000000}, 'outcomes': {'status': True},
                       'outcomes_agg': {'transaction_fee': 1.02969250104485e+22, 'gas_used': 103415615229485},
                       'receipts': [{'fts': [], 'nfts': []}, {'fts': [], 'nfts': []}, {'fts': [], 'nfts': []},
                                    {'fts': [], 'nfts': []}]}]}
        ]
        expected_txs_details5 = [{'success': False}]
        cls.get_tx_details(tx_details_mock_responses5, expected_txs_details5)

        tx_details_mock_responses5 = [
            {
                "blocks": [
                    {
                        "block_height": "99708065",
                        "block_hash": "AX7a6F6rZMHq6J5VpfAs6Rgw4FErKZyMKVn4doN2VWU8",
                        "block_timestamp": "1693051765178255585",
                        "author_account_id": "cryptium.poolv1.near",
                        "chunks_agg": {
                            "gas_used": 40765044344602
                        },
                        "transactions_agg": {
                            "count": 5
                        }
                    }
                ]
            },
            {'txns': [{'transaction_hash': '8WV8fM1Nb1q5f7vcyqGhX47o7MnyeXJTdi119VGbfQER',
                       'included_in_block_hash': '4dfNBgNsbt73m5BNSYvyF4y5UJx6pCUEqPksFMxXMB4i',
                       'block_timestamp': '1615774279964004498', 'signer_account_id': 'bridge.near',
                       'receiver_account_id': 'relayer.bridge.near', 'receipt_conversion_gas_burnt': '424555062500',
                       'receipt_conversion_tokens_burnt': '42455506250000000000', 'block': {'block_height': 32158723},
                       'actions': [{'action': 'CREATE_ACCOUNT', 'method': None}, {'action': 'TRANSFER', 'method': None},
                                   {'action': 'ADD_KEY', 'method': None}],
                       'actions_agg': {'deposit': 1e+27, 'gas_attached': 0}, 'outcomes': {'status': True},
                       'outcomes_agg': {'transaction_fee': 84911012500000000000, 'gas_used': 849110125000},
                       'receipts': [{'fts': [], 'nfts': []}, {'fts': [], 'nfts': []}]}]}
        ]
        expected_txs_details5 = [{'success': False}]
        cls.get_tx_details(tx_details_mock_responses5, expected_txs_details5)

    @classmethod
    def test_get_address_txs(cls):
        address_txs_mock_responses = [
            {
                "blocks": [
                    {
                        "block_height": "99708065",
                        "block_hash": "AX7a6F6rZMHq6J5VpfAs6Rgw4FErKZyMKVn4doN2VWU8",
                        "block_timestamp": "1693051765178255585",
                        "author_account_id": "cryptium.poolv1.near",
                        "chunks_agg": {
                            "gas_used": 40765044344602
                        },
                        "transactions_agg": {
                            "count": 5
                        }
                    }
                ]
            },
            {
                'txns': [
                    {'receipt_id': 'DTa3hPjCUH941o5uHktMsz9ro5d18vVjY6u1U8LQ5zcH',
                     'predecessor_account_id': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                     'receiver_account_id': 'ac2679a37be298c0bae1a1a2acfedca62898a83b28d42606aa69b5093e5fc43d',
                     'transaction_hash': 'BJf483ZQ3BEuBzqTAVPe148D9d8ACZhevbGHEosbtefL',
                     'included_in_block_hash': 'DnetYJdHEpjGdY7wRKbAsuWajWo4MgJnK23veX1Ye9Qf',
                     'block_timestamp': '1693058598974985770',
                     'block': {'block_height': 99706878},
                     'actions': [{'action': 'TRANSFER', 'method': None}],
                     'actions_agg': {'deposit': 1.268878e+25},
                     'outcomes': {'status': True},
                     'outcomes_agg': {'transaction_fee': 834989537500000000000}, 'logs': []},
                    {'receipt_id': 'HgiyU1xUu3zxt8K4BopPeb2nprrVn1nDgn4V8mQvr9jo',
                     'predecessor_account_id': 'system',
                     'receiver_account_id': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                     'transaction_hash': 'BJf483ZQ3BEuBzqTAVPe148D9d8ACZhevbGHEosbtefL',
                     'included_in_block_hash': 'DnetYJdHEpjGdY7wRKbAsuWajWo4MgJnK23veX1Ye9Qf',
                     'block_timestamp': '1693058598974985770',
                     'block': {'block_height': 99706878},
                     'actions': [{'action': 'TRANSFER', 'method': None}],
                     'actions_agg': {'deposit': 1.268878e+25},
                     'outcomes': {'status': True},
                     'outcomes_agg': {'transaction_fee': 834989537500000000000},
                     'logs': []},
                    {'receipt_id': 'tKpvEr3qvJdS96MvBDb3dnZnSa4UWKDJN9S9mfusPJ3',
                     'predecessor_account_id': '9b363d1cb2648d2a553f9813961cbda2422fb0d6283196890e78b4ef47a0d39c',
                     'receiver_account_id': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                     'transaction_hash': '7rJjitfY68AXwd6AypmrYEvme9sGZR5k91cEDH4KY2Ho',
                     'included_in_block_hash': '33rRmAuR26VuVNCupP6QaB5NwVMJnd8yxFzb2RKXFuQA',
                     'block_timestamp': '1693058056663827596', 'block': {'block_height': 99706392},
                     'actions': [{'action': 'TRANSFER', 'method': None}],
                     'actions_agg': {'deposit': 1.5552293163685625e+25}, 'outcomes': {'status': True},
                     'outcomes_agg': {'transaction_fee': 834989537500000000000}, 'logs': []},
                    {'receipt_id': '6vGLSSPeMLLwa9veJD5deMXdJm68Faw7hqLz5fBnNTiq',
                     'predecessor_account_id': 'e236f7133d89e431e3a0fed998979a81e37c983d235a7ecd9ab6758ad6270a60',
                     'receiver_account_id': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                     'transaction_hash': '9m2h7WQPtRfbBywZ8zLLuSz84N6kg2nLZfgPp33H4DBo',
                     'included_in_block_hash': 'A4dahM1xmtD6mmU2SSvFfRprpwPVDZc95CzFM34sygYW',
                     'block_timestamp': '1693057873655739272', 'block': {'block_height': 99706233},
                     'actions': [{'action': 'TRANSFER', 'method': None}],
                     'actions_agg': {'deposit': 1.4816803163685625e+25}, 'outcomes': {'status': True},
                     'outcomes_agg': {'transaction_fee': 834989537500000000000}, 'logs': []},
                    {'receipt_id': '8ytijnQEuE9DBk4KiBz5gNKkXuUPsz78WnebTFumW5Dn',
                     'predecessor_account_id': '9b363d1cb2648d2a553f9813961cbda2422fb0d6283196890e78b4ef47a0d39c',
                     'receiver_account_id': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                     'transaction_hash': 'B5BZ7x82PFuhCyAUhi6tCzm5q8oujzFwmP3k1KmJy3QM',
                     'included_in_block_hash': 'DtsurXK8kCoW7CZUr9tvFrN5zNYAyXx45TPtAAsYQyKV',
                     'block_timestamp': '1693057697288125164', 'block': {'block_height': 99706079},
                     'actions': [{'action': 'TRANSFER', 'method': None}],
                     'actions_agg': {'deposit': 1.7318153223125e+22}, 'outcomes': {'status': True},
                     'outcomes_agg': {'transaction_fee': 834989537500000000000}, 'logs': []},
                    {'receipt_id': 'Hzvq2NG4G5ygTmx4Dg1hte8TKUostCaJTQ7BDKxrSVSF',
                     'predecessor_account_id': 'e236f7133d89e431e3a0fed998979a81e37c983d235a7ecd9ab6758ad6270a60',
                     'receiver_account_id': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                     'transaction_hash': '8j89jiow41xeqkoQBjgEnqbohPunYGL3ZVsJM3JG32qH',
                     'included_in_block_hash': '39Y8SNBoCPqbrt8r8fgdZ91yijSfmWNMGmoRguSGxPp9',
                     'block_timestamp': '1693057525766443945', 'block': {'block_height': 99705926},
                     'actions': [{'action': 'TRANSFER', 'method': None}],
                     'actions_agg': {'deposit': 2.7318153223125e+22}, 'outcomes': {'status': True},
                     'outcomes_agg': {'transaction_fee': 834989537500000000000}, 'logs': []},
                    {'receipt_id': '9u3xXVVEW5GF9SDfXYGrQepMNWMyksKsgpGGZp7jrMJq',
                     'predecessor_account_id': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                     'receiver_account_id': 'eedb4e839366c563cf56220dd1d326e27a92db3de13ec0a5dd0e8bf6f1bac77d',
                     'transaction_hash': '9NQUmCUg2yUKN3zGX3jnGjxRANrEvR71RnTLUrBTdQdM',
                     'included_in_block_hash': '6SMqEbqzMSzLmpsDtTJwS2VmLruhcL3ArBzzs3BPq8sF',
                     'block_timestamp': '1693056204600964465', 'block': {'block_height': 99704763},
                     'actions': [{'action': 'TRANSFER', 'method': None}], 'actions_agg': {'deposit': 1.561257e+25},
                     'outcomes': {'status': True}, 'outcomes_agg': {'transaction_fee': 834989537500000000000},
                     'logs': []},
                    {'receipt_id': '2PXF4sHyTLcgneSwTYHTVss3ryLJCUfFcQ8gPRJ8YkEs', 'predecessor_account_id': 'system',
                     'receiver_account_id': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                     'transaction_hash': '9NQUmCUg2yUKN3zGX3jnGjxRANrEvR71RnTLUrBTdQdM',
                     'included_in_block_hash': '6SMqEbqzMSzLmpsDtTJwS2VmLruhcL3ArBzzs3BPq8sF',
                     'block_timestamp': '1693056204600964465', 'block': {'block_height': 99704763},
                     'actions': [{'action': 'TRANSFER', 'method': None}], 'actions_agg': {'deposit': 1.561257e+25},
                     'outcomes': {'status': True}, 'outcomes_agg': {'transaction_fee': 834989537500000000000},
                     'logs': []},
                    {'receipt_id': 'DqFrCxrCoazUPAJSjtonUZqPCdxc1WC6P1u19cu2pWDK', 'predecessor_account_id': 'system',
                     'receiver_account_id': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                     'transaction_hash': '7U7yRU1w691FPWxasCGMNu74oaPEopzMisqdV3EZy3Hu',
                     'included_in_block_hash': 'BASAZKxWUasR76VJ7PZjRKpap6mDh51c8PC1zxFcY6UT',
                     'block_timestamp': '1693055865210790131', 'block': {'block_height': 99704464},
                     'actions': [{'action': 'TRANSFER', 'method': None}], 'actions_agg': {'deposit': 1.22e+25},
                     'outcomes': {'status': True}, 'outcomes_agg': {'transaction_fee': 834989537500000000000},
                     'logs': []},
                    {'receipt_id': 'GvYkgEdG6MNSFzHX9ngN1n9gC1xgfKtCKydUq5sdPjAE',
                     'predecessor_account_id': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                     'receiver_account_id': 'a2646703e2a8cd3b5635fdc3a42ecef6f873605681e13b59b911eb8b819ad557',
                     'transaction_hash': '7U7yRU1w691FPWxasCGMNu74oaPEopzMisqdV3EZy3Hu',
                     'included_in_block_hash': 'BASAZKxWUasR76VJ7PZjRKpap6mDh51c8PC1zxFcY6UT',
                     'block_timestamp': '1693055865210790131', 'block': {'block_height': 99704464},
                     'actions': [{'action': 'TRANSFER', 'method': None}],
                     'actions_agg': {'deposit': 1.22e+25}, 'outcomes': {'status': True},
                     'outcomes_agg': {'transaction_fee': 834989537500000000000}, 'logs': []},
                    {'receipt_id': 'CnppaoCdRLorybzGRNYk2Fjjn8V2mq7mSK6PqTQoY3Ho',
                     'predecessor_account_id': '02087d7ef464a11a99e3885c93079ec55b6027975d36f5065060644a136df785',
                     'receiver_account_id': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                     'transaction_hash': '5jAzpqyDLcbjHZtAsT8Kkpnry7FqbjEwg6KD6oDkueks',
                     'included_in_block_hash': 'DiNV9uqEzsXrSgZRyqCH5d8YVQHQeCUznPVrg18fN5QB',
                     'block_timestamp': '1693053192353342492', 'block': {'block_height': 99702099},
                     'actions': [{'action': 'TRANSFER', 'method': None}],
                     'actions_agg': {'deposit': 2.3807733184610624e+25}, 'outcomes': {'status': True},
                     'outcomes_agg': {'transaction_fee': 834989537500000000000}, 'logs': []},
                    {'receipt_id': 'HmE86kwSaTzExGNnwRcE4DDZYjeYU9VbdTTcVfUNwiqy', 'predecessor_account_id': 'system',
                     'receiver_account_id': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                     'transaction_hash': '8dHSeQQYpDRpRS7qwjdnKDufACoj5JXgaSVMnTSriAin',
                     'included_in_block_hash': '2Z4p4kJS6g5QWD9v6QRLMRCRpDmYiExDpHtrTE6qW7wV',
                     'block_timestamp': '1693052794635136042', 'block': {'block_height': 99701739},
                     'actions': [{'action': 'TRANSFER', 'method': None}], 'actions_agg': {'deposit': 1.491983e+25},
                     'outcomes': {'status': True}, 'outcomes_agg': {'transaction_fee': 834989537500000000000},
                     'logs': []},
                    {'receipt_id': '7zf68zw6iB6ezfPaTCLvktBTefAtQJNXN8d8gTacSrNi',
                     'predecessor_account_id': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                     'receiver_account_id': '612509badfba7e0e85ad49e297900661b07c39140c20cb388134e0ae56896051',
                     'transaction_hash': '8dHSeQQYpDRpRS7qwjdnKDufACoj5JXgaSVMnTSriAin',
                     'included_in_block_hash': '2Z4p4kJS6g5QWD9v6QRLMRCRpDmYiExDpHtrTE6qW7wV',
                     'block_timestamp': '1693052794635136042', 'block': {'block_height': 99701739},
                     'actions': [{'action': 'TRANSFER', 'method': None}],
                     'actions_agg': {'deposit': 1.491983e+25}, 'outcomes': {'status': True},
                     'outcomes_agg': {'transaction_fee': 834989537500000000000}, 'logs': []},
                    {'receipt_id': '7EpnnfjSviWQjetZbJ3DgYsfeZjxwYcSfp3YMj2Vhm4Q',
                     'predecessor_account_id': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                     'receiver_account_id': '0d213e4a2a6ef14dd006a1f11d01d17b520aa3e49b0826b4caa1d0e331059090',
                     'transaction_hash': 'Fg2u8XQr2RdoUJgi3w9nc2jMhjQj6acTVp3PvbYbk4Yt',
                     'included_in_block_hash': '4vyyCFmehJWFv7WU4ppxvJ77UhLpny6JK8KSx5u4naBd',
                     'block_timestamp': '1693052397362318667', 'block': {'block_height': 99701380},
                     'actions': [{'action': 'TRANSFER', 'method': None}], 'actions_agg': {'deposit': 1.488708e+25},
                     'outcomes': {'status': True}, 'outcomes_agg': {'transaction_fee': 834989537500000000000},
                     'logs': []},
                    {'receipt_id': 'BAHbky283D7NXBowz3fhqUfC56V6DyNWmrsuPmPrGHvB', 'predecessor_account_id': 'system',
                     'receiver_account_id': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                     'transaction_hash': 'Fg2u8XQr2RdoUJgi3w9nc2jMhjQj6acTVp3PvbYbk4Yt',
                     'included_in_block_hash': '4vyyCFmehJWFv7WU4ppxvJ77UhLpny6JK8KSx5u4naBd',
                     'block_timestamp': '1693052397362318667', 'block': {'block_height': 99701380},
                     'actions': [{'action': 'TRANSFER', 'method': None}], 'actions_agg': {'deposit': 1.488708e+25},
                     'outcomes': {'status': True}, 'outcomes_agg': {'transaction_fee': 834989537500000000000},
                     'logs': []},
                    {'receipt_id': '7Rp4ppgbSP5CBWzERwbNUNNd2tMK497dEz8SwEmNULaK',
                     'predecessor_account_id': 'b491de108648d14e9baf29c92ee129a5772a49c69789925e7f5b59875ad68aa8',
                     'receiver_account_id': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                     'transaction_hash': 'CkvfE543xDbMDyo3ZtwPzg9NkuYQWx7G3QoAraoP2p8P',
                     'included_in_block_hash': '812YK1URGcSBpEpapqjCCq3dZD5WFjp8MCH3Hbx7MrH9',
                     'block_timestamp': '1693050193148403628', 'block': {'block_height': 99699405},
                     'actions': [{'action': 'TRANSFER', 'method': None}],
                     'actions_agg': {'deposit': 2.0045266244617386e+25}, 'outcomes': {'status': True},
                     'outcomes_agg': {'transaction_fee': 834989537500000000000}, 'logs': []},
                    {'receipt_id': '7YLKsWta1AuLKrH4TP4M2drLNKyaAzZWQFHaPi4mqGtH', 'predecessor_account_id': 'system',
                     'receiver_account_id': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                     'transaction_hash': '5HfN9C5UnRVp93RrcBRKSo24wFKJuT1Q2474qq9Q6q4H',
                     'included_in_block_hash': '7Zzp2H9kaJw7VZbkWaLaSgE2dbn6gbXmDbsAArPLYGWQ',
                     'block_timestamp': '1693049624043389692', 'block': {'block_height': 99698890},
                     'actions': [{'action': 'TRANSFER', 'method': None}], 'actions_agg': {'deposit': 8.12891e+24},
                     'outcomes': {'status': True}, 'outcomes_agg': {'transaction_fee': 834989537500000000000},
                     'logs': []},
                ]
            }
        ]
        expected_addresses_txs = [
            [
                {
                    'address': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                    'block': 99706878,
                    'confirmations': 1187,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294'],
                    'hash': 'BJf483ZQ3BEuBzqTAVPe148D9d8ACZhevbGHEosbtefL',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 8, 26, 14, 3, 18, 974986, tzinfo=UTC),
                    'value': Decimal('-12.688780000000000000000000')
                },
                {
                    'address': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                    'block': 99706392,
                    'confirmations': 1673,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['9b363d1cb2648d2a553f9813961cbda2422fb0d6283196890e78b4ef47a0d39c'],
                    'hash': '7rJjitfY68AXwd6AypmrYEvme9sGZR5k91cEDH4KY2Ho',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 8, 26, 13, 54, 16, 663828, tzinfo=UTC),
                    'value': Decimal('15.552293163685625000000000')
                },
                {
                    'address': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                    'block': 99706233,
                    'confirmations': 1832,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['e236f7133d89e431e3a0fed998979a81e37c983d235a7ecd9ab6758ad6270a60'],
                    'hash': '9m2h7WQPtRfbBywZ8zLLuSz84N6kg2nLZfgPp33H4DBo',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 8, 26, 13, 51, 13, 655739, tzinfo=UTC),
                    'value': Decimal('14.816803163685625000000000')
                },
                {
                    'address': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                    'block': 99704763,
                    'confirmations': 3302,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294'],
                    'hash': '9NQUmCUg2yUKN3zGX3jnGjxRANrEvR71RnTLUrBTdQdM',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 8, 26, 13, 23, 24, 600964, tzinfo=UTC),
                    'value': Decimal('-15.612570000000000000000000')
                },
                {
                    'address': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                    'block': 99704464,
                    'confirmations': 3601,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294'],
                    'hash': '7U7yRU1w691FPWxasCGMNu74oaPEopzMisqdV3EZy3Hu',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 8, 26, 13, 17, 45, 210790, tzinfo=UTC),
                    'value': Decimal('-12.200000000000000000000000')
                },
                {
                    'address': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                    'block': 99702099,
                    'confirmations': 5966,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['02087d7ef464a11a99e3885c93079ec55b6027975d36f5065060644a136df785'],
                    'hash': '5jAzpqyDLcbjHZtAsT8Kkpnry7FqbjEwg6KD6oDkueks',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 8, 26, 12, 33, 12, 353343, tzinfo=UTC),
                    'value': Decimal('23.807733184610624000000000')
                },
                {
                    'address': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                    'block': 99701739,
                    'confirmations': 6326,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294'],
                    'hash': '8dHSeQQYpDRpRS7qwjdnKDufACoj5JXgaSVMnTSriAin',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 8, 26, 12, 26, 34, 635136, tzinfo=UTC),
                    'value': Decimal('-14.919830000000000000000000')
                },
                {
                    'address': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                    'block': 99701380,
                    'confirmations': 6685,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294'],
                    'hash': 'Fg2u8XQr2RdoUJgi3w9nc2jMhjQj6acTVp3PvbYbk4Yt',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 8, 26, 12, 19, 57, 362319, tzinfo=UTC),
                    'value': Decimal('-14.887080000000000000000000')
                },
                {
                    'address': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
                    'block': 99699405,
                    'confirmations': 8660,
                    'contract_address': None,
                    'details': {},
                    'from_address': ['b491de108648d14e9baf29c92ee129a5772a49c69789925e7f5b59875ad68aa8'],
                    'hash': 'CkvfE543xDbMDyo3ZtwPzg9NkuYQWx7G3QoAraoP2p8P',
                    'huge': False,
                    'invoice': None,
                    'is_double_spend': False,
                    'tag': None,
                    'timestamp': datetime.datetime(2023, 8, 26, 11, 43, 13, 148404, tzinfo=UTC),
                    'value': Decimal('20.045266244617386000000000')
                },
            ]
        ]
        cls.get_address_txs(address_txs_mock_responses, expected_addresses_txs)
