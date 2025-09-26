import datetime
import pytest
from decimal import Decimal
from unittest import TestCase

from pytz import UTC

from exchange.blockchain.api.tezos.bitquery_tezos import BitQueryTezosApi
from exchange.blockchain.api.tezos.tezos_explorer_interface import TezosExplorerInterface
from exchange.base.models import Currencies
from exchange.blockchain.tests.api.general_test.general_test_from_explorer import TestFromExplorer


class TestBitQueryTezosApiCalls(TestCase):
    api = BitQueryTezosApi
    account_address = ['tz1XEJBiCZfBbo8rWNcQfABVb2dRGG5Kp9vB',
                       'tz1Kv61qYtajAr5jkXcbuYJ3Rv87k3523DKX']

    txs_hash = ['opNdzcqysGLu7YXmu26EDG9hqkLFD3GPSGpPiZs4wBcqCqX5QAa',
                'opGibCwmdUmikDQ2tuN4LBncpuhXRJbMaVFYzhLzfR96yB3Avgu',
                'opWN2DtNJwREBcqnJY686FvHKLsukjTV1mwv9CKPkdtDRuJQ32h']

    blocks = [3210456, 3029399, 3897587]

    def check_general_response(self, response):
        if not response:
            return False
        if not isinstance(response, dict):
            return False
        if not response.get('data'):
            return False
        if not isinstance(response.get('data'), dict):
            return False
        if not response.get('data').get('tezos'):
            return False
        if not isinstance(response.get('data').get('tezos'), dict):
            return False
        return True

    def check_block_response_part(self, response):
        if not response.get('blocks'):
            return False
        if not isinstance(response.get('blocks'), list):
            return False
        if not response.get('blocks')[0]:
            return False
        if not isinstance(response.get('blocks')[0], dict):
            return False
        if not response.get('blocks')[0].get('count'):
            return False
        if not isinstance(response.get('blocks')[0].get('count'), int):
            return False
        return True

    @pytest.mark.slow
    def test_get_balance_api(self):
        for address in self.account_address:
            get_balance_result = self.api.get_balance(address)
            assert self.check_general_response(get_balance_result)
            balance = get_balance_result.get('data').get('tezos')
            assert balance.get('address')
            assert isinstance(balance.get('address'), list)
            assert balance.get('address')[0]
            assert isinstance(balance.get('address')[0], dict)
            assert balance.get('address')[0].get('balance')
            assert isinstance(balance.get('address')[0].get('balance'), list)
            assert balance.get('address')[0].get('balance')[0]
            assert isinstance(balance.get('address')[0].get('balance')[0], dict)
            assert balance.get('address')[0].get('balance')[0].get('available') is not None
            assert isinstance(balance.get('address')[0].get('balance')[0].get('available'), float)

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_result = self.api.get_block_head()
        assert self.check_general_response(get_block_head_result)
        block_head = get_block_head_result.get('data').get('tezos')
        assert self.check_block_response_part(block_head)

    @pytest.mark.slow
    def test_get_tx_details_api(self):
        for tx_hash in self.txs_hash:
            get_details_tx_result = self.api.get_tx_details(tx_hash)
            self.check_general_response(get_details_tx_result)
            tx_details = get_details_tx_result.get('data').get('tezos')
            self.check_block_response_part(tx_details)
            if tx_details.get('transactions'):
                assert isinstance(tx_details.get('transactions'), list)
                for tx in get_details_tx_result.get('data').get('tezos').get('transactions'):
                    keys2check = [('hash', str), ('amount', str), ('receiver', dict), ('timestamp', dict),
                                  ('status', str),
                                  ('sender', dict), ('block', dict), ('internal', bool), ('success', bool),
                                  ('fee', str)]
                    for key, value in keys2check:
                        assert isinstance(tx.get(key), value)
                    assert isinstance(tx.get('receiver').get('address'), str)
                    assert isinstance(tx.get('sender').get('address'), str)
                    assert isinstance(tx.get('block').get('height'), str)
                    assert isinstance(tx.get('timestamp').get('time'), str)

    @pytest.mark.slow
    def test_get_address_txs_api(self):
        for address in self.account_address:
            get_address_txs_result = self.api.get_address_txs(address)
            assert self.check_general_response(get_address_txs_result)
            address_txs = get_address_txs_result.get('data').get('tezos')
            assert self.check_block_response_part(address_txs)
            if address_txs.get('transactions'):
                assert isinstance(address_txs.get('transactions'), list)
                for tx in get_address_txs_result.get('data').get('tezos').get('transactions'):
                    keys2check = [('hash', str), ('internal', bool), ('sender', dict), ('receiver', dict), ('fee', str),
                                  ('timestamp', dict), ('block', dict), ('amount', str), ('success', bool),
                                  ('status', str)]
                    for key, value in keys2check:
                        assert isinstance(tx.get(key), value)
                    assert isinstance(tx.get('receiver').get('address'), str)
                    assert isinstance(tx.get('sender').get('address'), str)
                    assert isinstance(tx.get('block').get('height'), str)
                    assert isinstance(tx.get('block').get('hash'), str)
                    assert isinstance(tx.get('timestamp').get('time'), str)

    @pytest.mark.slow
    def test_get_block_txs_api(self):
        for block in self.blocks:
            get_block_txs_result = self.api.get_block_txs(block)
            assert self.check_general_response(get_block_txs_result)
            block_txs = get_block_txs_result.get('data').get('tezos')
            if block_txs.get('transactions'):
                assert isinstance(block_txs.get('transactions'), list)
                for tx in block_txs.get('transactions'):
                    keys2check = [('hash', str), ('internal', bool), ('sender', dict), ('receiver', dict),
                                  ('status', str),
                                  ('success', bool), ('timestamp', dict), ('block', dict), ('amount', str),
                                  ('fee', str)]
                    for key, value in keys2check:
                        assert isinstance(tx.get(key), value)
                    assert isinstance(tx.get('receiver').get('address'), str)
                    assert isinstance(tx.get('sender').get('address'), str)
                    assert isinstance(tx.get('block').get('height'), str)
                    assert isinstance(tx.get('block').get('hash'), str)
                    assert isinstance(tx.get('timestamp').get('time'), str)


class TestBitQueryTezosFromExplorer(TestFromExplorer):
    api = BitQueryTezosApi
    addresses = ['tz1XEJBiCZfBbo8rWNcQfABVb2dRGG5Kp9vB']
    txs_addresses = ['tz1XEJBiCZfBbo8rWNcQfABVb2dRGG5Kp9vB', 'tz1Kv61qYtajAr5jkXcbuYJ3Rv87k3523DKX']
    txs_hash = ['opNdzcqysGLu7YXmu26EDG9hqkLFD3GPSGpPiZs4wBcqCqX5QAa',
                'opWN2DtNJwREBcqnJY686FvHKLsukjTV1mwv9CKPkdtDRuJQ32h']
    currencies = Currencies.xtz
    explorerInterface = TezosExplorerInterface
    symbol = 'XTZ'

    @classmethod
    def test_get_balance(cls):
        balance_mock_responses = [
            {
                'data': {
                    "tezos": {
                        "address": [
                            {
                                "balance": [
                                    {
                                        "available": 690.82767
                                    }
                                ],
                                "address": "tz1XEJBiCZfBbo8rWNcQfABVb2dRGG5Kp9vB"
                            }
                        ]
                    }
                }
            }
        ]
        expected_balances = [
            {'address': 'tz1XEJBiCZfBbo8rWNcQfABVb2dRGG5Kp9vB',
             'balance': Decimal('690.82767'),
             'received': Decimal('690.82767'),
             'rewarded': Decimal('0'),
             'sent': Decimal('0')}
        ]
        cls.get_balance(balance_mock_responses, expected_balances)

    @classmethod
    def test_get_tx_details(cls):
        tx_details_mock_response = [
            {'data': {'tezos': {'blocks': [{'count': 5815651}], 'transactions': [
                {'amount': '5.61084', 'hash': 'opNdzcqysGLu7YXmu26EDG9hqkLFD3GPSGpPiZs4wBcqCqX5QAa',
                 'receiver': {'address': 'tz1Kv61qYtajAr5jkXcbuYJ3Rv87k3523DKX'}, 'status': 'applied',
                 'timestamp': {'time': '2023-07-16T10:40:41Z'}, 'internal': False,
                 'sender': {'address': 'tz2WDATNYnp7FdsmuZDYSidioZqeoLNZqXvE'},
                 'block': {'height': '3887119', 'hash': 'BMMzo3eudpeZpXpbK48TRBT8nsfvccPZ52dXgrFyYQc9j3fHwgx'},
                 'success': True, 'fee': '0.0008'},
                {'amount': '11.5', 'hash': 'opNdzcqysGLu7YXmu26EDG9hqkLFD3GPSGpPiZs4wBcqCqX5QAa',
                 'receiver': {'address': 'tz1XEJBiCZfBbo8rWNcQfABVb2dRGG5Kp9vB'}, 'status': 'applied',
                 'timestamp': {'time': '2023-07-16T10:40:41Z'}, 'internal': False,
                 'sender': {'address': 'tz2WDATNYnp7FdsmuZDYSidioZqeoLNZqXvE'},
                 'block': {'height': '3887119', 'hash': 'BMMzo3eudpeZpXpbK48TRBT8nsfvccPZ52dXgrFyYQc9j3fHwgx'},
                 'success': True, 'fee': '0.0008'}]}}} ,
            {'data': {'tezos': {'blocks': [{'count': 5815651}], 'transactions': []}}}
        ]
        expected_txs_details = [
            {'hash': 'opNdzcqysGLu7YXmu26EDG9hqkLFD3GPSGpPiZs4wBcqCqX5QAa', 'success': True, 'block': 3887119, 'date': datetime.datetime(2023, 7, 16, 10, 40, 41, tzinfo=UTC), 'fees': Decimal('0.0008'), 'memo': None, 'confirmations': 1928532, 'raw': None, 'inputs': [], 'outputs': [], 'transfers': [{'type': 'MainCoin', 'symbol': 'XTZ', 'currency': 30, 'from': 'tz2WDATNYnp7FdsmuZDYSidioZqeoLNZqXvE', 'to': 'tz1Kv61qYtajAr5jkXcbuYJ3Rv87k3523DKX', 'value': Decimal('5.61084'), 'is_valid': True, 'memo': None, 'token': None}, {'type': 'MainCoin', 'symbol': 'XTZ', 'currency': 30, 'from': 'tz2WDATNYnp7FdsmuZDYSidioZqeoLNZqXvE', 'to': 'tz1XEJBiCZfBbo8rWNcQfABVb2dRGG5Kp9vB', 'value': Decimal('11.5'), 'is_valid': True,  'memo': None, 'memo': None,'token': None}]},
            {'success': False}
        ]
        cls.get_tx_details(tx_details_mock_response, expected_txs_details)

    @classmethod
    def test_get_address_txs(cls):
        address_txs_mock_response = [
            {'data': {'tezos': {'blocks': [{'count': 5815680}], 'transactions': []}}},
            {'data': {'tezos': {'blocks': [{'count': 5815680}], 'transactions': [
                {'hash': 'op5iZ95PZdzVWnj6P1STpfGwA8og5jaVCD3CComPNqX8VoUGUwL', 'internal': False,
                 'sender': {'address': 'tz1PpZctTPYj3GjY1B9wtWJh4hgd3XMo1t3R'},
                 'receiver': {'address': 'tz1Kv61qYtajAr5jkXcbuYJ3Rv87k3523DKX'},
                 'timestamp': {'time': '2024-06-13T21:00:00Z'},
                 'block': {'hash': 'BLo8Y2jXvjbQX8oJEdUSpv6KgFKsqMryShvGXdvQ4d17JrHkVo2', 'height': '5801356'},
                 'amount': '13.701613', 'success': True, 'status': 'applied', 'fee': '0.002854'}]}}}
        ]
        expected_addresses_txs = [
            [],
            [
                {'contract_address': None, 'address': 'tz1Kv61qYtajAr5jkXcbuYJ3Rv87k3523DKX', 'from_address': ['tz1PpZctTPYj3GjY1B9wtWJh4hgd3XMo1t3R'], 'hash': 'op5iZ95PZdzVWnj6P1STpfGwA8og5jaVCD3CComPNqX8VoUGUwL', 'block': 5801356, 'timestamp': datetime.datetime(2024, 6, 13, 21, 0, tzinfo=UTC), 'value': Decimal('13.701613'), 'confirmations': 14324, 'is_double_spend': False, 'details': {}, 'tag': None, 'huge': False, 'invoice': None}
            ]
        ]
        cls.get_address_txs(address_txs_mock_response, expected_addresses_txs)

    @classmethod
    def test_get_block_txs(cls):
        block_txs_mock_response = [
            {
                'data': {
                    "tezos": {
                        "blocks": [
                            {
                                "count": 4011631
                            }
                        ]
                    }
                }
            },
            {
                'data': {
                    "tezos": {
                        "transactions": [
                            {
                                "hash": "opRxX5QREPk7P1SViVdEvCBNCj2WNXX8LQJmZfYir87R1HejFfH",
                                "internal": False,
                                "sender": {
                                    "address": "tz1bDXD6nNSrebqmAnnKKwnX1QdePSMCj4MX"
                                },
                                "receiver": {
                                    "address": "tz1QWad59nCK6BSnoWsCp97HSr6qRtBVrgaJ"
                                },
                                "timestamp": {
                                    "time": "2023-04-19T19:21:17Z"
                                },
                                "block": {
                                    "hash": "BLMLEsV8xF7w9wmdfkgW2beUCSKXgW9mTqef3bnTesZuADv5bw5",
                                    "height": "3388485"
                                },
                                "amount": "477.37",
                                "success": True,
                                "status": "applied",
                                "fee": "0.0056"
                            },
                            {
                                "hash": "opUtmStZzNu344GxYrUXvQ7J1VC6KVTRrEGwPu1SQo8GK26xsqM",
                                "internal": False,
                                "sender": {
                                    "address": "tz1YpWsMwc4gSyjtxEF3JbmN6YrGiDidaSmg"
                                },
                                "receiver": {
                                    "address": "tz1QWad59nCK6BSnoWsCp97HSr6qRtBVrgaJ"
                                },
                                "timestamp": {
                                    "time": "2022-11-17T18:12:44Z"
                                },
                                "block": {
                                    "hash": "BLpA8m5srwQr3aLCCHKQhFLbpkGA3qb9Tvm4nayy6JzJ76Lobdb",
                                    "height": "2892475"
                                },
                                "amount": "3.68",
                                "success": True,
                                "status": "applied",
                                "fee": "0.0034"
                            },
                        ]
                    }
                }
            },
            {
                "tezos": {
                    "transactions": [
                        {
                            "hash": "ooXyGk9WwHUVwBHiaF4jceX8SCqTZk7bYrR5F5omLjZ2GYpzuWz",
                            "internal": False,
                            "sender": {
                                "address": "tz2NM7FS2diC2qEjU5ze4s894qGVybTshBgC"
                            },
                            "receiver": {
                                "address": "tz1XZo9b4FxoNJLDjgiNm8rHzgGtCNhT1FqA"
                            },
                            "status": "applied",
                            "success": True,
                            "timestamp": {
                                "time": "2022-12-25T15:39:29Z"
                            },
                            "block": {
                                "hash": "BLy59wMURkvHhKXNt18zj9iU3CxeZ8ua12fqj8Gyv4xokcSKKC4",
                                "height": "3000000"
                            },
                            "amount": "0.1",
                            "fee": "0.000372"
                        }
                    ]
                }
            },
            {
                "tezos": {
                    "transactions": [
                        {
                            "hash": "onqschvfTVVD75Fmk7heGtRo958EPBg2ckDAwX7gwTRFzX7ZuDu",
                            "internal": False,
                            "sender": {
                                "address": "tz1Q7RpsRvbozbY5zuhv5AaXuoqeXrcFAtgF"
                            },
                            "receiver": {
                                "address": "tz1LCbv9chfGEqrRSpiCtjKrw7x6D6Lobsc6"
                            },
                            "status": "applied",
                            "success": True,
                            "timestamp": {
                                "time": "2022-12-25T15:39:59Z"
                            },
                            "block": {
                                "hash": "BLnenWNtVr8h4nM4qcfJXxy8KtsGcbM3YUMmxpjUxfavxfRz3KL",
                                "height": "3000001"
                            },
                            "amount": "110.201471",
                            "fee": "0.0008"
                        },
                        {
                            "hash": "ooXXqb8JwBcVYrcEWGkLGABjD6w6u3d8PHqii5yWQ5fnnawRdqf",
                            "internal": False,
                            "sender": {
                                "address": "tz1XTZM55hF7g98CzY88MXWhmK8QioGXHtuY"
                            },
                            "receiver": {
                                "address": "tz1e77iwSWeDgyzv1M9VGjJEPcxiSCJ5oX2p"
                            },
                            "status": "applied",
                            "success": True,
                            "timestamp": {
                                "time": "2022-12-25T15:39:59Z"
                            },
                            "block": {
                                "hash": "BLnenWNtVr8h4nM4qcfJXxy8KtsGcbM3YUMmxpjUxfavxfRz3KL",
                                "height": "3000001"
                            },
                            "amount": "5.993229",
                            "fee": "0.000355"
                        }
                    ]
                }
            },
            {
                "tezos": {
                    "transactions": [
                        {
                            "hash": "ooC1aMYbiz4fzLEcbrX9V99kNhDrhNfFf7f5j9KBSnoM5TkKg8J",
                            "internal": False,
                            "sender": {
                                "address": "tz1iBJuZNNCdzFuGeQreQs81W1NWy9k85Kzi"
                            },
                            "receiver": {
                                "address": "tz1Q7RpsRvbozbY5zuhv5AaXuoqeXrcFAtgF"
                            },
                            "status": "applied",
                            "success": True,
                            "timestamp": {
                                "time": "2022-12-25T15:40:29Z"
                            },
                            "block": {
                                "hash": "BLPQKLPiApjq1ZU9HWXaLVKC8L47GmYr7KkuYgsAwZvQn6zJuCq",
                                "height": "3000002"
                            },
                            "amount": "845.005173",
                            "fee": "0.0008"
                        },
                        {
                            "hash": "ood3xDFdBprgyEGW2eG8YsesRVSgrb6sDzTrT83n5JmSobA6rLP",
                            "internal": False,
                            "sender": {
                                "address": "tz1bgDnAq1ex2bMRxNCaoAbvJpmc7XR3ZnXk"
                            },
                            "receiver": {
                                "address": "tz1QEwpaKh8BaWJbT41QRfez84GvD2uRgnh9"
                            },
                            "status": "applied",
                            "success": True,
                            "timestamp": {
                                "time": "2022-12-25T15:40:29Z"
                            },
                            "block": {
                                "hash": "BLPQKLPiApjq1ZU9HWXaLVKC8L47GmYr7KkuYgsAwZvQn6zJuCq",
                                "height": "3000002"
                            },
                            "amount": "1.241294",
                            "fee": "0.00245"
                        },
                        {
                            "hash": "op6rmFeoKEcxUPwJwQM4GUAg1TYW369rh4i8vkZievkuPJ95Y1x",
                            "internal": False,
                            "sender": {
                                "address": "tz1PpZctTPYj3GjY1B9wtWJh4hgd3XMo1t3R"
                            },
                            "receiver": {
                                "address": "tz1Y4AuSHzC2iAr4bQ2D6saoKSqZ5qKkifpR"
                            },
                            "status": "applied",
                            "success": True,
                            "timestamp": {
                                "time": "2022-12-25T15:40:29Z"
                            },
                            "block": {
                                "hash": "BLPQKLPiApjq1ZU9HWXaLVKC8L47GmYr7KkuYgsAwZvQn6zJuCq",
                                "height": "3000002"
                            },
                            "amount": "1.0",
                            "fee": "0.002854"
                        }
                    ]
                }
            },
            {
                "tezos": {
                    "transactions": [
                        {
                            "hash": "onf9wNXFmjrTy1PeuCNVGKTRio4oz5XABtXCRbfiupFx4974v3U",
                            "internal": False,
                            "sender": {
                                "address": "tz1LDb8Pq7Fd4RYAhHxqcHwDAUjNpxLmxdHT"
                            },
                            "receiver": {
                                "address": "tz1cSKxBLgdM5j3dnzmrP4PkiU7ospoKw1qX"
                            },
                            "status": "applied",
                            "success": True,
                            "timestamp": {
                                "time": "2022-12-25T15:40:59Z"
                            },
                            "block": {
                                "hash": "BLVD5huf5oVdC4ftJ5hvB6yiZvBhJcBvNgodSrUasFqMKhPDMiH",
                                "height": "3000003"
                            },
                            "amount": "55.0",
                            "fee": "0.000467"
                        },
                        {
                            "hash": "oo9bnk4kvCUVdkxysNjddKZiYUuZHDQgr7jyi7aF6EcbDAjGCZM",
                            "internal": False,
                            "sender": {
                                "address": "tz1gNjyzyT8L6WgNS4AdNMppsSFw76J4aDvT"
                            },
                            "receiver": {
                                "address": "tz2XNGTHVzY4PhKJTA1W5L9ritCrkdmLPQth"
                            },
                            "status": "applied",
                            "success": True,
                            "timestamp": {
                                "time": "2022-12-25T15:40:59Z"
                            },
                            "block": {
                                "hash": "BLVD5huf5oVdC4ftJ5hvB6yiZvBhJcBvNgodSrUasFqMKhPDMiH",
                                "height": "3000003"
                            },
                            "amount": "73.454738",
                            "fee": "0.00142"
                        },
                        {
                            "hash": "oopNS2bUgbfHgsfexVENhEmJpryzW1Fe1QfpVLEa8t5VBqSY8E3",
                            "internal": False,
                            "sender": {
                                "address": "tz1XTZM55hF7g98CzY88MXWhmK8QioGXHtuY"
                            },
                            "receiver": {
                                "address": "tz1SgudPp2kgUk9bYZvzPDu35Rpi7XNqA4Xc"
                            },
                            "status": "applied",
                            "success": True,
                            "timestamp": {
                                "time": "2022-12-25T15:40:59Z"
                            },
                            "block": {
                                "hash": "BLVD5huf5oVdC4ftJ5hvB6yiZvBhJcBvNgodSrUasFqMKhPDMiH",
                                "height": "3000003"
                            },
                            "amount": "7.873414",
                            "fee": "0.000355"
                        }
                    ]
                }
            }
        ]
        expected_txs_addresses = {
            'input_addresses': {'tz1bDXD6nNSrebqmAnnKKwnX1QdePSMCj4MX', 'tz1YpWsMwc4gSyjtxEF3JbmN6YrGiDidaSmg'},
            'output_addresses': {'tz1QWad59nCK6BSnoWsCp97HSr6qRtBVrgaJ'}
        }
        expected_txs_info = {
            'outgoing_txs': {
                'tz1bDXD6nNSrebqmAnnKKwnX1QdePSMCj4MX': {
                    Currencies.xtz: [
                        {'contract_address': None,
                         'tx_hash': 'opRxX5QREPk7P1SViVdEvCBNCj2WNXX8LQJmZfYir87R1HejFfH',
                         'value': Decimal('477.370000'),
                         'block_height': 3388485,
                         'symbol': 'XTZ'}
                    ]
                },
                'tz1YpWsMwc4gSyjtxEF3JbmN6YrGiDidaSmg': {
                    Currencies.xtz: [
                        {'contract_address': None,
                         'tx_hash': 'opUtmStZzNu344GxYrUXvQ7J1VC6KVTRrEGwPu1SQo8GK26xsqM',
                         'value': Decimal('3.680000'),
                         'block_height': 2892475,
                         'symbol': 'XTZ'
                         }
                    ]
                }
            },
            'incoming_txs': {
                'tz1QWad59nCK6BSnoWsCp97HSr6qRtBVrgaJ': {
                    Currencies.xtz: [
                        {'contract_address': None,
                         'tx_hash': 'opRxX5QREPk7P1SViVdEvCBNCj2WNXX8LQJmZfYir87R1HejFfH',
                         'value': Decimal('477.370000'),
                         'block_height': 3388485,
                         'symbol': 'XTZ'
                         },
                        {'contract_address': None,
                         'tx_hash': 'opUtmStZzNu344GxYrUXvQ7J1VC6KVTRrEGwPu1SQo8GK26xsqM',
                         'value': Decimal('3.680000'),
                         'block_height': 2892475,
                         'symbol': 'XTZ'
                         }
                    ]
                }
            }
        }
        cls.get_block_txs(block_txs_mock_response, expected_txs_addresses, expected_txs_info)
