from decimal import Decimal
from unittest.mock import Mock

from exchange.base.models import Currencies
from exchange.blockchain.api.doge import DogeExplorerInterface
from exchange.blockchain.api.doge.doge_tatum import DogeTatumApi
from exchange.blockchain.tests.fixtures.doge_tatum_fixtures import tx_hash, tx_hash_aggregation
from exchange.blockchain.tests.fixtures.doge_tatum_fixtures import tx_details_tx_hash_mock_response, \
    tx_details_tx_hash_from_address_mock_response, tx_details_tx_hash_aggregation_mock_response, \
    tx_details_tx_hash_aggregation_from_address_mock_response
from exchange.blockchain.utils import BlockchainUtilsMixin

api = DogeTatumApi
symbol = 'DOGE'
explorerInterface = DogeExplorerInterface()
currencies = Currencies.doge
explorerInterface.tx_details_apis = [api]


def test__tatum_doge__get_tx_details__explorer_interface__successful(tx_hash, tx_details_tx_hash_mock_response,
                                                                     tx_details_tx_hash_from_address_mock_response):
    tx_details_mock_responses = [
        tx_details_tx_hash_mock_response, tx_details_tx_hash_from_address_mock_response
    ]
    api.request = Mock(side_effect=tx_details_mock_responses)
    tx_details = explorerInterface.get_tx_details(tx_hash)
    expected_txs_details = {'block': None, 'confirmations': 0, 'date': None, 'fees': None,
                            'hash': '7c8c8088108ebaf9a6fcfc9273e52e68e4d5e089eeb4007e6149b414c8bb4b9a', 'inputs': [],
                            'memo': '', 'outputs': [], 'raw': None, 'success': True, 'transfers': [
            {'currency': 18, 'from': 'DJ4byAYWH6BuSx8ReLzkUr7ThSwzdvhQ93', 'is_valid': True, 'memo': '',
             'symbol': 'DOGE', 'to': '', 'token': None, 'type': 'MainCoin', 'value': Decimal('145.40124555')},
            {'currency': 18, 'from': '', 'is_valid': True, 'memo': '', 'symbol': 'DOGE',
             'to': 'DDdQHoebn7uhvuUCgaoDGLrvCFp4dy5c48', 'token': None, 'type': 'MainCoin',
             'value': Decimal('145.331')}]}
    BlockchainUtilsMixin.compare_dicts_without_order(expected_txs_details, tx_details)


def test__tatum_doge__get_tx_details__aggregation__explorer_interface__successful(tx_hash_aggregation,
                                                                                  tx_details_tx_hash_aggregation_mock_response,
                                                                                  tx_details_tx_hash_aggregation_from_address_mock_response):
    tx_details_mock_responses = [
        tx_details_tx_hash_aggregation_mock_response, tx_details_tx_hash_aggregation_from_address_mock_response
    ]
    api.request = Mock(side_effect=tx_details_mock_responses)
    tx_details = explorerInterface.get_tx_details(tx_hash_aggregation)
    expected_txs_details = {'block': None, 'confirmations': 0, 'date': None, 'fees': None,
                            'hash': '4494d6be3168ff70c6538c273f925446b477c1b4752d1fd7f076c2da6c2d3d10', 'inputs': [],
                            'memo': '', 'outputs': [], 'raw': None, 'success': True, 'transfers': [
            {'currency': 18, 'from': 'DDz1H7AcqPgmKzFEP3pBHW5b1GWuWEoAAP', 'is_valid': True, 'memo': '',
             'symbol': 'DOGE', 'to': '', 'token': None, 'type': 'MainCoin', 'value': Decimal('299177.12756900')},
            {'currency': 18, 'from': '', 'is_valid': True, 'memo': '', 'symbol': 'DOGE',
             'to': 'DBEYazMywpqaFUt4su2vxjPGhRVPkGGP7U', 'token': None, 'type': 'MainCoin', 'value': Decimal('244964')},
            {'currency': 18, 'from': '', 'is_valid': True, 'memo': '', 'symbol': 'DOGE',
             'to': 'D67kvFnJnJxxHxnNyDhMghC1bfZ74922XA', 'token': None, 'type': 'MainCoin', 'value': Decimal('54213')}]}
    BlockchainUtilsMixin.compare_dicts_without_order(expected_txs_details, tx_details)
