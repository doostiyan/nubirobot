import datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest

from exchange.base.models import Currencies
from exchange.blockchain.api.trx.new_tronscan import TronscanTronApi
from exchange.blockchain.api.trx.tron_explorer_interface import TronExplorerInterface
from exchange.blockchain.tests.api.avax.test_avax_oklink import TXS_HASH
from exchange.blockchain.tests.api.general_test.base_test_case import BaseTestCase

ADDRESSES_OF_ACCOUNT = ['TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm', 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag']
TRON_TXS_HASH = [
    '5d5578c477e80bb78ae4229d036eac26a988c659aae2b9e01ce93cd7894028b9',
]

CONTRACT_INFO_USDT = {
    'address': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t',
    'decimals': 6,
    'symbol': 'usdt'
}


@pytest.mark.slow
class TestTronscanTronApiCalls(BaseTestCase):
    api = TronscanTronApi.get_instance()

    @classmethod
    def _check_general_response(cls, response):
        if response is None:
            return False
        if response.get("error"):
            return False
        if response.get("message"):
            return False
        return True

    def test_get_balance_api(self):
        for address in ADDRESSES_OF_ACCOUNT:
            balance_response = self.api.get_balance(address)
            self.assertTrue(self._check_general_response(balance_response))
            self.assertIsNotNone(balance_response.get('balance'))
            self.assertIsInstance(balance_response.get('balance'), int)

    def test_get_tx_details_api(self):
        for tx_hash in TRON_TXS_HASH:
            tx_details_response = self.api.get_tx_details(tx_hash)
            self.assertTrue(self._check_general_response(tx_details_response))
            schema = {
                'block': int,
                'hash': str,
                'timestamp': int,
                'confirmations': int,
                'contractData': {
                    'amount': int,
                    'owner_address': str,
                    'to_address': str,
                },
                'contractRet': str,
                'revert': bool,
                'confirmed': bool,
            }
            self.assert_schema(tx_details_response, schema)

    def test_get_address_txs_api(self):
        for address in ADDRESSES_OF_ACCOUNT:
            tx_details_response = self.api.get_address_txs(address)
            self.assertTrue(self._check_general_response(tx_details_response))
            for tx in tx_details_response.get('data'):
                schema = {
                    'contractRet': str,
                    'revert': bool,
                    'tokenName': str,
                    'amount': int,
                    'confirmed': bool,
                    'transferFromAddress': str,
                    'transferToAddress': str,
                    'block': int,
                    'transactionHash': str,
                    'timestamp': int,
                }
                self.assert_schema(tx, schema)

    def test_get_token_txs_api(self):
        for address in ADDRESSES_OF_ACCOUNT:
            token_txs_response = self.api.get_token_txs(address, CONTRACT_INFO_USDT)

            self.assertTrue(self._check_general_response(token_txs_response))

            for tx in token_txs_response.get('token_transfers'):
                schema = {
                    'transaction_id': str,
                    'trigger_info': {
                        'parameter': {
                            '_value': str,
                            '_to': str
                        },
                        'contract_address': str
                    },
                    'from_address': str,
                    'to_address': str,
                    'block_ts': int,
                    'confirmed': bool,
                }

                self.assert_schema(tx, schema)


class TestTronscanTronExplorerInterface(BaseTestCase):
    explorer = TronExplorerInterface
    api = TronscanTronApi.get_instance()

    def setUp(self):
        self.explorer.balance_apis = [self.api]
        self.explorer.tx_details_apis = [self.api]
        self.explorer.address_txs_apis = [self.api]
        self.explorer.token_txs_apis = [self.api]

    def test_get_balance(self):
        balance_mock_response = [{
            "balances": [
                {
                    "amount": "31.369183",
                    "tokenPriceInTrx": 1,
                    "tokenId": "_",
                    "balance": "31369183",
                    "tokenName": "trx",
                    "tokenDecimal": 6,
                    "tokenAbbr": "trx",
                    "tokenCanShow": 1,
                    "tokenType": "trc10",
                    "vip": False,
                    "tokenLogo": "https://static.tronscan.org/production/logo/trx.png"
                }
            ],
            "trc721token_balances": [],
            "balance": 31369183,
            "voteTotal": 0,
            "totalFrozen": 0,
        }]

        self.api.get_balance = Mock(side_effect=balance_mock_response)

        balance_response = self.explorer().get_balance(ADDRESSES_OF_ACCOUNT[0])

        expected_result = {
            Currencies.trx: {
                'address': 'TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm',
                'symbol': 'TRX',
                'balance': Decimal('31.369183'),
                'unconfirmed_balance': None
            }
        }

        self.assertDictEqual(balance_response, expected_result)

    def test_tx_details(self):
        tx_details_mock_response = [
            {
                "contract_map": {
                    "TXqLHV6oyZXEmCHyHHGTYAcJaTGVegcaUf": False,
                    "TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm": False
                },
                "contractRet": "SUCCESS",
                "data": "",
                "contractInfo": {},
                "contractType": 1,
                "toAddress": "TXqLHV6oyZXEmCHyHHGTYAcJaTGVegcaUf",
                "confirmed": True,
                "cheat_status": 0,
                "block": 64470479,
                "riskTransaction": False,
                "timestamp": 1724058540000,
                "info": {},
                "normalAddressInfo": {
                    "TXqLHV6oyZXEmCHyHHGTYAcJaTGVegcaUf": {
                        "risk": False
                    },
                    "TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm": {
                        "risk": False
                    }
                },
                "cost": {
                    "net_fee_cost": 1000,
                    "date_created": 1724058540,
                    "fee": 0,
                    "energy_fee_cost": 420,
                    "net_usage": 275,
                    "multi_sign_fee": 0,
                    "net_fee": 0,
                    "energy_penalty_total": 0,
                    "energy_usage": 0,
                    "energy_fee": 0,
                    "energy_usage_total": 0,
                    "memoFee": 0,
                    "origin_energy_usage": 0,
                    "account_create_fee": 0
                },
                "noteLevel": 1,
                "addressTag": {
                    "TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm": "Binance 2"
                },
                "revert": False,
                "confirmations": 147006,
                "fee_limit": 15000000,
                "trigger_info": {},
                "signature_addresses": [],
                "ownerAddress": "TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm",
                "srConfirmList": [
                    {
                        "address": "TCZvvbn4SCVyNhCAt1L8Kp1qk5rtMiKdBB",
                        "name": "Crypto Labs",
                        "block": 64470479,
                        "url": "CryptoLabs"
                    },
                    {
                        "address": "TGJBjL8wmRVyRStkghnhcVNYYgn6Yjno6X",
                        "name": "BlockAnalysis",
                        "block": 64470480,
                        "url": "blockanalysis"
                    },
                    {
                        "address": "TJvaAeFb8Lykt9RQcVyyTFN2iDvGMuyD4M",
                        "name": "Poloniex",
                        "block": 64470481,
                        "url": "https://poloniex.com/"
                    },
                    {
                        "address": "TGyrSc9ZmTdbYziuk1SKEmdtCdETafewJ9",
                        "name": "Luganodes",
                        "block": 64470482,
                        "url": "https://luganodes.com"
                    },
                    {
                        "address": "TAQpCTFeJvwdWf6MQZtXXkzWrTS9aymshb",
                        "name": "Abra Capital Management",
                        "block": 64470483,
                        "url": "https://valkyrieinvest.com"
                    },
                    {
                        "address": "TNaJADoq1u2atryP1ZzwvmEE4ZBELXfMqw",
                        "name": "callmeSR",
                        "block": 64470484,
                        "url": "http://zempty.peiwo.cn/"
                    },
                    {
                        "address": "TDpt9adA6QidL1B1sy3D8NC717C6L5JxFo",
                        "name": "Chain Cloud",
                        "block": 64470485,
                        "url": "chaincloud"
                    },
                    {
                        "address": "TC6qGw3d6h25gjcM64KLuZn1cznNi5NR6t",
                        "name": "Crypto Innovation Fund",
                        "block": 64470486,
                        "url": "cryptoinnovationfund"
                    },
                    {
                        "address": "TAAdjpNYfeJ2edcETNpad1QpQWJfyBdB9V",
                        "name": "Ant Investment Group",
                        "block": 64470487,
                        "url": "antinvestmentgroup"
                    },
                    {
                        "address": "TKSXDA8HfE9E1y39RczVQ1ZascUEtaSToF",
                        "name": "CryptoChain",
                        "block": 64470488,
                        "url": "http://cryptochain.network"
                    },
                    {
                        "address": "TUD4YXYdj2t1gP5th3A7t97mx1AUmrrQRt",
                        "name": "TRONGrid",
                        "block": 64470489,
                        "url": "https://www.trongrid.io"
                    },
                    {
                        "address": "TTMNxTmRpBZnjtUnohX84j25NLkTqDga7j",
                        "name": "TronSpark",
                        "block": 64470490,
                        "url": "https://tronspark.com"
                    },
                    {
                        "address": "TNeEwWHXLLUgEtfzTnYN8wtVenGxuMzZCE",
                        "name": "OKCoinJapan",
                        "block": 64470491,
                        "url": "https://okcoin.jp/"
                    },
                    {
                        "address": "TTxrh32VJveqiYRwbLEX2wLTMFCfbpAUQj",
                        "name": "OKX Earn",
                        "block": 64470492,
                        "url": "https://www.okx.com/earn/home"
                    },
                    {
                        "address": "TQhuVjZtmp6k4fPmGZLr4wyXdziCVSPkEX",
                        "name": "Google Cloud",
                        "block": 64470493,
                        "url": "https://cloud.google.com/"
                    },
                    {
                        "address": "TCEo1hMAdaJrQmvnGTCcGT2LqrGU4N7Jqf",
                        "name": "TRONScan",
                        "block": 64470494,
                        "url": "https://tronscan.org"
                    },
                    {
                        "address": "TTcYhypP8m4phDhN6oRexz2174zAerjEWP",
                        "name": "CryptoGuyInZA",
                        "block": 64470495,
                        "url": "https://www.cryptoguyinza.co.za/"
                    },
                    {
                        "address": "TBsyKdNsCKNXLgvneeUJ3rbXgWSgk6paTM",
                        "name": "StakedTron",
                        "block": 64470496,
                        "url": "https://staked.us"
                    },
                    {
                        "address": "TLyqzVGLV1srkB7dToTAEqgDSfPtXRJZYH",
                        "name": "Binance Staking",
                        "block": 64470497,
                        "url": "https://www.binance.com/en/staking"
                    }
                ],
                "hash": "5d5578c477e80bb78ae4229d036eac26a988c659aae2b9e01ce93cd7894028b9",
                "contractData": {
                    "amount": 2896399700,
                    "owner_address": "TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm",
                    "to_address": "TXqLHV6oyZXEmCHyHHGTYAcJaTGVegcaUf"
                },
                "internal_transactions": {}
            }
        ]

        self.api.get_tx_details = Mock(side_effect=tx_details_mock_response)

        tx_details_response = self.explorer().get_tx_details(TXS_HASH[0])

        tx_details_response['date'] = tx_details_response.get('date').astimezone(datetime.timezone.utc)
        expected_result = {'hash': '5d5578c477e80bb78ae4229d036eac26a988c659aae2b9e01ce93cd7894028b9', 'success': True,
                           'block': 64470479,
                           'date': datetime.datetime(2024, 8, 19, 9, 9, tzinfo=datetime.timezone.utc), 'fees': None,
                           'memo': None, 'confirmations': 147006, 'raw': None, 'inputs': [], 'outputs': [],
                           'transfers': [{'type': 'MainCoin', 'symbol': 'TRX', 'currency': 20,
                                          'from': 'TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm',
                                          'to': 'TXqLHV6oyZXEmCHyHHGTYAcJaTGVegcaUf', 'value': Decimal('2896.399700'),
                                          'is_valid': True, 'token': None, 'memo': None}]}
        self.assertDictEqual(tx_details_response, expected_result)

    def test_get_address_txs(self):
        address_txs_mock_response = [
            {
                "total": 10000,
                "data": [
                    {
                        "id": "",
                        "block": 64620002,
                        "transactionHash": "fad9f4eae1936d4fc9dc208c538076379fdfedeb340d3239938aafe0e12b68c3",
                        "timestamp": 1724507295000,
                        "transferFromAddress": "TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm",
                        "transferFromTag": "Binance 2",
                        "transferToAddress": "TTysHyyGpENU39HWz647qVdj3mDzLbjaaW",
                        "amount": 6278014700,
                        "tokenName": "_",
                        "confirmed": False,
                        "data": "",
                        "contractRet": "SUCCESS",
                        "revert": False,
                        "cheatStatus": False,
                        "tokenInfo": {
                            "tokenId": "_",
                            "tokenAbbr": "trx",
                            "tokenName": "trx",
                            "tokenDecimal": 6,
                            "tokenCanShow": 1,
                            "tokenType": "trc10",
                            "tokenLogo": "https://static.tronscan.org/production/logo/trx.png",
                            "tokenLevel": "2",
                            "vip": True
                        },
                        "riskTransaction": False
                    },
                    {
                        "id": "",
                        "block": 64619998,
                        "transactionHash": "1134e8c5cac1cb823c0eaa0e00050ffd6de2dbde3bb65a51ca2121e530221c51",
                        "timestamp": 1724507283000,
                        "transferFromAddress": "TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm",
                        "transferFromTag": "Binance 2",
                        "transferToAddress": "TVpo91xSEChP5ipV49diQu7kUTAYbbGu8y",
                        "amount": 149000000,
                        "tokenName": "_",
                        "confirmed": False,
                        "data": "",
                        "contractRet": "SUCCESS",
                        "revert": False,
                        "cheatStatus": False,
                        "tokenInfo": {
                            "tokenId": "_",
                            "tokenAbbr": "trx",
                            "tokenName": "trx",
                            "tokenDecimal": 6,
                            "tokenCanShow": 1,
                            "tokenType": "trc10",
                            "tokenLogo": "https://static.tronscan.org/production/logo/trx.png",
                            "tokenLevel": "2",
                            "vip": True
                        },
                        "riskTransaction": False
                    },
                    {
                        "id": "",
                        "block": 64619994,
                        "transactionHash": "77b3f4b311869fd448ceb5fc2bb25488ec923645407ff3dfc5c8150a41f4c6f4",
                        "timestamp": 1724507271000,
                        "transferFromAddress": "TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm",
                        "transferFromTag": "Binance 2",
                        "transferToAddress": "TSiiVxudX5Yu896Jg3LB72n6ooBTMn13vr",
                        "amount": 1844845650,
                        "tokenName": "_",
                        "confirmed": False,
                        "data": "",
                        "contractRet": "SUCCESS",
                        "revert": False,
                        "cheatStatus": False,
                        "tokenInfo": {
                            "tokenId": "_",
                            "tokenAbbr": "trx",
                            "tokenName": "trx",
                            "tokenDecimal": 6,
                            "tokenCanShow": 1,
                            "tokenType": "trc10",
                            "tokenLogo": "https://static.tronscan.org/production/logo/trx.png",
                            "tokenLevel": "2",
                            "vip": True
                        },
                        "riskTransaction": False
                    },
                    {
                        "id": "",
                        "block": 64619987,
                        "transactionHash": "79b4b200e355b81c24bba0410b7bf0e6929a2ac24baafc4dca99554e075a1af8",
                        "timestamp": 1724507250000,
                        "transferFromAddress": "TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm",
                        "transferFromTag": "Binance 2",
                        "transferToAddress": "TC6fcZcAxbYambmZLwcf94C16mKiZ2yQyx",
                        "amount": 197000000,
                        "tokenName": "_",
                        "confirmed": True,
                        "data": "",
                        "contractRet": "SUCCESS",
                        "revert": False,
                        "cheatStatus": False,
                        "tokenInfo": {
                            "tokenId": "_",
                            "tokenAbbr": "trx",
                            "tokenName": "trx",
                            "tokenDecimal": 6,
                            "tokenCanShow": 1,
                            "tokenType": "trc10",
                            "tokenLogo": "https://static.tronscan.org/production/logo/trx.png",
                            "tokenLevel": "2",
                            "vip": True
                        },
                        "riskTransaction": False
                    },
                    {
                        "id": "",
                        "block": 64619987,
                        "transactionHash": "ee60de64784105809c5a7bae1439e0327f9f09da93e83b3c9486ce41ce43f33a",
                        "timestamp": 1724507250000,
                        "transferFromAddress": "TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm",
                        "transferFromTag": "Binance 2",
                        "transferToAddress": "TZ576G5WqsYRdNspbnu7oqj5xvDeTSiwHf",
                        "amount": 929384630,
                        "tokenName": "_",
                        "confirmed": True,
                        "data": "",
                        "contractRet": "SUCCESS",
                        "revert": False,
                        "cheatStatus": False,
                        "tokenInfo": {
                            "tokenId": "_",
                            "tokenAbbr": "trx",
                            "tokenName": "trx",
                            "tokenDecimal": 6,
                            "tokenCanShow": 1,
                            "tokenType": "trc10",
                            "tokenLogo": "https://static.tronscan.org/production/logo/trx.png",
                            "tokenLevel": "2",
                            "vip": True
                        },
                        "riskTransaction": False
                    }
                ],
                "contractMap": {
                    "TZ576G5WqsYRdNspbnu7oqj5xvDeTSiwHf": False,
                    "TTysHyyGpENU39HWz647qVdj3mDzLbjaaW": False,
                    "TC6fcZcAxbYambmZLwcf94C16mKiZ2yQyx": False,
                    "TVpo91xSEChP5ipV49diQu7kUTAYbbGu8y": False,
                    "TSiiVxudX5Yu896Jg3LB72n6ooBTMn13vr": False,
                    "TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm": False
                },
                "contractInfo": {},
                "rangeTotal": 6447582,
                "normalAddressInfo": {
                    "TZ576G5WqsYRdNspbnu7oqj5xvDeTSiwHf": {
                        "risk": False
                    },
                    "TTysHyyGpENU39HWz647qVdj3mDzLbjaaW": {
                        "risk": False
                    },
                    "TC6fcZcAxbYambmZLwcf94C16mKiZ2yQyx": {
                        "risk": False
                    },
                    "TVpo91xSEChP5ipV49diQu7kUTAYbbGu8y": {
                        "risk": False
                    },
                    "TSiiVxudX5Yu896Jg3LB72n6ooBTMn13vr": {
                        "risk": False
                    },
                    "TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm": {
                        "risk": False
                    }
                }
            }
        ]

        self.api.get_address_txs = Mock(side_effect=address_txs_mock_response)

        address_txs_response = self.explorer().get_txs(ADDRESSES_OF_ACCOUNT[0])

        expected_result = [{20: {'amount': Decimal('6278.014700'), 'from_address': 'TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm',
                                 'to_address': 'TTysHyyGpENU39HWz647qVdj3mDzLbjaaW',
                                 'hash': 'fad9f4eae1936d4fc9dc208c538076379fdfedeb340d3239938aafe0e12b68c3',
                                 'block': 64620002,
                                 'date': datetime.datetime(2024, 8, 24, 13, 48, 15, tzinfo=datetime.timezone.utc),
                                 'memo': None, 'confirmations': 0, 'address': 'TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm',
                                 'direction': 'outgoing', 'raw': None}}, {20: {'amount': Decimal('149.000000'),
                                                                               'from_address': 'TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm',
                                                                               'to_address': 'TVpo91xSEChP5ipV49diQu7kUTAYbbGu8y',
                                                                               'hash': '1134e8c5cac1cb823c0eaa0e00050ffd6de2dbde3bb65a51ca2121e530221c51',
                                                                               'block': 64619998,
                                                                               'date': datetime.datetime(2024, 8, 24,
                                                                                                         13, 48, 3,
                                                                                                         tzinfo=datetime.timezone.utc),
                                                                               'memo': None, 'confirmations': 0,
                                                                               'address': 'TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm',
                                                                               'direction': 'outgoing', 'raw': None}}, {
                               20: {'amount': Decimal('1844.845650'),
                                    'from_address': 'TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm',
                                    'to_address': 'TSiiVxudX5Yu896Jg3LB72n6ooBTMn13vr',
                                    'hash': '77b3f4b311869fd448ceb5fc2bb25488ec923645407ff3dfc5c8150a41f4c6f4',
                                    'block': 64619994,
                                    'date': datetime.datetime(2024, 8, 24, 13, 47, 51, tzinfo=datetime.timezone.utc),
                                    'memo': None, 'confirmations': 0, 'address': 'TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm',
                                    'direction': 'outgoing', 'raw': None}}, {20: {'amount': Decimal('197.000000'),
                                                                                  'from_address': 'TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm',
                                                                                  'to_address': 'TC6fcZcAxbYambmZLwcf94C16mKiZ2yQyx',
                                                                                  'hash': '79b4b200e355b81c24bba0410b7bf0e6929a2ac24baafc4dca99554e075a1af8',
                                                                                  'block': 64619987,
                                                                                  'date': datetime.datetime(2024, 8, 24,
                                                                                                            13, 47, 30,
                                                                                                            tzinfo=datetime.timezone.utc),
                                                                                  'memo': None, 'confirmations': 20,
                                                                                  'address': 'TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm',
                                                                                  'direction': 'outgoing',
                                                                                  'raw': None}}, {
                               20: {'amount': Decimal('929.384630'),
                                    'from_address': 'TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm',
                                    'to_address': 'TZ576G5WqsYRdNspbnu7oqj5xvDeTSiwHf',
                                    'hash': 'ee60de64784105809c5a7bae1439e0327f9f09da93e83b3c9486ce41ce43f33a',
                                    'block': 64619987,
                                    'date': datetime.datetime(2024, 8, 24, 13, 47, 30, tzinfo=datetime.timezone.utc),
                                    'memo': None, 'confirmations': 20, 'address': 'TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm',
                                    'direction': 'outgoing', 'raw': None}}]

        self.assertEqual(address_txs_response, expected_result)

    def test_get_token_txs(self):
        address_txs_mock_response = [
            {
                "total": 35,
                "contractInfo": {},
                "rangeTotal": 35,
                "token_transfers": [
                    {
                        "transaction_id": "8934bbfb5e152cc71ab0e635119ef402d2783c1632f91e75700ad9a52186ce18",
                        "status": 0,
                        "block_ts": 1728723540000,
                        "from_address": "TJqwA7SoZnERE4zW5uDEiPkbz4B66h9TFj",
                        "from_address_tag": {
                            "from_address_tag": "Binance-Hot 11",
                            "from_address_tag_logo": ""
                        },
                        "to_address": "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag",
                        "to_address_tag": {
                            "to_address_tag_logo": "",
                            "to_address_tag": ""
                        },
                        "block": 66024909,
                        "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                        "trigger_info": {
                            "method": "transfer(address _to,uint256 _value)",
                            "data": "a9059cbb000000000000000000000041784ec5627ac5c3f8de4117175db192c1b9e809c1000000000000000000000000000000000000000000000000000000000edb04a8",
                            "parameter": {
                                "_value": "249234600",
                                "_to": "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag"
                            },
                            "methodName": "transfer",
                            "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "call_value": 0
                        },
                        "quant": "249234600",
                        "approval_amount": "0",
                        "event_type": "Transfer",
                        "confirmed": True,
                        "contractRet": "SUCCESS",
                        "finalResult": "SUCCESS",
                        "tokenInfo": {
                            "tokenId": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "tokenAbbr": "USDT",
                            "tokenName": "Tether USD",
                            "tokenDecimal": 6,
                            "tokenCanShow": 1,
                            "tokenType": "trc20",
                            "tokenLogo": "https://static.tronscan.org/production/logo/usdtlogo.png",
                            "tokenLevel": "2",
                            "issuerAddr": "THPvaUhoh2Qn2y9THCZML3H815hhFhn5YC",
                            "vip": True
                        },
                        "revert": False,
                        "contract_type": "trc20",
                        "fromAddressIsContract": False,
                        "toAddressIsContract": False,
                        "riskTransaction": False
                    },
                    {
                        "transaction_id": "d44fca70f2f9352cfaa2a4183187dcd10e03505f5efcaca2d6350ae655aa8cee",
                        "status": 0,
                        "block_ts": 1728721929000,
                        "from_address": "TYASr5UV6HEcXatwdFQfmLVUqQQQMUxHLS",
                        "from_address_tag": {
                            "from_address_tag": "Binance-Hot 3",
                            "from_address_tag_logo": "https://coin.top/production/upload/logo/Binance.png"
                        },
                        "to_address": "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag",
                        "to_address_tag": {
                            "to_address_tag_logo": "",
                            "to_address_tag": ""
                        },
                        "block": 66024372,
                        "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                        "trigger_info": {
                            "method": "transfer(address _to,uint256 _value)",
                            "data": "a9059cbb000000000000000000000041784ec5627ac5c3f8de4117175db192c1b9e809c10000000000000000000000000000000000000000000000000000000008e18f40",
                            "parameter": {
                                "_value": "149000000",
                                "_to": "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag"
                            },
                            "methodName": "transfer",
                            "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "call_value": 0
                        },
                        "quant": "149000000",
                        "approval_amount": "0",
                        "event_type": "Transfer",
                        "confirmed": True,
                        "contractRet": "SUCCESS",
                        "finalResult": "SUCCESS",
                        "tokenInfo": {
                            "tokenId": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "tokenAbbr": "USDT",
                            "tokenName": "Tether USD",
                            "tokenDecimal": 6,
                            "tokenCanShow": 1,
                            "tokenType": "trc20",
                            "tokenLogo": "https://static.tronscan.org/production/logo/usdtlogo.png",
                            "tokenLevel": "2",
                            "issuerAddr": "THPvaUhoh2Qn2y9THCZML3H815hhFhn5YC",
                            "vip": True
                        },
                        "revert": False,
                        "contract_type": "trc20",
                        "fromAddressIsContract": False,
                        "toAddressIsContract": False,
                        "riskTransaction": False
                    },
                    {
                        "transaction_id": "951da41e0dbb92998b06fd8b07746c17b6de8b76028e270ffe79ac88b2092ad0",
                        "status": 0,
                        "block_ts": 1728721419000,
                        "from_address": "TDqSquXBgUCLYvYC4XZgrprLK589dkhSCf",
                        "from_address_tag": {
                            "from_address_tag": "Binance-Hot 7",
                            "from_address_tag_logo": ""
                        },
                        "to_address": "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag",
                        "to_address_tag": {
                            "to_address_tag_logo": "",
                            "to_address_tag": ""
                        },
                        "block": 66024202,
                        "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                        "trigger_info": {
                            "method": "transfer(address _to,uint256 _value)",
                            "data": "a9059cbb000000000000000000000041784ec5627ac5c3f8de4117175db192c1b9e809c10000000000000000000000000000000000000000000000000000000008e18f40",
                            "parameter": {
                                "_value": "149000000",
                                "_to": "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag"
                            },
                            "methodName": "transfer",
                            "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "call_value": 0
                        },
                        "quant": "149000000",
                        "approval_amount": "0",
                        "event_type": "Transfer",
                        "confirmed": True,
                        "contractRet": "SUCCESS",
                        "finalResult": "SUCCESS",
                        "tokenInfo": {
                            "tokenId": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "tokenAbbr": "USDT",
                            "tokenName": "Tether USD",
                            "tokenDecimal": 6,
                            "tokenCanShow": 1,
                            "tokenType": "trc20",
                            "tokenLogo": "https://static.tronscan.org/production/logo/usdtlogo.png",
                            "tokenLevel": "2",
                            "issuerAddr": "THPvaUhoh2Qn2y9THCZML3H815hhFhn5YC",
                            "vip": True
                        },
                        "revert": False,
                        "contract_type": "trc20",
                        "fromAddressIsContract": False,
                        "toAddressIsContract": False,
                        "riskTransaction": False
                    },
                    {
                        "transaction_id": "1029be850caa9ab3df17fe46c6015e2df97ba136aec3a8f2b398c039ad448b77",
                        "status": 0,
                        "block_ts": 1728702576000,
                        "from_address": "TJ5usJLLwjwn7Pw3TPbdzreG7dvgKzfQ5y",
                        "from_address_tag": {
                            "from_address_tag": "Binance-Hot 9",
                            "from_address_tag_logo": ""
                        },
                        "to_address": "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag",
                        "to_address_tag": {
                            "to_address_tag_logo": "",
                            "to_address_tag": ""
                        },
                        "block": 66017923,
                        "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                        "trigger_info": {
                            "method": "transfer(address _to,uint256 _value)",
                            "data": "a9059cbb000000000000000000000041784ec5627ac5c3f8de4117175db192c1b9e809c10000000000000000000000000000000000000000000000000000000017c841c0",
                            "parameter": {
                                "_value": "399000000",
                                "_to": "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag"
                            },
                            "methodName": "transfer",
                            "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "call_value": 0
                        },
                        "quant": "399000000",
                        "approval_amount": "0",
                        "event_type": "Transfer",
                        "confirmed": True,
                        "contractRet": "SUCCESS",
                        "finalResult": "SUCCESS",
                        "tokenInfo": {
                            "tokenId": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "tokenAbbr": "USDT",
                            "tokenName": "Tether USD",
                            "tokenDecimal": 6,
                            "tokenCanShow": 1,
                            "tokenType": "trc20",
                            "tokenLogo": "https://static.tronscan.org/production/logo/usdtlogo.png",
                            "tokenLevel": "2",
                            "issuerAddr": "THPvaUhoh2Qn2y9THCZML3H815hhFhn5YC",
                            "vip": True
                        },
                        "revert": False,
                        "contract_type": "trc20",
                        "fromAddressIsContract": False,
                        "toAddressIsContract": False,
                        "riskTransaction": False
                    },
                    {
                        "transaction_id": "8dfeb62597ef11a7efe8a3b9ea2817dd5a8ccca552d0734df16352d0739393df",
                        "status": 0,
                        "block_ts": 1728642456000,
                        "from_address": "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag",
                        "from_address_tag": {
                            "from_address_tag": "",
                            "from_address_tag_logo": ""
                        },
                        "to_address": "TWtcTcqSeoyRKCV89j8ZWXeqHAwNwq9pt6",
                        "to_address_tag": {
                            "to_address_tag_logo": "",
                            "to_address_tag": ""
                        },
                        "block": 65997889,
                        "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                        "trigger_info": {
                            "method": "transfer(address _to,uint256 _value)",
                            "data": "a9059cbb000000000000000000000000e57c24b1f2b9853420a6d3a3da0c19c4fb8da0630000000000000000000000000000000000000000000000000000000030604188",
                            "parameter": {
                                "_value": "811614600",
                                "_to": "TWtcTcqSeoyRKCV89j8ZWXeqHAwNwq9pt6"
                            },
                            "methodName": "transfer",
                            "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "call_value": 0
                        },
                        "quant": "811614600",
                        "approval_amount": "0",
                        "event_type": "Transfer",
                        "confirmed": True,
                        "contractRet": "SUCCESS",
                        "finalResult": "SUCCESS",
                        "tokenInfo": {
                            "tokenId": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "tokenAbbr": "USDT",
                            "tokenName": "Tether USD",
                            "tokenDecimal": 6,
                            "tokenCanShow": 1,
                            "tokenType": "trc20",
                            "tokenLogo": "https://static.tronscan.org/production/logo/usdtlogo.png",
                            "tokenLevel": "2",
                            "issuerAddr": "THPvaUhoh2Qn2y9THCZML3H815hhFhn5YC",
                            "vip": True
                        },
                        "revert": False,
                        "contract_type": "trc20",
                        "fromAddressIsContract": False,
                        "toAddressIsContract": False,
                        "riskTransaction": False
                    },
                    {
                        "transaction_id": "88ed569f0f50bbef0b4430793f1978e6110be79b25000a86601cd2084efeb2ed",
                        "status": 0,
                        "block_ts": 1728638244000,
                        "from_address": "TYASr5UV6HEcXatwdFQfmLVUqQQQMUxHLS",
                        "from_address_tag": {
                            "from_address_tag": "Binance-Hot 3",
                            "from_address_tag_logo": "https://coin.top/production/upload/logo/Binance.png"
                        },
                        "to_address": "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag",
                        "to_address_tag": {
                            "to_address_tag_logo": "",
                            "to_address_tag": ""
                        },
                        "block": 65996485,
                        "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                        "trigger_info": {
                            "method": "transfer(address _to,uint256 _value)",
                            "data": "a9059cbb000000000000000000000041784ec5627ac5c3f8de4117175db192c1b9e809c10000000000000000000000000000000000000000000000000000000012619358",
                            "parameter": {
                                "_value": "308384600",
                                "_to": "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag"
                            },
                            "methodName": "transfer",
                            "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "call_value": 0
                        },
                        "quant": "308384600",
                        "approval_amount": "0",
                        "event_type": "Transfer",
                        "confirmed": True,
                        "contractRet": "SUCCESS",
                        "finalResult": "SUCCESS",
                        "tokenInfo": {
                            "tokenId": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "tokenAbbr": "USDT",
                            "tokenName": "Tether USD",
                            "tokenDecimal": 6,
                            "tokenCanShow": 1,
                            "tokenType": "trc20",
                            "tokenLogo": "https://static.tronscan.org/production/logo/usdtlogo.png",
                            "tokenLevel": "2",
                            "issuerAddr": "THPvaUhoh2Qn2y9THCZML3H815hhFhn5YC",
                            "vip": True
                        },
                        "revert": False,
                        "contract_type": "trc20",
                        "fromAddressIsContract": False,
                        "toAddressIsContract": False,
                        "riskTransaction": False
                    },
                    {
                        "transaction_id": "5537aafab5b7f4b0b264f9904a49d9d0bac042cf42b58b56b96e8b89bb2b2168",
                        "status": 0,
                        "block_ts": 1728617814000,
                        "from_address": "TJ5usJLLwjwn7Pw3TPbdzreG7dvgKzfQ5y",
                        "from_address_tag": {
                            "from_address_tag": "Binance-Hot 9",
                            "from_address_tag_logo": ""
                        },
                        "to_address": "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag",
                        "to_address_tag": {
                            "to_address_tag_logo": "",
                            "to_address_tag": ""
                        },
                        "block": 65989678,
                        "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                        "trigger_info": {
                            "method": "transfer(address _to,uint256 _value)",
                            "data": "a9059cbb000000000000000000000041784ec5627ac5c3f8de4117175db192c1b9e809c1000000000000000000000000000000000000000000000000000000000ed77040",
                            "parameter": {
                                "_value": "249000000",
                                "_to": "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag"
                            },
                            "methodName": "transfer",
                            "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "call_value": 0
                        },
                        "quant": "249000000",
                        "approval_amount": "0",
                        "event_type": "Transfer",
                        "confirmed": True,
                        "contractRet": "SUCCESS",
                        "finalResult": "SUCCESS",
                        "tokenInfo": {
                            "tokenId": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "tokenAbbr": "USDT",
                            "tokenName": "Tether USD",
                            "tokenDecimal": 6,
                            "tokenCanShow": 1,
                            "tokenType": "trc20",
                            "tokenLogo": "https://static.tronscan.org/production/logo/usdtlogo.png",
                            "tokenLevel": "2",
                            "issuerAddr": "THPvaUhoh2Qn2y9THCZML3H815hhFhn5YC",
                            "vip": True
                        },
                        "revert": False,
                        "contract_type": "trc20",
                        "fromAddressIsContract": False,
                        "toAddressIsContract": False,
                        "riskTransaction": False
                    },
                    {
                        "transaction_id": "abb3914e5b6ca8b8b9a2b4f1474e84b667ff95276224bf8b4ea8c28f4e65c249",
                        "status": 0,
                        "block_ts": 1728615372000,
                        "from_address": "TJqwA7SoZnERE4zW5uDEiPkbz4B66h9TFj",
                        "from_address_tag": {
                            "from_address_tag": "Binance-Hot 11",
                            "from_address_tag_logo": ""
                        },
                        "to_address": "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag",
                        "to_address_tag": {
                            "to_address_tag_logo": "",
                            "to_address_tag": ""
                        },
                        "block": 65988864,
                        "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                        "trigger_info": {
                            "method": "transfer(address _to,uint256 _value)",
                            "data": "a9059cbb000000000000000000000041784ec5627ac5c3f8de4117175db192c1b9e809c1000000000000000000000000000000000000000000000000000000000f273df0",
                            "parameter": {
                                "_value": "254230000",
                                "_to": "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag"
                            },
                            "methodName": "transfer",
                            "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "call_value": 0
                        },
                        "quant": "254230000",
                        "approval_amount": "0",
                        "event_type": "Transfer",
                        "confirmed": True,
                        "contractRet": "SUCCESS",
                        "finalResult": "SUCCESS",
                        "tokenInfo": {
                            "tokenId": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "tokenAbbr": "USDT",
                            "tokenName": "Tether USD",
                            "tokenDecimal": 6,
                            "tokenCanShow": 1,
                            "tokenType": "trc20",
                            "tokenLogo": "https://static.tronscan.org/production/logo/usdtlogo.png",
                            "tokenLevel": "2",
                            "issuerAddr": "THPvaUhoh2Qn2y9THCZML3H815hhFhn5YC",
                            "vip": True
                        },
                        "revert": False,
                        "contract_type": "trc20",
                        "fromAddressIsContract": False,
                        "toAddressIsContract": False,
                        "riskTransaction": False
                    },
                    {
                        "transaction_id": "4305f07531eca2c30f965c48a30aab92b18f68cd3aec181834a1583587be8ce6",
                        "status": 0,
                        "block_ts": 1728575988000,
                        "from_address": "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag",
                        "from_address_tag": {
                            "from_address_tag": "",
                            "from_address_tag_logo": ""
                        },
                        "to_address": "TWtcTcqSeoyRKCV89j8ZWXeqHAwNwq9pt6",
                        "to_address_tag": {
                            "to_address_tag_logo": "",
                            "to_address_tag": ""
                        },
                        "block": 65975740,
                        "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                        "trigger_info": {
                            "method": "transfer(address _to,uint256 _value)",
                            "data": "a9059cbb000000000000000000000000e57c24b1f2b9853420a6d3a3da0c19c4fb8da0630000000000000000000000000000000000000000000000000000000017b8ff80",
                            "parameter": {
                                "_value": "398000000",
                                "_to": "TWtcTcqSeoyRKCV89j8ZWXeqHAwNwq9pt6"
                            },
                            "methodName": "transfer",
                            "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "call_value": 0
                        },
                        "quant": "398000000",
                        "approval_amount": "0",
                        "event_type": "Transfer",
                        "confirmed": True,
                        "contractRet": "SUCCESS",
                        "finalResult": "SUCCESS",
                        "tokenInfo": {
                            "tokenId": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "tokenAbbr": "USDT",
                            "tokenName": "Tether USD",
                            "tokenDecimal": 6,
                            "tokenCanShow": 1,
                            "tokenType": "trc20",
                            "tokenLogo": "https://static.tronscan.org/production/logo/usdtlogo.png",
                            "tokenLevel": "2",
                            "issuerAddr": "THPvaUhoh2Qn2y9THCZML3H815hhFhn5YC",
                            "vip": True
                        },
                        "revert": False,
                        "contract_type": "trc20",
                        "fromAddressIsContract": False,
                        "toAddressIsContract": False,
                        "riskTransaction": False
                    },
                    {
                        "transaction_id": "9fd8706bc650f77703a511120b79fc80967f01dc14a48e5c7ec23d61b86923ae",
                        "status": 0,
                        "block_ts": 1728556497000,
                        "from_address": "TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm",
                        "from_address_tag": {
                            "from_address_tag": "Binance 2",
                            "from_address_tag_logo": ""
                        },
                        "to_address": "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag",
                        "to_address_tag": {
                            "to_address_tag_logo": "",
                            "to_address_tag": ""
                        },
                        "block": 65969245,
                        "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                        "trigger_info": {
                            "method": "transfer(address _to,uint256 _value)",
                            "data": "a9059cbb000000000000000000000041784ec5627ac5c3f8de4117175db192c1b9e809c1000000000000000000000000000000000000000000000000000000000bdc7fc0",
                            "parameter": {
                                "_value": "199000000",
                                "_to": "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag"
                            },
                            "methodName": "transfer",
                            "contract_address": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "call_value": 0
                        },
                        "quant": "199000000",
                        "approval_amount": "0",
                        "event_type": "Transfer",
                        "confirmed": True,
                        "contractRet": "SUCCESS",
                        "finalResult": "SUCCESS",
                        "tokenInfo": {
                            "tokenId": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
                            "tokenAbbr": "USDT",
                            "tokenName": "Tether USD",
                            "tokenDecimal": 6,
                            "tokenCanShow": 1,
                            "tokenType": "trc20",
                            "tokenLogo": "https://static.tronscan.org/production/logo/usdtlogo.png",
                            "tokenLevel": "2",
                            "issuerAddr": "THPvaUhoh2Qn2y9THCZML3H815hhFhn5YC",
                            "vip": True
                        },
                        "revert": False,
                        "contract_type": "trc20",
                        "fromAddressIsContract": False,
                        "toAddressIsContract": False,
                        "riskTransaction": False
                    }
                ],
                "normalAddressInfo": {
                    "TWtcTcqSeoyRKCV89j8ZWXeqHAwNwq9pt6": {
                        "risk": False
                    },
                    "TJ5usJLLwjwn7Pw3TPbdzreG7dvgKzfQ5y": {
                        "risk": False
                    },
                    "TYASr5UV6HEcXatwdFQfmLVUqQQQMUxHLS": {
                        "risk": False
                    },
                    "TJqwA7SoZnERE4zW5uDEiPkbz4B66h9TFj": {
                        "risk": False
                    },
                    "TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag": {
                        "risk": False
                    },
                    "TDqSquXBgUCLYvYC4XZgrprLK589dkhSCf": {
                        "risk": False
                    },
                    "TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm": {
                        "risk": False
                    }
                }
            }
        ]

        self.api.get_token_txs = Mock(side_effect=address_txs_mock_response)

        address_txs_response = self.explorer().get_token_txs(ADDRESSES_OF_ACCOUNT[1], CONTRACT_INFO_USDT)

        expected_result = [
            {13: {'amount': Decimal('249.234600'), 'from_address': 'TJqwA7SoZnERE4zW5uDEiPkbz4B66h9TFj',
                  'to_address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag',
                  'hash': '8934bbfb5e152cc71ab0e635119ef402d2783c1632f91e75700ad9a52186ce18', 'block': 66024909,
                  'date': datetime.datetime(2024, 10, 12, 8, 59,
                                            tzinfo=datetime.timezone.utc), 'memo': None, 'confirmations': 20, 'address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag', 'direction': 'incoming', 'contract_address': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', 'raw': None}}, {
            13: {'amount': Decimal('149.000000'), 'from_address': 'TYASr5UV6HEcXatwdFQfmLVUqQQQMUxHLS',
                 'to_address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag',
                 'hash': 'd44fca70f2f9352cfaa2a4183187dcd10e03505f5efcaca2d6350ae655aa8cee', 'block': 66024372,
                 'date': datetime.datetime(2024, 10, 12, 8, 32, 9,
                                           tzinfo=datetime.timezone.utc), 'memo': None, 'confirmations': 20, 'address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag', 'direction': 'incoming', 'contract_address': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', 'raw': None}}, {
            13: {'amount': Decimal('149.000000'), 'from_address': 'TDqSquXBgUCLYvYC4XZgrprLK589dkhSCf',
                 'to_address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag',
                 'hash': '951da41e0dbb92998b06fd8b07746c17b6de8b76028e270ffe79ac88b2092ad0', 'block': 66024202,
                 'date': datetime.datetime(2024, 10, 12, 8, 23, 39,
                                           tzinfo=datetime.timezone.utc), 'memo': None, 'confirmations': 20, 'address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag', 'direction': 'incoming', 'contract_address': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', 'raw': None}}, {
            13: {'amount': Decimal('399.000000'), 'from_address': 'TJ5usJLLwjwn7Pw3TPbdzreG7dvgKzfQ5y',
                 'to_address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag',
                 'hash': '1029be850caa9ab3df17fe46c6015e2df97ba136aec3a8f2b398c039ad448b77', 'block': 66017923,
                 'date': datetime.datetime(2024, 10, 12, 3, 9, 36,
                                           tzinfo=datetime.timezone.utc), 'memo': None, 'confirmations': 20, 'address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag', 'direction': 'incoming', 'contract_address': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', 'raw': None}}, {
            13: {'amount': Decimal('811.614600'), 'from_address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag',
                 'to_address': 'TWtcTcqSeoyRKCV89j8ZWXeqHAwNwq9pt6',
                 'hash': '8dfeb62597ef11a7efe8a3b9ea2817dd5a8ccca552d0734df16352d0739393df', 'block': 65997889,
                 'date': datetime.datetime(2024, 10, 11, 10, 27, 36,
                                           tzinfo=datetime.timezone.utc), 'memo': None, 'confirmations': 20, 'address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag', 'direction': 'outgoing', 'contract_address': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', 'raw': None}}, {
            13: {'amount': Decimal('308.384600'), 'from_address': 'TYASr5UV6HEcXatwdFQfmLVUqQQQMUxHLS',
                 'to_address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag',
                 'hash': '88ed569f0f50bbef0b4430793f1978e6110be79b25000a86601cd2084efeb2ed', 'block': 65996485,
                 'date': datetime.datetime(2024, 10, 11, 9, 17, 24,
                                           tzinfo=datetime.timezone.utc), 'memo': None, 'confirmations': 20, 'address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag', 'direction': 'incoming', 'contract_address': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', 'raw': None}}, {
            13: {'amount': Decimal('249.000000'), 'from_address': 'TJ5usJLLwjwn7Pw3TPbdzreG7dvgKzfQ5y',
                 'to_address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag',
                 'hash': '5537aafab5b7f4b0b264f9904a49d9d0bac042cf42b58b56b96e8b89bb2b2168', 'block': 65989678,
                 'date': datetime.datetime(2024, 10, 11, 3, 36, 54,
                                           tzinfo=datetime.timezone.utc), 'memo': None, 'confirmations': 20, 'address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag', 'direction': 'incoming', 'contract_address': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', 'raw': None}}, {
            13: {'amount': Decimal('254.230000'), 'from_address': 'TJqwA7SoZnERE4zW5uDEiPkbz4B66h9TFj',
                 'to_address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag',
                 'hash': 'abb3914e5b6ca8b8b9a2b4f1474e84b667ff95276224bf8b4ea8c28f4e65c249', 'block': 65988864,
                 'date': datetime.datetime(2024, 10, 11, 2, 56, 12,
                                           tzinfo=datetime.timezone.utc), 'memo': None, 'confirmations': 20, 'address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag', 'direction': 'incoming', 'contract_address': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', 'raw': None}}, {
            13: {'amount': Decimal('398.000000'), 'from_address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag',
                 'to_address': 'TWtcTcqSeoyRKCV89j8ZWXeqHAwNwq9pt6',
                 'hash': '4305f07531eca2c30f965c48a30aab92b18f68cd3aec181834a1583587be8ce6', 'block': 65975740,
                 'date': datetime.datetime(2024, 10, 10, 15, 59, 48,
                                           tzinfo=datetime.timezone.utc), 'memo': None, 'confirmations': 20, 'address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag', 'direction': 'outgoing', 'contract_address': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', 'raw': None}}, {
            13: {'amount': Decimal('199.000000'), 'from_address': 'TQrY8tryqsYVCYS3MFbtffiPp2ccyn4STm',
                 'to_address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag',
                 'hash': '9fd8706bc650f77703a511120b79fc80967f01dc14a48e5c7ec23d61b86923ae', 'block': 65969245,
                 'date': datetime.datetime(2024, 10, 10, 10, 34, 57,
                                           tzinfo=datetime.timezone.utc), 'memo': None, 'confirmations': 20, 'address': 'TLwLTBk5k9nVNM3FK6yP8bXWsu6aTczcag', 'direction': 'incoming', 'contract_address': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', 'raw': None}}]

        self.assertEqual(address_txs_response, expected_result)