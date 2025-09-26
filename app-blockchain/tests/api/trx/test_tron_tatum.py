import datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest

from exchange.blockchain.api.trx.tron_tatum import TatumTronApi
from exchange.blockchain.api.trx.tron_explorer_interface import TronExplorerInterface
from exchange.blockchain.tests.api.general_test.base_test_case import BaseTestCase

ADDRESSES_OF_ACCOUNT = ['TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm']
TRON_TXS_HASH = [
    'dae8dd712faee7007376ed46246853c1d8c351dd5dfb12c457cc74e0405574cd',
]
TOKEN_TXS_HASH = [
    '6999cfb83a9e7a058a4682865765c2e84317b33a75882470190ec5f688ded631',
]

@pytest.mark.slow
class TestTatumTronApiCalls(BaseTestCase):
    api = TatumTronApi

    def test_get_trx_tx_details_api(self):
        for tx_hash in TRON_TXS_HASH:
            tx_details_response = self.api.get_tx_details(tx_hash)

            schema = {
                'ret':
                    {
                        'contractRet': str
                    }
                ,
                'blockNumber': int,
                'txID': str,
                'rawData': {
                    'contract':
                        {
                            'parameter': {
                                'value': {
                                    'amount': int,
                                    'ownerAddressBase58': str,
                                    'toAddressBase58': str
                                }
                            },
                            'type': str
                        }
                }
            }

            self.assert_schema(tx_details_response, schema)

    def test_get_token_tx_details_api(self):
        for tx_hash in TOKEN_TXS_HASH:
            tx_details_response = self.api.get_tx_details(tx_hash)

            schema = {
                'blockNumber': int,
                'txID': str,
                'ret':
                    {
                        'contractRet': str
                    }
                ,
                'rawData': {
                    'contract':
                        {
                            'parameter': {
                                'value': {
                                    'data': str,
                                    'owner_address': str,
                                    'contract_address': str,
                                    'ownerAddressBase58': str,
                                    'contractAddressBase58': str
                                },
                                'type_url': str
                            },
                            'type': str
                        }

                }
            }

            self.assert_schema(tx_details_response, schema)


class TestTronscanTronExplorerInterface(BaseTestCase):
    explorer = TronExplorerInterface
    api = TatumTronApi

    def setUp(self):
        self.explorer.tx_details_apis = [self.api]
        self.explorer.token_tx_details_apis = [self.api]

    def test_trx_tx_details(self):
        tx_details_mock_response =  {
                "ret": [
                    {
                        "contractRet": "SUCCESS"
                    }
                ],
                "signature": [
                    "1d8ef6213db4c2405f143af551654f10230b4b5f4f1e8c15d9c8f4a02836550fc78ac79f8f41bf20af7ed3ae78416475e81624ca330e0f8ed25fc673b6e16d3801"
                ],
                "blockNumber": 65693098,
                "txID": "dae8dd712faee7007376ed46246853c1d8c351dd5dfb12c457cc74e0405574cd",
                "netFee": 100000,
                "fee": 1100000,
                "rawData": {
                    "contract": [
                        {
                            "parameter": {
                                "value": {
                                    "amount": 30000000,
                                    "owner_address": "41986759cc653c16cfd3e6d7f3f9421c947aa4ca71",
                                    "to_address": "412bc68f9e3ddf9119d281f1fd50a3578b7a5c37c8",
                                    "ownerAddressBase58": "TPs3X9wZMU63oMmNGrSuXQN9E2aF4qtRch",
                                    "toAddressBase58": "TDxfvZvTJi12XqkXvxY1S3Bfo2hgSiRc68"
                                },
                                "type_url": "type.googleapis.com/protocol.TransferContract"
                            },
                            "type": "TransferContract"
                        }
                    ],
                    "ref_block_bytes": "6597",
                    "ref_block_hash": "487f3f82f79ba4f1",
                    "expiration": 1727727789000,
                    "timestamp": 1727727731689
                }
            }


        block_head_mock_response =  {
                "testnet": False,
                "hash": "0000000003eccdb0ac7647d76e4b9353bf8e088d724314fdcde693e26775af03",
                "blockNumber": 65850800
            }


        self.api.request = Mock(side_effect=[block_head_mock_response,tx_details_mock_response])

        tx_details_response = self.explorer().get_tx_details(TRON_TXS_HASH[0])

        expected_result = {'hash': 'dae8dd712faee7007376ed46246853c1d8c351dd5dfb12c457cc74e0405574cd', 'success': True,
                           'block': 65693098,
                           'date': datetime.datetime(2024, 9, 30, 20, 22, 11, 689000, tzinfo=datetime.timezone.utc),
                           'fees': None, 'memo': None, 'confirmations': 157702, 'raw': None, 'inputs': [],
                           'outputs': [], 'transfers': [
                {'type': 'MainCoin', 'symbol': 'TRX', 'currency': 20, 'from': 'TPs3X9wZMU63oMmNGrSuXQN9E2aF4qtRch',
                 'to': 'TDxfvZvTJi12XqkXvxY1S3Bfo2hgSiRc68', 'value': Decimal('30.000000'), 'is_valid': True,
                 'token': None, 'memo': None}]}
        self.assertDictEqual(tx_details_response, expected_result)

    def test_token_tx_details(self):
        tx_details_mock_response = {
                "ret": [
                    {
                        "contractRet": "SUCCESS"
                    }
                ],
                "signature": [
                    "eaef86f971ae747853ef33700453433d456de0cdad4c5a3ecc2749435f7f7da0fc764ecdfa6c926554705843a1487b8ef116ec49922e9c660e1a9a95d87a0aea00"
                ],
                "blockNumber": 65826286,
                "txID": "6999cfb83a9e7a058a4682865765c2e84317b33a75882470190ec5f688ded631",
                "netFee": 345000,
                "fee": 345000,
                "energyUsage": 130285,
                "energyUsageTotal": 130285,
                "rawData": {
                    "contract": [
                        {
                            "parameter": {
                                "value": {
                                    "data": "a9059cbb000000000000000000000000d10a220973b355d5c4994053e088e92017db93a7000000000000000000000000000000000000000000000000000000000ca0ba20",
                                    "owner_address": "4188ff7b4acab8f5a39abf784152e0163875ba0c8a",
                                    "contract_address": "41a614f803b6fd780986a42c78ec9c7f77e6ded13c",
                                    "ownerAddressBase58": "TNTaxKbS6KAfbWnZobDhBThTxnvq34yxZo",
                                    "contractAddressBase58": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
                                },
                                "type_url": "type.googleapis.com/protocol.TriggerSmartContract"
                            },
                            "type": "TriggerSmartContract"
                        }
                    ],
                    "ref_block_bytes": "6ded",
                    "ref_block_hash": "7fc1b07eab3ba5c0",
                    "expiration": 1728127473000,
                    "fee_limit": 100000000,
                    "timestamp": 1728127415001
                },
                "log": [
                    {
                        "address": "a614f803b6fd780986a42c78ec9c7f77e6ded13c",
                        "topics": [
                            "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                            "00000000000000000000000088ff7b4acab8f5a39abf784152e0163875ba0c8a",
                            "000000000000000000000000d10a220973b355d5c4994053e088e92017db93a7"
                        ],
                        "data": "000000000000000000000000000000000000000000000000000000000ca0ba20"
                    }
                ]
            }


        block_head_mock_response = {
                "testnet": False,
                "hash": "0000000003eccdb0ac7647d76e4b9353bf8e088d724314fdcde693e26775af03",
                "blockNumber": 65850800
            }


        self.api.request = Mock(side_effect=[block_head_mock_response, tx_details_mock_response])

        tx_details_response = self.explorer().get_token_tx_details(TOKEN_TXS_HASH[0])

        tx_details_response['date'] = tx_details_response.get('date').astimezone(datetime.timezone.utc)
        expected_result = {'hash': '6999cfb83a9e7a058a4682865765c2e84317b33a75882470190ec5f688ded631', 'success': True,
                           'block': 65826286,
                           'date': datetime.datetime(2024, 10, 5, 11, 23, 35, 1000, tzinfo=datetime.timezone.utc),
                           'fees': None, 'memo': None, 'confirmations': 24514, 'raw': None, 'inputs': [], 'outputs': [],
                           'transfers': [{'type': 'Token', 'symbol': 'USDT', 'currency': 13,
                                          'from': 'TNTaxKbS6KAfbWnZobDhBThTxnvq34yxZo',
                                          'to': 'TV2WNCetEM7AKm8u4VoM4hkXpPxWmTMtjQ', 'value': Decimal('211.860000'),
                                          'is_valid': True, 'token': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', 'memo': None}]}
        self.assertDictEqual(tx_details_response, expected_result)
