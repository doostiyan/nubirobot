from decimal import Decimal
from unittest import TestCase
from unittest.mock import Mock

import pytest

from exchange.blockchain.api.one.one_rpc import HarmonyRPC
from exchange.blockchain.api.one.one_covalent import ONECovalenthqAPI
from exchange.blockchain.api.one.one_web3 import OneWeb3API
from exchange.blockchain.one_erc20 import OneERC20BlockchainInspector


@pytest.mark.slow
class TestHarmonyBlockchainInspectorErc20(TestCase):
    usdt_currency = 13

    def test_get_wallets_balance_web3(self):
        address = '0xa67bffb64e2dd3728188595169176117cc77ff57'
        addresses = [address]
        api = OneWeb3API.get_api()
        api.get_token_balance = Mock()
        api.get_token_balance.side_effect = [{
            'symbol': 'USDT',
            'amount': Decimal('0.100000'),
            'address': '0xa67bffb64e2dd3728188595169176117cc77ff57'
        }]

        expected_result = {self.usdt_currency: [
            {
                'address': address,
                'balance': Decimal('0.100000'),
                'received': Decimal('0.100000'),
                'sent': Decimal('0'),
                'rewarded': Decimal('0'),
            },
        ]
        }

        result = OneERC20BlockchainInspector.get_wallets_balance_one_web3(addresses)
        self.assertEqual(result, expected_result)

    def test_get_wallets_balance_covalent(self):
        null = None
        false = False
        address = '0x15424ab0bbab79bad32ce779197748485b5ae456'
        addresses = [address]

        expected_result = {
            self.usdt_currency: [
            {
                'address': address,
                'balance': Decimal('2273.967508'),
                'received': Decimal('2273.967508'),
                'sent': Decimal('0'),
                'rewarded': Decimal('0'),
            },
            ]
        }

        test_data = {"data":{"address":"0x976464990b67a70dba691c1151d3beafcc9f2a06","updated_at":"2022-05-10T08:02:30.244046629Z","next_update_at":"2022-05-10T08:07:30.244047189Z","quote_currency":"USD","chain_id":1666600000,"items":[{"contract_decimals":6,"contract_name":"Tether USD","contract_ticker_symbol":"1USDT","contract_address":"0x3c2b8be99c50593081eaa2a724f0b8285f5aba8f","supports_erc":["erc20"],"logo_url":"https://logos.covalenthq.com/tokens/1666600000/0x3c2b8be99c50593081eaa2a724f0b8285f5aba8f.png","last_transferred_at":"2021-12-08T01:29:18Z","type":"cryptocurrency","balance":"2273967508","balance_24h":null,"quote_rate":1.0204461,"quote_rate_24h":1.0708454,"quote":2320.4612,"quote_24h":null,"nft_data":null},{"contract_decimals":18,"contract_name":"Harmony","contract_ticker_symbol":"ONE","contract_address":"0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee","supports_erc":null,"logo_url":"https://www.covalenthq.com/static/images/icons/display-icons/harmony-logo.svg","last_transferred_at":null,"type":"dust","balance":"2218405000000000","balance_24h":null,"quote_rate":0.06566745,"quote_rate_24h":0.06525928,"quote":1.45677E-4,"quote_24h":null,"nft_data":null},{"contract_decimals":9,"contract_name":"OXY","contract_ticker_symbol":"OXY","contract_address":"0x7a8698a1595d7821c04732a242f21c3c6f50cd66","supports_erc":["erc20"],"logo_url":"https://logos.covalenthq.com/tokens/1666600000/0x7a8698a1595d7821c04732a242f21c3c6f50cd66.png","last_transferred_at":"2021-12-08T01:28:35Z","type":"cryptocurrency","balance":"7","balance_24h":null,"quote_rate":null,"quote_rate_24h":null,"quote":0.0,"quote_24h":null,"nft_data":null},{"contract_decimals":9,"contract_name":"ODAO","contract_ticker_symbol":"ODAO","contract_address":"0x947394294f75d7502977ac6813fd99f77c2931ec","supports_erc":["erc20"],"logo_url":"https://logos.covalenthq.com/tokens/1666600000/0x947394294f75d7502977ac6813fd99f77c2931ec.png","last_transferred_at":"2021-12-08T01:29:18Z","type":"dust","balance":"0","balance_24h":null,"quote_rate":0.68170613,"quote_rate_24h":0.69642854,"quote":0.0,"quote_24h":null,"nft_data":null}],"pagination":null},"error":false,"error_message":null,"error_code":null}

        api = ONECovalenthqAPI.get_api()
        api.request = Mock()
        api.request.return_value = test_data
        result = OneERC20BlockchainInspector.get_wallets_balance_one_covalent(addresses)
        self.assertEqual(result, expected_result)

    def test_get_wallet_transactions_rpc(self):
        address = '0x15424ab0bbab79bad32ce779197748485b5ae456'
        dummy_tx_resp = {'jsonrpc': '2.0', 'id': 1, 'result': {'transactions': [{'blockHash': '0x7db4d5c085f937efe574ed3076bc9babbe31ebec3bfb77463654a6c6e38208b2', 'blockNumber': 26335397, 'ethHash': '0xaaeef58d71c326b020b4e77070cfe89e9ea74e02809872a760dd3cab5b1d6199', 'from': 'one15ealldjw9hfh9qvgt9gkj9mpzlx80l6hcf7qq0', 'gas': 76707, 'gasPrice': 35000000000, 'hash': '0x4126d365e96607beba808262d1c2d437af0af330ac27a24df3915ad445c89526', 'input': '0xa9059cbb0000000000000000000000007d68312fe7095c79987a2368bfb0cbd1cd3f87700000000000000000000000000000000000000000000000000000002e90f3ea80', 'nonce': 5, 'r': '0x30b1c001bc142f8d67fa4b8cf4a66f01e8e30b68b11813ae9bb1f455dffc4dcc', 's': '0x5b99055cb1c8787724c85eaa319a63fa1243621edc6ff9ee95d4cc93dbf98744', 'shardID': 0, 'timestamp': 1652171050, 'to': 'one18s4ch6vu2pvnpq0252njfu9c9p044w50gw3l6y', 'toShardID': 0, 'transactionIndex': 20, 'v': '0xc6ac98a3', 'value': 0}]}}

        dummy_status_resp = {'jsonrpc': '2.0', 'id': 1, 'result': {'blockHash': '0xac643e40a2347fb36e0de1540874af3425e579b6bd6efb32594172aa55c03627', 'blockNumber': 26338052, 'crossLinks': [{'block-number': 28581239, 'epoch-number': 976, 'hash': '0xab13821313ef5fe6d0a956f92370a5fbd3cf7e0b57269580abe02ef5e697242a', 'shard-id': 1, 'signature': 'e22f3651c0f97f50a1c78839cd679e95e431a5b16f3ab697ad319088584927664a3158dadf0b0c3e5ee940e39d4275019eceed3f7d995b0c5e90ce1f78fe85fbb240790cb8dce8c0e12229548177cf6fe21f3ed783174be1e08c83ba9170750d', 'signature-bitmap': 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff03', 'view-id': 28584541}, {'block-number': 28730327, 'epoch-number': 976, 'hash': '0xf4dca300946bd06308f2e9adc0763ee16053a9728e9cffbf27d982ebaaab6ffc', 'shard-id': 2, 'signature': '5e100adfa37dd42ef9d2c775556e3b3bd6616fa884d40589cc6c220844e32175e25675bdeff65082f4050f393b5dce15a86950d1c28f9f48355d8037fe05cddc19d85b4ca3913a2becbfca01999eae4cffe5a7ff5f9b8f9f76610b922969f60d', 'signature-bitmap': 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff3f', 'view-id': 28730824}, {'block-number': 28632060, 'epoch-number': 976, 'hash': '0x74c320e4479dbdf39592b34c81d758b4b616ce1f165dac6c2a01548ef782193b', 'shard-id': 3, 'signature': '8c8703727e8daf323f587cfbb8b03087b1872ead0efb2144bdb60592266f6bff44801265d9aef4e2a8f51c2f7d1df10864eb9c9c312865cb7f44205c7b5f925764e52c23b9a4fd166a4bcb228b925ab09418754fe20accf022ffb22a9b0e408d', 'signature-bitmap': 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f', 'view-id': 28633289}], 'epoch': 976, 'lastCommitBitmap': 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff01', 'lastCommitSig': '7d7b76db1938fe291c8f2c58f2a7da6e318bac47be7a2b2e613a6489b9be8298327686527721ce745e41a1062c40440919a054693a7a38b9c37ca4335cde2cf9e909ad1a893f939aed4ba4c47689f40dd0453b7c062f22042d6c25bea7baba93', 'leader': 'one1nn2c86kwaq4nk8lda50fnepepqr9y73kd9w2z3', 'shardID': 0, 'timestamp': '2022-05-10 09:53:16 +0000 UTC', 'unixtime': 1652176396, 'viewID': 26340942, 'vrf': '2b44e76bc23667b41d7f6af79a800c83aa29af189cb430b9c1c8eff950f894c7', 'vrfProof': '28b96cf514684aa4129e48b895c36a1c60055d5f28e4ed39e01aea97be25a2a9c41ef5e17ca0de76bdea4bd4efa4f917bcb8bb52ede189ef1f843847ff83b2e33db722d600322d534f8001645e29c5e63e1dc90225e86eb59667954e7ea72984'}}

        dummy_receipt_resp = {'jsonrpc': '2.0', 'id': 1, 'result': {'blockHash': '0x19a4ff92049b11394d029d93f3fd297a4b3e04b6af491d3218c40153ca3459bd','status':1, 'blockNumber': 26213993, 'ethHash': '0x4086877b30a0bee6275bf54aab09d73bd10dcef0bf4d1003405308a022ed4f75', 'from': 'one1wmupuw4pvaca2kx8r6vfpjmwqad5mk8qmzv6n9', 'gas': 21000, 'gasPrice': 35000000000, 'hash': '0x5ddd02d3e7d3cd9779115c1a4ba87aa4e30c74ecfb038f5d2d9b2c6decfde11f', 'input': '0x', 'nonce': 2349, 'r': '0x85d9db598b68972034f3412a69f79633cd2e022edca2d74ecb7931ca9cf75b1c', 's': '0x45fd036a85aa1f08347822115b1c5e67244774058d0bf331ce7734187d847d00', 'shardID': 0, 'timestamp': 1651922246, 'to': 'one1sd5a698q6ut894nhn3ph3pvxs8cmdh26tdcvnc', 'toShardID': 0, 'transactionIndex': 90, 'v': '0xc6ac98a3', 'value': 105063497927660000000000}}

        api = HarmonyRPC.get_api()
        api.request = Mock()
        api.request.side_effect = [dummy_tx_resp, dummy_receipt_resp, dummy_status_resp]

        OneERC20BlockchainInspector.USE_EXPLORER_TRANSACTION_ONE = 'one_rpc'
        results = OneERC20BlockchainInspector.get_wallet_transactions_one(address)
        results = vars(results[self.usdt_currency][0])

        self.assertEqual(results['address'], address)
        self.assertEqual(results['hash'], "0xaaeef58d71c326b020b4e77070cfe89e9ea74e02809872a760dd3cab5b1d6199")
        self.assertEqual(results['from_address'], "0xa67bffb64e2dd3728188595169176117cc77ff57")
        self.assertEqual(results['block'], 26335397)
        self.assertEqual(float(results['value']), 200000.4)
