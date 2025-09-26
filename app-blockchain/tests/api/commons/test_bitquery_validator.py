from decimal import Decimal

from exchange.blockchain.api.commons.bitquery import BitqueryResponseParser, BitqueryValidator

BitqueryResponseParser.symbol = 'TST'


def test__validate_general_response__has_errors__return_false():
    assert not BitqueryValidator.validate_general_response({'errors': ['err']})


def test__validate_general_response__no_data__return_false():
    assert not BitqueryValidator.validate_general_response({'data': None})


def test__validate_general_response__no_bitcoin__return_false():
    assert not BitqueryValidator.validate_general_response({'data': {}})


def test__validate_general_response__empty_bitcoin__return_false():
    assert not BitqueryValidator.validate_general_response({'data': {'bitcoin': {}}})


def test__validate_balances_response__invalid_general__return_false():
    assert not BitqueryValidator.validate_balances_response({'errors': ['err']})


def test__validate_balances_response__no_addressStats__return_false():
    resp = {'data': {'bitcoin': {'alaki': ''}}}
    assert not BitqueryValidator.validate_balances_response(resp)


def test__validate_balances_response__addressStats_not_list__return_false():
    resp = {'data': {'bitcoin': {'addressStats': 5}}}
    assert not BitqueryValidator.validate_balances_response(resp)


def test__validate_balances_response__invalid_balance_dicts__return_false():
    resp = {'data': {'bitcoin': {'addressStats': [None, 1, {}]}}}
    assert not BitqueryValidator.validate_balances_response(resp)


def test__validate_balances_response__address_type_mismatch__return_false():
    resp = {'data': {'bitcoin': {'addressStats': [{'address': None}]}}}
    assert not BitqueryValidator.validate_balances_response(resp)
    resp = {'data': {'bitcoin': {'addressStats': [{'address': 1}]}}}
    assert not BitqueryValidator.validate_balances_response(resp)


def test__validate_balances_response__balance_is_none__return_false():
    resp = {'data': {'bitcoin': {'addressStats': [{'address': {'balance': None, 'address': 'a'}}]}}}
    assert not BitqueryValidator.validate_balances_response(resp)


def test__validate_balances_response__address_string_missing__return_false():
    resp = {'data': {'bitcoin': {'addressStats': [{'address': {'balance': 1}}]}}}
    assert not BitqueryValidator.validate_balances_response(resp)


def test__validate_balances_response__successful():
    resp = {'data': {'bitcoin': {'addressStats': [{'address': {'balance': 1, 'address': 'a'}}]}}}
    assert BitqueryValidator.validate_balances_response(resp)


def test__validate_block_head_response__no_blocks__return_false():
    resp = {'data': {'bitcoin': {}}}
    assert not BitqueryValidator.validate_block_head_response(resp)


def test__validate_block_head_response_blocks__not_len1__return_false():
    resp = {'data': {'bitcoin': {'blocks': [1, 2]}}}
    assert not BitqueryValidator.validate_block_head_response(resp)


def test__validate_block_head__successful():
    resp = {'data': {'bitcoin': {'blocks': [{'height': 1}]}}}
    assert BitqueryValidator.validate_block_head_response(resp)


def test__validate_block_txs_response__with_errors__return_false():
    assert not BitqueryValidator.validate_block_txs_response({'errors': ['err']})


def test__validate_block_txs_response__no_inputs__return_false():
    resp = {'data': {'bitcoin': {'alaki': ''}}}
    assert not BitqueryValidator.validate_block_txs_response(resp)


def test__validate_block_txs_response__no_outputs__return_false():
    resp = {'data': {'bitcoin': {'inputs': [1]}}}
    assert not BitqueryValidator.validate_block_txs_response(resp)


def test__validate_block_txs_response__successful():
    resp = {'data': {'bitcoin': {'inputs': [1], 'outputs': [2]}}}
    assert BitqueryValidator.validate_block_txs_response(resp)


def test__validate_block_tx_transaction__no_value__return_false():
    assert not BitqueryValidator.validate_block_tx_transaction({})


def test__validate_block_tx_transaction__below_min__return_false():
    assert not BitqueryValidator.validate_block_tx_transaction({'value': Decimal('0.0001')})


def test__validate_block_tx_transaction__successful():
    assert BitqueryValidator.validate_block_tx_transaction({'value': Decimal('0.001')})


def test__validate_block_txs_raw_response__not_dict__return_false():
    assert not BitqueryValidator.validate_block_txs_raw_response([])


def test__validate_block_txs_raw_response__no_data__return_false():
    assert not BitqueryValidator.validate_block_txs_raw_response({'foo': 1})


def test__validate_block_txs_raw_response__no_bitcoin__return_false():
    assert not BitqueryValidator.validate_block_txs_raw_response({'data': {}, 'foo': 1})


def test__validate_block_txs_raw_response__no_inputs_outputs__return_false():
    resp = {'data': {'bitcoin': {'alaki': ''}}, 'foo': 1}
    assert not BitqueryValidator.validate_block_txs_raw_response(resp)


def test__validate_block_txs_raw_response__no_bitcoin_outputs__return_false():
    resp = {'data': {'bitcoin': {}}, 'foo': 1}
    assert not BitqueryValidator.validate_block_txs_raw_response(resp)


def test__validate_block_txs_raw_response__valid_inputs__successful():
    resp = {'data': {'bitcoin': {'inputs': [1]}}, 'foo': 1}
    assert BitqueryValidator.validate_block_txs_raw_response(resp)


def test__validate_block_txs_raw_response__valid_outputs__successful():
    resp = {'data': {'bitcoin': {'outputs': [1]}}, 'foo': 1}
    assert BitqueryValidator.validate_block_txs_raw_response(resp)


def test__validate_block_txs_raw_response__valid_both__successful():
    resp = {'data': {'bitcoin': {'inputs': [1], 'outputs': [2]}}, 'foo': 1}
    assert BitqueryValidator.validate_block_txs_raw_response(resp)
