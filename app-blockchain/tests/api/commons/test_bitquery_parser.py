from decimal import Decimal
from unittest.mock import patch

import pytest

from exchange.blockchain.api.commons.bitquery import BitqueryResponseParser, BitqueryValidator
from exchange.blockchain.api.general.dtos import Balance, TransferTx


def test__parse_balances__successful():
    resp = {'data': {'bitcoin': {'addressStats': [{'address': {'balance': 1, 'address': 'a'}}]}}}
    balances = BitqueryResponseParser.parse_balances_response(resp)
    assert len(balances) == 1
    assert isinstance(balances[0], Balance)


def test__parse_balances__response_invalid__return_empty():
    resp = {'data': {'bitcoin': {'addressStats': 5}}}
    balances = BitqueryResponseParser.parse_balances_response(resp)
    assert balances == []


def test__convert_address__successful():
    assert BitqueryResponseParser.convert_address('abc') == 'abc'


def test__parse_block_head__successful():
    resp = {'data': {'bitcoin': {'blocks': [{'height': 123}]}}}
    with patch.object(BitqueryValidator, 'validate_block_head_response', return_value=True):
        assert BitqueryResponseParser.parse_block_head_response(resp) == 123


def test__parse_block_head__response_invalid__return_none():
    resp = {'data': {'bitcoin': {'blocks': [{'height': 123}]}}}
    with patch.object(BitqueryValidator, 'validate_block_head_response', return_value=False):
        assert BitqueryResponseParser.parse_block_head_response(resp) is None


def test__parse_batch_block_txs__successful():
    resp = {
        'data': {
            'bitcoin': {
                'inputs': [
                    {'block': {'height': 1}, 'inputAddress': {'address': 'A'}, 'value': Decimal('1.0'),
                     'transaction': {'hash': 'h1'}},
                ],
                'outputs': [
                    {'block': {'height': 1}, 'outputAddress': {'address': 'B'}, 'value': Decimal('2.0'),
                     'transaction': {'hash': 'h1'}},
                    {'block': {'height': 1}, 'outputAddress': {'address': 'A'}, 'value': Decimal('1.0'),
                     'transaction': {'hash': 'h1'}},
                ]
            }
        }
    }
    with patch.object(BitqueryValidator, 'validate_block_txs_response', return_value=True), \
            patch.object(BitqueryValidator, 'validate_block_tx_transaction', return_value=True):
        txs = BitqueryResponseParser.parse_batch_block_txs_response(resp)
        assert all(isinstance(tx, TransferTx) for tx in txs)
        assert any(tx.from_address == 'A' or tx.to_address == 'B' for tx in txs)


def test__parse_batch_block_txs_response__invalid_response__return_empty():
    resp = {
        'data': {
            'bitcoin': {
                'inputs': [
                    {'block': {'height': 1}, 'inputAddress': {'address': 'A'}, 'value': Decimal('1.0'),
                     'transaction': {'hash': 'h1'}},
                ],
                'outputs': [
                    {'block': {'height': 1}, 'outputAddress': {'address': 'B'}, 'value': Decimal('2.0'),
                     'transaction': {'hash': 'h1'}},
                ]
            }
        }
    }
    with patch.object(BitqueryValidator, 'validate_block_txs_response', return_value=False):
        assert BitqueryResponseParser.parse_batch_block_txs_response(resp) == []


def test__parse_batch_block_txs_response__input_output_tx_not_valid__return_empty():
    resp = {
        'data': {
            'bitcoin': {
                'inputs': [
                    {'block': {'height': 1}, 'inputAddress': {'address': 'A'}, 'value': Decimal('1.0'),
                     'transaction': {'hash': 'h1'}},
                ],
                'outputs': [
                    {'block': {'height': 1}, 'outputAddress': {'address': 'B'}, 'value': Decimal('2.0'),
                     'transaction': {'hash': 'h1'}},
                ]
            }
        }
    }
    with patch.object(BitqueryValidator, 'validate_block_txs_response', return_value=True), \
            patch.object(BitqueryValidator, 'validate_block_tx_transaction', return_value=False):
        assert BitqueryResponseParser.parse_batch_block_txs_response(resp) == []


def test__parse_block_transfer_tx__invalid_direction__throw_error():
    tx = {'block': {'height': 1}, 'outputAddress': {'address': 'B'}, 'value': 1, 'transaction': {'hash': 'h'}}
    with pytest.raises(ValueError):
        BitqueryResponseParser._parse_block_transfer_tx(tx, 'other')
