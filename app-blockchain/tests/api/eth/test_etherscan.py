import pytest
from pytz import UTC
import datetime
from decimal import Decimal
from django.core.cache import cache

from exchange.blockchain.contracts_conf import ERC20_contract_info
from exchange.blockchain.api.eth.etherscan import EtherscanAPI
from exchange.blockchain.api.eth.eth_explorer_interface import EthExplorerInterface
from exchange.blockchain.apis_conf import APIS_CLASSES
from exchange.blockchain.explorer_original import BlockchainExplorer
from exchange.blockchain.utils import BlockchainUtilsMixin
from exchange.blockchain.contracts_conf import CONTRACT_INFO
from exchange.base.models import Currencies

from unittest.mock import Mock
from unittest import TestCase

API = EtherscanAPI
ADDRESSES = ['0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
             '0xEcAB70cABCC60DCd86e64642da29947EbCA0981A']
TOEKN_ADDRESSES = ['0xd765cef565794d80A5DA6175F3EEd1A6979EB23c']
TXS_HASH = ['0x8bfaca2a444109e3d17d584618317011b10448ee6c4b14a1018e010a7b8802fb']
BLOCK_HEIGHT = [18368973]


@pytest.mark.slow
class TestBlockScanApiCalls(TestCase):
    api = EtherscanAPI
    addresses = ['EQCA1BI4QRZ8qYmskSRDzJmkucGodYRTZCf_b9hckjla6dZl',
                 'EQC9gfdnZesicH7aqqe9dajUMigvPqADBTcLFS3IP_w8dDu5']
    txs_hash = ['tdOToZDKIeTzzSua9Q/qnBM21nx2k2actWNfCSC7RYA=']

    @classmethod
    def _check_hex(cls, value):
        try:
            int(value, 16)
            return True
        except ValueError:
            return False

    @classmethod
    def _check_general_response_one(cls, response):
        return set(response.keys()) == {'status', 'message', 'result'}

    @classmethod
    def _check_general_response_two(cls, response):
        return set(response.keys()) == {'result', 'id', 'jsonrpc'}

    def test_get_balance_api(self):
        for address in ADDRESSES:
            get_balance_result = API.get_balance(address)
            assert API.parser.validator.validate_balance_response(get_balance_result)
            assert self._check_general_response_one(get_balance_result)
            assert isinstance(get_balance_result.get('result'), str)

    def test_get_token_balance_api(self):
        contract_info = ERC20_contract_info.get('mainnet').get(Currencies.usdc)
        for address in TOEKN_ADDRESSES:
            get_token_balance_result = API.get_token_balance(address, contract_info)
            assert API.parser.validator.validate_balance_response(get_token_balance_result)
            assert self._check_general_response_one(get_token_balance_result)
            assert isinstance(get_token_balance_result.get('result'), str)

    def test_get_block_head_api(self):
        get_block_head_response = API.get_block_head()
        assert self._check_general_response_two(get_block_head_response)
        assert self._check_hex(get_block_head_response.get('result'))

    def test_get_tx_details_api(self):
        transaction_keys = {'blockHash', 'blockNumber', 'from', 'gas', 'gasPrice', 'hash', 'input', 'to',
                            'transactionIndex', 'type', 'value'}
        for tx_hash in TXS_HASH:
            get_tx_details_response = API.get_tx_details(tx_hash)
            assert self._check_general_response_two(get_tx_details_response)
            assert len(get_tx_details_response) != 0
            assert isinstance(get_tx_details_response, dict)
            assert isinstance(get_tx_details_response.get('result'), dict)
            assert transaction_keys.issubset(get_tx_details_response.get('result'))
            assert self._check_hex(get_tx_details_response.get('result').get('gas'))
            assert self._check_hex(get_tx_details_response.get('result').get('gasPrice'))
            assert self._check_hex(get_tx_details_response.get('result').get('blockNumber'))

    def test_get_address_txs_api(self):
        transaction_keys = {'value', 'input', 'from', 'to', 'contractAddress', 'isError', 'txreceipt_status',
                            'gasPrice', 'blockHash', 'timeStamp', 'blockNumber', 'confirmations', 'gas', 'hash'}
        for address in ADDRESSES:
            get_address_txs_response = API.get_address_txs(address)
            assert self._check_general_response_one(get_address_txs_response)
            assert API.parser.validator.validate_address_txs_response(get_address_txs_response)
            assert len(get_address_txs_response) != 0
            assert isinstance(get_address_txs_response, dict)
            assert isinstance(get_address_txs_response.get('result'), list)
            for tx in get_address_txs_response.get('result'):
                assert transaction_keys.issubset(tx)
                assert tx.get('gas').isdigit() and tx.get('gasPrice').isdigit() and tx.get('blockNumber').isdigit()

    def test_get_token_txs_api(self):
        token = "0xf31b70A2D3E86bA61d28ede02a5587E7BB3B4B20"
        transaction_keys = {'value', 'input', 'from', 'to', 'contractAddress', 'gasPrice', 'blockHash', 'timeStamp',
                            'blockNumber', 'confirmations', 'gas', 'hash', 'contractAddress'}
        contract_info = ERC20_contract_info.get('mainnet').get(Currencies.usdc)
        get_token_txs_response = API.get_token_txs(token, contract_info)
        assert self._check_general_response_one(get_token_txs_response)
        assert API.parser.validator.validate_address_txs_response(get_token_txs_response)
        assert len(get_token_txs_response) != 0
        assert isinstance(get_token_txs_response, dict)
        assert isinstance(get_token_txs_response.get('result'), list)
        for tx in get_token_txs_response.get('result'):
            assert transaction_keys.issubset(tx)
            assert tx.get('gas').isdigit() and tx.get('gasPrice').isdigit() and tx.get('blockNumber').isdigit()

    def test_block_txs_api(self):
        transaction_keys = {'blockHash', 'blockNumber', 'from', 'gas', 'gasPrice', 'hash', 'input', 'to', 'type',
                            'value'}
        for block_height in BLOCK_HEIGHT:
            get_block_txs_response = API.get_block_txs(block_height)
            assert API.parser.validator.validate_block_txs_response(get_block_txs_response)
            assert self._check_general_response_two(get_block_txs_response)
            assert len(get_block_txs_response) != 0
            assert isinstance(get_block_txs_response, dict)
            assert isinstance(get_block_txs_response.get('result'), dict)
            assert isinstance(get_block_txs_response.get('result').get('transactions'), list)
            for tx in get_block_txs_response.get('result').get('transactions'):
                assert transaction_keys.issubset(tx)
                assert self._check_hex(tx.get('gas'))
                assert self._check_hex(tx.get('gasPrice'))
                assert self._check_hex(tx.get('blockNumber'))


class TestBlockScanFromExplorer(TestCase):

    def _get_api_name(self) -> str:
        #  Get None if api_name dose not exists inside of APIS_CONF
        try:
            return 'eth_explorer_interface' if APIS_CLASSES['eth_explorer_interface'] else None
        except KeyError:
            raise ValueError('api name does not exists or changed')

    def test_get_tx_details(self):
        tx_details_mock_responses = [
            {'jsonrpc': '2.0', 'id': 1,
             'result': {'blockHash': '0xbbcc6244c674a110179712aebb65051f99d4b27c3cd5a7bbdd9124ce8784703c',
                        'blockNumber': '0x117618a',
                        'from': '0xecab70cabcc60dcd86e64642da29947ebca0981a',
                        'gas': '0xb41d',
                        'gasPrice': '0x1aa0a1464',
                        'maxFeePerGas': '0x280bffb80',
                        'maxPriorityFeePerGas': '0x3b9aca00',
                        'hash': '0x8bfaca2a444109e3d17d584618317011b10448ee6c4b14a1018e010a7b8802fb',
                        'input': '0xa9059cbb000000000000000000000000a9d1e08c7793af67e9d92fe308d5697fb81d3e43000000000000000000000000000000000000000000000000000000004c84d630',
                        'nonce': '0x1',
                        'to': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                        'transactionIndex': '0x2f',
                        'value': '0x0',
                        'type': '0x2',
                        'accessList': [],
                        'chainId': '0x1',
                        'v': '0x0',
                        'r': '0x19d337f772258f7ec1daa4c48952518b21c2e7168a4304b6dc16b49177f6b3dc',
                        's': '0x39bd39c45b334f1bd6041657f4ef74b4f03971351f7c5a2920c161340cd35090'
                        }
             }
        ]

        block_head_mock_responses = [
            {'jsonrpc': '2.0', 'id': 83, 'result': '0x117f69e'}
        ]

        API.get_block_head = Mock(side_effect=block_head_mock_responses)
        API.get_tx_details = Mock(side_effect=tx_details_mock_responses)

        EthExplorerInterface.tx_details_apis[0] = API
        api_name = self._get_api_name()
        txs_details = BlockchainExplorer.get_transactions_details(TXS_HASH, 'ETH', api_name=api_name)
        expected_txs_details = [
            {'hash': '0x8bfaca2a444109e3d17d584618317011b10448ee6c4b14a1018e010a7b8802fb', 'success': True,
             'block': 18309514, 'date': None, 'fees': None, 'memo': None, 'confirmations': 0,
             'raw': None, 'inputs': [], 'outputs': [], 'transfers': [{'type': 'Token', 'symbol': 'USDT', 'currency': 13,
                                                                      'from': '0xecab70cabcc60dcd86e64642da29947ebca0981a',
                                                                      'to': '0xa9d1e08c7793af67e9d92fe308d5697fb81d3e43',
                                                                      'value': Decimal('1283.774000'),
                                                                      'is_valid': True,
                                                                      'memo': None,
                                                                      'token': '0xdac17f958d2ee523a2206206994597c13d831ec7'}]}
        ]
        for expected_tx_details, tx_hash in zip(expected_txs_details, TXS_HASH):
            if txs_details[tx_hash].get('success'):
                txs_details[tx_hash]['confirmations'] = expected_tx_details.get('confirmations')
            assert txs_details.get(tx_hash) == expected_tx_details

    def test_get_balances(self):
        balance_mock_responses = [{'message': 'OK', 'result': [
            {'account': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'balance': '316273376495586457384227'},
            {'account': '0xEcAB70cABCC60DCd86e64642da29947EbCA0981A', 'balance': '200405155393836'}], 'status': '1'}]
        API.get_balances = Mock(side_effect=balance_mock_responses)
        EthExplorerInterface.balance_apis[0] = API
        balances = BlockchainExplorer.get_wallets_balance({'ETH': ADDRESSES}, Currencies.eth)

        expected_balances = [
            {'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'received': Decimal('316273.376495586457384227'),
             'sent': Decimal('0'), 'rewarded': Decimal('0'), 'balance': Decimal('316273.376495586457384227')},
            {'address': '0xEcAB70cABCC60DCd86e64642da29947EbCA0981A', 'received': Decimal('0.000200405155393836'),
             'sent': Decimal('0'), 'rewarded': Decimal('0'), 'balance': Decimal('0.000200405155393836')}]
        for balance, expected_balance in zip(balances.get(Currencies.eth), expected_balances):
            assert balance == expected_balance

    def test_get_token_balance(self):
        contract_info = ERC20_contract_info.get('mainnet').get(Currencies.usdc)
        balance_mock_responses = [
            {'message': 'OK', 'result': '0', 'status': '1'}
        ]
        API.get_token_balance = Mock(side_effect=balance_mock_responses)
        expected_balances = [
            {'address': '0xd765cef565794d80A5DA6175F3EEd1A6979EB23c', 'amount': 0.0, 'symbol': 'USDC'}
        ]
        EthExplorerInterface.balance_apis[0] = API
        for address, expected_balance in zip(TOEKN_ADDRESSES, expected_balances):
            balances = EthExplorerInterface.get_api().get_token_balance(address, {105: contract_info})
            assert balances == expected_balance

    def test_get_address_txs(self):
        address_txs_mock_responses = [
            {'status': '1', 'message': 'OK', 'result': [{'blockNumber': '18365421', 'timeStamp': '1697489267',
                                                         'hash': '0xa863926987dbb9310be26088a6d2db8082c51b6b20b22591b365bb9b1b03f47c',
                                                         'nonce': '30',
                                                         'blockHash': '0x9d9dfbed0e1714e9c43d911cacbf651a66d65cc0b89a8474b6740f5d3f352c0f',
                                                         'transactionIndex': '82',
                                                         'from': '0x080712afbb402897bc77d7867a4a5d8a3dde6790',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '0', 'gas': '37722', 'gasPrice': '9306388485',
                                                         'isError': '0', 'txreceipt_status': '1',
                                                         'input': '0xb61d27f6000000000000000000000000080712afbb402897bc77d7867a4a5d8a3dde679000000000000000000000000000000000000000000000000000002d79883d200000000000000000000000000000000000000000000000000000000000000000600000000000000000000000000000000000000000000000000000000000000020e01b7818b40b30741c746a2ddb371833abba52a9bba9ecc6cd0121f95ba03a0d',
                                                         'contractAddress': '', 'cumulativeGasUsed': '12539864',
                                                         'gasUsed': '25148', 'confirmations': '2829',
                                                         'methodId': '0xb61d27f6',
                                                         'functionName': 'execute(address _to, uint256 _value, bytes _data)'},
                                                        {'blockNumber': '18362116', 'timeStamp': '1697449403',
                                                         'hash': '0xb212a6f1b1a977e80aea2a3577f217c0b50d2a5e0f46d22b39b72dce9507ff83',
                                                         'nonce': '10',
                                                         'blockHash': '0xff4d918518ef4a80f64ffd287c122e009a02208452f61f8e4d4c626c7f594610',
                                                         'transactionIndex': '105',
                                                         'from': '0xbe7184da1a6f3c86bbd5fa581612a7d6ee5317bd',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '0', 'gas': '37182', 'gasPrice': '7478430193',
                                                         'isError': '0', 'txreceipt_status': '1',
                                                         'input': '0xb61d27f6000000000000000000000000be7184da1a6f3c86bbd5fa581612a7d6ee5317bd00000000000000000000000000000000000000000000003635c9adc5dea00000000000000000000000000000000000000000000000000000000000000000006000000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000000',
                                                         'contractAddress': '', 'cumulativeGasUsed': '11836850',
                                                         'gasUsed': '24788', 'confirmations': '6134',
                                                         'methodId': '0xb61d27f6',
                                                         'functionName': 'execute(address _to, uint256 _value, bytes _data)'},
                                                        {'blockNumber': '18362066', 'timeStamp': '1697448803',
                                                         'hash': '0x4f2e73c59b37ffc95a48c3727ad21a6845bf9e4e768899dc1ae8e278df375e0a',
                                                         'nonce': '9',
                                                         'blockHash': '0x24afd418d71e616d9b24280892b6caaf34101b188200b5180c99cfda2e86f91d',
                                                         'transactionIndex': '123',
                                                         'from': '0xbe7184da1a6f3c86bbd5fa581612a7d6ee5317bd',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '0', 'gas': '37182', 'gasPrice': '9188398120',
                                                         'isError': '0', 'txreceipt_status': '1',
                                                         'input': '0xb61d27f6000000000000000000000000be7184da1a6f3c86bbd5fa581612a7d6ee5317bd0000000000000000000000000000000000000000000000056bc75e2d631000000000000000000000000000000000000000000000000000000000000000000060000000000000000000000000000000000000000000000000000000000000000a0000000000000000000000000000000000000000000000000000000000000000',
                                                         'contractAddress': '', 'cumulativeGasUsed': '11131096',
                                                         'gasUsed': '24788', 'confirmations': '6184',
                                                         'methodId': '0xb61d27f6',
                                                         'functionName': 'execute(address _to, uint256 _value, bytes _data)'},
                                                        {'blockNumber': '18362053', 'timeStamp': '1697448647',
                                                         'hash': '0xa08b151a9d827940df2420a37e8cdc25a831f078f7b98a4d4fa1bfe26f538a3d',
                                                         'nonce': '8',
                                                         'blockHash': '0x488368bdb629292e6b1e85614fdf37512ca95a87060550357a93fa6793b180c5',
                                                         'transactionIndex': '130',
                                                         'from': '0xbe7184da1a6f3c86bbd5fa581612a7d6ee5317bd',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '0', 'gas': '35869', 'gasPrice': '9361809365',
                                                         'isError': '0', 'txreceipt_status': '1',
                                                         'input': '0x2f54bf6e000000000000000000000000be7184da1a6f3c86bbd5fa581612a7d6ee5317bd',
                                                         'contractAddress': '', 'cumulativeGasUsed': '9430475',
                                                         'gasUsed': '23913', 'confirmations': '6197',
                                                         'methodId': '0x2f54bf6e',
                                                         'functionName': 'isOwner(address _addr)'},
                                                        {'blockNumber': '18362051', 'timeStamp': '1697448623',
                                                         'hash': '0xec881000a64ab44b46accdb9a98c7243a9f01d2fdbd6138470561f964014e50b',
                                                         'nonce': '7',
                                                         'blockHash': '0x8fa74156f57a1f6a5a6688111d185920957744382473ee9c4d05a866ea6869b4',
                                                         'transactionIndex': '174',
                                                         'from': '0xbe7184da1a6f3c86bbd5fa581612a7d6ee5317bd',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '0', 'gas': '36073', 'gasPrice': '9793032536',
                                                         'isError': '0', 'txreceipt_status': '1',
                                                         'input': '0x173825d9000000000000000000000000be7184da1a6f3c86bbd5fa581612a7d6ee5317bd',
                                                         'contractAddress': '', 'cumulativeGasUsed': '12329091',
                                                         'gasUsed': '24049', 'confirmations': '6199',
                                                         'methodId': '0x173825d9',
                                                         'functionName': 'removeOwner(address _owner)'},
                                                        {'blockNumber': '18336430', 'timeStamp': '1697139023',
                                                         'hash': '0xa60ec9eb2854cc6566eed4b4e22a6a711b93a5c0f9380b011cb5908e9dafbdcf',
                                                         'nonce': '0',
                                                         'blockHash': '0xe335e1db2157c732301beb0c96fdb93fa48c291b4f691eddac52031ba8fdd81a',
                                                         'transactionIndex': '114',
                                                         'from': '0xe8d3aab52c6b05225244af5d9c04325c1316c914',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '19540858158899650', 'gas': '33726',
                                                         'gasPrice': '8461008084', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '11349740', 'gasUsed': '22484',
                                                         'confirmations': '31820', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18320587', 'timeStamp': '1696947323',
                                                         'hash': '0xddf6125ee5cb1718a997a9831cdf4e5360d5d1715f27a9ef33634bef53927a50',
                                                         'nonce': '8',
                                                         'blockHash': '0x9b7e2eff2bf58c39d171ab34fd51d0e07028d8832e8bc84da593246fec949fe8',
                                                         'transactionIndex': '131',
                                                         'from': '0x243abff2b68b25a12762d8ab89ca9ab0815869b2',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '500000000000000', 'gas': '24732',
                                                         'gasPrice': '11545785794', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '12784859', 'gasUsed': '22484',
                                                         'confirmations': '47663', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18312106', 'timeStamp': '1696844747',
                                                         'hash': '0x6c8645764215ad0c19e75138060d437132f3702d574f779aa3c2b139e9becc16',
                                                         'nonce': '8',
                                                         'blockHash': '0xe4afef97a9491f0a715ea8fc9dafa26957260c035782825463611ba691be1a81',
                                                         'transactionIndex': '202',
                                                         'from': '0x96abb7f1d7271a6db69a652cd64da1f1080790c9',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '950000000000', 'gas': '24732',
                                                         'gasPrice': '7038931913', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '25661446', 'gasUsed': '22484',
                                                         'confirmations': '56144', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18306070', 'timeStamp': '1696771823',
                                                         'hash': '0xf4c24e55aef90c1911a86d3dfb462f4b770f518747e8b56491a6c475c4199d3b',
                                                         'nonce': '8',
                                                         'blockHash': '0x1f5ac6ed873171dbf8de96406d797a72d3c4c52fb062386fc2b8c8742fadd18c',
                                                         'transactionIndex': '80',
                                                         'from': '0x7e3a7dd202efe324497e4c420dc867a539199dc7',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '342000000000', 'gas': '24732',
                                                         'gasPrice': '10756515848', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '8769605', 'gasUsed': '22484',
                                                         'confirmations': '62180', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18305914', 'timeStamp': '1696769915',
                                                         'hash': '0x09866d32ae11d4f30f19bdf41ee1b7f1416261b1adaeb56c1f72f5510e992481',
                                                         'nonce': '7',
                                                         'blockHash': '0x9c57641f33ac8e9f0767f3506e37b017c5a70c302205a236be0e7b6f5e2f9b3a',
                                                         'transactionIndex': '231',
                                                         'from': '0x972aac82e541894b6d0c13b8075be3b97c4ee9fc',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '684000000000', 'gas': '24732',
                                                         'gasPrice': '5900275380', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '22150287', 'gasUsed': '22484',
                                                         'confirmations': '62336', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18298693', 'timeStamp': '1696682735',
                                                         'hash': '0x988aea9bc8941e4bcc7caca77045b899c841d44555fc5c25122b786ef0ca1752',
                                                         'nonce': '6',
                                                         'blockHash': '0xa3138a4588eb86235ad94a1222a2cd7988acce913a4c0f8a458c7c24f8604d4c',
                                                         'transactionIndex': '160',
                                                         'from': '0xe80cb272797b2167b165a4e767c515267d1e2760',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '195000000000', 'gas': '24732',
                                                         'gasPrice': '6374441739', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '15406543', 'gasUsed': '22484',
                                                         'confirmations': '69557', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18298670', 'timeStamp': '1696682459',
                                                         'hash': '0x42cc13d54351c10e19b7c71fa4030ace31734b290a63718a523eb87bcc28ab51',
                                                         'nonce': '5',
                                                         'blockHash': '0xf2173f5659fc3fb35235c401be4077b3d98e8cab4dd1490f26500fcdd198cc44',
                                                         'transactionIndex': '109',
                                                         'from': '0xf63da572fe4b866b7c94f9eba3bac15793eff9ec',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '225000000000', 'gas': '24732',
                                                         'gasPrice': '6379975236', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '12376489', 'gasUsed': '22484',
                                                         'confirmations': '69580', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18298339', 'timeStamp': '1696678463',
                                                         'hash': '0x9b1c107f80784f91a7203b29778ee6a19fe7fc4e3cd83d10fb8327ee757e0c15',
                                                         'nonce': '7',
                                                         'blockHash': '0x4a06271048cfaabb0f854ad923c308b728e410b68ee767b6d91b85277184257d',
                                                         'transactionIndex': '126',
                                                         'from': '0x0d8de826d95dc4c890d6cef3786c44f5fdaab611',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '942000000000', 'gas': '24732',
                                                         'gasPrice': '5080775069', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '15306614', 'gasUsed': '22484',
                                                         'confirmations': '69911', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18298298', 'timeStamp': '1696677971',
                                                         'hash': '0x6da57cd22722dde86472f82f740d39dd2ecdbca5a04fd644d6a073f2ef1d698d',
                                                         'nonce': '5',
                                                         'blockHash': '0x103e216d2186dab516d7a50a95a2eeb33eb3b9a9d52bb3c2ed14ec524d21ccee',
                                                         'transactionIndex': '205',
                                                         'from': '0xc15946e418e95cf3efdf90f94d81b1809eccb863',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '651000000000', 'gas': '24732',
                                                         'gasPrice': '4964306464', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '20210854', 'gasUsed': '22484',
                                                         'confirmations': '69952', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18297027', 'timeStamp': '1696662623',
                                                         'hash': '0x8a61a48c7c97367b5f6707c87c262aad8db044191e5b20c5e22493d25e69dfb1',
                                                         'nonce': '10',
                                                         'blockHash': '0x2fda56b3dc76c931a49c12159783ec3e222b03acb1ce2f1c28260e9d35170cb4',
                                                         'transactionIndex': '106',
                                                         'from': '0x3a4243ef670a1b50796f8530bf847cc8c9b1ef9a',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '0', 'gas': '31611', 'gasPrice': '6284268718',
                                                         'isError': '0', 'txreceipt_status': '1', 'input': '0x',
                                                         'contractAddress': '', 'cumulativeGasUsed': '10461786',
                                                         'gasUsed': '21074', 'confirmations': '71223', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18282023', 'timeStamp': '1696481255',
                                                         'hash': '0xbfecf104e3bbe3dfcc0690a857a180477d248f17359f0bdc1ee4d107e1801c3f',
                                                         'nonce': '8',
                                                         'blockHash': '0x0f16d9a840688fcb35407670b94483188565bc7d09dde75daa85ff21b8346d2d',
                                                         'transactionIndex': '123',
                                                         'from': '0xeb0b2a3175686df957fe20e4e5c61add10291bcf',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '404000000000', 'gas': '24732',
                                                         'gasPrice': '5696099048', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '28958073', 'gasUsed': '22484',
                                                         'confirmations': '86227', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18280083', 'timeStamp': '1696457867',
                                                         'hash': '0xa2bfe670359b2ff75a1d90c57134c5ee1e2da58fc12bd728954c1cfcbe9113e8',
                                                         'nonce': '17',
                                                         'blockHash': '0x491798ab2c37b06c8cdb67dced6fa389149d3c72d8091979b04b06442a3b6594',
                                                         'transactionIndex': '108',
                                                         'from': '0xae26192d4bd1b4138ebaf3bb5b9d721466d4dc08',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '414000000000', 'gas': '24732',
                                                         'gasPrice': '6635897769', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '8880022', 'gasUsed': '22484',
                                                         'confirmations': '88167', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18275791', 'timeStamp': '1696406003',
                                                         'hash': '0x4434822578de149b1d848b339f1a57a7923c3a9de990f92cc59139bcca0e808e',
                                                         'nonce': '8',
                                                         'blockHash': '0x13030ce79d204902aaa4c52f0a8b3c3e165c79405244c25019f4d72b6e138321',
                                                         'transactionIndex': '155',
                                                         'from': '0x06bb2276080a23cbe759dcc1cda242960b1dc42f',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '771000000000', 'gas': '24732',
                                                         'gasPrice': '7604431484', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '12205216', 'gasUsed': '22484',
                                                         'confirmations': '92459', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18275128', 'timeStamp': '1696398011',
                                                         'hash': '0x7de18516d5621bc8ced8230a46f81ccd11ee358d97d59a30e5ada3b4971a1c40',
                                                         'nonce': '7',
                                                         'blockHash': '0x33e595fc837bbcac0b1c53e03f43f562d34c2838767632e707c0b68fb081489d',
                                                         'transactionIndex': '144',
                                                         'from': '0x41e89710c7afacfef0f598f6acd05156fa258e89',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '498000000000', 'gas': '24732',
                                                         'gasPrice': '5588785583', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '26902189', 'gasUsed': '22484',
                                                         'confirmations': '93122', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18275068', 'timeStamp': '1696397291',
                                                         'hash': '0x87fb9f0b6d9dd24450a979eaedbce2fe8133ffa3a4863a71d6d12f1107be4abf',
                                                         'nonce': '8',
                                                         'blockHash': '0x08294cd56ef0b498f96419c5b0dfbcae57ba2c66158bd487f2a508b388f526f3',
                                                         'transactionIndex': '61',
                                                         'from': '0x29edb734afae160c390616ca810c0218b024ecb5',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '378000000000', 'gas': '24732',
                                                         'gasPrice': '6395502181', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '5046878', 'gasUsed': '22484',
                                                         'confirmations': '93182', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18274408', 'timeStamp': '1696389347',
                                                         'hash': '0xee84afa253e858ddfa9eb2d2e744043e2884fc668eda813c4b6702c075bc5bce',
                                                         'nonce': '8',
                                                         'blockHash': '0xe3018ac785e70a4af1dd3347f7531515aa4e6d07075da0bd3ce846e4daadaf3f',
                                                         'transactionIndex': '111',
                                                         'from': '0x1dd5bcd7c2dc167ce108d7767cb2206f0427cc2c',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '862000000000', 'gas': '24732',
                                                         'gasPrice': '6370536395', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '12633340', 'gasUsed': '22484',
                                                         'confirmations': '93842', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18273414', 'timeStamp': '1696377335',
                                                         'hash': '0x073d73a991ecf46e988574eef049d73d11951bc9e9ee91d12f3a19768239d1d0',
                                                         'nonce': '7',
                                                         'blockHash': '0x6bf867082b86de90c05feaf77612ae659401f9f56179b67b4ae69cc9894d4e86',
                                                         'transactionIndex': '166',
                                                         'from': '0xbbc2240895a49377b529e2f6c2ee6ff7c6ca5986',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '443000000000', 'gas': '24732',
                                                         'gasPrice': '9194227250', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '14257525', 'gasUsed': '22484',
                                                         'confirmations': '94836', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18268660', 'timeStamp': '1696319771',
                                                         'hash': '0x94db6da4facc3d25072a778a2cd9fb4af23bdc161b9b5125b8c138cacfdeecfd',
                                                         'nonce': '8',
                                                         'blockHash': '0x99ce1fa95ee82a0269c6e8510845a244c0e5a82668300ce235a0af5211b721be',
                                                         'transactionIndex': '102',
                                                         'from': '0x726992de9313b26e902e5211ae5c174034582e32',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '517000000000', 'gas': '24732',
                                                         'gasPrice': '6578504001', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '8063502', 'gasUsed': '22484',
                                                         'confirmations': '99590', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18268640', 'timeStamp': '1696319531',
                                                         'hash': '0x9e56172019333beb9877b6309de206f00c262148ac13b850bfb2785672bf20bf',
                                                         'nonce': '7',
                                                         'blockHash': '0xb7defeb5864c1cf6112b04d11fbd14d1b09f9891922ee582d004f180dcc6776e',
                                                         'transactionIndex': '68',
                                                         'from': '0x07501c121e83135d78cb07625626c182c0685b37',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '716000000000', 'gas': '24732',
                                                         'gasPrice': '7981496189', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '11724076', 'gasUsed': '22484',
                                                         'confirmations': '99610', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18268623', 'timeStamp': '1696319327',
                                                         'hash': '0x6b51276e2683e57682e67f8c2cf239b00baf2c915d02b94c9b31354252aa762c',
                                                         'nonce': '7',
                                                         'blockHash': '0x56f6a418fc7bcdd168144bd9372610f71b219a9c1cc0e25cb143bbb2573912a5',
                                                         'transactionIndex': '84',
                                                         'from': '0x1684c3ba3423b568beb97e8b4c47ab36751f78f5',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '783000000000', 'gas': '24732',
                                                         'gasPrice': '6257023004', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '10313440', 'gasUsed': '22484',
                                                         'confirmations': '99627', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18267896', 'timeStamp': '1696310603',
                                                         'hash': '0x415f2ea5562594165ddeee51ab47129b208823dc967d109e66128cf332d51a04',
                                                         'nonce': '8',
                                                         'blockHash': '0xd8a8e3016c905a816c5085964e3ffa6692dea42fb01cbc97a99414869dff5ed7',
                                                         'transactionIndex': '98',
                                                         'from': '0xe9b38cc8f83340ee67a10c62b2c19063efd53ced',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '883000000000', 'gas': '24732',
                                                         'gasPrice': '6656235566', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '13453539', 'gasUsed': '22484',
                                                         'confirmations': '100354', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18267830', 'timeStamp': '1696309799',
                                                         'hash': '0x5aae91243da2d24c98305259faa8732d3a912daf638cafc6b884dc3d1a99099a',
                                                         'nonce': '7',
                                                         'blockHash': '0x84988399ffc78ba84900d5cde9b5c8b8c0cf706e2764c98a9483e3dc379f7fab',
                                                         'transactionIndex': '57',
                                                         'from': '0x923978d89a456fc83b87d5bda3683aca32b6fcb4',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '560000000000', 'gas': '24732',
                                                         'gasPrice': '6352900708', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '4758904', 'gasUsed': '22484',
                                                         'confirmations': '100420', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18267734', 'timeStamp': '1696308635',
                                                         'hash': '0xd56d5a294b84bee84282c7ae9d3c180abb1e312a585f44554996cd9835606436',
                                                         'nonce': '7',
                                                         'blockHash': '0xcd975e6b8c4e2a018ced53d1a0e1efc67191d353c8feea7cddd36dababe703cb',
                                                         'transactionIndex': '128',
                                                         'from': '0x764de8fed30c2c7cc5b09df30b2241933d22c2ef',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '695000000000', 'gas': '24732',
                                                         'gasPrice': '6142894175', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '12882409', 'gasUsed': '22484',
                                                         'confirmations': '100516', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18267690', 'timeStamp': '1696308107',
                                                         'hash': '0x8d0c75ef728dbdad9552045d2a66508c64984a0eda378846adc115aefe581300',
                                                         'nonce': '8',
                                                         'blockHash': '0x3839e60515b56fcc8a803cdd505a2e93edc5ca88d210fc941e093d23f0f5c872',
                                                         'transactionIndex': '65',
                                                         'from': '0xdaaf5c2378e96f9376bff51f0d63fe3f18c261b5',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '394000000000', 'gas': '24732',
                                                         'gasPrice': '5896259277', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '12328860', 'gasUsed': '22484',
                                                         'confirmations': '100560', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18267599', 'timeStamp': '1696306991',
                                                         'hash': '0xf6d5c1f8c914349d0ca0b7a884a06bc4314ef22b002701fc3c6788f7fc1456f2',
                                                         'nonce': '6',
                                                         'blockHash': '0x2e66bb9d69a87fc54959adb82fa1ceac9344b59b84a907f11b0b8ab58ea108a2',
                                                         'transactionIndex': '125',
                                                         'from': '0x5defe08e4ad28cdd7633a7e082612ae4f6d93c9a',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '299000000000', 'gas': '24732',
                                                         'gasPrice': '7571362773', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '10471575', 'gasUsed': '22484',
                                                         'confirmations': '100651', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18267464', 'timeStamp': '1696305347',
                                                         'hash': '0x9c815e1f7f0efecee60392b40d5374b1671641d8ae2dcf2374e9411db58eb025',
                                                         'nonce': '7',
                                                         'blockHash': '0x7fa92ee6721777d6fe1d91e6c7ad3ef3b3f73c5a39dcc211a4ee6a5dd3b20ebf',
                                                         'transactionIndex': '144',
                                                         'from': '0xb17aa77ed63d9bc676b74ca22eb7f671878acf59',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '400000000000', 'gas': '24732',
                                                         'gasPrice': '6643676418', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '16294267', 'gasUsed': '22484',
                                                         'confirmations': '100786', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18267308', 'timeStamp': '1696303451',
                                                         'hash': '0xc7f631f63b409633bcd293c6fe4c3fe44c9a4c211a2dee2b50a3976c0c53bae2',
                                                         'nonce': '6',
                                                         'blockHash': '0x72fe1709a5824bb1a5d8ac4b28341b881569f9036a6e46f83c54e64da36b91b5',
                                                         'transactionIndex': '163',
                                                         'from': '0x7fe51835b96df766c3e042ccf48c802c299a22c0',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '980000000000', 'gas': '24732',
                                                         'gasPrice': '6052484662', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '17061366', 'gasUsed': '22484',
                                                         'confirmations': '100942', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18267040', 'timeStamp': '1696300223',
                                                         'hash': '0x4a282740e8d4b5745337b1df484a3450729b6bbbbf96d169db02cad83b640176',
                                                         'nonce': '7',
                                                         'blockHash': '0x01132cc175b8c18419b0e38442406e628e28507598cfcf38fbc666063a0cd027',
                                                         'transactionIndex': '102',
                                                         'from': '0xd1b9125517e61c889b259109e2c2bfda379a95a2',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '689000000000', 'gas': '24732',
                                                         'gasPrice': '6568096774', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '8123625', 'gasUsed': '22484',
                                                         'confirmations': '101210', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18266878', 'timeStamp': '1696298279',
                                                         'hash': '0x68030b120d1830fe2bc6bf33d74f211d01a5ae3f849500c887a3c14542da85a4',
                                                         'nonce': '8',
                                                         'blockHash': '0xcfb9bfdfa25462c950b7b924381e85b47e2c467d6f727349cd8bb815c1b5dc78',
                                                         'transactionIndex': '93',
                                                         'from': '0xf244c8dda18bea635964b8088aab69eaf2ba8c03',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '785000000000', 'gas': '24732',
                                                         'gasPrice': '8011273999', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '8397398', 'gasUsed': '22484',
                                                         'confirmations': '101372', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18266709', 'timeStamp': '1696296227',
                                                         'hash': '0xb091684456ff4d057ee4effb2a18425c9799cab0a46f4b8ad539e2df697606ee',
                                                         'nonce': '5',
                                                         'blockHash': '0xa1ce77f097c81854aef2960a390c037028cf0e9e1150ecc77ad55d0372aadf16',
                                                         'transactionIndex': '112',
                                                         'from': '0xa35b89b6d4eb77a83103dd2d0b3dba2b6e432d3c',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '408000000000', 'gas': '24732',
                                                         'gasPrice': '6882866989', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '8829116', 'gasUsed': '22484',
                                                         'confirmations': '101541', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18266494', 'timeStamp': '1696293635',
                                                         'hash': '0x405fc69464a8a1031dd569fecf0641492ccd9a9dc20522dda300a33c86f6ea5f',
                                                         'nonce': '4',
                                                         'blockHash': '0x66dae9b144f6c843c6e3016487563fa1e4d982fe4684c255892a02025a0d5e9a',
                                                         'transactionIndex': '98',
                                                         'from': '0x6114e0f1eb17448f80f42b1ff220285351b183c4',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '972000000000', 'gas': '24732',
                                                         'gasPrice': '7468790658', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '9116076', 'gasUsed': '22484',
                                                         'confirmations': '101756', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18264204', 'timeStamp': '1696266071',
                                                         'hash': '0xbaeeefff9597f8ddd941710330732e122313b0fc9503771f21f1767b10a9c43a',
                                                         'nonce': '7',
                                                         'blockHash': '0x1b74f4b4b1fe0606dd40124569637f291617dbbad735294c7a4fd84f7725f6b8',
                                                         'transactionIndex': '70',
                                                         'from': '0xd9d946a86c9f9cfe1e427822c419e06398c46612',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '0', 'gas': '90000', 'gasPrice': '40215124366',
                                                         'isError': '0', 'txreceipt_status': '1',
                                                         'input': '0xa9059cbb000000000000000000000000d9d946a86c9f9cfe1e427822c419e06398c466120000000000000000000000000000000000000000000000000000000000000000',
                                                         'contractAddress': '', 'cumulativeGasUsed': '6076296',
                                                         'gasUsed': '22041', 'confirmations': '104046',
                                                         'methodId': '0xa9059cbb',
                                                         'functionName': 'transfer(address _to, uint256 _value)'},
                                                        {'blockNumber': '18262008', 'timeStamp': '1696239587',
                                                         'hash': '0xfe9724ca6d3025f71d45b744305ca1cce24934547f6f4195c99746c7b3e9401b',
                                                         'nonce': '833',
                                                         'blockHash': '0x280f98bb298f425268e9dd289b31dc69ea3f1752f7925ec8a4346730a18a9143',
                                                         'transactionIndex': '131',
                                                         'from': '0x5ed8cee6b63b1c6afce3ad7c92f4fd7e1b8fad9f',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '0', 'gas': '83844', 'gasPrice': '7530862587',
                                                         'isError': '0', 'txreceipt_status': '1',
                                                         'input': '0xb61d27f6000000000000000000000000bc9a9ac7dc36b1706732374bf632ef39fb6efbc300000000000000000000000000000000000000000000003635c9adc5dea0000000000000000000000000000000000000000000000000000000000000000000600000000000000000000000000000000000000000000000000000000000000000',
                                                         'contractAddress': '', 'cumulativeGasUsed': '17827442',
                                                         'gasUsed': '53096', 'confirmations': '106242',
                                                         'methodId': '0xb61d27f6',
                                                         'functionName': 'execute(address _to, uint256 _value, bytes _data)'},
                                                        {'blockNumber': '18261731', 'timeStamp': '1696236251',
                                                         'hash': '0xb6ea38bfdf7f4a02eac1480b609f2e2e0d8eb3afe5a4eb0a99d9c439c8fab778',
                                                         'nonce': '6',
                                                         'blockHash': '0xd02afe1a7893b46c9f67954e6f497d1e5d958529309e82ce860e7778e4bcd656',
                                                         'transactionIndex': '124',
                                                         'from': '0x980b018cf2c5c9cb367c3eec7004d93a5c176434',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '275000000000', 'gas': '24732',
                                                         'gasPrice': '9038841509', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '9964828', 'gasUsed': '22484',
                                                         'confirmations': '106519', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18260046', 'timeStamp': '1696215923',
                                                         'hash': '0xf08e2e1822430063df2fb68f9b04ece50361d305244210068e1f99d66ac2eaa1',
                                                         'nonce': '7',
                                                         'blockHash': '0xa2120dfff3b109793739a5b899a095eb0b4a62261cf3597c9b7d57730aae46f6',
                                                         'transactionIndex': '120',
                                                         'from': '0x32ac25c9dc02cacebec9596a5453d410c5c0da86',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '898000000000', 'gas': '24732',
                                                         'gasPrice': '6535567436', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '12591287', 'gasUsed': '22484',
                                                         'confirmations': '108204', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18260012', 'timeStamp': '1696215515',
                                                         'hash': '0x6b1d324850e29623934ea34eab4e73d8eefe122e1a73c6e178bd1821eea03eef',
                                                         'nonce': '6',
                                                         'blockHash': '0x9eed47062cab2f4ce8da72acb16cd6916c90c471e6d753dac4a0683c04f5fb69',
                                                         'transactionIndex': '121',
                                                         'from': '0xe3d5aeae88ef03ea694f310a5585ffb7bf40cb31',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '148000000000', 'gas': '24732',
                                                         'gasPrice': '6540980163', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '12653587', 'gasUsed': '22484',
                                                         'confirmations': '108238', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18259806', 'timeStamp': '1696213031',
                                                         'hash': '0xaa9ccae60a3800d73e3522c459f5675ebdffe399277a13cfeff44c094013f4e0',
                                                         'nonce': '8',
                                                         'blockHash': '0x64a206f4e3d680b55977daded45b75261f64466361896c04727d244536b5ab2f',
                                                         'transactionIndex': '136',
                                                         'from': '0xac6d42e8e1ecc0b678a366542662a6e5717a1d3e',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '761000000000', 'gas': '24732',
                                                         'gasPrice': '7527366119', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '12994171', 'gasUsed': '22484',
                                                         'confirmations': '108444', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18259661', 'timeStamp': '1696211279',
                                                         'hash': '0x3c7a6a4e1c6368a69ee831baa16253be4f4a2f88d8ce65d8221f851185bfde67',
                                                         'nonce': '7',
                                                         'blockHash': '0xca80b49a009e7750fc57b0912cd01054e386e5f102fc5a6e2067b2b8636ee5ca',
                                                         'transactionIndex': '111',
                                                         'from': '0x65ad5671d444fd88bdde32f6fa494d7f2eb44b4f',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '944000000000', 'gas': '24732',
                                                         'gasPrice': '8002726424', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '12637946', 'gasUsed': '22484',
                                                         'confirmations': '108589', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18259589', 'timeStamp': '1696210415',
                                                         'hash': '0x7c57a54699b97b478b7dd828ba5148bda389221d6c072cbeed09bb3264872cce',
                                                         'nonce': '5',
                                                         'blockHash': '0x7d4829a1d671d36a7093433ef67de3b7d553efcfa9ccbb44d1102293e758f656',
                                                         'transactionIndex': '130',
                                                         'from': '0x6755f91e226af9f26fd9da261cc58bd6f298bd06',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '906000000000', 'gas': '24732',
                                                         'gasPrice': '7143964587', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '10486948', 'gasUsed': '22484',
                                                         'confirmations': '108661', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18258970', 'timeStamp': '1696202951',
                                                         'hash': '0x01f09445d66c7d8aea11f3fa14a304f2e5a3f60b65eea60f75dd031d07cb3b73',
                                                         'nonce': '6',
                                                         'blockHash': '0x1afb498be21c3f83c5c9cb0ba89290f922363d26987b17e8da9bb15059146250',
                                                         'transactionIndex': '143',
                                                         'from': '0xfa4d3bd6bad2ff7c837cced4d43ca67dae2e1676',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '315000000000', 'gas': '24732',
                                                         'gasPrice': '8734883695', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '16374281', 'gasUsed': '22484',
                                                         'confirmations': '109280', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18258446', 'timeStamp': '1696196651',
                                                         'hash': '0x6d79a9d1ccd42d68d2798951042982b5ebf8abeda66944b70fa5969ceacb0c26',
                                                         'nonce': '5',
                                                         'blockHash': '0x1a1603f6c0b5d83703cf3362daa8ae905f86bc713b16a4510f89e9793da5887c',
                                                         'transactionIndex': '101',
                                                         'from': '0x7afa0e00161d287c0dcd43057d69081076787b0e',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '526000000000', 'gas': '24732',
                                                         'gasPrice': '9883003323', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '15115128', 'gasUsed': '22484',
                                                         'confirmations': '109804', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18258421', 'timeStamp': '1696196351',
                                                         'hash': '0x7d14caa8da64033438762605b4db2c6470d5871ec9a88999cfdc3ce3715ed37a',
                                                         'nonce': '6',
                                                         'blockHash': '0x37feb507891ec70c76d4e13a0c505e11ed458293c2cf3de7d8564d483f111b7a',
                                                         'transactionIndex': '176',
                                                         'from': '0x5c3aa55c66750706cda6a14ae9cf31aebb142bf2',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '883000000000', 'gas': '24732',
                                                         'gasPrice': '9106506708', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '15685512', 'gasUsed': '22484',
                                                         'confirmations': '109829', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18257102', 'timeStamp': '1696180403',
                                                         'hash': '0xd844ac7666ff9f3559a604b7f1e37411aef350cb66eee9db8b1be14411466b89',
                                                         'nonce': '7',
                                                         'blockHash': '0x106a3ea8e3a0b695ea2554db138b19c28fbd70b7571b212189c2978554090aa9',
                                                         'transactionIndex': '135',
                                                         'from': '0xd4cc87b8120e45fd6932d577237328d1ce2e21a6',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '0', 'gas': '36216', 'gasPrice': '8916487371',
                                                         'isError': '0', 'txreceipt_status': '1',
                                                         'input': '0x7065cb48000000000000000000000000d4cc87b8120e45fd6932d577237328d1ce2e21a6',
                                                         'contractAddress': '', 'cumulativeGasUsed': '16221742',
                                                         'gasUsed': '24144', 'confirmations': '111148',
                                                         'methodId': '0x7065cb48',
                                                         'functionName': 'addOwner(address _owner)'},
                                                        {'blockNumber': '18256334', 'timeStamp': '1696171151',
                                                         'hash': '0x10ca0952596bba37d6a3c5426c858313525f9fad55491614304be770e9188206',
                                                         'nonce': '5',
                                                         'blockHash': '0x40a18156fca5518db9baf604f8ae126faa4da1a5ab9443f1c7b7e6b8ea1d8ab8',
                                                         'transactionIndex': '147',
                                                         'from': '0x9f148f4f174f478e03cc71e55bb495b559473625',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '660000000000', 'gas': '24732',
                                                         'gasPrice': '8887389285', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '14762465', 'gasUsed': '22484',
                                                         'confirmations': '111916', 'methodId': '0x',
                                                         'functionName': ''},
                                                        {'blockNumber': '18256293', 'timeStamp': '1696170647',
                                                         'hash': '0x065ec3124a1b26b9e1ad476ab519e9f26cc844d9f55f0cd2759466bc4f8bafa7',
                                                         'nonce': '6',
                                                         'blockHash': '0x2b475ab38d97d8d488251e331108dde355135079d72c6cc52f0fc289a866c56e',
                                                         'transactionIndex': '151',
                                                         'from': '0x515eecb5623784c292c3c0d6462179de4a0e261f',
                                                         'to': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae',
                                                         'value': '148000000000', 'gas': '24732',
                                                         'gasPrice': '9167196267', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '20154737', 'gasUsed': '22484',
                                                         'confirmations': '111957', 'methodId': '0x',
                                                         'functionName': ''}]},
            {'status': '1', 'message': 'OK', 'result': [{'blockNumber': '18309514', 'timeStamp': '1696813451',
                                                         'hash': '0x8bfaca2a444109e3d17d584618317011b10448ee6c4b14a1018e010a7b8802fb',
                                                         'nonce': '1',
                                                         'blockHash': '0xbbcc6244c674a110179712aebb65051f99d4b27c3cd5a7bbdd9124ce8784703c',
                                                         'transactionIndex': '47',
                                                         'from': '0xecab70cabcc60dcd86e64642da29947ebca0981a',
                                                         'to': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                                                         'value': '0', 'gas': '46109', 'gasPrice': '7147754596',
                                                         'isError': '0', 'txreceipt_status': '1',
                                                         'input': '0xa9059cbb000000000000000000000000a9d1e08c7793af67e9d92fe308d5697fb81d3e43000000000000000000000000000000000000000000000000000000004c84d630',
                                                         'contractAddress': '', 'cumulativeGasUsed': '4682484',
                                                         'gasUsed': '41309', 'confirmations': '58739',
                                                         'methodId': '0xa9059cbb',
                                                         'functionName': 'transfer(address _to, uint256 _value)'},
                                                        {'blockNumber': '18262422', 'timeStamp': '1696244591',
                                                         'hash': '0xccfbe5a1c5329d1500ab86ef516cfb1560efad2f1cde3649c2ed484fd9ce6a70',
                                                         'nonce': '0',
                                                         'blockHash': '0x7cab1616b6227647f384412b2e74663d4282b03135bb0e14d6b764d2b4172387',
                                                         'transactionIndex': '173',
                                                         'from': '0xecab70cabcc60dcd86e64642da29947ebca0981a',
                                                         'to': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                                                         'value': '0', 'gas': '46109', 'gasPrice': '22729020325',
                                                         'isError': '0', 'txreceipt_status': '1',
                                                         'input': '0xa9059cbb000000000000000000000000a9d1e08c7793af67e9d92fe308d5697fb81d3e4300000000000000000000000000000000000000000000000000000000068e7780',
                                                         'contractAddress': '', 'cumulativeGasUsed': '12462703',
                                                         'gasUsed': '41309', 'confirmations': '105831',
                                                         'methodId': '0xa9059cbb',
                                                         'functionName': 'transfer(address _to, uint256 _value)'},
                                                        {'blockNumber': '18262412', 'timeStamp': '1696244471',
                                                         'hash': '0x1f9800c73f5575f276827d35d91064287a505c3942096338af76aaec04fa324e',
                                                         'nonce': '1602165',
                                                         'blockHash': '0x4bf8d8703c2ec526a1aad725e29a09ff367a3a58cb4523c7611b1dd08e7165ff',
                                                         'transactionIndex': '145',
                                                         'from': '0x71660c4005ba85c37ccec55d0c4493e66fe775d3',
                                                         'to': '0xecab70cabcc60dcd86e64642da29947ebca0981a',
                                                         'value': '1048979750000000', 'gas': '21000',
                                                         'gasPrice': '19532379077', 'isError': '0',
                                                         'txreceipt_status': '1', 'input': '0x', 'contractAddress': '',
                                                         'cumulativeGasUsed': '9798494', 'gasUsed': '21000',
                                                         'confirmations': '105841', 'methodId': '0x',
                                                         'functionName': ''}]}
        ]
        block_head_mock_responses = [{'id': 83, 'jsonrpc': '2.0', 'result': '0x11994b5'},
                                     {'id': 83, 'jsonrpc': '2.0', 'result': '0x11995c2'}]

        API.get_address_txs = Mock(side_effect=address_txs_mock_responses)
        API.get_block_head = Mock(side_effect=block_head_mock_responses)

        EthExplorerInterface.address_txs_apis[0] = API
        expected_addresses_txs = [
            [{11: {'amount': Decimal('0.019540858158899650'), 'from_address': '0xe8d3aab52c6b05225244af5d9c04325c1316c914', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0xa60ec9eb2854cc6566eed4b4e22a6a711b93a5c0f9380b011cb5908e9dafbdcf', 'block': 18336430, 'date': datetime.datetime(2023, 10, 12, 19, 30, 23, tzinfo=UTC), 'memo': None, 'confirmations': 31820, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('0.000500000000000000'), 'from_address': '0x243abff2b68b25a12762d8ab89ca9ab0815869b2', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0xddf6125ee5cb1718a997a9831cdf4e5360d5d1715f27a9ef33634bef53927a50', 'block': 18320587, 'date': datetime.datetime(2023, 10, 10, 14, 15, 23, tzinfo=UTC), 'memo': None, 'confirmations': 47663, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('9.50000000000E-7'), 'from_address': '0x96abb7f1d7271a6db69a652cd64da1f1080790c9', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x6c8645764215ad0c19e75138060d437132f3702d574f779aa3c2b139e9becc16', 'block': 18312106, 'date': datetime.datetime(2023, 10, 9, 9, 45, 47, tzinfo=UTC), 'memo': None, 'confirmations': 56144, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('3.42000000000E-7'), 'from_address': '0x7e3a7dd202efe324497e4c420dc867a539199dc7', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0xf4c24e55aef90c1911a86d3dfb462f4b770f518747e8b56491a6c475c4199d3b', 'block': 18306070, 'date': datetime.datetime(2023, 10, 8, 13, 30, 23, tzinfo=UTC), 'memo': None, 'confirmations': 62180, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('6.84000000000E-7'), 'from_address': '0x972aac82e541894b6d0c13b8075be3b97c4ee9fc', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x09866d32ae11d4f30f19bdf41ee1b7f1416261b1adaeb56c1f72f5510e992481', 'block': 18305914, 'date': datetime.datetime(2023, 10, 8, 12, 58, 35, tzinfo=UTC), 'memo': None, 'confirmations': 62336, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('1.95000000000E-7'), 'from_address': '0xe80cb272797b2167b165a4e767c515267d1e2760', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x988aea9bc8941e4bcc7caca77045b899c841d44555fc5c25122b786ef0ca1752', 'block': 18298693, 'date': datetime.datetime(2023, 10, 7, 12, 45, 35, tzinfo=UTC), 'memo': None, 'confirmations': 69557, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('2.25000000000E-7'), 'from_address': '0xf63da572fe4b866b7c94f9eba3bac15793eff9ec', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x42cc13d54351c10e19b7c71fa4030ace31734b290a63718a523eb87bcc28ab51', 'block': 18298670, 'date': datetime.datetime(2023, 10, 7, 12, 40, 59, tzinfo=UTC), 'memo': None, 'confirmations': 69580, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('9.42000000000E-7'), 'from_address': '0x0d8de826d95dc4c890d6cef3786c44f5fdaab611', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x9b1c107f80784f91a7203b29778ee6a19fe7fc4e3cd83d10fb8327ee757e0c15', 'block': 18298339, 'date': datetime.datetime(2023, 10, 7, 11, 34, 23, tzinfo=UTC), 'memo': None, 'confirmations': 69911, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('6.51000000000E-7'), 'from_address': '0xc15946e418e95cf3efdf90f94d81b1809eccb863', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x6da57cd22722dde86472f82f740d39dd2ecdbca5a04fd644d6a073f2ef1d698d', 'block': 18298298, 'date': datetime.datetime(2023, 10, 7, 11, 26, 11, tzinfo=UTC), 'memo': None, 'confirmations': 69952, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('4.04000000000E-7'), 'from_address': '0xeb0b2a3175686df957fe20e4e5c61add10291bcf', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0xbfecf104e3bbe3dfcc0690a857a180477d248f17359f0bdc1ee4d107e1801c3f', 'block': 18282023, 'date': datetime.datetime(2023, 10, 5, 4, 47, 35, tzinfo=UTC), 'memo': None, 'confirmations': 86227, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('4.14000000000E-7'), 'from_address': '0xae26192d4bd1b4138ebaf3bb5b9d721466d4dc08', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0xa2bfe670359b2ff75a1d90c57134c5ee1e2da58fc12bd728954c1cfcbe9113e8', 'block': 18280083, 'date': datetime.datetime(2023, 10, 4, 22, 17, 47, tzinfo=UTC), 'memo': None, 'confirmations': 88167, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('7.71000000000E-7'), 'from_address': '0x06bb2276080a23cbe759dcc1cda242960b1dc42f', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x4434822578de149b1d848b339f1a57a7923c3a9de990f92cc59139bcca0e808e', 'block': 18275791, 'date': datetime.datetime(2023, 10, 4, 7, 53, 23, tzinfo=UTC), 'memo': None, 'confirmations': 92459, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('4.98000000000E-7'), 'from_address': '0x41e89710c7afacfef0f598f6acd05156fa258e89', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x7de18516d5621bc8ced8230a46f81ccd11ee358d97d59a30e5ada3b4971a1c40', 'block': 18275128, 'date': datetime.datetime(2023, 10, 4, 5, 40, 11, tzinfo=UTC), 'memo': None, 'confirmations': 93122, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('3.78000000000E-7'), 'from_address': '0x29edb734afae160c390616ca810c0218b024ecb5', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x87fb9f0b6d9dd24450a979eaedbce2fe8133ffa3a4863a71d6d12f1107be4abf', 'block': 18275068, 'date': datetime.datetime(2023, 10, 4, 5, 28, 11, tzinfo=UTC), 'memo': None, 'confirmations': 93182, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('8.62000000000E-7'), 'from_address': '0x1dd5bcd7c2dc167ce108d7767cb2206f0427cc2c', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0xee84afa253e858ddfa9eb2d2e744043e2884fc668eda813c4b6702c075bc5bce', 'block': 18274408, 'date': datetime.datetime(2023, 10, 4, 3, 15, 47, tzinfo=UTC), 'memo': None, 'confirmations': 93842, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('4.43000000000E-7'), 'from_address': '0xbbc2240895a49377b529e2f6c2ee6ff7c6ca5986', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x073d73a991ecf46e988574eef049d73d11951bc9e9ee91d12f3a19768239d1d0', 'block': 18273414, 'date': datetime.datetime(2023, 10, 3, 23, 55, 35, tzinfo=UTC), 'memo': None, 'confirmations': 94836, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('5.17000000000E-7'), 'from_address': '0x726992de9313b26e902e5211ae5c174034582e32', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x94db6da4facc3d25072a778a2cd9fb4af23bdc161b9b5125b8c138cacfdeecfd', 'block': 18268660, 'date': datetime.datetime(2023, 10, 3, 7, 56, 11, tzinfo=UTC), 'memo': None, 'confirmations': 99590, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('7.16000000000E-7'), 'from_address': '0x07501c121e83135d78cb07625626c182c0685b37', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x9e56172019333beb9877b6309de206f00c262148ac13b850bfb2785672bf20bf', 'block': 18268640, 'date': datetime.datetime(2023, 10, 3, 7, 52, 11, tzinfo=UTC), 'memo': None, 'confirmations': 99610, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('7.83000000000E-7'), 'from_address': '0x1684c3ba3423b568beb97e8b4c47ab36751f78f5', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x6b51276e2683e57682e67f8c2cf239b00baf2c915d02b94c9b31354252aa762c', 'block': 18268623, 'date': datetime.datetime(2023, 10, 3, 7, 48, 47, tzinfo=UTC), 'memo': None, 'confirmations': 99627, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('8.83000000000E-7'), 'from_address': '0xe9b38cc8f83340ee67a10c62b2c19063efd53ced', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x415f2ea5562594165ddeee51ab47129b208823dc967d109e66128cf332d51a04', 'block': 18267896, 'date': datetime.datetime(2023, 10, 3, 5, 23, 23, tzinfo=UTC), 'memo': None, 'confirmations': 100354, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('5.60000000000E-7'), 'from_address': '0x923978d89a456fc83b87d5bda3683aca32b6fcb4', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x5aae91243da2d24c98305259faa8732d3a912daf638cafc6b884dc3d1a99099a', 'block': 18267830, 'date': datetime.datetime(2023, 10, 3, 5, 9, 59, tzinfo=UTC), 'memo': None, 'confirmations': 100420, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('6.95000000000E-7'), 'from_address': '0x764de8fed30c2c7cc5b09df30b2241933d22c2ef', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0xd56d5a294b84bee84282c7ae9d3c180abb1e312a585f44554996cd9835606436', 'block': 18267734, 'date': datetime.datetime(2023, 10, 3, 4, 50, 35, tzinfo=UTC), 'memo': None, 'confirmations': 100516, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('3.94000000000E-7'), 'from_address': '0xdaaf5c2378e96f9376bff51f0d63fe3f18c261b5', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x8d0c75ef728dbdad9552045d2a66508c64984a0eda378846adc115aefe581300', 'block': 18267690, 'date': datetime.datetime(2023, 10, 3, 4, 41, 47, tzinfo=UTC), 'memo': None, 'confirmations': 100560, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('2.99000000000E-7'), 'from_address': '0x5defe08e4ad28cdd7633a7e082612ae4f6d93c9a', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0xf6d5c1f8c914349d0ca0b7a884a06bc4314ef22b002701fc3c6788f7fc1456f2', 'block': 18267599, 'date': datetime.datetime(2023, 10, 3, 4, 23, 11, tzinfo=UTC), 'memo': None, 'confirmations': 100651, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('4.00000000000E-7'), 'from_address': '0xb17aa77ed63d9bc676b74ca22eb7f671878acf59', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x9c815e1f7f0efecee60392b40d5374b1671641d8ae2dcf2374e9411db58eb025', 'block': 18267464, 'date': datetime.datetime(2023, 10, 3, 3, 55, 47, tzinfo=UTC), 'memo': None, 'confirmations': 100786, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('9.80000000000E-7'), 'from_address': '0x7fe51835b96df766c3e042ccf48c802c299a22c0', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0xc7f631f63b409633bcd293c6fe4c3fe44c9a4c211a2dee2b50a3976c0c53bae2', 'block': 18267308, 'date': datetime.datetime(2023, 10, 3, 3, 24, 11, tzinfo=UTC), 'memo': None, 'confirmations': 100942, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('6.89000000000E-7'), 'from_address': '0xd1b9125517e61c889b259109e2c2bfda379a95a2', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x4a282740e8d4b5745337b1df484a3450729b6bbbbf96d169db02cad83b640176', 'block': 18267040, 'date': datetime.datetime(2023, 10, 3, 2, 30, 23, tzinfo=UTC), 'memo': None, 'confirmations': 101210, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('7.85000000000E-7'), 'from_address': '0xf244c8dda18bea635964b8088aab69eaf2ba8c03', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x68030b120d1830fe2bc6bf33d74f211d01a5ae3f849500c887a3c14542da85a4', 'block': 18266878, 'date': datetime.datetime(2023, 10, 3, 1, 57, 59, tzinfo=UTC), 'memo': None, 'confirmations': 101372, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('4.08000000000E-7'), 'from_address': '0xa35b89b6d4eb77a83103dd2d0b3dba2b6e432d3c', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0xb091684456ff4d057ee4effb2a18425c9799cab0a46f4b8ad539e2df697606ee', 'block': 18266709, 'date': datetime.datetime(2023, 10, 3, 1, 23, 47, tzinfo=UTC), 'memo': None, 'confirmations': 101541, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('9.72000000000E-7'), 'from_address': '0x6114e0f1eb17448f80f42b1ff220285351b183c4', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x405fc69464a8a1031dd569fecf0641492ccd9a9dc20522dda300a33c86f6ea5f', 'block': 18266494, 'date': datetime.datetime(2023, 10, 3, 0, 40, 35, tzinfo=UTC), 'memo': None, 'confirmations': 101756, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('2.75000000000E-7'), 'from_address': '0x980b018cf2c5c9cb367c3eec7004d93a5c176434', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0xb6ea38bfdf7f4a02eac1480b609f2e2e0d8eb3afe5a4eb0a99d9c439c8fab778', 'block': 18261731, 'date': datetime.datetime(2023, 10, 2, 8, 44, 11, tzinfo=UTC), 'memo': None, 'confirmations': 106519, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('8.98000000000E-7'), 'from_address': '0x32ac25c9dc02cacebec9596a5453d410c5c0da86', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0xf08e2e1822430063df2fb68f9b04ece50361d305244210068e1f99d66ac2eaa1', 'block': 18260046, 'date': datetime.datetime(2023, 10, 2, 3, 5, 23, tzinfo=UTC), 'memo': None, 'confirmations': 108204, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('1.48000000000E-7'), 'from_address': '0xe3d5aeae88ef03ea694f310a5585ffb7bf40cb31', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x6b1d324850e29623934ea34eab4e73d8eefe122e1a73c6e178bd1821eea03eef', 'block': 18260012, 'date': datetime.datetime(2023, 10, 2, 2, 58, 35, tzinfo=UTC), 'memo': None, 'confirmations': 108238, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('7.61000000000E-7'), 'from_address': '0xac6d42e8e1ecc0b678a366542662a6e5717a1d3e', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0xaa9ccae60a3800d73e3522c459f5675ebdffe399277a13cfeff44c094013f4e0', 'block': 18259806, 'date': datetime.datetime(2023, 10, 2, 2, 17, 11, tzinfo=UTC), 'memo': None, 'confirmations': 108444, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('9.44000000000E-7'), 'from_address': '0x65ad5671d444fd88bdde32f6fa494d7f2eb44b4f', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x3c7a6a4e1c6368a69ee831baa16253be4f4a2f88d8ce65d8221f851185bfde67', 'block': 18259661, 'date': datetime.datetime(2023, 10, 2, 1, 47, 59, tzinfo=UTC), 'memo': None, 'confirmations': 108589, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('9.06000000000E-7'), 'from_address': '0x6755f91e226af9f26fd9da261cc58bd6f298bd06', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x7c57a54699b97b478b7dd828ba5148bda389221d6c072cbeed09bb3264872cce', 'block': 18259589, 'date': datetime.datetime(2023, 10, 2, 1, 33, 35, tzinfo=UTC), 'memo': None, 'confirmations': 108661, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('3.15000000000E-7'), 'from_address': '0xfa4d3bd6bad2ff7c837cced4d43ca67dae2e1676', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x01f09445d66c7d8aea11f3fa14a304f2e5a3f60b65eea60f75dd031d07cb3b73', 'block': 18258970, 'date': datetime.datetime(2023, 10, 1, 23, 29, 11, tzinfo=UTC), 'memo': None, 'confirmations': 109280, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('5.26000000000E-7'), 'from_address': '0x7afa0e00161d287c0dcd43057d69081076787b0e', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x6d79a9d1ccd42d68d2798951042982b5ebf8abeda66944b70fa5969ceacb0c26', 'block': 18258446, 'date': datetime.datetime(2023, 10, 1, 21, 44, 11, tzinfo=UTC), 'memo': None, 'confirmations': 109804, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('8.83000000000E-7'), 'from_address': '0x5c3aa55c66750706cda6a14ae9cf31aebb142bf2', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x7d14caa8da64033438762605b4db2c6470d5871ec9a88999cfdc3ce3715ed37a', 'block': 18258421, 'date': datetime.datetime(2023, 10, 1, 21, 39, 11, tzinfo=UTC), 'memo': None, 'confirmations': 109829, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('6.60000000000E-7'), 'from_address': '0x9f148f4f174f478e03cc71e55bb495b559473625', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x10ca0952596bba37d6a3c5426c858313525f9fad55491614304be770e9188206', 'block': 18256334, 'date': datetime.datetime(2023, 10, 1, 14, 39, 11, tzinfo=UTC), 'memo': None, 'confirmations': 111916, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}, {11: {'amount': Decimal('1.48000000000E-7'), 'from_address': '0x515eecb5623784c292c3c0d6462179de4a0e261f', 'to_address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'hash': '0x065ec3124a1b26b9e1ad476ab519e9f26cc844d9f55f0cd2759466bc4f8bafa7', 'block': 18256293, 'date': datetime.datetime(2023, 10, 1, 14, 30, 47, tzinfo=UTC), 'memo': None, 'confirmations': 111957, 'address': '0xde0b295669a9fd93d5f28d9ec85e40f4cb697bae', 'direction': 'incoming', 'raw': None}}],
            [{11: {'amount': Decimal('0.001048979750000000'), 'from_address': '0x71660c4005ba85c37ccec55d0c4493e66fe775d3', 'to_address': '0xecab70cabcc60dcd86e64642da29947ebca0981a', 'hash': '0x1f9800c73f5575f276827d35d91064287a505c3942096338af76aaec04fa324e', 'block': 18262412, 'date': datetime.datetime(2023, 10, 2, 11, 1, 11, tzinfo=UTC), 'memo': None, 'confirmations': 105841, 'address': '0xEcAB70cABCC60DCd86e64642da29947EbCA0981A', 'direction': 'incoming', 'raw': None}}],
        ]
        for address, expected_address_txs in zip(ADDRESSES, expected_addresses_txs):
            address_txs = EthExplorerInterface.get_api().get_txs(address)
            assert len(expected_address_txs) == len(address_txs)
            for expected_address_tx, address_tx in zip(expected_address_txs, address_txs):
                expected_address_tx, address_tx = expected_address_tx.get(Currencies.eth), address_tx.get(
                    Currencies.eth)
                assert address_tx.get('confirmations') >= expected_address_tx.get('confirmations')
                address_tx['confirmations'] = expected_address_tx.get('confirmations')
                assert address_tx == expected_address_tx

    def test_get_token_txs(self):
        block_head_mock_responses = [{'id': 83, 'jsonrpc': '2.0', 'result': '0x11994b5'}]
        token_txs_mock_responses = [{'status': '1', 'message': 'OK', 'result': [
            {'blockNumber': '18461870', 'timeStamp': '1698655547',
             'hash': '0xc37639197df9ead7e5251ab3feccb060febec1bb03c0c773691c1bbb78ffecea', 'nonce': '0',
             'blockHash': '0x3d3ba9ac6aa7c080a3abbf7c28dc431aa891740de99b023c26d8f9cb112d7c65',
             'from': '0xd765cef565794d80a5da6175f3eed1a6979eb23c',
             'contractAddress': '0xdac17f958d2ee523a2206206994597c13d831ec7',
             'to': '0x9bc77498c40c022bca20c3fe0172a4e6cd5ee7c9', 'value': '49000000', 'tokenName': 'Tether USD',
             'tokenSymbol': 'USDT', 'tokenDecimal': '6', 'transactionIndex': '274', 'gas': '94813',
             'gasPrice': '13900691895', 'gasUsed': '58409', 'cumulativeGasUsed': '17333888', 'input': 'deprecated',
             'confirmations': '690'},
            {'blockNumber': '18078687', 'timeStamp': '1694018843',
             'hash': '0xfb02154ab66bdded755ec9866801e90d92b0b07f807f3c3f9c7305c61d0011f0',
             'nonce': '2',
             'blockHash': '0x0fb88682a2c4bd8ac9cfc2e4f6184f1da9d6a17c2dc821a2d931f0c2bb0fae31',
             'from': '0x4ee29485bf7466dd03cca184528d84d4715758a8',
             'contractAddress': '0xdac17f958d2ee523a2206206994597c13d831ec7',
             'to': '0xd765cef565794d80a5da6175f3eed1a6979eb23c', 'value': '49000000',
             'tokenName': 'Tether USD', 'tokenSymbol': 'USDT', 'tokenDecimal': '6',
             'transactionIndex': '118', 'gas': '69529', 'gasPrice': '29602228220',
             'gasUsed': '63209', 'cumulativeGasUsed': '11320550', 'input': 'deprecated',
             'confirmations': '383873'}]}]

        API.get_block_head = Mock(side_effect=block_head_mock_responses)
        API.get_token_txs = Mock(side_effect=token_txs_mock_responses)

        EthExplorerInterface.token_txs_apis[0] = API
        expected_tokens_txs = [
            [{13: {'amount': Decimal('49.000000'), 'from_address': '0xd765cef565794d80a5da6175f3eed1a6979eb23c',
                   'to_address': '0x9bc77498c40c022bca20c3fe0172a4e6cd5ee7c9',
                   'hash': '0xc37639197df9ead7e5251ab3feccb060febec1bb03c0c773691c1bbb78ffecea', 'block': 18461870,
                   'date': datetime.datetime(2023, 10, 30, 8, 45, 47,
                                             tzinfo=UTC), 'memo': None, 'confirmations': 690,
                   'address': '0xd765cef565794d80A5DA6175F3EEd1A6979EB23c', 'direction': 'outgoing', 'raw': None}}, {
                 13: {'amount': Decimal('49.000000'), 'from_address': '0x4ee29485bf7466dd03cca184528d84d4715758a8',
                      'to_address': '0xd765cef565794d80a5da6175f3eed1a6979eb23c',
                      'hash': '0xfb02154ab66bdded755ec9866801e90d92b0b07f807f3c3f9c7305c61d0011f0', 'block': 18078687,
                      'date': datetime.datetime(2023, 9, 6, 16, 47, 23,
                                                tzinfo=UTC), 'memo': None, 'confirmations': 383873,
                      'address': '0xd765cef565794d80A5DA6175F3EEd1A6979EB23c', 'direction': 'incoming', 'raw': None}}]
        ]

        for address, expected_token_txs in zip(TOEKN_ADDRESSES, expected_tokens_txs):
            contract_info = CONTRACT_INFO.get('ETH').get('mainnet').get(Currencies.usdt)
            token_txs = EthExplorerInterface.get_api().get_token_txs(address, contract_info)
            assert len(expected_token_txs) == len(token_txs)
            for expected_token_tx, token_tx in zip(expected_token_txs, token_txs):
                assert token_tx == expected_token_tx
