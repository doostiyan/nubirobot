from decimal import Decimal

from exchange.base.models import Currencies
from exchange.blockchain.api.eth.eth_explorer_interface import EthExplorerInterface
from exchange.blockchain.api.eth.eth_tatum import ETHTatumApi
from exchange.blockchain.tests.fixtures.eth_tatum_fixtures import tx_hash_successful, tx_hash_failed, \
    token_tx_hash_successful
from exchange.blockchain.tests.fixtures.eth_tatum_fixtures import tx_details_tx_hash_successful_mock_response, \
    tx_details_tx_hash_failed_mock_response, tx_detail_block_head_successful_mock_response, \
    tx_detail_block_head_failed_response, token_tx_detail_block_head_successful_mock_response, \
    token_tx_details_tx_hash_successful_mock_response, batch_token_tx_hash_successful, \
    batch_tx_details_tx_hash_successful_mock_response, batch_tx_detail_block_head_successful_mock_response
from unittest.mock import Mock
from exchange.blockchain.utils import BlockchainUtilsMixin

api = ETHTatumApi
explorerInterface = EthExplorerInterface()
currencies = Currencies.eth
symbol = 'ETH'
explorerInterface.tx_details_apis = [api]
explorerInterface.token_tx_details_apis = [api]


def test__tatum_eth__get_tx_details__explorer_interface__successful(tx_hash_successful,
                                                                    tx_details_tx_hash_successful_mock_response,
                                                                    tx_detail_block_head_successful_mock_response):
    tx_details_mock_responses = [tx_detail_block_head_successful_mock_response,
                                 tx_details_tx_hash_successful_mock_response]
    api.request = Mock(side_effect=tx_details_mock_responses)
    tx_details = explorerInterface.get_tx_details(tx_hash_successful)
    expected_tx_details = {'hash': '0x1a4c7dabdd839bf2147cbf626e9397fec472605723f4bb4cd83efac13f7060e0',
                           'success': True,
                           'block': 22153400,
                           'date': None,
                           'fees': Decimal('0.000008513189895000'),
                           'memo': None,
                           'confirmations': 620,
                           'raw': None,
                           'inputs': [],
                           'outputs': [],
                           'transfers': [{'type': 'MainCoin',
                                          'symbol': 'ETH',
                                          'currency': 11,
                                          'from': '0x4838b106fce9647bdf1e7877bf73ce8b0bad5f97',
                                          'to': '0xf84aab3d91b251b468ac3d7536d5beaa1c1f61d2',
                                          'value': Decimal('0.018625826777595028'),
                                          'is_valid': True,
                                          'token': None,
                                          'memo': None}]}

    expected_tx_details['confirmations'] = tx_details['confirmations']

    assert BlockchainUtilsMixin.compare_dicts_without_order(tx_details, expected_tx_details)


def test__tatum_eth__get_token_tx_details__explorer_interface__successful(token_tx_hash_successful,
                                                                          token_tx_details_tx_hash_successful_mock_response,
                                                                          token_tx_detail_block_head_successful_mock_response):
    token_tx_details_mock_responses = [token_tx_detail_block_head_successful_mock_response,
                                       token_tx_details_tx_hash_successful_mock_response]
    api.request = Mock(side_effect=token_tx_details_mock_responses)
    tx_details = explorerInterface.get_token_tx_details(token_tx_hash_successful)
    expected_tx_details = {'hash': '0x6c5fdd3c2de57ed259c7fecf564d1760ac24b972264f2b9d16f56c59896df00a',
                           'success': True,
                           'block': 22217753,
                           'date': None,
                           'fees': Decimal('0.000821758449120000'),
                           'memo': None,
                           'confirmations': 480,
                           'raw': None,
                           'inputs': [],
                           'outputs': [],
                           'transfers': [{'type': 'Token',
                                          'symbol': 'USDT',
                                          'currency': 13,
                                          'from': '0xa6ab3b345598ff5705de7863e622589732362149',
                                          'to': '0x42b26a7a2cb08f5fa24a06620859f697fe0241b7',
                                          'value': Decimal('250.000000'),
                                          'is_valid': True,
                                          'token': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                                          'memo': None}]}

    expected_tx_details['confirmations'] = tx_details['confirmations']

    assert BlockchainUtilsMixin.compare_dicts_without_order(tx_details, expected_tx_details)


def test__tatum_eth__batch_get_token_tx_details__explorer_interface__successful(batch_token_tx_hash_successful,
                                                                                batch_tx_details_tx_hash_successful_mock_response,
                                                                                batch_tx_detail_block_head_successful_mock_response):
    tx_details_mock_responses = [batch_tx_detail_block_head_successful_mock_response,
                                 batch_tx_details_tx_hash_successful_mock_response]
    api.request = Mock(side_effect=tx_details_mock_responses)
    tx_details = explorerInterface.get_token_tx_details(batch_token_tx_hash_successful)
    expected_tx_details = {'hash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                           'success': True,
                           'block': 21474469,
                           'date': None,
                           'fees': None,
                           'memo': None,
                           'confirmations': 751011,
                           'raw': None,
                           'inputs': [],
                           'outputs': [],
                           'transfers': [{'type': 'Token',
                                          'symbol': 'LDO',
                                          'currency': 119,
                                          'from': '0xd91efec7e42f80156d1d9f660a69847188950747',
                                          'to': '0xdeee5f8d867340bf6e56e9ae069a790ef537d400',
                                          'value': Decimal('286.204800000000000000'),
                                          'is_valid': True,
                                          'token': '0x5a98fcbea516cf06857215779fd812ca3bef1b32',
                                          'memo': None},
                                         {'type': 'Token',
                                          'symbol': '1M_PEPE',
                                          'currency': 191,
                                          'from': '0xd91efec7e42f80156d1d9f660a69847188950747',
                                          'to': '0x52c5233d3d12e9d5522759ace8b551d926b797d1',
                                          'value': Decimal('4962.169820070000000000000000'),
                                          'is_valid': True,
                                          'token': '0x6982508145454ce325ddbe47a25d4ec3d2311933',
                                          'memo': None},
                                         {'type': 'Token',
                                          'symbol': 'SHIB',
                                          'currency': 42,
                                          'from': '0xd91efec7e42f80156d1d9f660a69847188950747',
                                          'to': '0x8cd7fea8630a030ea16009914b6f8a79bea05c30',
                                          'value': Decimal('4219.190600522190000000000'),
                                          'is_valid': True,
                                          'token': '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce',
                                          'memo': None},
                                         {'type': 'Token',
                                          'symbol': 'USDC',
                                          'currency': 102,
                                          'from': '0xd91efec7e42f80156d1d9f660a69847188950747',
                                          'to': '0x45dcec86a1eded2af0858396f26619be801677aa',
                                          'value': Decimal('1149.493380'),
                                          'is_valid': True,
                                          'token': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
                                          'memo': None},
                                         {'type': 'Token',
                                          'symbol': 'USDT',
                                          'currency': 13,
                                          'from': '0xd91efec7e42f80156d1d9f660a69847188950747',
                                          'to': '0xaf2a7f37df0fcad99db3714e6283ff10a56db092',
                                          'value': Decimal('27.434000'),
                                          'is_valid': True,
                                          'token': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                                          'memo': None},
                                         {'type': 'Token',
                                          'symbol': 'USDT',
                                          'currency': 13,
                                          'from': '0xd91efec7e42f80156d1d9f660a69847188950747',
                                          'to': '0x66a9e3db3bac9a4fc151bcbab4dde98f7b3932e1',
                                          'value': Decimal('21390.392592'),
                                          'is_valid': True,
                                          'token': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                                          'memo': None},
                                         {'type': 'Token',
                                          'symbol': 'USDT',
                                          'currency': 13,
                                          'from': '0xd91efec7e42f80156d1d9f660a69847188950747',
                                          'to': '0x23f6cd8c3e6f5defd7aeecfbad1f8462b92717f7',
                                          'value': Decimal('500.000000'),
                                          'is_valid': True,
                                          'token': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                                          'memo': None}]}

    expected_tx_details['confirmations'] = tx_details['confirmations']

    assert BlockchainUtilsMixin.compare_dicts_without_order(tx_details, expected_tx_details)


def test__tatum_eth__get_tx_details__explorer_interface__failed(tx_hash_failed,
                                                                tx_details_tx_hash_failed_mock_response,
                                                                tx_detail_block_head_failed_response):
    tx_details_mock_responses = [tx_detail_block_head_failed_response,
                                 tx_details_tx_hash_failed_mock_response]
    api.request = Mock(side_effect=tx_details_mock_responses)
    tx_details = explorerInterface.get_tx_details(tx_hash_failed)

    expected_tx_details = {'success': False}
    assert BlockchainUtilsMixin.compare_dicts_without_order(tx_details, expected_tx_details)
