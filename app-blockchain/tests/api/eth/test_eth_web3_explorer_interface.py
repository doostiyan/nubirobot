from decimal import Decimal
from unittest.mock import Mock
from exchange.blockchain.api.eth.eth_explorer_interface import EthExplorerInterface
from exchange.base.models import Currencies
from exchange.blockchain.api.eth.eth_web3_new import ETHWeb3Api
from exchange.blockchain.tests.fixtures.eth_web3_fixtures import tx_hash, block_height
from exchange.blockchain.tests.fixtures.eth_web3_fixtures import tx_details_mock_response, block_head_mock_response, \
    block_txs_mock_response, tx_receipt_mock_response

from exchange.blockchain.utils import BlockchainUtilsMixin

api = ETHWeb3Api
symbol = 'ETH'
explorerInterface = EthExplorerInterface()
explorerInterface.block_txs_apis = [api]
explorerInterface.tx_details_apis = [api]
currencies = Currencies.eth


def test__web3_eth__get_tx_details__explorer_interface__successful(tx_hash, block_head_mock_response, tx_details_mock_response, tx_receipt_mock_response):
    api.get_tx_details = Mock(side_effect=[tx_details_mock_response])
    api.get_block_head = Mock(side_effect=[block_head_mock_response])
    api.get_tx_receipt = Mock(side_effect=[tx_receipt_mock_response])
    tx_details = explorerInterface.get_tx_details(tx_hash)
    expected_tx_details = {'block': 21474469, 'confirmations': 45219, 'date': None, 'fees': None,
                           'hash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783', 'inputs': [],
                           'memo': None, 'outputs': [], 'raw': None, 'success': True, 'transfers': [
            {'currency': 119, 'from': '0xd91efec7e42f80156d1d9f660a69847188950747', 'is_valid': True, 'memo': None,
             'symbol': 'LDO', 'to': '0xdeee5f8d867340bf6e56e9ae069a790ef537d400',
             'token': '0x5a98fcbea516cf06857215779fd812ca3bef1b32', 'type': 'Token',
             'value': Decimal('286.204800000000000000')},
            {'currency': 191, 'from': '0xd91efec7e42f80156d1d9f660a69847188950747', 'is_valid': True, 'memo': None,
             'symbol': '1M_PEPE', 'to': '0x52c5233d3d12e9d5522759ace8b551d926b797d1',
             'token': '0x6982508145454ce325ddbe47a25d4ec3d2311933', 'type': 'Token',
             'value': Decimal('4962.169820070000000000000000')},
            {'currency': 42, 'from': '0xd91efec7e42f80156d1d9f660a69847188950747', 'is_valid': True, 'memo': None,
             'symbol': 'SHIB', 'to': '0x8cd7fea8630a030ea16009914b6f8a79bea05c30',
             'token': '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce', 'type': 'Token',
             'value': Decimal('4219.190600522190000000000')},
            {'currency': 102, 'from': '0xd91efec7e42f80156d1d9f660a69847188950747', 'is_valid': True, 'memo': None,
             'symbol': 'USDC', 'to': '0x45dcec86a1eded2af0858396f26619be801677aa',
             'token': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48', 'type': 'Token', 'value': Decimal('1149.493380')},
            {'currency': 13, 'from': '0xd91efec7e42f80156d1d9f660a69847188950747', 'is_valid': True, 'memo': None,
             'symbol': 'USDT', 'to': '0xaf2a7f37df0fcad99db3714e6283ff10a56db092',
             'token': '0xdac17f958d2ee523a2206206994597c13d831ec7', 'type': 'Token', 'value': Decimal('27.434000')},
            {'currency': 13, 'from': '0xd91efec7e42f80156d1d9f660a69847188950747', 'is_valid': True, 'memo': None,
             'symbol': 'USDT', 'to': '0x66a9e3db3bac9a4fc151bcbab4dde98f7b3932e1',
             'token': '0xdac17f958d2ee523a2206206994597c13d831ec7', 'type': 'Token', 'value': Decimal('21390.392592')},
            {'currency': 13, 'from': '0xd91efec7e42f80156d1d9f660a69847188950747', 'is_valid': True, 'memo': None,
             'symbol': 'USDT', 'to': '0x23f6cd8c3e6f5defd7aeecfbad1f8462b92717f7',
             'token': '0xdac17f958d2ee523a2206206994597c13d831ec7', 'type': 'Token', 'value': Decimal('500.000000')}]}
    assert BlockchainUtilsMixin.compare_dicts_without_order(tx_details, expected_tx_details)


def test__web3_eth__get_block_txs__explorer_interface__successful(block_height, block_txs_mock_response, block_head_mock_response):
    api.get_block_txs = Mock(side_effect=[block_txs_mock_response])
    api.get_block_head = Mock(side_effect=[block_head_mock_response])
    txs_addresses, txs_info, _ = explorerInterface.get_latest_block(block_height - 1, block_height, include_inputs=True,
                                                                    include_info=True)
    expected_txs_addresses = {
        'input_addresses': {'0xd85de14d20e079fdf0c1b5d79837b8da5e44ac65', '0xd91efec7e42f80156d1d9f660a69847188950747'},
        'output_addresses': {'0x23f6cd8c3e6f5defd7aeecfbad1f8462b92717f7', '0x25db7ce35fa802194410678745b735fdbaca4f87',
                             '0x45dcec86a1eded2af0858396f26619be801677aa', '0x52c5233d3d12e9d5522759ace8b551d926b797d1',
                             '0x66a9e3db3bac9a4fc151bcbab4dde98f7b3932e1', '0x8cd7fea8630a030ea16009914b6f8a79bea05c30',
                             '0xaf2a7f37df0fcad99db3714e6283ff10a56db092',
                             '0xdeee5f8d867340bf6e56e9ae069a790ef537d400'}}
    expected_txs_info = {
        'outgoing_txs': {'0xd91efec7e42f80156d1d9f660a69847188950747':
                             {119: [{'tx_hash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                                     'value': Decimal('286.204800000000000000'),
                                     'contract_address': '0x5a98fcbea516cf06857215779fd812ca3bef1b32',
                                     'block_height': 21474469,
                                     'symbol': 'LDO'}],
                              191: [{'tx_hash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                                     'value': Decimal('4962.169820070000000000000000'),
                                     'contract_address': '0x6982508145454ce325ddbe47a25d4ec3d2311933',
                                     'block_height': 21474469,
                                     'symbol': '1M_PEPE'}],
                              42: [{'tx_hash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                                    'value': Decimal('4219.190600522190000000000'),
                                    'contract_address': '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce',
                                    'block_height': 21474469,
                                    'symbol': 'SHIB'}],
                              102: [{'tx_hash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                                     'value': Decimal('1149.493380'),
                                     'contract_address': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
                                     'block_height': 21474469,
                                     'symbol': 'USDC'}],
                              13: [{'tx_hash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                                    'value': Decimal('21917.826592'),
                                    'contract_address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                                    'block_height': 21474469,
                                    'symbol': 'USDT'}]},
                         '0xd85de14d20e079fdf0c1b5d79837b8da5e44ac65':
                             {97: [{'tx_hash': '0xf50c316987a1423d3d9d9f086f3732fc683275a4c1c82d21c1e6b8bdb006cf67',
                                    'value': Decimal('600.000000000000000000'),
                                    'contract_address': None,
                                    'block_height': 21474469,
                                    'symbol': 'MANA'}]}},
        'incoming_txs':
            {'0xdeee5f8d867340bf6e56e9ae069a790ef537d400':
                {119: [{
                    'tx_hash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                    'value': Decimal(
                        '286.204800000000000000'),
                    'contract_address': '0x5a98fcbea516cf06857215779fd812ca3bef1b32',
                    'block_height': 21474469,
                    'symbol': 'LDO'}]},
                '0x52c5233d3d12e9d5522759ace8b551d926b797d1':
                    {191: [{
                        'tx_hash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                        'value': Decimal(
                            '4962.169820070000000000000000'),
                        'contract_address': '0x6982508145454ce325ddbe47a25d4ec3d2311933',
                        'block_height': 21474469,
                        'symbol': '1M_PEPE'}]},
                '0x8cd7fea8630a030ea16009914b6f8a79bea05c30':
                    {42: [{
                        'tx_hash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                        'value': Decimal(
                            '4219.190600522190000000000'),
                        'contract_address': '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce',
                        'block_height': 21474469,
                        'symbol': 'SHIB'}]},
                '0x45dcec86a1eded2af0858396f26619be801677aa':
                    {102: [{
                        'tx_hash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                        'value': Decimal('1149.493380'),
                        'contract_address': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
                        'block_height': 21474469,
                        'symbol': 'USDC'}]},
                '0xaf2a7f37df0fcad99db3714e6283ff10a56db092':
                    {13: [{
                        'tx_hash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                        'value': Decimal('27.434000'),
                        'contract_address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                        'block_height': 21474469,
                        'symbol': 'USDT'}]},
                '0x66a9e3db3bac9a4fc151bcbab4dde98f7b3932e1':
                    {13: [{
                        'tx_hash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                        'value': Decimal('21390.392592'),
                        'contract_address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                        'block_height': 21474469,
                        'symbol': 'USDT'}]},
                '0x23f6cd8c3e6f5defd7aeecfbad1f8462b92717f7':
                    {13: [{
                        'tx_hash': '0x1493b44f337b334c8ec0c7093ea7ad4b0357f6cb1cb2bfc94fabd1e990710783',
                        'value': Decimal('500.000000'),
                        'contract_address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                        'block_height': 21474469,
                        'symbol': 'USDT'}]},
                '0x25db7ce35fa802194410678745b735fdbaca4f87':
                    {97: [{
                        'tx_hash': '0xf50c316987a1423d3d9d9f086f3732fc683275a4c1c82d21c1e6b8bdb006cf67',
                        'value': Decimal('600.000000000000000000'),
                        'contract_address': None,
                        'block_height': 21474469,
                        'symbol': 'MANA'}]}}
    }

    assert BlockchainUtilsMixin.compare_dicts_without_order(expected_txs_addresses, txs_addresses)
    assert BlockchainUtilsMixin.compare_dicts_without_order(expected_txs_info, txs_info)
