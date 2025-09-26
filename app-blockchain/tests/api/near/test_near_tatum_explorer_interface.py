from decimal import Decimal

from exchange.base.models import Currencies
from exchange.blockchain.api.near.near_explorer_interface import NearExplorerInterface
from exchange.blockchain.api.near.near_1rpc import NearTatumApi
from exchange.blockchain.tests.fixtures.near_tatum_fixtures import tx_hash_successful, tx_hash_failed
from exchange.blockchain.tests.fixtures.near_tatum_fixtures import tx_details_tx_hash_successful_mock_response, \
    tx_details_tx_hash_failed_mock_response
from unittest.mock import Mock
from exchange.blockchain.utils import BlockchainUtilsMixin

api = NearTatumApi
explorerInterface = NearExplorerInterface()
currencies = Currencies.near
symbol = 'NEAR'
explorerInterface.tx_details_apis = [api]


def test__tatum_near__get_tx_details__explorer_interface__successful(tx_hash_successful,
                                                                     tx_details_tx_hash_successful_mock_response):
    tx_details_mock_responses = [tx_details_tx_hash_successful_mock_response]
    api.request = Mock(side_effect=tx_details_mock_responses)
    tx_details = explorerInterface.get_tx_details(tx_hash_successful)
    expected_tx_details = {'block': None, 'confirmations': 0, 'date': None, 'fees': None,
                           'hash': 'EYf7MFDneobGfVWXwjJGbc7gSJWsafUbPxfap5BVBVx', 'inputs': [], 'memo': None,
                           'outputs': [], 'raw': None, 'success': True, 'transfers': [
            {'currency': 84, 'from': 'eb3c2bfd6bf357f433be30292d78b23f948ee75f63baca2cc5f56cff1751c294',
             'is_valid': True, 'memo': None, 'symbol': 'NEAR',
             'to': 'e9b2fd9f3a6280ab37f6ce6909f4487aa86e76be3627c83583c0c69a11dd0fe1', 'token': None,
             'type': 'MainCoin', 'value': Decimal('0.999000000000000000000000')}]}
    assert BlockchainUtilsMixin.compare_dicts_without_order(tx_details, expected_tx_details)


def test__tatum_near__get_tx_details__explorer_interface__failed(tx_hash_failed,
                                                                 tx_details_tx_hash_failed_mock_response):
    tx_details_mock_responses = [tx_details_tx_hash_failed_mock_response]
    api.request = Mock(side_effect=tx_details_mock_responses)
    tx_details = explorerInterface.get_tx_details(tx_hash_failed)
    expected_tx_details = {'success': False}
    assert BlockchainUtilsMixin.compare_dicts_without_order(tx_details, expected_tx_details)
