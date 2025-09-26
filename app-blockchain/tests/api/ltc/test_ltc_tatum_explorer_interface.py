from decimal import Decimal
import datetime
from unittest.mock import Mock
from pytz import UTC

from exchange.base.models import Currencies
from exchange.blockchain.api.ltc.ltc_explorer_interface import LTCExplorerInterface
from exchange.blockchain.api.ltc.ltc_tatum import LiteCoinTatumApi
from exchange.blockchain.tests.fixtures.ltc_tatum_fixtures import tx_hash, tx_hash_aggregation
from exchange.blockchain.tests.fixtures.ltc_tatum_fixtures import block_head_mock_response, \
    tx_details_mock_response_tx_hash, tx_details_mock_response_tx_hash_aggregation
from exchange.blockchain.utils import BlockchainUtilsMixin

api = LiteCoinTatumApi
symbol = 'LTC'
explorerInterface = LTCExplorerInterface()
currencies = Currencies.ltc


def test__tatum_ltc__get_tx_details__explorer_interface__successful(tx_hash, block_head_mock_response,
                                                                    tx_details_mock_response_tx_hash):
    tx_details_mock_responses = [
        block_head_mock_response, tx_details_mock_response_tx_hash
    ]
    api.request = Mock(side_effect=tx_details_mock_responses)
    explorerInterface.tx_details_apis = [api]
    explorerInterface.block_txs_apis = [api]
    tx_details = explorerInterface.get_tx_details(tx_hash)
    expected_tx_details = {'block': 2707106, 'confirmations': 114923,
                           'date': datetime.datetime(2024, 6, 22, 2, 28, 19, tzinfo=UTC), 'fees': Decimal('0.000037'),
                           'hash': 'a9e13035052225a65ed7d9fd400d65a57e471d1d1fbf7121207f803e4e9681ef', 'inputs': [],
                           'memo': '', 'outputs': [], 'raw': None, 'success': True, 'transfers': [
            {'currency': 12, 'from': 'Lc8H5EAFBKbGmnJGRNGkLVpLY9XXaeiujw', 'is_valid': True, 'memo': '',
             'symbol': api.symbol, 'to': '', 'token': None, 'type': 'MainCoin', 'value': Decimal('0.04335659')},
            {'currency': 12, 'from': '', 'is_valid': True, 'memo': '', 'symbol': api.symbol,
             'to': 'MKJ3hKvF75dA47PyFceqK8P1jpsFqJzLYJ', 'token': None, 'type': 'MainCoin',
             'value': Decimal('0.01390822')},
            {'currency': 12, 'from': '', 'is_valid': True, 'memo': '', 'symbol': api.symbol,
             'to': 'ltc1qz89kssmkzqh6z4p2f0f5wnj7fmdjx0a8sxxvju', 'token': None, 'type': 'MainCoin',
             'value': Decimal('0.02941137')}]}

    assert BlockchainUtilsMixin.compare_dicts_without_order(tx_details, expected_tx_details)


def test__tatum_ltc__get_tx_details__aggregation__explorer_interface__successful(tx_hash_aggregation,
                                                                                 block_head_mock_response,
                                                                                 tx_details_mock_response_tx_hash_aggregation):
    tx_details_mock_responses = [
        block_head_mock_response, tx_details_mock_response_tx_hash_aggregation
    ]
    api.request = Mock(side_effect=tx_details_mock_responses)
    explorerInterface.tx_details_apis = [api]
    explorerInterface.block_txs_apis = [api]
    tx_details = explorerInterface.get_tx_details(tx_hash_aggregation)
    expected_tx_details = {'block': 2707106, 'confirmations': 114923,
                           'date': datetime.datetime(2024, 6, 22, 2, 28, 19, tzinfo=UTC), 'fees': Decimal('0.0000336'),
                           'hash': '83b41ceb8e79209bec1c82aa0ae8c9a83db87e6e199f764a167b6ee5e01a3026', 'inputs': [],
                           'memo': '', 'outputs': [], 'raw': None, 'success': True, 'transfers': [
            {'currency': 12, 'from': 'MRnv1iF722SUsrFZxmZSg1Ey7Vhghy8Gz6', 'is_valid': True, 'memo': '',
             'symbol': api.symbol, 'to': '', 'token': None, 'type': 'MainCoin', 'value': Decimal('0.04944048')},
            {'currency': 12, 'from': 'MRSXyMETyqz1zrAvNjhHNsspDz1vGjZv6f', 'is_valid': True, 'memo': '',
             'symbol': api.symbol, 'to': '', 'token': None, 'type': 'MainCoin', 'value': Decimal('0.00059312')},
            {'currency': 12, 'from': '', 'is_valid': True, 'memo': '', 'symbol': api.symbol,
             'to': 'Lbj6aqXbjagnyJhvbtArC5ozQhksmdL5mV', 'token': None, 'type': 'MainCoin', 'value': Decimal('0.05')}]}

    assert BlockchainUtilsMixin.compare_dicts_without_order(tx_details, expected_tx_details)