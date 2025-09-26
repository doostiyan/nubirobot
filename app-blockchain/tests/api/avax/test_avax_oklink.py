import pytest
import datetime
from pytz import UTC

from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

from django.core.cache import cache

from exchange.base.models import Currencies
from exchange.blockchain.api.avax import AvalancheOkLinkApi
from exchange.blockchain.api.avax.avax_explorer_interface import AvalancheExplorerInterface
from exchange.blockchain.utils import BlockchainUtilsMixin

API = AvalancheOkLinkApi
ADDRESSES = [
    "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
    "0xbF72c5ECDd12903aa55121CB989A6D948F001Df6",
]
TOKEN_ADDRESSES = ["0x7E4aA755550152a522d9578621EA22eDAb204308", "0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B"]
TXS_HASH = [
    "0xcb02eca856eb0e4e5c0fc95c268b68edc361a442ea41095259fbb0ca477654cd",
    "0xd78bcd9e665c4c0900a91bbd734f9125e193aa6d1cb632e809b25a59cb300952",
]
BLOCK_HEIGHT = [38298429]


@pytest.mark.slow
class TestAvalancheOklinkApiCalls(TestCase):
    @classmethod
    def _check_general_response(cls, response):
        if response.get("code") != "0":
            return False
        if not response.get("data"):
            return False
        return True

    def test_get_balance_api(self):
        for address in ADDRESSES:
            get_balance_result = API.get_balance(address)
            assert self._check_general_response(get_balance_result)
            assert get_balance_result.get("data")[0].get("balance")
            assert isinstance(get_balance_result.get("data")[0].get("balance"), str)

    def test_get_balances_api(self):
        get_balance_result = API.get_balances(ADDRESSES)
        assert self._check_general_response(get_balance_result)
        assert API.parser.validator.validate_balances_response(get_balance_result)
        assert get_balance_result.get("data")[0].get("balanceList")
        assert get_balance_result.get("data")[0].get("balanceList")[0].get("balance")
        assert isinstance(
            get_balance_result.get("data")[0].get("balanceList")[0].get("balance"), str
        )
        assert get_balance_result.get("data")[0].get("balanceList")[0].get("address")

    def test_get_token_balance(self):
        fake_contract_info = {
            'address': '0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7',
            'decimals': 6,
            'symbol': 'USDT',
        }
        for address in TOKEN_ADDRESSES:
            get_token_balance_result = API.get_token_balance(address, fake_contract_info)
            assert self._check_general_response(get_token_balance_result)
            assert get_token_balance_result.get("data")[0].get("tokenList")
            assert isinstance(get_token_balance_result.get("data")[0].get("tokenList"), list)
            assert get_token_balance_result.get("data")[0].get("tokenList")[0].get("holdingAmount")
            assert isinstance(
                get_token_balance_result.get("data")[0].get("tokenList")[0].get("holdingAmount"), str
            )

    def test_get_token_balances(self):
        get_token_balances_result = API.get_token_balances(TOKEN_ADDRESSES)
        assert self._check_general_response(get_token_balances_result)
        balances = get_token_balances_result.get("data")[0].get("balanceList")
        for balance in balances:
            assert balance.get('address')
            assert isinstance(balance.get('address'), str)
            assert balance.get('holdingAmount')
            assert isinstance(balance.get('holdingAmount'), str)
            assert balance.get('tokenContractAddress')
            assert isinstance(balance.get('tokenContractAddress'), str)

    def test_get_block_head_api(self):
        get_block_head_response = API.get_block_head()
        assert self._check_general_response(get_block_head_response)
        assert get_block_head_response.get("data")[0].get("blockList")
        assert isinstance(
            get_block_head_response.get("data")[0].get("blockList")[0], dict
        )
        assert get_block_head_response.get("data")[0].get("blockList")[0].get("height")
        assert isinstance(
            get_block_head_response.get("data")[0].get("blockList")[0].get("height"),
            str,
        )

    def test_get_tx_details_api(self):
        transaction_keys = {
            "methodId",
            "inputDetails",
            "outputDetails",
            "transactionTime",
            "height",
            "txid",
            "confirm",
            "txfee",
        }
        token_transactoin_keys = {
            "from",
            "to",
            "amount",
            "symbol",
            "tokenContractAddress",
        }

        for tx_hash in TXS_HASH:
            get_tx_details_response = API.get_tx_details(tx_hash)
            assert API.parser.validator.validate_tx_details_transaction(
                get_tx_details_response
            )
            data = get_tx_details_response.get("data")[0]
            assert isinstance(get_tx_details_response, dict)
            assert isinstance(data, dict)
            if data.get("methodId") == "0xa9059cbb":
                assert token_transactoin_keys.issubset(
                    data.get("tokenTransferDetails")[0]
                )
            assert transaction_keys.issubset(data)

    def test_get_address_txs_api(self):
        address_transaction_keys = {
            "height",
            "blockHash",
            "txId",
            "transactionTime",
            "from",
            "to",
            "txFee",
            "amount",
        }
        for address in ADDRESSES:
            get_address_txs_response = API.get_address_txs(address)
            assert self._check_general_response(get_address_txs_response)
            assert isinstance(get_address_txs_response, dict)
            data = get_address_txs_response.get("data")[0]
            assert data.get("transactionLists")
            assert isinstance(data.get("transactionLists"), list)
            for tx in data.get("transactionLists"):
                assert address_transaction_keys.issubset(tx)
                for key, value in tx.items():
                    if key.lower().startswith("is"):
                        assert isinstance(value, bool)
                    else:
                        assert isinstance(value, str)

    def test_get_token_txs_api(self):
        token_transaction_keys = {
            'height',
            'blockHash',
            'txId',
            'transactionTime',
            'from',
            'to',
            'txFee',
            'amount',
            'tokenContractAddress'
        }
        fake_contract_info = {
            'address': '0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7',
            'decimals': 6,
            'symbol': 'USDT',
        }
        for address in TOKEN_ADDRESSES:
            get_token_txs_response = API.get_token_txs(address, fake_contract_info)
            assert self._check_general_response(get_token_txs_response)
            txs = get_token_txs_response['data'][0].get('transactionLists')
            assert txs
            assert isinstance(txs, list)
            for tx_item in txs:
                assert token_transaction_keys.issubset(tx_item)
                for key, value in tx_item.items():
                    if key.lower().startswith('is'):
                        assert isinstance(value, bool)
                    else:
                        assert isinstance(value, str)

    def test_block_txs_api(self):
        block_transaction_keys = {
            'height',
            'blockHash',
            'txid',
            'transactionTime',
            'from',
            'to',
            'txfee',
            'amount',
        }
        for block_height in BLOCK_HEIGHT:
            get_block_txs_response = API.get_block_txs(block_height)
            assert self._check_general_response(get_block_txs_response)
            data = get_block_txs_response.get("data")[0]
            assert isinstance(data, dict)
            assert data.get("blockList")
            assert isinstance(data.get("blockList"), list)
            for tx in data.get("blockList"):
                assert block_transaction_keys.issubset(tx)
                for key, value in tx.items():
                    if key.lower().startswith("is"):
                        assert isinstance(value, bool)
                    else:
                        assert isinstance(value, str)


class TestAvalancheOklinkFromExplorer(TestCase):
    def test_get_tx_details(self):
        tx_details_mock_responses = [
            {
                "code": "0",
                "msg": "",
                "data": [
                    {
                        "chainFullName": "Avalanche-C",
                        "chainShortName": "AVAXC",
                        "txid": "0xcb02eca856eb0e4e5c0fc95c268b68edc361a442ea41095259fbb0ca477654cd",
                        "height": "38301393",
                        "transactionTime": "1701074236000",
                        "amount": "1.432361",
                        "transactionSymbol": "AVAX",
                        "txfee": "0.000546",
                        "index": "3",
                        "confirm": "7657",
                        "inputDetails": [
                            {
                                "inputHash": "0xb985cf3042a9ce3a2dc48399f8e39d7119d39d6f",
                                "isContract": False,
                                "amount": "",
                            }
                        ],
                        "outputDetails": [
                            {
                                "outputHash": "0x2f13d388b85e0ecd32e7c3d7f36d1053354ef104",
                                "isContract": False,
                                "amount": "",
                            }
                        ],
                        "state": "success",
                        "gasLimit": "21000",
                        "gasUsed": "21000",
                        "gasPrice": "0.000000026",
                        "totalTransactionSize": "",
                        "virtualSize": "1",
                        "weight": "",
                        "nonce": "221",
                        "transactionType": "2",
                        "methodId": "",
                        "errorLog": "",
                        "inputData": "0x",
                        "isAaTransaction": False,
                        "tokenTransferDetails": [],
                        "contractDetails": [],
                    }
                ],
            },
            {
                "code": "0",
                "msg": "",
                "data": [
                    {
                        "chainFullName": "Avalanche-C",
                        "chainShortName": "AVAXC",
                        "txid": "0xd78bcd9e665c4c0900a91bbd734f9125e193aa6d1cb632e809b25a59cb300952",
                        "height": "38301415",
                        "transactionTime": "1701074280000",
                        "amount": "0",
                        "transactionSymbol": "AVAX",
                        "txfee": "0.001650726",
                        "index": "1",
                        "confirm": "7742",
                        "inputDetails": [
                            {
                                "inputHash": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                                "isContract": False,
                                "amount": "",
                            }
                        ],
                        "outputDetails": [
                            {
                                "outputHash": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                                "isContract": True,
                                "amount": "",
                            }
                        ],
                        "state": "success",
                        "gasLimit": "61608",
                        "gasUsed": "61138",
                        "gasPrice": "0.000000027",
                        "totalTransactionSize": "",
                        "virtualSize": "0",
                        "weight": "",
                        "nonce": "2890066",
                        "transactionType": "2",
                        "methodId": "0xa9059cbb",
                        "errorLog": "",
                        "inputData": "0xa9059cbb0000000000000000000000007863d6ec13b333e90cad94ebb8e8e8979770868d000000000000000000000000000000000000000000000000000000001dbe22c0",
                        # noqa
                        "isAaTransaction": False,
                        "tokenTransferDetails": [
                            {
                                "index": "1",
                                "token": "TetherToken",
                                "tokenContractAddress": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                                "symbol": "USDt",
                                "from": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                                "to": "0x7863d6ec13b333e90cad94ebb8e8e8979770868d",
                                "tokenId": "",
                                "amount": "499",
                                "isFromContract": False,
                                "isToContract": False,
                            }
                        ],
                        "contractDetails": [
                            {
                                "index": "0",
                                "from": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                                "to": "0xba2a995bd4ab9e605454ccef88169352cd5f75a6",
                                "amount": "0",
                                "gasLimit": "32196",
                                "isFromContract": True,
                                "isToContract": True,
                            }
                        ],
                    }
                ],
            },
        ]

        block_head_mock_responses = [
            {
                "code": "0",
                "msg": "",
                "data": [
                    {
                        "page": "1",
                        "limit": "1",
                        "totalPage": "10000",
                        "chainFullName": "Avalanche-C",
                        "chainShortName": "AVAXC",
                        "blockList": [
                            {
                                "hash": "0x04e7187b78686d944f555f9bbd55c60515095ca798e014e660956602390cbf5f",
                                "height": "38309023",
                                "validator": "0x0100000000000000000000000000000000000000",
                                "blockTime": "1701089627000",
                                "txnCount": "5",
                                "blockSize": "5255",
                                "mineReward": "0",
                                "totalFee": "0.030109252",
                                "feeSymbol": "AVAX",
                                "avgFee": "0.006",
                                "ommerBlock": "",
                                "gasUsed": "1085434",
                                "gasLimit": "15000000",
                                "gasAvgPrice": "0.000000027739366926",
                                "state": "",
                                "burnt": "0.030109252",
                                "netWork": "",
                            }
                        ],
                    }
                ],
            },
            {
                "code": "0",
                "msg": "",
                "data": [
                    {
                        "page": "1",
                        "limit": "1",
                        "totalPage": "10000",
                        "chainFullName": "Avalanche-C",
                        "chainShortName": "AVAXC",
                        "blockList": [
                            {
                                "hash": "0x7ebca9462a7a098438306dd1f314c67338532fe0aa77d8a71fcbe3a0ffc87cc0",
                                "height": "38309131",
                                "validator": "0x0100000000000000000000000000000000000000",
                                "blockTime": "1701089842000",
                                "txnCount": "17",
                                "blockSize": "9168",
                                "mineReward": "0",
                                "totalFee": "0.0703527385",
                                "feeSymbol": "AVAX",
                                "avgFee": "0.0041",
                                "ommerBlock": "",
                                "gasUsed": "2596900",
                                "gasLimit": "15000000",
                                "gasAvgPrice": "0.00000002709104644",
                                "state": "",
                                "burnt": "0.0703527385",
                                "netWork": "",
                            }
                        ],
                    }
                ],
            },
        ]
        API.get_block_head = Mock(side_effect=block_head_mock_responses)
        API.get_tx_details = Mock(side_effect=tx_details_mock_responses)

        AvalancheExplorerInterface.tx_details_apis[0] = API

        expected_txs_details = [
            {
                "hash": "0xcb02eca856eb0e4e5c0fc95c268b68edc361a442ea41095259fbb0ca477654cd",
                "success": True,
                "block": 38301393,
                "date": datetime.datetime(2023, 11, 27, 8, 37, 16, tzinfo=UTC),
                "fees": Decimal("0.000546"),
                "memo": None,
                "confirmations": "7657",
                "raw": None,
                "inputs": [],
                "outputs": [],
                "transfers": [
                    {
                        "type": "MainCoin",
                        "symbol": "AVAX",
                        "currency": 57,
                        "from": "0xb985cf3042a9ce3a2dc48399f8e39d7119d39d6f",
                        "to": "0x2f13d388b85e0ecd32e7c3d7f36d1053354ef104",
                        "value": Decimal("1.432361"),
                        "is_valid": True,
                        "token": None,
                        'memo': None,
                    }
                ],
            },
            {
                "hash": "0xd78bcd9e665c4c0900a91bbd734f9125e193aa6d1cb632e809b25a59cb300952",
                "success": True,
                "block": 38301415,
                "date": datetime.datetime(2023, 11, 27, 8, 38, tzinfo=UTC),
                "fees": Decimal("0.001650726"),
                "memo": None,
                "confirmations": "7742",
                "raw": None,
                "inputs": [],
                "outputs": [],
                "transfers": [
                    {
                        "type": "Token",
                        "symbol": "USDt",
                        "currency": 13,
                        "from": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                        "to": "0x7863d6ec13b333e90cad94ebb8e8e8979770868d",
                        "value": Decimal("499"),
                        "is_valid": True,
                        'memo': None,
                        "token": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                    }
                ],
            },
        ]
        for expected_tx_details, tx_hash in zip(expected_txs_details, TXS_HASH):
            txs_details = AvalancheExplorerInterface.get_api().get_tx_details(tx_hash)
            assert txs_details == expected_tx_details

    def test_get_balances(self):
        balance_mock_responses = [
            {
                "code": "0",
                "data": [
                    {
                        "balanceList": [
                            {
                                "address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "balance": "0",
                            },
                            {
                                "address": "0xbf72c5ecdd12903aa55121cb989a6d948f001df6",
                                "balance": "0.002970974",
                            },
                        ],
                        "symbol": "AVAX",
                    }
                ],
                "msg": "",
            }
        ]
        API.get_balances = Mock(side_effect=balance_mock_responses)
        AvalancheExplorerInterface.balance_apis[0] = API
        expected_balances = [
            {
                57: {
                    "address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                    "amount": Decimal("0"),
                    "symbol": "AVAX",
                }
            },
            {
                57: {
                    "address": "0xbf72c5ecdd12903aa55121cb989a6d948f001df6",
                    "amount": Decimal("0.002970974"),
                    "symbol": "AVAX",
                }
            },
        ]
        balances = AvalancheExplorerInterface.get_api().get_balances(ADDRESSES)
        assert balances == expected_balances

    def test_get_token_balance(self):
        fake_contract_info = {
            13: {
                'address': '0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7',
                'decimals': 6,
                'symbol': 'USDT',
            }
        }
        token_balance_mock_responses = [
            {'code': '0', 'msg': '', 'data': [{'limit': '20', 'page': '1', 'totalPage': '1', 'tokenList': [
                {'symbol': 'USDt', 'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7',
                 'holdingAmount': '48103535.416806', 'priceUsd': '', 'valueUsd': '48099687.13397265552',
                 'tokenId': ''}]}]},
            {'code': '0', 'msg': '', 'data': [{'limit': '20', 'page': '1', 'totalPage': '1', 'tokenList': [
                {'symbol': 'USDt', 'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7',
                 'holdingAmount': '1203351.227072', 'priceUsd': '', 'valueUsd': '1203206.82492475136',
                 'tokenId': ''}]}]}

        ]

        API.get_token_balance = Mock(side_effect=token_balance_mock_responses)
        AvalancheExplorerInterface.token_balance_apis[0] = API
        expected_balances = [
            Decimal('48103535.416806'),
            Decimal('1203351.227072')

        ]
        for address, expcted_balance in zip(TOKEN_ADDRESSES, expected_balances):
            balances = AvalancheExplorerInterface.get_api().get_token_balance(address, fake_contract_info)
            assert balances.get('amount') == expcted_balance

    def test_get_token_balances(self):
        fake_contract_info_list = {
            66: {
                'address': '0xcA414DA46f9874fDEb1F8A46F5A0173e0145B26a',
                'decimals': 18,
                'symbol': 'RAI'
            }
        }
        token_balance_mock_responses = [
            {'code': '0', 'msg': '', 'data': [{'page': '1', 'limit': '20', 'totalPage': '3', 'balanceList': [
                {'address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b', 'holdingAmount': '1.1017',
                 'tokenContractAddress': '0x3af6e2619140f356b04507b1a47e00091649244a'},
                {'address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b', 'holdingAmount': '188.75',
                 'tokenContractAddress': '0xf7fe425a4f0a735ac2d2fd1c1e275c1e4550cdc3'},
                {'address': '0x7e4aa755550152a522d9578621ea22edab204308', 'holdingAmount': '188.75',
                 'tokenContractAddress': '0xf7fe425a4f0a735ac2d2fd1c1e275c1e4550cdc3'},
                {'address': '0x7e4aa755550152a522d9578621ea22edab204308', 'holdingAmount': '3000',
                 'tokenContractAddress': '0xca414da46f9874fdeb1f8a46f5a0173e0145b26a'},
                {'address': '0x7e4aa755550152a522d9578621ea22edab204308', 'holdingAmount': '424635.44025447',
                 'tokenContractAddress': '0x31c994ac062c1970c086260bc61babb708643fac'},
                {'address': '0x7e4aa755550152a522d9578621ea22edab204308', 'holdingAmount': '673065914.3338135',
                 'tokenContractAddress': '0x714f020c54cc9d104b6f4f6998c63ce2a31d1888'},
                {'address': '0x7e4aa755550152a522d9578621ea22edab204308', 'holdingAmount': '1000000',
                 'tokenContractAddress': '0x0db1ac300a55ec29519e3440b17a4a4ea1b570f7'},
                {'address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b', 'holdingAmount': '74.04175',
                 'tokenContractAddress': '0x4c4f4f4122c3a80d30c1ad6ad2828953015bd52c'},
                {'address': '0x7e4aa755550152a522d9578621ea22edab204308', 'holdingAmount': '500',
                 'tokenContractAddress': '0xd23345e0e6340616b1cf7200762d0289547ccf87'},
                {'address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b', 'holdingAmount': '59.0539428',
                 'tokenContractAddress': '0x9bf843b1ba38edd1d737d0728f1b999e984fa3fc'},
                {'address': '0x7e4aa755550152a522d9578621ea22edab204308', 'holdingAmount': '7395',
                 'tokenContractAddress': '0x78f365fe249eff7e6f3ab2e537a151a448a597db'},
                {'address': '0x7e4aa755550152a522d9578621ea22edab204308', 'holdingAmount': '1000.11',
                 'tokenContractAddress': '0xf80fc26d5d20cca25c1c987abf7932942f9e57eb'},
                {'address': '0x7e4aa755550152a522d9578621ea22edab204308', 'holdingAmount': '267004.109742542',
                 'tokenContractAddress': '0xc024019e53ab2eccd14b3a2dbf1e6604a8026c1c'},
                {'address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b', 'holdingAmount': '300000',
                 'tokenContractAddress': '0xf9d922c055a3f1759299467dafafdf43be844f7a'},
                {'address': '0x7e4aa755550152a522d9578621ea22edab204308', 'holdingAmount': '0.19765547784572784',
                 'tokenContractAddress': '0x8729438eb15e2c8b576fcc6aecda6a148776c0f5'},
                {'address': '0x7e4aa755550152a522d9578621ea22edab204308', 'holdingAmount': '8',
                 'tokenContractAddress': '0x2e7b14e25d2eb81ec70ac7ef9033e89e588c8954'},
                {'address': '0x7e4aa755550152a522d9578621ea22edab204308', 'holdingAmount': '1228.263303',
                 'tokenContractAddress': '0xde3a24028580884448a5397872046a019649b084'},
                {'address': '0x7e4aa755550152a522d9578621ea22edab204308', 'holdingAmount': '100',
                 'tokenContractAddress': '0xa010cd55a383251c5996b697d02a818e542e2fc3'},
                {'address': '0x7e4aa755550152a522d9578621ea22edab204308', 'holdingAmount': '74.04175',
                 'tokenContractAddress': '0x4c4f4f4122c3a80d30c1ad6ad2828953015bd52c'},
                {'address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b', 'holdingAmount': '925',
                 'tokenContractAddress': '0xc98432303cdfe843c752cd748d57e283a4338a40'}]}]}

        ]
        API.get_token_balances = Mock(side_effect=token_balance_mock_responses)
        API.parser.contract_info_list = Mock(return_value=fake_contract_info_list)
        AvalancheExplorerInterface.balance_apis[0] = API
        expected_balances = [
            {'address': '0x7e4aa755550152a522d9578621ea22edab204308', 'amount': Decimal(3000), 'symbol': 'RAI',
             'token': '0xcA414DA46f9874fDEb1F8A46F5A0173e0145B26a'}
        ]
        balances = AvalancheExplorerInterface.get_api().get_token_balances(TOKEN_ADDRESSES)
        assert balances == expected_balances

    def test_get_block_txs(self):
        cache.delete('latest_block_height_processed_avax')
        block_head_mock_response = [
            {
                "code": "0",
                "msg": "",
                "data": [
                    {
                        "page": "1",
                        "limit": "1",
                        "totalPage": "10000",
                        "chainFullName": "Avalanche-C",
                        "chainShortName": "AVAXC",
                        "blockList": [
                            {
                                "hash": "0x9a82a63d7d078583b30f10da9e8dc8b178e1d4ca834e14f34511c7904dcb65e2",
                                "height": "38311001",
                                "validator": "0x0100000000000000000000000000000000000000",
                                "blockTime": "1701093611000",
                                "txnCount": "7",
                                "blockSize": "2358",
                                "mineReward": "0",
                                "totalFee": "0.017517765",
                                "feeSymbol": "AVAX",
                                "avgFee": "0.0025",
                                "ommerBlock": "",
                                "gasUsed": "690734",
                                "gasLimit": "15000000",
                                "gasAvgPrice": "0.000000025361086902",
                                "state": "",
                                "burnt": "0.017517765",
                                "netWork": "",
                            }
                        ],
                    }
                ],
            }
        ]
        block_txs_mock_responses = [
            {
                "code": "0",
                "msg": "",
                "data": [
                    {
                        "page": "1",
                        "limit": "20",
                        "totalPage": "1",
                        "chainFullName": "Avalanche-C",
                        "chainShortName": "AVAXC",
                        "blockList": [
                            {
                                "txid": "0x9c1daa4e66828308e3044c805bb720704c375bb386792fc722665173f2fccc40",
                                "methodId": "0x17835d1c",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0x48f5f003559a239ff37cbfdcc6a6d936365bd4c4",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xe547cadbe081749e5b3dc53cb792dfaea2d02fd2",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00903008",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0xeae3cb31cbdc5fe2b17d62830a3ed619bbe8433b2fce3bf0e8f81adb19c76458",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0x1467c513b7eb309471c419f6284829eda5d49f88",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.001651425",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x21aabd6ac72f7be7d482275db2a08fbd6cb08e4e0ee84df3af08da96ddcfadf1",
                                "methodId": "0xdfe11312",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0x9e0fbb6c48e571744c09d695552ad20d44c3fc50",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x3dbc7f6b6ab5178c7e0eefbcf361dba1968dbf58",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.0007421975",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x0341b4f2b634ec89ebd7c0eb6b99bb814a43210fbb4dd6bd2b72f720e23c4fe4",
                                "methodId": "0xb6e224c1",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0xd1cc0f4d02e792dae1e4c85f84c2fc25f8e689aa",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x100fe3b3e1b1b6b14c5cb1d6ce4eab32cddf3d66",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.001406991",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0xbe9af7b7724b8e16db610dc3715a403f93abe34c2aecb466b5be34bdfb0be1a7",
                                "methodId": "0xe5585666",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0x5be16d26d94fe761dea197d8fe7f8f91219a2ce6",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xd85b5e176a30edd1915d6728faebd25669b60d8b",
                                "amount": "0.036586093656176322",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.0116353285",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x1870748cf7d061300723245183d53e10d4987f1294f5de24c4ad84c1e15e245b",
                                "methodId": "0x82b8ebc7",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0xbe7aaef41e97926b042832fcd17e62a9cfe9c3c1",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x4ca5dd575dace76781c41cafe68281dfc4df0038",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.0008244945",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x878417409a589228b1ce8e27bdc30b2cf22d780d3abd0c9820d93837719b9f19",
                                "methodId": "0x9324b8c2",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0x644e5b7c5d4bc8073732cea72c66e0bb90dfc00f",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xbdd1cda63d5243fe563756065e94f23e3577e1ef",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.005095116",
                                "state": "fail",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0xb53d9a5b2aaa0d8434f4edd6a8bd7302f16eff46214a781d1451edc33efe27f8",
                                "methodId": "0x2db897d0",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0x677c64bc62aadbbc89b1be83a26213fe241a6a2d",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x8c27abf05de1d4847c3924566c3cbafec6efb42a",
                                "amount": "0.05",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00711246",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x5ea3a60c202077df5f13318189de38b51c587e16f678ddeb6f0c5644d27a2842",
                                "methodId": "0x9324b8c2",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0xd312427b78e4cc05a23fbb855ae87c77728d644b",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xbdd1cda63d5243fe563756065e94f23e3577e1ef",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.014258631",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x7c78611ea2a81f02442604e573b98a7ccb0107afc167acdeb02b490c8381904d",
                                "methodId": "0x9324b8c2",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0xaee4b1937b2f7574f9ca43db3a4d7c6773c4d11e",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xbdd1cda63d5243fe563756065e94f23e3577e1ef",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.004995807",
                                "state": "fail",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x544282bc9e0f1d62b9554a928628594f22217758e1a73c1f8f99786e431b2186",
                                "methodId": "0x64617461",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0xdcc959ccc5e71ce9204f3bf52985997f4dcb21f2",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0xbb7f1d4414386e12710f6fb65246ad4135bbc617",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.0005506",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x3aeab80123585cfa365e8636f46e1b59784ddf0f6191bf9a0b3d83ca63e7c468",
                                "methodId": "",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0x8c7e2aa9c1d1994ced6a7738e7495d1bdcbe3e23",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                                "amount": "1435.03916682",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.000525",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0xf6c13884dabd10c65bb040fe26c76c3b8edce5c6494dda37559554f1646c08bf",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0x42655fc8443fb69e9ccdb94e89c1ee9317508a6d",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.001127075",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x57343293471b8519e193cc5077d113247a6a16c4e9d9667f5e2a29bd1fdd128d",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0x95dd83560ad4ebb42f0c8942cd03554b670de3fc",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00110125",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x3575cc9562bdaa06c8fb13f1fcb0e44fb251ad63b69165219bc79a3c610c4f5b",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0xa89e61cd83b0add1dfc1e466886ffd0bc1be9ae0",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x6e84a6216ea6dacc71ee8e6b0a5b7322eebc0fdd",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.000867025",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0xcc825739c48339b5614a6e1a5c769eb1823b5774e10620920321273b5210a97f",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0x867234bc64c3fafa785c562d7691a5fa2a347995",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00152845",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x13cbd8b504c5f738bd3b80ed6e746f4225bf9234466f8aa3717e389f16eec2c4",
                                "methodId": "",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0x9430801ebaf509ad49202aabc5f5bc6fd8a3daf8",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0xd1c4c01a2bfff4df0f3ca070c1a038c66be7b9fb",
                                "amount": "0.06",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.000525",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0xdb6943558ab3f4c7c7656c98ddf8d000f614f672299e511aebd55ad00d5f0ec8",
                                "methodId": "0x64617461",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0x5717329e5b0754a24771a27533d72c1730c31c18",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0x08e34c0e8f7657ac0a9a2e47743cb9b843fbc932",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.0005506",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0xc087e309420f373b22ec9256113878f3b6f19e6ced5630d3ae69e64752083cd7",
                                "methodId": "",
                                "blockHash": "0x62d77ec74b8de08f0e5f80b8d027a848e197246abbd342272d999dc718cf7173",
                                "height": "38310997",
                                "transactionTime": "1701093602000",
                                "from": "0xfbd88ed21f077005abe744dc292b432f1170a1da",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                                "amount": "1371.39908278",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.000525",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                        ],
                    }
                ],
            },
            {
                "code": "0",
                "msg": "",
                "data": [
                    {
                        "page": "1",
                        "limit": "20",
                        "totalPage": "1",
                        "chainFullName": "Avalanche-C",
                        "chainShortName": "AVAXC",
                        "blockList": [
                            {
                                "txid": "0x650b817ea02df932b79de7bdc3191b1f6fd3a65569770b25ad7b9f891ac55906",
                                "methodId": "0xb143044b",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0x21c3de23d98caddc406e3d31b25e807addf33633",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xd56e4eab23cb81f43168f9f45211eb027b9ac7cc",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00228162",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0xc109a83df06bb6ea66893b64fd6f0b7a805da45ca3e255f6f03038d6296c0c21",
                                "methodId": "0x252f7b01",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0xe93685f3bba03016f02bd1828badd6195988d950",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xcd2e3622d483c7dc855f72e5eafadcd577ac78b4",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00696726",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x6da0e0b8506ca6bd7ae52d2b913769a8e4697dd9510d05a602babbe761430763",
                                "methodId": "0x51905636",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0x862198ea280cb9ad5534a6385207654182e3808c",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x5ecfec22aa950cb5a3b4fd7249dc30b2bd160f18",
                                "amount": "0.00291",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.006502636",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x90087a2a57acd288b7ec578c33edc9e2612342dffa3a1964701d030f09157bee",
                                "methodId": "0x095ea7b3",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0x007472775ea33cffe03501c50fa670ff7dbe0987",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.001420877",
                                "state": "fail",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x71a3e51c797714e59a4919ec5a5d4a7f63d370a7a32bd308ac7fb8f7bd80298e",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0x3b1ed12c1dd9bde1cffee655b95a573095477247",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xec3492a2508ddf4fdc0cd76f31f340b30d1793e6",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.001210534",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x250e13a67afc4f9017d07c9e3faeca7bd64f44b1bdfc4f2fedfbe4f666432692",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0x2a779c41c31cb83a47bfbf931db14a513131cf24",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00110125",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x0e2129e49ce905d452df6f207a0b9aad4ab878b15dba1903a137c144dca81909",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0x020635d91b986fd542bdf6b8e7832bed927e9d9f",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.001126775",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0xbad3c41ea658ff58998ed1869187c8b94519fe8985080ed61950e1dbf427f55b",
                                "methodId": "",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0xb3e8c75912438c2282e0afa51b41bff8e835bc88",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                                "amount": "1195.099475",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.000525",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x5061da2e78df31ee634488dad00b9e32c74b4b16af5e9dc32fc85ed57941b732",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0x0f1e491bdcfbb683404efd8484c94b154ab9ceae",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00110095",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x68bfbc9c5d78e1d298ce2b55ee3efdc2331a34bcc242d781f5ec0929a38f0a89",
                                "methodId": "0x207aab94",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0x10bb279126abd92d886aa3f2a60955c28bf14926",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x3487e27b663bfb273b7b90bf0e087342792572b1",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.005469375",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x472110bd6388acd183732cbac6e26a6ce6f480b2371d9d516716c7991ee12417",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0x7e2fa72cf078050e4448d4272be612ac736b7a06",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.001126775",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x6fe566ea17cdf89df68ed08f5ff86183f5317a103380b975299fc6ba7c280798",
                                "methodId": "",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0x8a8eb3118ac01d5ba0c4ccea38227f4a74b76bbc",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                                "amount": "594.94",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.000525",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x9bc237a23337fbd6b283d424f11c6097de42d37c9ac2cad796ff7f129cb94484",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0x586ce8792bac7f013a0774f0d1e27e32b867b723",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00110095",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x8f1db179d7a28d9f292005e349a57ffde075b0e23f96d33acc7cc11620595f7d",
                                "methodId": "0x64617461",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0x5717329e5b0754a24771a27533d72c1730c31c18",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0x08e34c0e8f7657ac0a9a2e47743cb9b843fbc932",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.0005506",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0xc8ef1a0f538aba3a395f643046697363daa1e14f0148bf5567dcc124895aafad",
                                "methodId": "0x5ae401dc",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0x23677133f24ef170379cf750906fda93385b36de",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xbb00ff08d01d300023c629e8ffffcb65a5a578ce",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.0066412",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x79d932324a8da05cab3990fa5f0c77b51f3b59c135147d4aa97ec2aab11d2aa7",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0xaec74ccda12da20816accf7bd51f979113cdea30",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.001126775",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0xd9c5cfead0a36e9bb558d211992183a8fbd1c290249eae61c2a59cc9e9467acf",
                                "methodId": "",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0x6767526a362ec6c6b1df185478e4f01506b73ff3",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                                "amount": "374.624475",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.000525",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0xd55ce73f07f0262ee3697e66edf4cb302cf99fd09f2f62bab491491334dac99f",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0x698171e371f23276ad6910d9d841edaf9b654760",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00110095",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x898b7a4b0b8de1d8e31a964b80d42783a610257d7281bb6ef767f5c7dafa4b66",
                                "methodId": "",
                                "blockHash": "0xa2ac9cec7ef6e7a1e4362003c3b914a583573954fe45c406714738305f7276e4",
                                "height": "38310998",
                                "transactionTime": "1701093605000",
                                "from": "0x19f00b3a7b6f55c9da966fe3723251784a797fa7",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                                "amount": "271.730895",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.000525",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                        ],
                    }
                ],
            },
            {
                "code": "0",
                "msg": "",
                "data": [
                    {
                        "page": "1",
                        "limit": "20",
                        "totalPage": "1",
                        "chainFullName": "Avalanche-C",
                        "chainShortName": "AVAXC",
                        "blockList": [
                            {
                                "txid": "0x9a48846f4b8505af2680e97c8ce2527b69632198255786065f1077d14f2183ed",
                                "methodId": "0x252f7b01",
                                "blockHash": "0x4be188d364923a466f9ac000df21b2f20c06419a15c74831c534317582f5eb73",
                                "height": "38310999",
                                "transactionTime": "1701093607000",
                                "from": "0xe93685f3bba03016f02bd1828badd6195988d950",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xcd2e3622d483c7dc855f72e5eafadcd577ac78b4",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00847416",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x826db3269366aa56b377251d78babbd1753cbdecf9148756e111861076f7d2d3",
                                "methodId": "",
                                "blockHash": "0x4be188d364923a466f9ac000df21b2f20c06419a15c74831c534317582f5eb73",
                                "height": "38310999",
                                "transactionTime": "1701093607000",
                                "from": "0xaec0f27fbb316732aa5fb7f8c1568f14415b81cf",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0xd09381c3f7e986934904cc3866642cae15de7422",
                                "amount": "0.02350942649055",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00060375",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x47666e398a1e4422a2d662e6a060383ee7a1e1f828a929de758e9a6ae02b7ace",
                                "methodId": "0x6bc85a76",
                                "blockHash": "0x4be188d364923a466f9ac000df21b2f20c06419a15c74831c534317582f5eb73",
                                "height": "38310999",
                                "transactionTime": "1701093607000",
                                "from": "0x9e0fbb6c48e571744c09d695552ad20d44c3fc50",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x3dbc7f6b6ab5178c7e0eefbcf361dba1968dbf58",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00085162",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0xccd5baa1db30fb2851eb33d93df11f9e37d39ee12f8a29cfc452816010b7f605",
                                "methodId": "0x9ab6156b",
                                "blockHash": "0x4be188d364923a466f9ac000df21b2f20c06419a15c74831c534317582f5eb73",
                                "height": "38310999",
                                "transactionTime": "1701093607000",
                                "from": "0x79c29d97110d10d17bf5508f598c3df1ddb68ecd",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xb4315e873dbcf96ffd0acd8ea43f689d8c20fb30",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00791645032",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x8fcb6e115d75dfc21edfb3ca0769af354e80e040476e9b7a3e535e99165df8a6",
                                "methodId": "",
                                "blockHash": "0x4be188d364923a466f9ac000df21b2f20c06419a15c74831c534317582f5eb73",
                                "height": "38310999",
                                "transactionTime": "1701093607000",
                                "from": "0x9430801ebaf509ad49202aabc5f5bc6fd8a3daf8",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0x6b1a5b7d652521d694d301ec9a4b5271d18f5f79",
                                "amount": "0.06",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.000525",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0xa6e1cc7ff2cfc300ebe15ee08a1aec5317a4387e67445a03904b15fb572f9a9f",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0x4be188d364923a466f9ac000df21b2f20c06419a15c74831c534317582f5eb73",
                                "height": "38310999",
                                "transactionTime": "1701093607000",
                                "from": "0x01d8a38cd9dae5a6d1c728368120b1fc00254425",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00110065",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x854379254244dedf9584b57c1d73eb4bcbe6f6a209a8fe52b9b1d7e777a1a1f6",
                                "methodId": "0x095ea7b3",
                                "blockHash": "0x4be188d364923a466f9ac000df21b2f20c06419a15c74831c534317582f5eb73",
                                "height": "38310999",
                                "transactionTime": "1701093607000",
                                "from": "0x11254b7d20e8017b9eec4059507cab861a785ae0",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xec3492a2508ddf4fdc0cd76f31f340b30d1793e6",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00072815",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x114aa6d012a13bd8fede9cb6a9c715582612e365c9850d0ea23ecaf55f26b86a",
                                "methodId": "",
                                "blockHash": "0x4be188d364923a466f9ac000df21b2f20c06419a15c74831c534317582f5eb73",
                                "height": "38310999",
                                "transactionTime": "1701093607000",
                                "from": "0x6991f63390dd73ac6630a896e4f958a7ab4f3259",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                                "amount": "54.9958",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.000525",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x25f1b1ba0e4d3812492d4d8dd88dc014c5e9894a03d64bd94724d5baea4fb590",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0x4be188d364923a466f9ac000df21b2f20c06419a15c74831c534317582f5eb73",
                                "height": "38310999",
                                "transactionTime": "1701093607000",
                                "from": "0x0f27bf7bbb3fd13205adaf852fa556b8a5f4b6e6",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00110095",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x6cda5df4c6cd041877ccbae140e45fd342f82b47c2d93b154baddcc5c323e18b",
                                "methodId": "0x64617461",
                                "blockHash": "0x4be188d364923a466f9ac000df21b2f20c06419a15c74831c534317582f5eb73",
                                "height": "38310999",
                                "transactionTime": "1701093607000",
                                "from": "0xdcc959ccc5e71ce9204f3bf52985997f4dcb21f2",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0xbb7f1d4414386e12710f6fb65246ad4135bbc617",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.0005506",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                        ],
                    }
                ],
            },
            {
                "code": "0",
                "msg": "",
                "data": [
                    {
                        "page": "1",
                        "limit": "20",
                        "totalPage": "1",
                        "chainFullName": "Avalanche-C",
                        "chainShortName": "AVAXC",
                        "blockList": [
                            {
                                "txid": "0x072935891e05692ee1180685e4cbe9d8fdd6cc28c5f0e37e7dabac9a9019897d",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0x867275d63d76716e36bb3d2493d40c3ee77538f8abad7ee7e54c2461f0f030bf",
                                "height": "38311000",
                                "transactionTime": "1701093609000",
                                "from": "0x0d0707963952f2fba59dd06f2b425ace40b492fe",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.001431235",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0xee0392044b53069247f3a3c1fe722e2628cb5e125751c039c7c03c43852a89af",
                                "methodId": "0x095ea7b3",
                                "blockHash": "0x867275d63d76716e36bb3d2493d40c3ee77538f8abad7ee7e54c2461f0f030bf",
                                "height": "38311000",
                                "transactionTime": "1701093609000",
                                "from": "0xd3401a5d42a06165523499b3d71e6074829e852d",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.0014693985",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x7f5a38432e647ebce6bd3cb703f1c4b62291a27450c813af6c4618b3dae2722d",
                                "methodId": "0x76aede05",
                                "blockHash": "0x867275d63d76716e36bb3d2493d40c3ee77538f8abad7ee7e54c2461f0f030bf",
                                "height": "38311000",
                                "transactionTime": "1701093609000",
                                "from": "0x95fea25b4b103e860f0089a19f33e1906c3ef072",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x366247644107ebc00ee637cdcdb5d9d33afa09c2",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.004710481",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0xe382b9a288a948064d1d8ad11a97b72e701179c541b745f300a223960ad56e54",
                                "methodId": "",
                                "blockHash": "0x867275d63d76716e36bb3d2493d40c3ee77538f8abad7ee7e54c2461f0f030bf",
                                "height": "38311000",
                                "transactionTime": "1701093609000",
                                "from": "0xdd21d72c1a7574361aede31a50a46985511d9c4f",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                                "amount": "51.499475",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.000525",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x4e041d1b22f73ba23933f39ceca8191f5bfcf64d6993b24dab4d46bfd5fdd2b8",
                                "methodId": "",
                                "blockHash": "0x867275d63d76716e36bb3d2493d40c3ee77538f8abad7ee7e54c2461f0f030bf",
                                "height": "38311000",
                                "transactionTime": "1701093609000",
                                "from": "0x9430801ebaf509ad49202aabc5f5bc6fd8a3daf8",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0xbb5b191223e154342927b92ddeed03cbfd0570cf",
                                "amount": "0.06",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.000525",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x286ec3f91aa6525b87ddf3add6d41584ab1251e206481f981f05b145c89f88a7",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0x867275d63d76716e36bb3d2493d40c3ee77538f8abad7ee7e54c2461f0f030bf",
                                "height": "38311000",
                                "transactionTime": "1701093609000",
                                "from": "0x1623b6c53e311b5e45da2c23adde327d3c0ae712",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00110095",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x4bc57c67002382ae937ba316f6b54e157e9fe191c55e72b54dbfed7c20767241",
                                "methodId": "",
                                "blockHash": "0x867275d63d76716e36bb3d2493d40c3ee77538f8abad7ee7e54c2461f0f030bf",
                                "height": "38311000",
                                "transactionTime": "1701093609000",
                                "from": "0x2578d1f75a14b9266a329c0ef368ca53c3400aac",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                                "amount": "43.561968485362665",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.000525",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x17f7d54e8bd3430b0a46b14e33c86b755f12b52c76f933190db0e8fb48814ac8",
                                "methodId": "0x64617461",
                                "blockHash": "0x867275d63d76716e36bb3d2493d40c3ee77538f8abad7ee7e54c2461f0f030bf",
                                "height": "38311000",
                                "transactionTime": "1701093609000",
                                "from": "0x5717329e5b0754a24771a27533d72c1730c31c18",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0x08e34c0e8f7657ac0a9a2e47743cb9b843fbc932",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.0005506",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                        ],
                    }
                ],
            },
            {
                "code": "0",
                "msg": "",
                "data": [
                    {
                        "page": "1",
                        "limit": "20",
                        "totalPage": "1",
                        "chainFullName": "Avalanche-C",
                        "chainShortName": "AVAXC",
                        "blockList": [
                            {
                                "txid": "0x8450eb62219b507a408542bba86a3492b1e17659aeb90180f26c077de9e6f845",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0x9a82a63d7d078583b30f10da9e8dc8b178e1d4ca834e14f34511c7904dcb65e2",
                                "height": "38311001",
                                "transactionTime": "1701093611000",
                                "from": "0x464fc339add314932920d3e060745bd7ea3e92ad",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xd402298a793948698b9a63311404fbbee944eafd",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00103179",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x24e109a8fc7c5207369528c5c99dd8c40e6d9798b0da0cb5cb8812f7fd254594",
                                "methodId": "0x6bc85a76",
                                "blockHash": "0x9a82a63d7d078583b30f10da9e8dc8b178e1d4ca834e14f34511c7904dcb65e2",
                                "height": "38311001",
                                "transactionTime": "1701093611000",
                                "from": "0x9e0fbb6c48e571744c09d695552ad20d44c3fc50",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0x3dbc7f6b6ab5178c7e0eefbcf361dba1968dbf58",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.00085195",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0xa53d3819d90f9a6b88047b740f3a8e6b745483f07bc7b0d76a97924275a658e7",
                                "methodId": "",
                                "blockHash": "0x9a82a63d7d078583b30f10da9e8dc8b178e1d4ca834e14f34511c7904dcb65e2",
                                "height": "38311001",
                                "transactionTime": "1701093611000",
                                "from": "0x09b30faf8c5183a5d26af15a6ee11fce3b87bdbc",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                                "amount": "41.632476077155082533",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.000525",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x103bf8917fcd2fb36a6f07c525f6561735d7472fc31812096e2bec5dbaf1cf08",
                                "methodId": "0xfd594a08",
                                "blockHash": "0x9a82a63d7d078583b30f10da9e8dc8b178e1d4ca834e14f34511c7904dcb65e2",
                                "height": "38311001",
                                "transactionTime": "1701093611000",
                                "from": "0xc0f39623c2f961815219c42f2dff3786aa0ab54e",
                                "isFromContract": False,
                                "isToContract": True,
                                "to": "0xca10e8825fa9f1db0651cd48a9097997dbf7615d",
                                "amount": "0.032311531690642522",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.013508425",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x1bc3e30934aa7dbb84ddb88d33055c0c9d298f262bdee0ae4a28357813010202",
                                "methodId": "",
                                "blockHash": "0x9a82a63d7d078583b30f10da9e8dc8b178e1d4ca834e14f34511c7904dcb65e2",
                                "height": "38311001",
                                "transactionTime": "1701093611000",
                                "from": "0xe72838fe26fb77dcf97686262a165ed9a72eddf4",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                                "amount": "36.999475",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.000525",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x6ae0e1bb39a7679d34889b39a8e795c12a31ace2a8bef903603c16b7fc09bb61",
                                "methodId": "0x64617461",
                                "blockHash": "0x9a82a63d7d078583b30f10da9e8dc8b178e1d4ca834e14f34511c7904dcb65e2",
                                "height": "38311001",
                                "transactionTime": "1701093611000",
                                "from": "0xdcc959ccc5e71ce9204f3bf52985997f4dcb21f2",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0xbb7f1d4414386e12710f6fb65246ad4135bbc617",
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.0005506",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                            {
                                "txid": "0x478442b22d038e2b1dbc8d86354a86595d65bcde99da4dad84c1fa2e6a01f3fc",
                                "methodId": "",
                                "blockHash": "0x9a82a63d7d078583b30f10da9e8dc8b178e1d4ca834e14f34511c7904dcb65e2",
                                "height": "38311001",
                                "transactionTime": "1701093611000",
                                "from": "0x8a383bde3ae9f5bb379ea94f3bdb406f434912e8",
                                "isFromContract": False,
                                "isToContract": False,
                                "to": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                                "amount": "34.963797",
                                "transactionSymbol": "AVAX",
                                "txfee": "0.000525",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                            },
                        ],
                    }
                ],
            },
        ]
        #
        API.get_block_head = Mock(side_effect=block_head_mock_response)
        API.get_block_txs = Mock(side_effect=block_txs_mock_responses)

        AvalancheExplorerInterface.block_txs_apis[0] = API
        txs_addresses, txs_info, _ = AvalancheExplorerInterface.get_api().get_latest_block(
            include_inputs=True, include_info=True
        )
        expected_txs_addresses = {
            "input_addresses": {
                "0x19f00b3a7b6f55c9da966fe3723251784a797fa7",
                "0x8a8eb3118ac01d5ba0c4ccea38227f4a74b76bbc",
                "0xaec0f27fbb316732aa5fb7f8c1568f14415b81cf",
                "0x6991f63390dd73ac6630a896e4f958a7ab4f3259",
                "0x2578d1f75a14b9266a329c0ef368ca53c3400aac",
                "0xb3e8c75912438c2282e0afa51b41bff8e835bc88",
                "0x8c7e2aa9c1d1994ced6a7738e7495d1bdcbe3e23",
                "0xfbd88ed21f077005abe744dc292b432f1170a1da",
                "0x6767526a362ec6c6b1df185478e4f01506b73ff3",
                "0xe72838fe26fb77dcf97686262a165ed9a72eddf4",
                "0xdd21d72c1a7574361aede31a50a46985511d9c4f",
                "0x8a383bde3ae9f5bb379ea94f3bdb406f434912e8",
                "0x9430801ebaf509ad49202aabc5f5bc6fd8a3daf8",
                "0x09b30faf8c5183a5d26af15a6ee11fce3b87bdbc",
            },
            "output_addresses": {
                "0xd1c4c01a2bfff4df0f3ca070c1a038c66be7b9fb",
                "0x6b1a5b7d652521d694d301ec9a4b5271d18f5f79",
                "0xbb5b191223e154342927b92ddeed03cbfd0570cf",
                "0xd09381c3f7e986934904cc3866642cae15de7422",
                "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
            },
        }
        expected_txs_info = {
            "outgoing_txs": {
                "0x8c7e2aa9c1d1994ced6a7738e7495d1bdcbe3e23": {
                    57: [
                        {
                            "tx_hash": "0x3aeab80123585cfa365e8636f46e1b59784ddf0f6191bf9a0b3d83ca63e7c468",
                            "value": Decimal("1435.03916682"),
                            "contract_address": None,
                            "block_height": 38310997,
                            "symbol": "AVAX"
                        }
                    ]
                },
                "0x9430801ebaf509ad49202aabc5f5bc6fd8a3daf8": {
                    57: [
                        {
                            "tx_hash": "0x13cbd8b504c5f738bd3b80ed6e746f4225bf9234466f8aa3717e389f16eec2c4",
                            "value": Decimal("0.06"),
                            "contract_address": None,
                            "block_height": 38310997,
                            "symbol": "AVAX"
                        },
                        {
                            "tx_hash": "0x8fcb6e115d75dfc21edfb3ca0769af354e80e040476e9b7a3e535e99165df8a6",
                            "value": Decimal("0.06"),
                            "contract_address": None,
                            "block_height": 38310999,
                            "symbol": "AVAX"
                        },
                        {
                            "tx_hash": "0x4e041d1b22f73ba23933f39ceca8191f5bfcf64d6993b24dab4d46bfd5fdd2b8",
                            "value": Decimal("0.06"),
                            "contract_address": None,
                            "block_height": 38311000,
                            "symbol": "AVAX"
                        },
                    ]
                },
                "0xfbd88ed21f077005abe744dc292b432f1170a1da": {
                    57: [
                        {
                            "tx_hash": "0xc087e309420f373b22ec9256113878f3b6f19e6ced5630d3ae69e64752083cd7",
                            "value": Decimal("1371.39908278"),
                            "contract_address": None,
                            "block_height": 38310997,
                            "symbol": "AVAX"
                        }
                    ]
                },
                "0xb3e8c75912438c2282e0afa51b41bff8e835bc88": {
                    57: [
                        {
                            "tx_hash": "0xbad3c41ea658ff58998ed1869187c8b94519fe8985080ed61950e1dbf427f55b",
                            "value": Decimal("1195.099475"),
                            "contract_address": None,
                            "block_height": 38310998,
                            "symbol": "AVAX"
                        }
                    ]
                },
                "0x8a8eb3118ac01d5ba0c4ccea38227f4a74b76bbc": {
                    57: [
                        {
                            "tx_hash": "0x6fe566ea17cdf89df68ed08f5ff86183f5317a103380b975299fc6ba7c280798",
                            "value": Decimal("594.94"),
                            "contract_address": None,
                            "block_height": 38310998,
                            "symbol": "AVAX"
                        }
                    ]
                },
                "0x6767526a362ec6c6b1df185478e4f01506b73ff3": {
                    57: [
                        {
                            "tx_hash": "0xd9c5cfead0a36e9bb558d211992183a8fbd1c290249eae61c2a59cc9e9467acf",
                            "value": Decimal("374.624475"),
                            "contract_address": None,
                            "block_height": 38310998,
                            "symbol": "AVAX"
                        }
                    ]
                },
                "0x19f00b3a7b6f55c9da966fe3723251784a797fa7": {
                    57: [
                        {
                            "tx_hash": "0x898b7a4b0b8de1d8e31a964b80d42783a610257d7281bb6ef767f5c7dafa4b66",
                            "value": Decimal("271.730895"),
                            "contract_address": None,
                            "block_height": 38310998,
                            "symbol": "AVAX"
                        }
                    ]
                },
                "0xaec0f27fbb316732aa5fb7f8c1568f14415b81cf": {
                    57: [
                        {
                            "tx_hash": "0x826db3269366aa56b377251d78babbd1753cbdecf9148756e111861076f7d2d3",
                            "value": Decimal("0.02350942649055"),
                            "contract_address": None,
                            "block_height": 38310999,
                            "symbol": "AVAX"
                        }
                    ]
                },
                "0x6991f63390dd73ac6630a896e4f958a7ab4f3259": {
                    57: [
                        {
                            "tx_hash": "0x114aa6d012a13bd8fede9cb6a9c715582612e365c9850d0ea23ecaf55f26b86a",
                            "value": Decimal("54.9958"),
                            "contract_address": None,
                            "block_height": 38310999,
                            "symbol": "AVAX"
                        }
                    ]
                },
                "0xdd21d72c1a7574361aede31a50a46985511d9c4f": {
                    57: [
                        {
                            "tx_hash": "0xe382b9a288a948064d1d8ad11a97b72e701179c541b745f300a223960ad56e54",
                            "value": Decimal("51.499475"),
                            "contract_address": None,
                            "block_height": 38311000,
                            "symbol": "AVAX"
                        }
                    ]
                },
                "0x2578d1f75a14b9266a329c0ef368ca53c3400aac": {
                    57: [
                        {
                            "tx_hash": "0x4bc57c67002382ae937ba316f6b54e157e9fe191c55e72b54dbfed7c20767241",
                            "value": Decimal("43.561968485362665"),
                            "contract_address": None,
                            "block_height": 38311000,
                            "symbol": "AVAX"
                        }
                    ]
                },
                "0x09b30faf8c5183a5d26af15a6ee11fce3b87bdbc": {
                    57: [
                        {
                            "tx_hash": "0xa53d3819d90f9a6b88047b740f3a8e6b745483f07bc7b0d76a97924275a658e7",
                            "value": Decimal("41.632476077155082533"),
                            "contract_address": None,
                            "block_height": 38311001,
                            "symbol": "AVAX"
                        }
                    ]
                },
                "0xe72838fe26fb77dcf97686262a165ed9a72eddf4": {
                    57: [
                        {
                            "tx_hash": "0x1bc3e30934aa7dbb84ddb88d33055c0c9d298f262bdee0ae4a28357813010202",
                            "value": Decimal("36.999475"),
                            "contract_address": None,
                            "block_height": 38311001,
                            "symbol": "AVAX"
                        }
                    ]
                },
                "0x8a383bde3ae9f5bb379ea94f3bdb406f434912e8": {
                    57: [
                        {
                            "tx_hash": "0x478442b22d038e2b1dbc8d86354a86595d65bcde99da4dad84c1fa2e6a01f3fc",
                            "value": Decimal("34.963797"),
                            "contract_address": None,
                            "block_height": 38311001,
                            "symbol": "AVAX"
                        }
                    ]
                },
            },
            "incoming_txs": {
                "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9": {
                    57: [
                        {
                            "tx_hash": "0x3aeab80123585cfa365e8636f46e1b59784ddf0f6191bf9a0b3d83ca63e7c468",
                            "value": Decimal("1435.03916682"),
                            "contract_address": None,
                            "block_height": 38310997,
                            "symbol": "AVAX"
                        },
                        {
                            "tx_hash": "0xc087e309420f373b22ec9256113878f3b6f19e6ced5630d3ae69e64752083cd7",
                            "value": Decimal("1371.39908278"),
                            "contract_address": None,
                            "block_height": 38310997,
                            "symbol": "AVAX"
                        },
                        {
                            "tx_hash": "0xbad3c41ea658ff58998ed1869187c8b94519fe8985080ed61950e1dbf427f55b",
                            "value": Decimal("1195.099475"),
                            "contract_address": None,
                            "block_height": 38310998,
                            "symbol": "AVAX"
                        },
                        {
                            "tx_hash": "0x6fe566ea17cdf89df68ed08f5ff86183f5317a103380b975299fc6ba7c280798",
                            "value": Decimal("594.94"),
                            "contract_address": None,
                            "block_height": 38310998,
                            "symbol": "AVAX"
                        },
                        {
                            "tx_hash": "0xd9c5cfead0a36e9bb558d211992183a8fbd1c290249eae61c2a59cc9e9467acf",
                            "value": Decimal("374.624475"),
                            "contract_address": None,
                            "block_height": 38310998,
                            "symbol": "AVAX"
                        },
                        {
                            "tx_hash": "0x898b7a4b0b8de1d8e31a964b80d42783a610257d7281bb6ef767f5c7dafa4b66",
                            "value": Decimal("271.730895"),
                            "contract_address": None,
                            "block_height": 38310998,
                            "symbol": "AVAX"
                        },
                        {
                            "tx_hash": "0x114aa6d012a13bd8fede9cb6a9c715582612e365c9850d0ea23ecaf55f26b86a",
                            "value": Decimal("54.9958"),
                            "contract_address": None,
                            "block_height": 38310999,
                            "symbol": "AVAX"
                        },
                        {
                            "tx_hash": "0xe382b9a288a948064d1d8ad11a97b72e701179c541b745f300a223960ad56e54",
                            "value": Decimal("51.499475"),
                            "contract_address": None,
                            "block_height": 38311000,
                            "symbol": "AVAX"
                        },
                        {
                            "tx_hash": "0x4bc57c67002382ae937ba316f6b54e157e9fe191c55e72b54dbfed7c20767241",
                            "value": Decimal("43.561968485362665"),
                            "contract_address": None,
                            "block_height": 38311000,
                            "symbol": "AVAX"
                        },
                        {
                            "tx_hash": "0xa53d3819d90f9a6b88047b740f3a8e6b745483f07bc7b0d76a97924275a658e7",
                            "value": Decimal("41.632476077155082533"),
                            "contract_address": None,
                            "block_height": 38311001,
                            "symbol": "AVAX"
                        },
                        {
                            "tx_hash": "0x1bc3e30934aa7dbb84ddb88d33055c0c9d298f262bdee0ae4a28357813010202",
                            "value": Decimal("36.999475"),
                            "contract_address": None,
                            "block_height": 38311001,
                            "symbol": "AVAX"
                        },
                        {
                            "tx_hash": "0x478442b22d038e2b1dbc8d86354a86595d65bcde99da4dad84c1fa2e6a01f3fc",
                            "value": Decimal("34.963797"),
                            "contract_address": None,
                            "block_height": 38311001,
                            "symbol": "AVAX"
                        },
                    ]
                },
                "0xd1c4c01a2bfff4df0f3ca070c1a038c66be7b9fb": {
                    57: [
                        {
                            "tx_hash": "0x13cbd8b504c5f738bd3b80ed6e746f4225bf9234466f8aa3717e389f16eec2c4",
                            "value": Decimal("0.06"),
                            "contract_address": None,
                            "block_height": 38310997,
                            "symbol": "AVAX"
                        }
                    ]
                },
                "0xd09381c3f7e986934904cc3866642cae15de7422": {
                    57: [
                        {
                            "tx_hash": "0x826db3269366aa56b377251d78babbd1753cbdecf9148756e111861076f7d2d3",
                            "value": Decimal("0.02350942649055"),
                            "contract_address": None,
                            "block_height": 38310999,
                            "symbol": "AVAX"
                        }
                    ]
                },
                "0x6b1a5b7d652521d694d301ec9a4b5271d18f5f79": {
                    57: [
                        {
                            "tx_hash": "0x8fcb6e115d75dfc21edfb3ca0769af354e80e040476e9b7a3e535e99165df8a6",
                            "value": Decimal("0.06"),
                            "contract_address": None,
                            "block_height": 38310999,
                            "symbol": "AVAX"
                        }
                    ]
                },
                "0xbb5b191223e154342927b92ddeed03cbfd0570cf": {
                    57: [
                        {
                            "tx_hash": "0x4e041d1b22f73ba23933f39ceca8191f5bfcf64d6993b24dab4d46bfd5fdd2b8",
                            "value": Decimal("0.06"),
                            "contract_address": None,
                            "block_height": 38311000,
                            "symbol": "AVAX"
                        }
                    ]
                },
            },
        }

        assert BlockchainUtilsMixin.compare_dicts_without_order(
            expected_txs_addresses, txs_addresses
        )
        assert BlockchainUtilsMixin.compare_dicts_without_order(
            expected_txs_info, txs_info
        )

    def test_get_address_txs(self):
        block_head_mock_responses = [
            {
                "code": "0",
                "msg": "",
                "data": [
                    {
                        "page": "1",
                        "limit": "1",
                        "totalPage": "10000",
                        "chainFullName": "Avalanche-C",
                        "chainShortName": "AVAXC",
                        "blockList": [
                            {
                                "hash": "0x3f7bcfd5f7f7413a255fddea6c7fbf04239dbc2f168addf1d8c78a07c149163f",
                                "height": "38312221",
                                "validator": "0x0100000000000000000000000000000000000000",
                                "blockTime": "1701096064000",
                                "txnCount": "2",
                                "blockSize": "941",
                                "mineReward": "0",
                                "totalFee": "0.0011386",
                                "feeSymbol": "AVAX",
                                "avgFee": "0.0006",
                                "ommerBlock": "",
                                "gasUsed": "43024",
                                "gasLimit": "15000000",
                                "gasAvgPrice": "0.000000026464298996",
                                "state": "",
                                "burnt": "0.0011386",
                                "netWork": "",
                            }
                        ],
                    }
                ],
            },
            {
                "code": "0",
                "msg": "",
                "data": [
                    {
                        "page": "1",
                        "limit": "1",
                        "totalPage": "10000",
                        "chainFullName": "Avalanche-C",
                        "chainShortName": "AVAXC",
                        "blockList": [
                            {
                                "hash": "0x6cba4968511d0562032780894aeff5d0584959c4cacefcf45ac3bd74ecbadfd4",
                                "height": "38312238",
                                "validator": "0x0100000000000000000000000000000000000000",
                                "blockTime": "1701096100000",
                                "txnCount": "3",
                                "blockSize": "1444",
                                "mineReward": "0",
                                "totalFee": "0.004368891",
                                "feeSymbol": "AVAX",
                                "avgFee": "0.0015",
                                "ommerBlock": "",
                                "gasUsed": "173034",
                                "gasLimit": "15000000",
                                "gasAvgPrice": "0.000000025248743022",
                                "state": "",
                                "burnt": "0.004368891",
                                "netWork": "",
                            }
                        ],
                    }
                ],
            },
        ]
        address_txs_mock_responses = [
            {
                "code": "0",
                "msg": "",
                "data": [
                    {
                        "page": "1",
                        "limit": "20",
                        "totalPage": "114",
                        "chainFullName": "Avalanche-C",
                        "chainShortName": "AVAXC",
                        "transactionLists": [
                            {
                                "txId": "0x02ee2ae962202680f91486d1509bc813a8a0cda2363a1ba52dc7b781cf1a13cd",
                                "methodId": "",
                                "blockHash": "0x68fbdfc11fd670797a080ec8bfe0cb2eb7f052d8d73588bd0a238cd2d6104bf1",
                                "height": "38298305",
                                "transactionTime": "1701068017000",
                                "from": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "to": "0xe5d98d739f5b248b45caa6bc645ecf7f24f2e610",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "4555.28773616",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.00063",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0x695ecddf13e42986514ce7c89bd2ac96855fcaa624b6da2be8a3d049d1b3463b",
                                "methodId": "",
                                "blockHash": "0x8d5f0418d50f878371fcb8252c318e72a7ef0cb671f34c7c606cff1593888be1",
                                "height": "38298171",
                                "transactionTime": "1701067748000",
                                "from": "0x4375c83f270df97e24a1055bc0306a3591d74626",
                                "to": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "2999.89998494",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.00063",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0xff11e7681128d6ef11b6998af1b7436ce67c4d4337a834ed516a959155afac23",
                                "methodId": "",
                                "blockHash": "0x8d5f0418d50f878371fcb8252c318e72a7ef0cb671f34c7c606cff1593888be1",
                                "height": "38298171",
                                "transactionTime": "1701067748000",
                                "from": "0x4375c83f270df97e24a1055bc0306a3591d74626",
                                "to": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "1555.38838122",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.00063",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0x30c1886d3b66ae9b6858130dc6c10b802e74963a041228ccf2ccd138cc22ac30",
                                "methodId": "",
                                "blockHash": "0x2649b5cb1de539f038c01dc64a300cb4739548c6e4ac9b19d89c65a0c0fda99a",
                                "height": "38177177",
                                "transactionTime": "1700822417000",
                                "from": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "to": "0xe5d98d739f5b248b45caa6bc645ecf7f24f2e610",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "2223.91209356",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.00063",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0x311a57d64de5d4822ad6ef70c1a8715993e0f4e07b98a8e3dbc54dd93f7887ff",
                                "methodId": "",
                                "blockHash": "0xe0ca81635c381cb9f120b24ffaefb2aa9f3c22a9588aa9bf4d2d2320201229c9",
                                "height": "38177023",
                                "transactionTime": "1700822109000",
                                "from": "0x4375c83f270df97e24a1055bc0306a3591d74626",
                                "to": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "2223.91272356",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.00063",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0xfacd377dc3c617b762621fbcc05c7307f27c102c99d745c88ad4b199d5948847",
                                "methodId": "",
                                "blockHash": "0x9548fd2312090214d9276aae24318e424b25860809f51709a9101c494172f61e",
                                "height": "38049739",
                                "transactionTime": "1700563021000",
                                "from": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "to": "0x0c200fdce2edbdcb838e66d589a3bddbb5c0b303",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "9429.109673422587",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.001669047412767",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0x4de23a3ba4c0a8d8d3648034beeac1aa1d43c792b10e1ecf454d3458b27a3351",
                                "methodId": "",
                                "blockHash": "0x05c76217b40b66998f7d59dad7ee73b88abb7c008ad955cb61cace513dc779c4",
                                "height": "38049545",
                                "transactionTime": "1700562622000",
                                "from": "0xa16f524a804beaed0d791de0aa0b5836295a2a84",
                                "to": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "5565.907",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.001652978243952",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0x6cf7528b7e87940f17449fdcd598cf46d2653ac599d137e00cb86febca8cec90",
                                "methodId": "",
                                "blockHash": "0x12608f8d8275d8b3f27b3eb07d634e7e4266da6ce68a48fffa207265daaec5c0",
                                "height": "38049517",
                                "transactionTime": "1700562564000",
                                "from": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                                "to": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "3863.20434247",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.001538404884828",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0xe2a4ab81a85f0bd48d9bf18ecef7948978b702babf676198bc2e018b1c5a2a55",
                                "methodId": "",
                                "blockHash": "0x4e4066b464d05207133f9c4d3c39f0ecab3c2a6a82c3b5f425280f816b2378d4",
                                "height": "38048122",
                                "transactionTime": "1700559727000",
                                "from": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "to": "0xd07ada35a47cf2cd93e7f59561d5f558c429ad7a",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "4651.105441696468",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.001417513532001",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0x6b14d12dc3aeb8aaa3d8e56b0c1f04bda08d7c8887d912cbf0478c2b42a03a57",
                                "methodId": "",
                                "blockHash": "0x82185705c0699653837d1a5412222f152ad3a3ef3a9fd3fef7219dfa2a76e701",
                                "height": "38048078",
                                "transactionTime": "1700559637000",
                                "from": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                                "to": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "4651.10685921",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.001363315833243",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0x3658369b7024aa3b91e52f8420ec20f93806f47e061f51ada88c83080d11c411",
                                "methodId": "",
                                "blockHash": "0x635a25d50adff6a6f1b01de3672a5f24c4cba668d74dbb7354215dcb7908c328",
                                "height": "38014680",
                                "transactionTime": "1700491910000",
                                "from": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "to": "0xefdc8fc1145ea88e3f5698ee7b7b432f083b4246",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "7886.565573276589",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.001473663410646",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0xaabbfd194f0542e6e660216c500fc9894607c8500a393af23de12ebd023057e2",
                                "methodId": "",
                                "blockHash": "0xd7a784261c2e3424f80ab11b5ae7a8c95c66d1e4184ea2a974bc1a7e454519bc",
                                "height": "38013867",
                                "transactionTime": "1700490256000",
                                "from": "0x4375c83f270df97e24a1055bc0306a3591d74626",
                                "to": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "305.38806975",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.00147",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0xf7743e4b8e44821d00baf5fd916dadad25d37c1fcda1086088425f988908a18b",
                                "methodId": "",
                                "blockHash": "0xa456860a4cce6b374d557443000979f2d7ea230efd7d0fae7eb309b807bfe67d",
                                "height": "38013865",
                                "transactionTime": "1700490252000",
                                "from": "0x4375c83f270df97e24a1055bc0306a3591d74626",
                                "to": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "2999.89997719",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.00147",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0xbe26660e630654db519f913e83e6fefd556d1ab4766a058a4530133b80479e7c",
                                "methodId": "",
                                "blockHash": "0x07bb9eef28dc02a64af2e33edad8f24ca9fb6df9c630753998b931683684e404",
                                "height": "38013799",
                                "transactionTime": "1700490116000",
                                "from": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "to": "0xd07ada35a47cf2cd93e7f59561d5f558c429ad7a",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "2586.4605353785673",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.001493131432653",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0xdc356ae384c7b9a27bb390d9fd2545b85feb62a567b07020e5ab5fcae251d1b3",
                                "methodId": "",
                                "blockHash": "0x27248f1be0a3690cea792a5620dbd3fd68862ad96c3a7f1e638b04b12f96d1df",
                                "height": "38013732",
                                "transactionTime": "1700489981000",
                                "from": "0xa16f524a804beaed0d791de0aa0b5836295a2a84",
                                "to": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "4581.279",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.001694243623611",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0x0957732c276095b975055ab9735cc51b695aa5e75208006f45c42a02ce19391f",
                                "methodId": "",
                                "blockHash": "0x20c25915eb84966c307b254fb335495a3db3df15c004546fc8ae18d0c7e59486",
                                "height": "38013700",
                                "transactionTime": "1700489916000",
                                "from": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                                "to": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "2586.46202851",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.001475462910222",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0xdf61fb8b13adc2b23a0fc9d5d2316602ebe2287b8d72ce6122d16778be459e19",
                                "methodId": "",
                                "blockHash": "0x0dc57e3db6021518035f22c1d1271af09b3c69c2de95248bfaf99c18ead121b5",
                                "height": "38007904",
                                "transactionTime": "1700478094000",
                                "from": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "to": "0x7e65bee9caa681c5e627d3ed34cf010bbb15069a",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "7555.999393915171",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.00090854482866",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0x25f4e69c7d96887bac1de383c1c66ed14df929aafdea25e73b218fc5935c4a34",
                                "methodId": "",
                                "blockHash": "0x8569bd43e959e6909235148c2e10d9f5265865129046220839e084854c6bf801",
                                "height": "38007752",
                                "transactionTime": "1700477791000",
                                "from": "0xa16f524a804beaed0d791de0aa0b5836295a2a84",
                                "to": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "4980.032",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.000989036633613",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0x0a9ca7e30ce5618631f37d78a306c5fc7df1fee6a2b21ce1b3bc6ef4be741806",
                                "methodId": "",
                                "blockHash": "0x3f1647089b835743b706836d2b0d5a3b2a5e155493283d1d9b7478fccd83c221",
                                "height": "38007728",
                                "transactionTime": "1700477743000",
                                "from": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                                "to": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "2575.96830246",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.000901564170465",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0xe8298b5028ed5ab23b40c6e2acb5de5bd8c4a8ebb07d3b81b7e14c6a1df6020f",
                                "methodId": "",
                                "blockHash": "0x946e4e8927ee8df7444a1b9996b746e25adb8e847fd0d9acb3329b89d588e14f",
                                "height": "38006573",
                                "transactionTime": "1700475393000",
                                "from": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                                "to": "0x63127b9bc5ff1124ec3b6e34003e49bf4d0bcc39",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "4732.43150330949",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.001139160509865",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                        ],
                    }
                ],
            },
            {
                "code": "0",
                "msg": "",
                "data": [
                    {
                        "page": "1",
                        "limit": "20",
                        "totalPage": "1",
                        "chainFullName": "Avalanche-C",
                        "chainShortName": "AVAXC",
                        "transactionLists": [
                            {
                                "txId": "0xb269b46a1f90a50b441b122491f51712757b5a8da2578adda801db9380bc072e",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0x67d038b4ad4ae4e97c6043e1e3035d7c1f4702404a70346f75fb74ce825262d0",
                                "height": "38298315",
                                "transactionTime": "1701068037000",
                                "from": "0xbf72c5ecdd12903aa55121cb989a6d948f001df6",
                                "to": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                                "isFromContract": False,
                                "isToContract": True,
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.001189026",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0x4b26c4742b85e9583bbffd5b3dd36267111a3833c0d0581d8fd60a29d668fdbb",
                                "methodId": "",
                                "blockHash": "0xac3a901e08eaae9897e9b70630c559a6e735fb820bcce86e7ca65728561eed5e",
                                "height": "38298285",
                                "transactionTime": "1701067977000",
                                "from": "0xb02f1329d6a6acef07a763258f8509c2847a0a3e",
                                "to": "0xbf72c5ecdd12903aa55121cb989a6d948f001df6",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "0.00118529187408",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.000567",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0x9339286623b05345f9d2c2963988f8aa264db8cd3158c632f755322a31e4506a",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0x79ca7cb3d026b0fbcf38718536b2ede81a2fd3514ba330fcdd990f8366875386",
                                "height": "38001426",
                                "transactionTime": "1700464918000",
                                "from": "0xbf72c5ecdd12903aa55121cb989a6d948f001df6",
                                "to": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                                "isFromContract": False,
                                "isToContract": True,
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.001189026",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0x43ce32e222c68a364a97571af3e81f555cfdedca69403aabd408a1382d65d290",
                                "methodId": "",
                                "blockHash": "0x99324e3f0f67aad23c6f3e172445775a0fb59eca46d63f16ee3cce0e6c9450e3",
                                "height": "38001397",
                                "transactionTime": "1700464859000",
                                "from": "0xb02f1329d6a6acef07a763258f8509c2847a0a3e",
                                "to": "0xbf72c5ecdd12903aa55121cb989a6d948f001df6",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "0.00119308412592",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.000570145870854",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0x9e15d29c412084a76b5c83d21f39b71ce5981582514c44b877d1fdfbae4f9e7d",
                                "methodId": "0xa9059cbb",
                                "blockHash": "0xfbbc20d2dbf78f0ccf6f211e73ee7304e988791dfe7272b5d66037e5819516df",
                                "height": "37810544",
                                "transactionTime": "1700081171000",
                                "from": "0xbf72c5ecdd12903aa55121cb989a6d948f001df6",
                                "to": "0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7",
                                "isFromContract": False,
                                "isToContract": True,
                                "amount": "0",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.00118935",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                            {
                                "txId": "0xe7d97cecc34ed39fc7bf89a0527c033e8be831cbd12ecf6efd6b08df09a40335",
                                "methodId": "",
                                "blockHash": "0xa362b4d02edcf65c303642f984389513f4b61879249bbe39fabcb25a6a5b9863",
                                "height": "37810512",
                                "transactionTime": "1700081109000",
                                "from": "0xb02f1329d6a6acef07a763258f8509c2847a0a3e",
                                "to": "0xbf72c5ecdd12903aa55121cb989a6d948f001df6",
                                "isFromContract": False,
                                "isToContract": False,
                                "amount": "0.00416",
                                "transactionSymbol": "AVAX",
                                "txFee": "0.000567",
                                "state": "success",
                                "tokenId": "",
                                "tokenContractAddress": "",
                                "challengeStatus": "",
                                "l1OriginHash": "",
                            },
                        ],
                    }
                ],
            },
        ]

        API.get_block_head = Mock(side_effect=block_head_mock_responses)
        API.get_address_txs = Mock(side_effect=address_txs_mock_responses)

        AvalancheExplorerInterface.address_txs_apis[0] = API
        expected_addresses_txs = [
            [
                {
                    57: {
                        "amount": Decimal("4555.28773616"),
                        "from_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "to_address": "0xe5d98d739f5b248b45caa6bc645ecf7f24f2e610",
                        "hash": "0x02ee2ae962202680f91486d1509bc813a8a0cda2363a1ba52dc7b781cf1a13cd",
                        "block": 38298305,
                        "date": datetime.datetime(2023, 11, 27, 6, 53, 37, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 13916,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "outgoing",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("2999.89998494"),
                        "from_address": "0x4375c83f270df97e24a1055bc0306a3591d74626",
                        "to_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "hash": "0x695ecddf13e42986514ce7c89bd2ac96855fcaa624b6da2be8a3d049d1b3463b",
                        "block": 38298171,
                        "date": datetime.datetime(2023, 11, 27, 6, 49, 8, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 14050,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "incoming",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("1555.38838122"),
                        "from_address": "0x4375c83f270df97e24a1055bc0306a3591d74626",
                        "to_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "hash": "0xff11e7681128d6ef11b6998af1b7436ce67c4d4337a834ed516a959155afac23",
                        "block": 38298171,
                        "date": datetime.datetime(2023, 11, 27, 6, 49, 8, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 14050,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "incoming",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("2223.91209356"),
                        "from_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "to_address": "0xe5d98d739f5b248b45caa6bc645ecf7f24f2e610",
                        "hash": "0x30c1886d3b66ae9b6858130dc6c10b802e74963a041228ccf2ccd138cc22ac30",
                        "block": 38177177,
                        "date": datetime.datetime(2023, 11, 24, 10, 40, 17, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 135044,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "outgoing",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("2223.91272356"),
                        "from_address": "0x4375c83f270df97e24a1055bc0306a3591d74626",
                        "to_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "hash": "0x311a57d64de5d4822ad6ef70c1a8715993e0f4e07b98a8e3dbc54dd93f7887ff",
                        "block": 38177023,
                        "date": datetime.datetime(2023, 11, 24, 10, 35, 9, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 135198,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "incoming",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("9429.109673422587"),
                        "from_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "to_address": "0x0c200fdce2edbdcb838e66d589a3bddbb5c0b303",
                        "hash": "0xfacd377dc3c617b762621fbcc05c7307f27c102c99d745c88ad4b199d5948847",
                        "block": 38049739,
                        "date": datetime.datetime(2023, 11, 21, 10, 37, 1, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 262482,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "outgoing",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("5565.907"),
                        "from_address": "0xa16f524a804beaed0d791de0aa0b5836295a2a84",
                        "to_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "hash": "0x4de23a3ba4c0a8d8d3648034beeac1aa1d43c792b10e1ecf454d3458b27a3351",
                        "block": 38049545,
                        "date": datetime.datetime(2023, 11, 21, 10, 30, 22, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 262676,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "incoming",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("3863.20434247"),
                        "from_address": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                        "to_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "hash": "0x6cf7528b7e87940f17449fdcd598cf46d2653ac599d137e00cb86febca8cec90",
                        "block": 38049517,
                        "date": datetime.datetime(2023, 11, 21, 10, 29, 24, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 262704,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "incoming",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("4651.105441696468"),
                        "from_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "to_address": "0xd07ada35a47cf2cd93e7f59561d5f558c429ad7a",
                        "hash": "0xe2a4ab81a85f0bd48d9bf18ecef7948978b702babf676198bc2e018b1c5a2a55",
                        "block": 38048122,
                        "date": datetime.datetime(2023, 11, 21, 9, 42, 7, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 264099,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "outgoing",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("4651.10685921"),
                        "from_address": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                        "to_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "hash": "0x6b14d12dc3aeb8aaa3d8e56b0c1f04bda08d7c8887d912cbf0478c2b42a03a57",
                        "block": 38048078,
                        "date": datetime.datetime(2023, 11, 21, 9, 40, 37, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 264143,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "incoming",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("7886.565573276589"),
                        "from_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "to_address": "0xefdc8fc1145ea88e3f5698ee7b7b432f083b4246",
                        "hash": "0x3658369b7024aa3b91e52f8420ec20f93806f47e061f51ada88c83080d11c411",
                        "block": 38014680,
                        "date": datetime.datetime(2023, 11, 20, 14, 51, 50, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 297541,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "outgoing",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("305.38806975"),
                        "from_address": "0x4375c83f270df97e24a1055bc0306a3591d74626",
                        "to_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "hash": "0xaabbfd194f0542e6e660216c500fc9894607c8500a393af23de12ebd023057e2",
                        "block": 38013867,
                        "date": datetime.datetime(2023, 11, 20, 14, 24, 16, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 298354,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "incoming",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("2999.89997719"),
                        "from_address": "0x4375c83f270df97e24a1055bc0306a3591d74626",
                        "to_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "hash": "0xf7743e4b8e44821d00baf5fd916dadad25d37c1fcda1086088425f988908a18b",
                        "block": 38013865,
                        "date": datetime.datetime(2023, 11, 20, 14, 24, 12, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 298356,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "incoming",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("2586.4605353785673"),
                        "from_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "to_address": "0xd07ada35a47cf2cd93e7f59561d5f558c429ad7a",
                        "hash": "0xbe26660e630654db519f913e83e6fefd556d1ab4766a058a4530133b80479e7c",
                        "block": 38013799,
                        "date": datetime.datetime(2023, 11, 20, 14, 21, 56, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 298422,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "outgoing",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("4581.279"),
                        "from_address": "0xa16f524a804beaed0d791de0aa0b5836295a2a84",
                        "to_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "hash": "0xdc356ae384c7b9a27bb390d9fd2545b85feb62a567b07020e5ab5fcae251d1b3",
                        "block": 38013732,
                        "date": datetime.datetime(2023, 11, 20, 14, 19, 41, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 298489,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "incoming",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("2586.46202851"),
                        "from_address": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                        "to_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "hash": "0x0957732c276095b975055ab9735cc51b695aa5e75208006f45c42a02ce19391f",
                        "block": 38013700,
                        "date": datetime.datetime(2023, 11, 20, 14, 18, 36, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 298521,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "incoming",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("7555.999393915171"),
                        "from_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "to_address": "0x7e65bee9caa681c5e627d3ed34cf010bbb15069a",
                        "hash": "0xdf61fb8b13adc2b23a0fc9d5d2316602ebe2287b8d72ce6122d16778be459e19",
                        "block": 38007904,
                        "date": datetime.datetime(2023, 11, 20, 11, 1, 34, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 304317,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "outgoing",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("4980.032"),
                        "from_address": "0xa16f524a804beaed0d791de0aa0b5836295a2a84",
                        "to_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "hash": "0x25f4e69c7d96887bac1de383c1c66ed14df929aafdea25e73b218fc5935c4a34",
                        "block": 38007752,
                        "date": datetime.datetime(2023, 11, 20, 10, 56, 31, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 304469,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "incoming",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("2575.96830246"),
                        "from_address": "0x9f8c163cba728e99993abe7495f06c0a3c8ac8b9",
                        "to_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "hash": "0x0a9ca7e30ce5618631f37d78a306c5fc7df1fee6a2b21ce1b3bc6ef4be741806",
                        "block": 38007728,
                        "date": datetime.datetime(2023, 11, 20, 10, 55, 43, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 304493,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "incoming",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("4732.43150330949"),
                        "from_address": "0xa1f9c05b46ac95d0113b29a16d6d39626e3805ec",
                        "to_address": "0x63127b9bc5ff1124ec3b6e34003e49bf4d0bcc39",
                        "hash": "0xe8298b5028ed5ab23b40c6e2acb5de5bd8c4a8ebb07d3b81b7e14c6a1df6020f",
                        "block": 38006573,
                        "date": datetime.datetime(2023, 11, 20, 10, 16, 33, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 305648,
                        "address": "0xa1f9C05B46Ac95d0113b29a16D6D39626E3805eC",
                        "direction": "outgoing",
                        "raw": None,
                    }
                },
            ],
            [
                {
                    57: {
                        "amount": Decimal("0.00118529187408"),
                        "from_address": "0xb02f1329d6a6acef07a763258f8509c2847a0a3e",
                        "to_address": "0xbf72c5ecdd12903aa55121cb989a6d948f001df6",
                        "hash": "0x4b26c4742b85e9583bbffd5b3dd36267111a3833c0d0581d8fd60a29d668fdbb",
                        "block": 38298285,
                        "date": datetime.datetime(2023, 11, 27, 6, 52, 57, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 13953,
                        "address": "0xbF72c5ECDd12903aa55121CB989A6D948F001Df6",
                        "direction": "incoming",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("0.00119308412592"),
                        "from_address": "0xb02f1329d6a6acef07a763258f8509c2847a0a3e",
                        "to_address": "0xbf72c5ecdd12903aa55121cb989a6d948f001df6",
                        "hash": "0x43ce32e222c68a364a97571af3e81f555cfdedca69403aabd408a1382d65d290",
                        "block": 38001397,
                        "date": datetime.datetime(2023, 11, 20, 7, 20, 59, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 310841,
                        "address": "0xbF72c5ECDd12903aa55121CB989A6D948F001Df6",
                        "direction": "incoming",
                        "raw": None,
                    }
                },
                {
                    57: {
                        "amount": Decimal("0.00416"),
                        "from_address": "0xb02f1329d6a6acef07a763258f8509c2847a0a3e",
                        "to_address": "0xbf72c5ecdd12903aa55121cb989a6d948f001df6",
                        "hash": "0xe7d97cecc34ed39fc7bf89a0527c033e8be831cbd12ecf6efd6b08df09a40335",
                        "block": 37810512,
                        "date": datetime.datetime(2023, 11, 15, 20, 45, 9, tzinfo=UTC),
                        "memo": None,
                        "confirmations": 501726,
                        "address": "0xbF72c5ECDd12903aa55121CB989A6D948F001Df6",
                        "direction": "incoming",
                        "raw": None,
                    }
                },
            ],
        ]
        for address, expected_address_txs in zip(ADDRESSES, expected_addresses_txs):
            address_txs = AvalancheExplorerInterface.get_api().get_txs(address)
            assert len(expected_address_txs) == len(address_txs)
            for expected_address_tx, address_tx in zip(
                    expected_address_txs, address_txs
            ):
                expected_address_tx, address_tx = expected_address_tx.get(
                    Currencies.avax
                ), address_tx.get(Currencies.avax)
                assert address_tx == expected_address_tx

    def test_get_token_txs(self):
        fake_contract_info = {
            'address': '0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7',
            'decimals': 6,
            'symbol': 'USDT',
        }
        block_head_mock_responses = [
            {'code': '0', 'msg': '', 'data': [
                {'page': '1', 'limit': '1', 'totalPage': '10000', 'chainFullName': 'Avalanche-C',
                 'chainShortName': 'AVAXC', 'blockList': [
                    {'hash': '0x3f7bcfd5f7f7413a255fddea6c7fbf04239dbc2f168addf1d8c78a07c149163f', 'height': '38312221',
                     'validator': '0x0100000000000000000000000000000000000000', 'blockTime': '1701096064000',
                     'txnCount': '2', 'blockSize': '941', 'mineReward': '0', 'totalFee': '0.0011386',
                     'feeSymbol': 'AVAX', 'avgFee': '0.0006', 'ommerBlock': '', 'gasUsed': '43024',
                     'gasLimit': '15000000', 'gasAvgPrice': '0.000000026464298996', 'state': '', 'burnt': '0.0011386',
                     'netWork': ''}]}]},
            {
                "code": "0",
                "msg": "",
                "data": [
                    {
                        "page": "1",
                        "limit": "1",
                        "totalPage": "10000",
                        "chainFullName": "Avalanche-C",
                        "chainShortName": "AVAXC",
                        "blockList": [
                            {
                                "hash": "0x6cba4968511d0562032780894aeff5d0584959c4cacefcf45ac3bd74ecbadfd4",
                                "height": "38312238",
                                "validator": "0x0100000000000000000000000000000000000000",
                                "blockTime": "1701096100000",
                                "txnCount": "3",
                                "blockSize": "1444",
                                "mineReward": "0",
                                "totalFee": "0.004368891",
                                "feeSymbol": "AVAX",
                                "avgFee": "0.0015",
                                "ommerBlock": "",
                                "gasUsed": "173034",
                                "gasLimit": "15000000",
                                "gasAvgPrice": "0.000000025248743022",
                                "state": "",
                                "burnt": "0.004368891",
                                "netWork": "",
                            }
                        ],
                    }
                ],
            },
        ]
        token_txs_mock_responses = [
            {'code': '0', 'msg': '', 'data': [
                {'page': '1', 'limit': '20', 'totalPage': '500', 'chainFullName': 'Avalanche-C',
                 'chainShortName': 'AVAXC', 'transactionLists': [
                    {'txId': '0x273d1de4fbd3dbb5bfc2a2082ee5d7fd9e2c0c1db0b0f8474cc9fcd9053e2a7b', 'methodId': '',
                     'blockHash': '0xb6f2437de23810d1f0172c76bf92334301462f1f2de037b6d4ba862524322af8',
                     'height': '38695926', 'transactionTime': '1701873091000',
                     'from': '0xd4052b5ba23c13800685a2a472cbd00239366124',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '1041.8869', 'transactionSymbol': 'USDC', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x5b601de07f9833243337ba99f2420ebf43ed2492c98369f91147e3bdf389c060', 'methodId': '',
                     'blockHash': '0xb6f2437de23810d1f0172c76bf92334301462f1f2de037b6d4ba862524322af8',
                     'height': '38695926', 'transactionTime': '1701873091000',
                     'from': '0x1d746beb1536821ea99c6b972d7ca926a79b1077',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '600', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x1b263c6706d1828edc1882880d7bc17faa07bee59d366a250ac4c8ba4264c1b5', 'methodId': '',
                     'blockHash': '0xb6f2437de23810d1f0172c76bf92334301462f1f2de037b6d4ba862524322af8',
                     'height': '38695926', 'transactionTime': '1701873091000',
                     'from': '0x2d03af06d0ed69d0f8b2e22a50236f6c9f870975',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '4037.87', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x289f8c947bfe4e643e7aee5452e5cdaa421cf1283a82c7a8dd160e223940c47e', 'methodId': '',
                     'blockHash': '0xb6f2437de23810d1f0172c76bf92334301462f1f2de037b6d4ba862524322af8',
                     'height': '38695926', 'transactionTime': '1701873091000',
                     'from': '0x25566afa9fd804189aee39bef303c8923063ca71',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '4', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x1d3cab4a8dbac60df0a36b2d0332b3db12a9ab510f836bcc2518dfedacb566db', 'methodId': '',
                     'blockHash': '0xb6f2437de23810d1f0172c76bf92334301462f1f2de037b6d4ba862524322af8',
                     'height': '38695926', 'transactionTime': '1701873091000',
                     'from': '0x22a4f29f93718dd3bbec72c04547256d18d3aa46',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '541.9', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x645b6cb003290607843e7ca7ee7de4fd7bcf77f591c9726fc3b1559aaf77bd7c', 'methodId': '',
                     'blockHash': '0xb6f2437de23810d1f0172c76bf92334301462f1f2de037b6d4ba862524322af8',
                     'height': '38695926', 'transactionTime': '1701873091000',
                     'from': '0x746d78739f9504283ee4f4d792b443f03c0f8b3d',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '9334.340737', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success',
                     'tokenId': '', 'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7',
                     'challengeStatus': '', 'l1OriginHash': ''},
                    {'txId': '0x480ba151d20905cb7f9f0a1045f79ae3845599737002b74630fed2b4345f74f2', 'methodId': '',
                     'blockHash': '0x0d13ae6357260a8a30c76501e1eb18b410974412af6b5a4d2ba94cc54378dd69',
                     'height': '38695726', 'transactionTime': '1701872692000',
                     'from': '0x7e4aa755550152a522d9578621ea22edab204308',
                     'to': '0xdafa0afd79e547ddf2bb78f92d197d46790babe1', 'isFromContract': False, 'isToContract': False,
                     'amount': '39.097162', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0xc993bd57b6023b23ebd9d8fb0c0a6ac6457e55639bcf94691cf39b38058b2a47', 'methodId': '',
                     'blockHash': '0x4794ee791693dc9b7ec23eba3594196f9d8a9662857efbdafc16f68d1f3bff11',
                     'height': '38695629', 'transactionTime': '1701872495000',
                     'from': '0x21ada9709945744449e56fe611925eab5963fa2f',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '1700.055112', 'transactionSymbol': 'USDC', 'txFee': '', 'state': 'success',
                     'tokenId': '', 'tokenContractAddress': '0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e',
                     'challengeStatus': '', 'l1OriginHash': ''},
                    {'txId': '0x772a1c4f58796fbc7d1abed171067e9a84e5091a02cec1a470334eaf6541b4d2', 'methodId': '',
                     'blockHash': '0x4794ee791693dc9b7ec23eba3594196f9d8a9662857efbdafc16f68d1f3bff11',
                     'height': '38695629', 'transactionTime': '1701872495000',
                     'from': '0x786fe231e5a066f6625397ee78dc9b2902e4796b',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '1500', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x47ab1ba1e60344732f21a96e61c31cb543d4fce71d618971686e54026c6274cb', 'methodId': '',
                     'blockHash': '0x4794ee791693dc9b7ec23eba3594196f9d8a9662857efbdafc16f68d1f3bff11',
                     'height': '38695629', 'transactionTime': '1701872495000',
                     'from': '0x5eafdcf4912e81c482355d6313594196621ad80d',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '107.947771', 'transactionSymbol': 'USDC', 'txFee': '', 'state': 'success',
                     'tokenId': '', 'tokenContractAddress': '0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e',
                     'challengeStatus': '', 'l1OriginHash': ''},
                    {'txId': '0x58f28adc1c6249fade7a92ee8fb219d56414fb850613ec71cbf3504653cd72d8', 'methodId': '',
                     'blockHash': '0xe15be7d37a4b8a465c438a46a9e4ad91aa29873b52540322bea980a454938c2e',
                     'height': '38695628', 'transactionTime': '1701872491000',
                     'from': '0x579c3513f43a21a947659a92011e76de1fea2557',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '4125', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0xadf068274a40f27e0a585832b4fbca190f7b6bc2f09e3db01567bef3a6c56caa', 'methodId': '',
                     'blockHash': '0xe15be7d37a4b8a465c438a46a9e4ad91aa29873b52540322bea980a454938c2e',
                     'height': '38695628', 'transactionTime': '1701872491000',
                     'from': '0x1cc240ebb690b9283bb59b5deadd8f24cdcfccba',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '10770.43386', 'transactionSymbol': 'USDC', 'txFee': '', 'state': 'success',
                     'tokenId': '', 'tokenContractAddress': '0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e',
                     'challengeStatus': '', 'l1OriginHash': ''},
                    {'txId': '0x1622c950c30b588a22773946c51fa5266ff1231f14d279c34d626139f4307541', 'methodId': '',
                     'blockHash': '0xe15be7d37a4b8a465c438a46a9e4ad91aa29873b52540322bea980a454938c2e',
                     'height': '38695628', 'transactionTime': '1701872491000',
                     'from': '0x7fa962ba9c23153ad9c60403d17c3fba033a38d2',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '1972.162849', 'transactionSymbol': 'USDC', 'txFee': '', 'state': 'success',
                     'tokenId': '', 'tokenContractAddress': '0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e',
                     'challengeStatus': '', 'l1OriginHash': ''},
                    {'txId': '0xa4eadde12b645457f9d1a04f04c1ddb8997595769ff9cdf5f17366e395e3503b', 'methodId': '',
                     'blockHash': '0xe15be7d37a4b8a465c438a46a9e4ad91aa29873b52540322bea980a454938c2e',
                     'height': '38695628', 'transactionTime': '1701872491000',
                     'from': '0xc369cd8fe7263a108b75997ef2b342d205331488',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '96.953274', 'transactionSymbol': 'USDC', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x9d481e74f67de2936b08b9627222e079590f9304d25dea5cb97a568ef0c2da46', 'methodId': '',
                     'blockHash': '0xe15be7d37a4b8a465c438a46a9e4ad91aa29873b52540322bea980a454938c2e',
                     'height': '38695628', 'transactionTime': '1701872491000',
                     'from': '0x1baf35f6fb0e89e67780a504ca876403cca233b7',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '247.197413', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success',
                     'tokenId': '', 'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7',
                     'challengeStatus': '', 'l1OriginHash': ''},
                    {'txId': '0x935c0c235e79633a06f86f9732fa9edf9c3262ebbfed6c6783bb0cec4fb49fd7', 'methodId': '',
                     'blockHash': '0xe15be7d37a4b8a465c438a46a9e4ad91aa29873b52540322bea980a454938c2e',
                     'height': '38695628', 'transactionTime': '1701872491000',
                     'from': '0xb9bad2a109d0c4ec2cfb0ea1f42f13ea366bb2ea',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '1000', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x1115a5f9d8c6deef7aa7baeade914bc13be9e2ad3670daeb389492f4775bad5c', 'methodId': '',
                     'blockHash': '0xe15be7d37a4b8a465c438a46a9e4ad91aa29873b52540322bea980a454938c2e',
                     'height': '38695628', 'transactionTime': '1701872491000',
                     'from': '0x1f2c31848468b31ada405bc8699b11d35504f074',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '514.5', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x319f58ce4546ff0fc89f296c8f90bc494d37409dcc69ea02ae1753537a31d95e', 'methodId': '',
                     'blockHash': '0xe15be7d37a4b8a465c438a46a9e4ad91aa29873b52540322bea980a454938c2e',
                     'height': '38695628', 'transactionTime': '1701872491000',
                     'from': '0x5813faf1d92f0cae3d83d750872c48403200b905',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '506.01447', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x999590b310e04569901374db2ca12e8bbb801e7368ea0099008699df21738e39', 'methodId': '',
                     'blockHash': '0xe15be7d37a4b8a465c438a46a9e4ad91aa29873b52540322bea980a454938c2e',
                     'height': '38695628', 'transactionTime': '1701872491000',
                     'from': '0x1e8a5f8cf884c204d330ef4e347d7308a3995357',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '98.480876', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0xee20abd14caf6af709a75c8304277a2b04603f0ddb3ca0608e92d63bca42eab3', 'methodId': '',
                     'blockHash': '0xe15be7d37a4b8a465c438a46a9e4ad91aa29873b52540322bea980a454938c2e',
                     'height': '38695628', 'transactionTime': '1701872491000',
                     'from': '0x60f406b595ffe533b49d3a280f17d9016c2dd243',
                     'to': '0x7e4aa755550152a522d9578621ea22edab204308', 'isFromContract': False, 'isToContract': False,
                     'amount': '9527.964611', 'transactionSymbol': 'USDC', 'txFee': '', 'state': 'success',
                     'tokenId': '', 'tokenContractAddress': '0xb97ef9ef8734c71904d8002f8b6bc66dd9c48a6e',
                     'challengeStatus': '', 'l1OriginHash': ''}]}]},
            {'code': '0', 'msg': '', 'data': [
                {'page': '1', 'limit': '20', 'totalPage': '500', 'chainFullName': 'Avalanche-C',
                 'chainShortName': 'AVAXC', 'transactionLists': [
                    {'txId': '0x8c4c3d9788cd470c700842790fb7f3a0f75a867000860907a8491118a67022cf', 'methodId': '',
                     'blockHash': '0x3f152066ac19223a6f6cb270962824562660b57cb0eda1876db7aa2f8dcb6226',
                     'height': '38696898', 'transactionTime': '1701875001000',
                     'from': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                     'to': '0x2103bcc8da98aa2e98e8d8a35edba777e2eb8a82', 'isFromContract': False, 'isToContract': False,
                     'amount': '49.79', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x13edce4cf07a5fea9b46a7f6efa1f725f7535906993c39fccd0815b456224569', 'methodId': '',
                     'blockHash': '0x7a2b96029ead75c529318a4ebf486fed85c932eb19b549a8f4d7619154d5c5f4',
                     'height': '38696868', 'transactionTime': '1701874942000',
                     'from': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                     'to': '0x3aeae25dbd294bbb53ac4423ce482297ba736ff8', 'isFromContract': False, 'isToContract': False,
                     'amount': '20160.58', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x55672f949f2039c33ecc876ff266e59ecac48afef15a1252aae11a639742cafd', 'methodId': '',
                     'blockHash': '0x541da75605bdce2e7b8ff61bca2a159150fdb83d5c79498272e5ec16b119379c',
                     'height': '38696840', 'transactionTime': '1701874889000',
                     'from': '0x07ea2f06c25848b105193a3af537d432f32b1d6f',
                     'to': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b', 'isFromContract': False, 'isToContract': False,
                     'amount': '484.179085', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success',
                     'tokenId': '', 'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7',
                     'challengeStatus': '', 'l1OriginHash': ''},
                    {'txId': '0x54cba8f558eef039a2b95b47d28ec02a04f35ce3bf6b6d0aba19274817b48215', 'methodId': '',
                     'blockHash': '0x2b85d6997b890ca2c5a9ecb57fedbaa6b11d6351e2cb4995b4b16ce99f889c75',
                     'height': '38696836', 'transactionTime': '1701874881000',
                     'from': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                     'to': '0x61b310a55ce19a7721a1f0b1558b6ef7cd810eee', 'isFromContract': False, 'isToContract': False,
                     'amount': '36.03', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0xd551dd5aa438a8a95d8bdfc0581f7fa16f06affe9a6051e499dc9333dcff146d', 'methodId': '',
                     'blockHash': '0x9d8adfe3e825b5f878e146e8b47d213431b9079449dabed751892df5a39b69cf',
                     'height': '38696810', 'transactionTime': '1701874829000',
                     'from': '0x48dd7aa4a378bc7d7b15a0869511915b1df5fab9',
                     'to': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b', 'isFromContract': False, 'isToContract': False,
                     'amount': '128.400371', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success',
                     'tokenId': '', 'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7',
                     'challengeStatus': '', 'l1OriginHash': ''},
                    {'txId': '0x705b22f2197c99974209528b00fc2f2ebc016ebe0099670be5009a2358a63ce1', 'methodId': '',
                     'blockHash': '0x347555f2b8b125ba018a2a06788d8ade654de4cf39ad29158f11defee43e4f02',
                     'height': '38696805', 'transactionTime': '1701874819000',
                     'from': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                     'to': '0x117b1dec8f10b91d79794f68aac9063ad8d3fbd1', 'isFromContract': False, 'isToContract': False,
                     'amount': '27142.71', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x3c6f298540ef7440265f5099bdda65982b7398974cb6bbc50dafbcd48dab5f06', 'methodId': '',
                     'blockHash': '0x292f227d52e5b5eb0ab7d0328867cc67764fbe94fad1fea245e0b1653b3cefae',
                     'height': '38696775', 'transactionTime': '1701874759000',
                     'from': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                     'to': '0x6d40b4e734079a299c64ba01fbdca6dc0fbaaea2', 'isFromContract': False, 'isToContract': False,
                     'amount': '22.75', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x0f37631e53c7e555375abfce1691c91d8da9137be1a1a7705c98c444c3c5bf4b', 'methodId': '',
                     'blockHash': '0x292f227d52e5b5eb0ab7d0328867cc67764fbe94fad1fea245e0b1653b3cefae',
                     'height': '38696775', 'transactionTime': '1701874759000',
                     'from': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                     'to': '0x5f2469fc523b1704d28805f7414ba7067e6639de', 'isFromContract': False, 'isToContract': False,
                     'amount': '342.69', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0xe1067257803a2db117470d9092e8cd1f2ad69fdc63cc1e2627e8d3d86db6f5b1', 'methodId': '',
                     'blockHash': '0x292f227d52e5b5eb0ab7d0328867cc67764fbe94fad1fea245e0b1653b3cefae',
                     'height': '38696775', 'transactionTime': '1701874759000',
                     'from': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                     'to': '0xf1887456bf823ab0843dc23f99402664b091960f', 'isFromContract': False, 'isToContract': False,
                     'amount': '57.64', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0xd18deb2fc5cf892b4edb005d7639dc5adf896de4d9c4bbb5a9e2f7d4ad7b6416', 'methodId': '',
                     'blockHash': '0x2648faec822113bb7f7c6d11c9c8dd3d5ca7fc295cf552ff0aa88a9328c7cec0',
                     'height': '38696715', 'transactionTime': '1701874639000',
                     'from': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                     'to': '0x4029cf9753f3dcc0f7c90e8ec47901a019925c2e', 'isFromContract': False, 'isToContract': False,
                     'amount': '2999.5', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x7e90f5388bd0bad36c00e3c0edbec52193d270d1452196359a8b64b0df9471b8', 'methodId': '',
                     'blockHash': '0x2648faec822113bb7f7c6d11c9c8dd3d5ca7fc295cf552ff0aa88a9328c7cec0',
                     'height': '38696715', 'transactionTime': '1701874639000',
                     'from': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                     'to': '0x29153fb8f8a2583fcc8692756160673d322d2712', 'isFromContract': False, 'isToContract': False,
                     'amount': '20', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0xe7e749e3252aefa492d80c27294dad585bbb99bee8f242ae1e2efc88930e0cb0', 'methodId': '',
                     'blockHash': '0x6fe079f3e61129bae59b98c29fd8aa150fb16ff87917fd082b04cb9293fd52a4',
                     'height': '38696660', 'transactionTime': '1701874529000',
                     'from': '0xc6c006d497ca08cdcded19b921e07501c9997a78',
                     'to': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b', 'isFromContract': False, 'isToContract': False,
                     'amount': '100', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x616bcb73ec14c9b0c43bc4a152b8baf8f62dabd245de5b91f27bce82035e68eb', 'methodId': '',
                     'blockHash': '0xf61440ea2deab5ba8dfa37b68758e076ddc28a47b7868484d567a3e2beacb7d5',
                     'height': '38696625', 'transactionTime': '1701874460000',
                     'from': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                     'to': '0x979d3bb218a4ca85b5ead98cd625f849988ba178', 'isFromContract': False, 'isToContract': False,
                     'amount': '171.12', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x439c4c1b88cce03e840aa5cb56adfedaa6889fcb4f8767afd284e3e6920ce627', 'methodId': '',
                     'blockHash': '0xb7de74c8032ca6d3019826842101f07939bbf5f08d1a68c8363bb4b4bbda5aac',
                     'height': '38696624', 'transactionTime': '1701874457000',
                     'from': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                     'to': '0x958b4fb27724186a49b04402dafb1dab54c2dfb0', 'isFromContract': False, 'isToContract': False,
                     'amount': '205.44', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x689a5a5d027dcd405f216bf8679c26f6e3a93d84a8e42562c2f23669939b079e', 'methodId': '',
                     'blockHash': '0x43e0eb1ff3edef557b1a032df23534a1b02b03312aff57551621953a8b902c46',
                     'height': '38696564', 'transactionTime': '1701874338000',
                     'from': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                     'to': '0xbb4185593bb8eef31ab5dd9c10b0d420d5266cf8', 'isFromContract': False, 'isToContract': False,
                     'amount': '68.14', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x3daa03e33fca677c8cc983390b840cf2f3e547eb1c14e9bc79e83db419bf1225', 'methodId': '',
                     'blockHash': '0x1f4591e251c87ddd8511bd4841143e3e631f2b453c2ad2ed0b22ca3a9679d3e3',
                     'height': '38696533', 'transactionTime': '1701874276000',
                     'from': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                     'to': '0x3327c0c8fc3b9f81d992591ea5ab80efff6ad254', 'isFromContract': False, 'isToContract': False,
                     'amount': '4215.76', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0x2fbb51a3badeedceedaae9ce7ec4995d32c705d4b33f3de97824d25048b4fadb', 'methodId': '',
                     'blockHash': '0xb6dfaf3aa838de68e7e59d112f4ddd79d45600aafd391f7bfaf68017685a019c',
                     'height': '38696505', 'transactionTime': '1701874217000',
                     'from': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                     'to': '0x1427d1a84f385455d7ff220c9a7e262e0cc97b33', 'isFromContract': False, 'isToContract': False,
                     'amount': '212.28', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0xf060dfd894bda9aca4c115ee24f9305fe6388a6efa4466196e8c8387909cfd41', 'methodId': '',
                     'blockHash': '0xed52a9b96aa65a385760b16be1bf5ec41c39c37489e8d5084f6634657895d39a',
                     'height': '38696481', 'transactionTime': '1701874169000',
                     'from': '0x3b36b11fd283121342d7ffc910f739efb80e162b',
                     'to': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b', 'isFromContract': False, 'isToContract': False,
                     'amount': '898.36746', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0xd32ca6869dfc52f3013bda29c22e9fd086a2fcfab92a297b0e6a5345c55bcdfb', 'methodId': '',
                     'blockHash': '0x5a810b190a0e3984d5bbe30195930767da2058dd2f305d26104b3a9517c86541',
                     'height': '38696475', 'transactionTime': '1701874156000',
                     'from': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                     'to': '0x6d40b4e734079a299c64ba01fbdca6dc0fbaaea2', 'isFromContract': False, 'isToContract': False,
                     'amount': '266.84', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''},
                    {'txId': '0xd6ab30c4889cd097d5ef7b16928bfd5ffbeb47b907f6a164bebc2cbef8810427', 'methodId': '',
                     'blockHash': '0x5a810b190a0e3984d5bbe30195930767da2058dd2f305d26104b3a9517c86541',
                     'height': '38696475', 'transactionTime': '1701874156000',
                     'from': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                     'to': '0xe78e821e41d746ef392377bcdfc87496cb378a0d', 'isFromContract': False, 'isToContract': False,
                     'amount': '2299.92', 'transactionSymbol': 'USDt', 'txFee': '', 'state': 'success', 'tokenId': '',
                     'tokenContractAddress': '0x9702230a8ea53601f5cd2dc00fdbc13d4df4a8c7', 'challengeStatus': '',
                     'l1OriginHash': ''}]}]}

        ]

        API.get_block_head = Mock(side_effect=block_head_mock_responses)
        API.get_token_txs = Mock(side_effect=token_txs_mock_responses)
        AvalancheExplorerInterface.token_txs_apis[0] = API

        expected_token_txs = [
            [{13: {'amount': Decimal('600'), 'from_address': '0x1d746beb1536821ea99c6b972d7ca926a79b1077',
                   'to_address': '0x7e4aa755550152a522d9578621ea22edab204308',
                   'hash': '0x5b601de07f9833243337ba99f2420ebf43ed2492c98369f91147e3bdf389c060', 'block': 38695926,
                   'date': datetime.datetime(2023, 12, 6, 14, 31, 31, tzinfo=UTC), 'memo': None,
                   'confirmations': -383705, 'address': '0x7E4aA755550152a522d9578621EA22eDAb204308',
                   'direction': 'incoming', 'raw': None}}, {
                 13: {'amount': Decimal('4037.87'), 'from_address': '0x2d03af06d0ed69d0f8b2e22a50236f6c9f870975',
                      'to_address': '0x7e4aa755550152a522d9578621ea22edab204308',
                      'hash': '0x1b263c6706d1828edc1882880d7bc17faa07bee59d366a250ac4c8ba4264c1b5', 'block': 38695926,
                      'date': datetime.datetime(2023, 12, 6, 14, 31, 31, tzinfo=UTC), 'memo': None,
                      'confirmations': -383705, 'address': '0x7E4aA755550152a522d9578621EA22eDAb204308',
                      'direction': 'incoming', 'raw': None}}, {
                 13: {'amount': Decimal('4'), 'from_address': '0x25566afa9fd804189aee39bef303c8923063ca71',
                      'to_address': '0x7e4aa755550152a522d9578621ea22edab204308',
                      'hash': '0x289f8c947bfe4e643e7aee5452e5cdaa421cf1283a82c7a8dd160e223940c47e', 'block': 38695926,
                      'date': datetime.datetime(2023, 12, 6, 14, 31, 31, tzinfo=UTC), 'memo': None,
                      'confirmations': -383705, 'address': '0x7E4aA755550152a522d9578621EA22eDAb204308',
                      'direction': 'incoming', 'raw': None}}, {
                 13: {'amount': Decimal('541.9'), 'from_address': '0x22a4f29f93718dd3bbec72c04547256d18d3aa46',
                      'to_address': '0x7e4aa755550152a522d9578621ea22edab204308',
                      'hash': '0x1d3cab4a8dbac60df0a36b2d0332b3db12a9ab510f836bcc2518dfedacb566db', 'block': 38695926,
                      'date': datetime.datetime(2023, 12, 6, 14, 31, 31, tzinfo=UTC), 'memo': None,
                      'confirmations': -383705, 'address': '0x7E4aA755550152a522d9578621EA22eDAb204308',
                      'direction': 'incoming', 'raw': None}}, {
                 13: {'amount': Decimal('9334.340737'), 'from_address': '0x746d78739f9504283ee4f4d792b443f03c0f8b3d',
                      'to_address': '0x7e4aa755550152a522d9578621ea22edab204308',
                      'hash': '0x645b6cb003290607843e7ca7ee7de4fd7bcf77f591c9726fc3b1559aaf77bd7c', 'block': 38695926,
                      'date': datetime.datetime(2023, 12, 6, 14, 31, 31, tzinfo=UTC), 'memo': None,
                      'confirmations': -383705, 'address': '0x7E4aA755550152a522d9578621EA22eDAb204308',
                      'direction': 'incoming', 'raw': None}}, {
                 13: {'amount': Decimal('39.097162'), 'from_address': '0x7e4aa755550152a522d9578621ea22edab204308',
                      'to_address': '0xdafa0afd79e547ddf2bb78f92d197d46790babe1',
                      'hash': '0x480ba151d20905cb7f9f0a1045f79ae3845599737002b74630fed2b4345f74f2', 'block': 38695726,
                      'date': datetime.datetime(2023, 12, 6, 14, 24, 52, tzinfo=UTC), 'memo': None,
                      'confirmations': -383505, 'address': '0x7E4aA755550152a522d9578621EA22eDAb204308',
                      'direction': 'outgoing', 'raw': None}}, {
                 13: {'amount': Decimal('1500'), 'from_address': '0x786fe231e5a066f6625397ee78dc9b2902e4796b',
                      'to_address': '0x7e4aa755550152a522d9578621ea22edab204308',
                      'hash': '0x772a1c4f58796fbc7d1abed171067e9a84e5091a02cec1a470334eaf6541b4d2', 'block': 38695629,
                      'date': datetime.datetime(2023, 12, 6, 14, 21, 35, tzinfo=UTC), 'memo': None,
                      'confirmations': -383408, 'address': '0x7E4aA755550152a522d9578621EA22eDAb204308',
                      'direction': 'incoming', 'raw': None}}, {
                 13: {'amount': Decimal('4125'), 'from_address': '0x579c3513f43a21a947659a92011e76de1fea2557',
                      'to_address': '0x7e4aa755550152a522d9578621ea22edab204308',
                      'hash': '0x58f28adc1c6249fade7a92ee8fb219d56414fb850613ec71cbf3504653cd72d8', 'block': 38695628,
                      'date': datetime.datetime(2023, 12, 6, 14, 21, 31, tzinfo=UTC), 'memo': None,
                      'confirmations': -383407, 'address': '0x7E4aA755550152a522d9578621EA22eDAb204308',
                      'direction': 'incoming', 'raw': None}}, {
                 13: {'amount': Decimal('247.197413'), 'from_address': '0x1baf35f6fb0e89e67780a504ca876403cca233b7',
                      'to_address': '0x7e4aa755550152a522d9578621ea22edab204308',
                      'hash': '0x9d481e74f67de2936b08b9627222e079590f9304d25dea5cb97a568ef0c2da46', 'block': 38695628,
                      'date': datetime.datetime(2023, 12, 6, 14, 21, 31, tzinfo=UTC), 'memo': None,
                      'confirmations': -383407, 'address': '0x7E4aA755550152a522d9578621EA22eDAb204308',
                      'direction': 'incoming', 'raw': None}}, {
                 13: {'amount': Decimal('1000'), 'from_address': '0xb9bad2a109d0c4ec2cfb0ea1f42f13ea366bb2ea',
                      'to_address': '0x7e4aa755550152a522d9578621ea22edab204308',
                      'hash': '0x935c0c235e79633a06f86f9732fa9edf9c3262ebbfed6c6783bb0cec4fb49fd7', 'block': 38695628,
                      'date': datetime.datetime(2023, 12, 6, 14, 21, 31, tzinfo=UTC), 'memo': None,
                      'confirmations': -383407, 'address': '0x7E4aA755550152a522d9578621EA22eDAb204308',
                      'direction': 'incoming', 'raw': None}}, {
                 13: {'amount': Decimal('514.5'), 'from_address': '0x1f2c31848468b31ada405bc8699b11d35504f074',
                      'to_address': '0x7e4aa755550152a522d9578621ea22edab204308',
                      'hash': '0x1115a5f9d8c6deef7aa7baeade914bc13be9e2ad3670daeb389492f4775bad5c', 'block': 38695628,
                      'date': datetime.datetime(2023, 12, 6, 14, 21, 31, tzinfo=UTC), 'memo': None,
                      'confirmations': -383407, 'address': '0x7E4aA755550152a522d9578621EA22eDAb204308',
                      'direction': 'incoming', 'raw': None}}, {
                 13: {'amount': Decimal('506.01447'), 'from_address': '0x5813faf1d92f0cae3d83d750872c48403200b905',
                      'to_address': '0x7e4aa755550152a522d9578621ea22edab204308',
                      'hash': '0x319f58ce4546ff0fc89f296c8f90bc494d37409dcc69ea02ae1753537a31d95e', 'block': 38695628,
                      'date': datetime.datetime(2023, 12, 6, 14, 21, 31, tzinfo=UTC), 'memo': None,
                      'confirmations': -383407, 'address': '0x7E4aA755550152a522d9578621EA22eDAb204308',
                      'direction': 'incoming', 'raw': None}}, {
                 13: {'amount': Decimal('98.480876'), 'from_address': '0x1e8a5f8cf884c204d330ef4e347d7308a3995357',
                      'to_address': '0x7e4aa755550152a522d9578621ea22edab204308',
                      'hash': '0x999590b310e04569901374db2ca12e8bbb801e7368ea0099008699df21738e39', 'block': 38695628,
                      'date': datetime.datetime(2023, 12, 6, 14, 21, 31, tzinfo=UTC), 'memo': None,
                      'confirmations': -383407, 'address': '0x7E4aA755550152a522d9578621EA22eDAb204308',
                      'direction': 'incoming', 'raw': None}}],
            [{13: {'amount': Decimal('49.79'), 'from_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                   'to_address': '0x2103bcc8da98aa2e98e8d8a35edba777e2eb8a82',
                   'hash': '0x8c4c3d9788cd470c700842790fb7f3a0f75a867000860907a8491118a67022cf', 'block': 38696898,
                   'date': datetime.datetime(2023, 12, 6, 15, 3, 21,
                                             tzinfo=UTC), 'memo': None, 'confirmations': -384660,
                   'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'outgoing', 'raw': None}}, {
                 13: {'amount': Decimal('20160.58'), 'from_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'to_address': '0x3aeae25dbd294bbb53ac4423ce482297ba736ff8',
                      'hash': '0x13edce4cf07a5fea9b46a7f6efa1f725f7535906993c39fccd0815b456224569', 'block': 38696868,
                      'date': datetime.datetime(2023, 12, 6, 15, 2, 22,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384630,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'outgoing', 'raw': None}}, {
                 13: {'amount': Decimal('484.179085'), 'from_address': '0x07ea2f06c25848b105193a3af537d432f32b1d6f',
                      'to_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'hash': '0x55672f949f2039c33ecc876ff266e59ecac48afef15a1252aae11a639742cafd', 'block': 38696840,
                      'date': datetime.datetime(2023, 12, 6, 15, 1, 29,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384602,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'incoming', 'raw': None}}, {
                 13: {'amount': Decimal('36.03'), 'from_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'to_address': '0x61b310a55ce19a7721a1f0b1558b6ef7cd810eee',
                      'hash': '0x54cba8f558eef039a2b95b47d28ec02a04f35ce3bf6b6d0aba19274817b48215', 'block': 38696836,
                      'date': datetime.datetime(2023, 12, 6, 15, 1, 21,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384598,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'outgoing', 'raw': None}}, {
                 13: {'amount': Decimal('128.400371'), 'from_address': '0x48dd7aa4a378bc7d7b15a0869511915b1df5fab9',
                      'to_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'hash': '0xd551dd5aa438a8a95d8bdfc0581f7fa16f06affe9a6051e499dc9333dcff146d', 'block': 38696810,
                      'date': datetime.datetime(2023, 12, 6, 15, 0, 29,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384572,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'incoming', 'raw': None}}, {
                 13: {'amount': Decimal('27142.71'), 'from_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'to_address': '0x117b1dec8f10b91d79794f68aac9063ad8d3fbd1',
                      'hash': '0x705b22f2197c99974209528b00fc2f2ebc016ebe0099670be5009a2358a63ce1', 'block': 38696805,
                      'date': datetime.datetime(2023, 12, 6, 15, 0, 19,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384567,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'outgoing', 'raw': None}}, {
                 13: {'amount': Decimal('22.75'), 'from_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'to_address': '0x6d40b4e734079a299c64ba01fbdca6dc0fbaaea2',
                      'hash': '0x3c6f298540ef7440265f5099bdda65982b7398974cb6bbc50dafbcd48dab5f06', 'block': 38696775,
                      'date': datetime.datetime(2023, 12, 6, 14, 59, 19,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384537,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'outgoing', 'raw': None}}, {
                 13: {'amount': Decimal('342.69'), 'from_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'to_address': '0x5f2469fc523b1704d28805f7414ba7067e6639de',
                      'hash': '0x0f37631e53c7e555375abfce1691c91d8da9137be1a1a7705c98c444c3c5bf4b', 'block': 38696775,
                      'date': datetime.datetime(2023, 12, 6, 14, 59, 19,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384537,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'outgoing', 'raw': None}}, {
                 13: {'amount': Decimal('57.64'), 'from_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'to_address': '0xf1887456bf823ab0843dc23f99402664b091960f',
                      'hash': '0xe1067257803a2db117470d9092e8cd1f2ad69fdc63cc1e2627e8d3d86db6f5b1', 'block': 38696775,
                      'date': datetime.datetime(2023, 12, 6, 14, 59, 19,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384537,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'outgoing', 'raw': None}}, {
                 13: {'amount': Decimal('2999.5'), 'from_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'to_address': '0x4029cf9753f3dcc0f7c90e8ec47901a019925c2e',
                      'hash': '0xd18deb2fc5cf892b4edb005d7639dc5adf896de4d9c4bbb5a9e2f7d4ad7b6416', 'block': 38696715,
                      'date': datetime.datetime(2023, 12, 6, 14, 57, 19,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384477,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'outgoing', 'raw': None}}, {
                 13: {'amount': Decimal('20'), 'from_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'to_address': '0x29153fb8f8a2583fcc8692756160673d322d2712',
                      'hash': '0x7e90f5388bd0bad36c00e3c0edbec52193d270d1452196359a8b64b0df9471b8', 'block': 38696715,
                      'date': datetime.datetime(2023, 12, 6, 14, 57, 19,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384477,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'outgoing', 'raw': None}}, {
                 13: {'amount': Decimal('100'), 'from_address': '0xc6c006d497ca08cdcded19b921e07501c9997a78',
                      'to_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'hash': '0xe7e749e3252aefa492d80c27294dad585bbb99bee8f242ae1e2efc88930e0cb0', 'block': 38696660,
                      'date': datetime.datetime(2023, 12, 6, 14, 55, 29,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384422,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'incoming', 'raw': None}}, {
                 13: {'amount': Decimal('171.12'), 'from_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'to_address': '0x979d3bb218a4ca85b5ead98cd625f849988ba178',
                      'hash': '0x616bcb73ec14c9b0c43bc4a152b8baf8f62dabd245de5b91f27bce82035e68eb', 'block': 38696625,
                      'date': datetime.datetime(2023, 12, 6, 14, 54, 20,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384387,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'outgoing', 'raw': None}}, {
                 13: {'amount': Decimal('205.44'), 'from_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'to_address': '0x958b4fb27724186a49b04402dafb1dab54c2dfb0',
                      'hash': '0x439c4c1b88cce03e840aa5cb56adfedaa6889fcb4f8767afd284e3e6920ce627', 'block': 38696624,
                      'date': datetime.datetime(2023, 12, 6, 14, 54, 17,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384386,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'outgoing', 'raw': None}}, {
                 13: {'amount': Decimal('68.14'), 'from_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'to_address': '0xbb4185593bb8eef31ab5dd9c10b0d420d5266cf8',
                      'hash': '0x689a5a5d027dcd405f216bf8679c26f6e3a93d84a8e42562c2f23669939b079e', 'block': 38696564,
                      'date': datetime.datetime(2023, 12, 6, 14, 52, 18,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384326,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'outgoing', 'raw': None}}, {
                 13: {'amount': Decimal('4215.76'), 'from_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'to_address': '0x3327c0c8fc3b9f81d992591ea5ab80efff6ad254',
                      'hash': '0x3daa03e33fca677c8cc983390b840cf2f3e547eb1c14e9bc79e83db419bf1225', 'block': 38696533,
                      'date': datetime.datetime(2023, 12, 6, 14, 51, 16,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384295,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'outgoing', 'raw': None}}, {
                 13: {'amount': Decimal('212.28'), 'from_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'to_address': '0x1427d1a84f385455d7ff220c9a7e262e0cc97b33',
                      'hash': '0x2fbb51a3badeedceedaae9ce7ec4995d32c705d4b33f3de97824d25048b4fadb', 'block': 38696505,
                      'date': datetime.datetime(2023, 12, 6, 14, 50, 17,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384267,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'outgoing', 'raw': None}}, {
                 13: {'amount': Decimal('898.36746'), 'from_address': '0x3b36b11fd283121342d7ffc910f739efb80e162b',
                      'to_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'hash': '0xf060dfd894bda9aca4c115ee24f9305fe6388a6efa4466196e8c8387909cfd41', 'block': 38696481,
                      'date': datetime.datetime(2023, 12, 6, 14, 49, 29,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384243,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'incoming', 'raw': None}}, {
                 13: {'amount': Decimal('266.84'), 'from_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'to_address': '0x6d40b4e734079a299c64ba01fbdca6dc0fbaaea2',
                      'hash': '0xd32ca6869dfc52f3013bda29c22e9fd086a2fcfab92a297b0e6a5345c55bcdfb', 'block': 38696475,
                      'date': datetime.datetime(2023, 12, 6, 14, 49, 16,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384237,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'outgoing', 'raw': None}}, {
                 13: {'amount': Decimal('2299.92'), 'from_address': '0x40e832c3df9562dfae5a86a4849f27f687a9b46b',
                      'to_address': '0xe78e821e41d746ef392377bcdfc87496cb378a0d',
                      'hash': '0xd6ab30c4889cd097d5ef7b16928bfd5ffbeb47b907f6a164bebc2cbef8810427', 'block': 38696475,
                      'date': datetime.datetime(2023, 12, 6, 14, 49, 16,
                                                tzinfo=UTC), 'memo': None, 'confirmations': -384237,
                      'address': '0x40E832C3Df9562DfaE5A86A4849F27F687A9B46B', 'direction': 'outgoing', 'raw': None}}]
        ]
        for address, expected_token_tx in zip(TOKEN_ADDRESSES, expected_token_txs):
            token_txs = AvalancheExplorerInterface.get_api().get_token_txs(address, fake_contract_info)
            assert len(expected_token_tx) == len(token_txs)
            assert token_txs == expected_token_tx

