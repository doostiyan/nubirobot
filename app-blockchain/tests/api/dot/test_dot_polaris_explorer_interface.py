from exchange.blockchain.api.dot.dot_polaris import DotPolarisApi
from decimal import Decimal
from unittest.mock import Mock

from exchange.base.models import Currencies
from exchange.blockchain.api.dot.dot_explorer_interface import DotExplorerInterface
from exchange.blockchain.tests.fixtures.dot_polaris_fixtures import tx_hash_successful_transfer_all, \
    tx_hash_successful_transfer_allow_death, tx_hash_successful_transfer_keep_alive, \
    tx_hash_successful_utility_batch_all, from_block, to_block, \
    address_txs_address, tx_hash_fail
from exchange.blockchain.tests.fixtures.dot_polaris_fixtures import tx_details_tx_hash_fail_mock_response, \
    tx_details_tx_hash_transfer_allow_death_mock_response, tx_details_tx_hash_transfer_keep_alive_mock_response, \
    tx_details_tx_hash_utility_batch_all_mock_response, \
    tx_details_tx_hash_transfer_all_mock_response, \
    address_txs_mock_response, block_txs_mock_response, block_head_mock_response
from exchange.blockchain.utils import BlockchainUtilsMixin

api = DotPolarisApi

explorerInterface = DotExplorerInterface()
currencies = Currencies.dot
symbol = 'DOT'
explorerInterface.tx_details_apis = [api]
explorerInterface.address_txs_apis = [api]
explorerInterface.block_head_apis = [api]
explorerInterface.block_txs_apis = [api]


def test__polaris_dot__get_tx_details__explorer_interface__transfer_all__successful(tx_hash_successful_transfer_all,
                                                                                    tx_details_tx_hash_transfer_all_mock_response,
                                                                                    block_head_mock_response):
    tx_details_mock_responses = [block_head_mock_response, tx_details_tx_hash_transfer_all_mock_response]
    api.request = Mock(side_effect=tx_details_mock_responses)
    tx_details = explorerInterface.get_tx_details(tx_hash_successful_transfer_all)
    expected_tx_details = {'block': 25771671, 'confirmations': 1434, 'date': None, 'fees': Decimal('0.0153293982'),
                           'hash': '0x02d4fbc7a2842db2cd7e6ec89f65912584b683fe50191a68f9dede45795b1e97', 'inputs': [],
                           'memo': None, 'outputs': [], 'raw': None, 'success': True, 'transfers': [
            {'currency': 34, 'from': '12ByC23YDTxxepAgxA5K38N9wxGkQDeUZAj3fz7MSYqTS4Wx', 'is_valid': True, 'memo': None,
             'symbol': 'DOT', 'to': '1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7', 'token': None,
             'type': 'MainCoin', 'value': Decimal('317.6963933818')}]}
    if tx_details.get('success'):
        tx_details['confirmations'] = expected_tx_details.get('confirmations')
    assert BlockchainUtilsMixin.compare_dicts_without_order(tx_details, expected_tx_details)


def test__polaris_dot__get_tx_details__explorer_interface__transfer_allow_death__successful(
        tx_hash_successful_transfer_allow_death,
        tx_details_tx_hash_transfer_allow_death_mock_response,
        block_head_mock_response):
    tx_details_mock_responses = [block_head_mock_response, tx_details_tx_hash_transfer_allow_death_mock_response]
    api.request = Mock(side_effect=tx_details_mock_responses)
    tx_details = explorerInterface.get_tx_details(tx_hash_successful_transfer_allow_death)
    expected_tx_details = {'block': 25772140, 'confirmations': 965, 'date': None, 'fees': Decimal('0.0161305248'),
                           'hash': '0xe261441e5d2cd771452078b6e25a37161446605966f0f1a7a2bd538435e7c670', 'inputs': [],
                           'memo': None, 'outputs': [], 'raw': None, 'success': True, 'transfers': [
            {'currency': 34, 'from': '1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7', 'is_valid': True, 'memo': None,
             'symbol': 'DOT', 'to': '16eQrUMFZKyFXqYh4Ntdf8HZfUFYbJekcJuZLEjny11PqLDT', 'token': None,
             'type': 'MainCoin', 'value': Decimal('25.0000000000')}]}
    if tx_details.get('success'):
        tx_details['confirmations'] = expected_tx_details.get('confirmations')
    assert BlockchainUtilsMixin.compare_dicts_without_order(tx_details, expected_tx_details)


def test__polaris_dot__get_tx_details__explorer_interface__transfer_keep_alive__successful(
        tx_hash_successful_transfer_keep_alive,
        tx_details_tx_hash_transfer_keep_alive_mock_response,
        block_head_mock_response):
    tx_details_mock_responses = [block_head_mock_response, tx_details_tx_hash_transfer_keep_alive_mock_response]
    api.request = Mock(side_effect=tx_details_mock_responses)
    tx_details = explorerInterface.get_tx_details(tx_hash_successful_transfer_keep_alive)
    expected_tx_details = {'block': 25772000, 'confirmations': 1105, 'date': None, 'fees': Decimal('0.0162203062'),
                           'hash': '0x86fe92a3bded6cefafd6d55edc375f5f9c2c7ce82c969d74f3fb878b9ee080cb', 'inputs': [],
                           'memo': None, 'outputs': [], 'raw': None, 'success': True, 'transfers': [
            {'currency': 34, 'from': '12nr7GiDrYHzAYT9L8HdeXnMfWcBuYfAXpgfzf3upujeCciz', 'is_valid': True, 'memo': None,
             'symbol': 'DOT', 'to': '12ByC23YDTxxepAgxA5K38N9wxGkQDeUZAj3fz7MSYqTS4Wx', 'token': None,
             'type': 'MainCoin', 'value': Decimal('258.1292828000')}]}
    if tx_details.get('success'):
        tx_details['confirmations'] = expected_tx_details.get('confirmations')
    assert BlockchainUtilsMixin.compare_dicts_without_order(tx_details, expected_tx_details)


def test__polaris_dot__get_tx_details__explorer_interface__utility_batch_all__successful(
        tx_hash_successful_utility_batch_all,
        tx_details_tx_hash_utility_batch_all_mock_response,
        block_head_mock_response):
    tx_details_mock_responses = [block_head_mock_response, tx_details_tx_hash_utility_batch_all_mock_response]
    api.request = Mock(side_effect=tx_details_mock_responses)
    tx_details = explorerInterface.get_tx_details(tx_hash_successful_utility_batch_all)
    expected_tx_details = {'block': 25899774, 'confirmations': 965, 'date': None, 'fees': Decimal('0.0207759772'),
                           'hash': '0x0672369bfab4fc72c5c778344780e7446ad1947076c688a35f55f35ee5678a0f', 'inputs': [],
                           'memo': None, 'outputs': [], 'raw': None, 'success': True, 'transfers': [
            {'currency': 34, 'from': '1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7', 'is_valid': True, 'memo': None,
             'symbol': 'DOT', 'to': '1UHqx94H2v7CHWeyaexnD8R6ZnpBCdh74cQfoFh33Ubtf1u', 'token': None,
             'type': 'MainCoin', 'value': Decimal('7.8000000000')},
            {'currency': 34, 'from': '1qnJN7FViy3HZaxZK9tGAA71zxHSBeUweirKqCaox4t8GT7', 'is_valid': True, 'memo': None,
             'symbol': 'DOT', 'to': '15hom8Ej7xJSALZfDXcuGvMyBeJtvaTbDcJaajsE5XXNKPSP', 'token': None,
             'type': 'MainCoin', 'value': Decimal('1235.0851819400')}]}
    if tx_details.get('success'):
        tx_details['confirmations'] = expected_tx_details.get('confirmations')
    assert BlockchainUtilsMixin.compare_dicts_without_order(tx_details, expected_tx_details)


def test__polaris_dot__get_tx_details__explorer_interface__fail(
        tx_hash_fail,
        tx_details_tx_hash_fail_mock_response,
        block_head_mock_response):
    tx_details_mock_responses = [block_head_mock_response, tx_details_tx_hash_fail_mock_response]
    api.request = Mock(side_effect=tx_details_mock_responses)
    tx_details = explorerInterface.get_tx_details(tx_hash_fail)
    expected_tx_details = {'success': False}
    assert BlockchainUtilsMixin.compare_dicts_without_order(tx_details, expected_tx_details)


def test__polaris_dot__get_txs__explorer_interface_successful(address_txs_address, address_txs_mock_response,
                                                              block_head_mock_response):
    address_txs_mock_responses = [block_head_mock_response, address_txs_mock_response]
    api.request = Mock(side_effect=address_txs_mock_responses)
    address_txs = explorerInterface.get_txs(address_txs_address)
    expected_tx_details = [{Currencies.dot: {'address': '12xtAYsRUrmbniiWQqJtECiBQrMn8AypQcXhnQAc6RB6XkLW',
                                             'amount': Decimal('1989.9830694752'), 'block': 25773048,
                                             'confirmations': 57,
                                             'date': None, 'direction': 'incoming',
                                             'from_address': '14KVE545ypr51NFAZqPXFhWALqqJSXXaS7PQ4bPXPT8m5sLz',
                                             'hash': '0x5f858e14489d6b11758fc50038234a628e3a993f0a58b8c9a044382e5b26d522',
                                             'memo': None, 'raw': None,
                                             'to_address': '12xtAYsRUrmbniiWQqJtECiBQrMn8AypQcXhnQAc6RB6XkLW'}}]
    assert expected_tx_details == address_txs


def test__polaris_dot_blocks_txs__explorer_interface_successful(from_block, to_block, block_txs_mock_response):
    blocks_txs_mock_responses = [block_txs_mock_response]
    api.request = Mock(side_effect=blocks_txs_mock_responses)
    blocks_txs = explorerInterface.get_latest_block(from_block, to_block, include_inputs=True, include_info=True)
    expected_input_addresses = {'134a6Qj1XnkoVNy6qr9rHCT5RhKAxbFnFWiGL6NHRacdNpzj'}
    expected_output_addresses = {'124fm7rSHqAvzuhk3XkeQJooEhxAAssQAvjtRqPAd6Yk3hcR'}
    expected_outgoing_txs = {'134a6Qj1XnkoVNy6qr9rHCT5RhKAxbFnFWiGL6NHRacdNpzj': {34: [
        {'block_height': 25771587, 'contract_address': None, 'index': None, 'symbol': 'DOT',
         'tx_hash': '0x99e2a8a9c06dab90b622cbed043e9f836d6319aa8741eccf49bfe64370dd3dac',
         'value': Decimal('1011.5234416900')}]}
    }
    expected_incoming_txs = {'124fm7rSHqAvzuhk3XkeQJooEhxAAssQAvjtRqPAd6Yk3hcR': {34: [
        {'block_height': 25771587, 'contract_address': None, 'index': None, 'symbol': 'DOT',
         'tx_hash': '0x99e2a8a9c06dab90b622cbed043e9f836d6319aa8741eccf49bfe64370dd3dac',
         'value': Decimal('1011.5234416900')}]}}
    assert expected_input_addresses == blocks_txs[0].get('input_addresses')
    assert expected_output_addresses == blocks_txs[0].get('output_addresses')
    assert BlockchainUtilsMixin.compare_dicts_without_order(expected_incoming_txs, blocks_txs[1].get('incoming_txs'))
    assert BlockchainUtilsMixin.compare_dicts_without_order(expected_outgoing_txs, blocks_txs[1].get('outgoing_txs'))
