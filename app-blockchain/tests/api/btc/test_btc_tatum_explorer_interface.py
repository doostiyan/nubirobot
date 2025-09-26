from decimal import Decimal
import datetime
from unittest.mock import Mock
from pytz import UTC

from exchange.base.models import Currencies
from exchange.blockchain.api.btc.btc_explorer_interface import BTCExplorerInterface
from exchange.blockchain.api.btc.btc_tatum import BitcoinTatumApi
from exchange.blockchain.tests.fixtures.btc_tatum_fixtures import tx_hash
from exchange.blockchain.tests.fixtures.btc_tatum_fixtures import block_head_mock_response, \
    tx_details_mock_response_tx_hash_1
from exchange.blockchain.utils import BlockchainUtilsMixin

api = BitcoinTatumApi
symbol = 'BTC'
explorerInterface = BTCExplorerInterface()
currencies = Currencies.btc


def test__tatum_btc__get_tx_details__explorer_interface__successful(tx_hash, block_head_mock_response,
                                                                    tx_details_mock_response_tx_hash_1):
    tx_details_mock_responses = [block_head_mock_response, tx_details_mock_response_tx_hash_1]
    api.request = Mock(side_effect=tx_details_mock_responses)
    explorerInterface.tx_details_apis = [api]
    explorerInterface.block_txs_apis = [api]
    tx_details = explorerInterface.get_tx_details(tx_hash)

    expected_tx_details = {'block': 879307, 'confirmations': 30,
         'date': datetime.datetime(2025, 1, 15, 6, 57, 48, tzinfo=UTC), 'fees': Decimal(
            '0.00001115'), 'hash': '779f2698c3af0ec141d1257c76dfc9a0b21d3098b35e0fa4bbaead30001566ed', 'inputs': [],
         'memo': '', 'outputs': [], 'raw': None, 'success': True, 'transfers': [
            {'currency': 10, 'from': '1M3Tiu6PLrHkHmyEux8rkXB3bWS1mY6sXR', 'is_valid': True, 'memo': '',
             'symbol': 'BTC',
             'to': '', 'token': None, 'type': 'MainCoin', 'value': Decimal('0.00108000')},
            {'currency': 10, 'from': '', 'is_valid': True, 'memo': '', 'symbol': 'BTC',
             'to': 'bc1qzupzvgw5zsh4pzxj5zgytcftynqlklw4wn6422', 'token': None, 'type': 'MainCoin',
             'value': Decimal('0.00106104')},
            {'currency': 10, 'from': '', 'is_valid': True, 'memo': '', 'symbol': 'BTC',
             'to': '1AKArMmoZwBSE9QA2aKY3Uv2DjVTvd9JcP', 'token': None,
             'type': 'MainCoin', 'value': Decimal('0.00000781')}]}

    assert BlockchainUtilsMixin.compare_dicts_without_order(expected_tx_details, tx_details)