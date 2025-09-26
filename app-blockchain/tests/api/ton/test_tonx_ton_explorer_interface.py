import datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from pytz import UTC

from exchange.base.models import Currencies
from exchange.blockchain.api.ton.ton_explorer_interface import TonExplorerInterface
from exchange.blockchain.api.ton.ton_tonx import TonXTonApi
from exchange.blockchain.tests.fixtures.ton_tonx_fixtures import tx_hash_successful_in_msg, tx_hash_successful_out_msg
from exchange.blockchain.tests.fixtures.ton_tonx_fixtures import tx_details_tx_hash_in_msg_mock_response, \
    tx_details_tx_hash_out_msg_mock_response
from exchange.blockchain.utils import BlockchainUtilsMixin

api = TonXTonApi
explorerInterface = TonExplorerInterface()
currencies = Currencies.ton
symbol = 'TON'
explorerInterface.tx_details_apis = [api]


@pytest.mark.skip
def test__tonx_ton__get_tx_details__explorer_interface__in_msg__successful(tx_hash_successful_in_msg,
                                                                           tx_details_tx_hash_in_msg_mock_response):
    tx_details_mock_responses = [tx_details_tx_hash_in_msg_mock_response]
    api.request = Mock(side_effect=tx_details_mock_responses)
    tx_details = explorerInterface.get_tx_details(tx_hash_successful_in_msg)
    expected_tx_details = {'block': 49859297, 'confirmations': 127702,
                           'date': datetime.datetime(2025, 2, 22, 11, 55, 32, tzinfo=UTC),
                           'fees': Decimal('0.000266669'), 'hash': 'AnyidRmybKx3I3oYbvMEGHTrawIsMvklxBVk3dBGApU=',
                           'inputs': [], 'memo': '123142978', 'outputs': [], 'raw': None, 'success': True,
                           'transfers': [{'currency': 145, 'from': 'EQAXhGlA1gdX-eqB6ClephUjdHSxfNj0Mt9fnCw8zl1Xtp94',
                                          'is_valid': True, 'memo': '123142978', 'symbol': 'TON',
                                          'to': 'EQCjLVLO2Aoj_k_pC6lFk-9obeA_n72qBp5kKCapUjS5grhs', 'token': None,
                                          'type': 'MainCoin', 'value': Decimal('1.436400000')}]}
    if tx_details.get('success'):
        tx_details['confirmations'] = expected_tx_details.get('confirmations')
    assert BlockchainUtilsMixin.compare_dicts_without_order(tx_details, expected_tx_details)

@pytest.mark.skip
def test__tonx_ton__get_tx_details__explorer_interface__out_msg__successful(tx_hash_successful_out_msg,
                                                                            tx_details_tx_hash_out_msg_mock_response):
    tx_details_mock_responses = [tx_details_tx_hash_out_msg_mock_response]
    api.request = Mock(side_effect=tx_details_mock_responses)
    tx_details = explorerInterface.get_tx_details(tx_hash_successful_out_msg)
    expected_tx_details = {'block': 49918136, 'confirmations': 95179,
                           'date': datetime.datetime(2025, 2, 24, 9, 14, 49, tzinfo=UTC),
                           'fees': Decimal('0.000321070'), 'hash': 'lljO7TqOjNQxigdp/OWM/Tto8iZAhhTu/LpcukcqVkQ=',
                           'inputs': [], 'memo': '626737281', 'outputs': [], 'raw': None, 'success': True,
                           'transfers': [{'currency': 145, 'from': 'EQC-DhIofjuR0ZlqzFHIXnpuu7UyDKffmXzRRCrD6IC5Ycwx',
                                          'is_valid': True, 'memo': '626737281', 'symbol': 'TON',
                                          'to': 'EQCjLVLO2Aoj_k_pC6lFk-9obeA_n72qBp5kKCapUjS5grhs', 'token': None,
                                          'type': 'MainCoin', 'value': Decimal('5.300000000')}]}
    if tx_details.get('success'):
        tx_details['confirmations'] = expected_tx_details.get('confirmations')
    assert BlockchainUtilsMixin.compare_dicts_without_order(tx_details, expected_tx_details)
