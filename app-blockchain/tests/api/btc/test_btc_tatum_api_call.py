import pytest
from exchange.blockchain.api.btc.btc_tatum import BitcoinTatumApi
from exchange.blockchain.tests.fixtures.btc_tatum_fixtures import tx_hash


api = BitcoinTatumApi


def check_general_response(response, keys):
    if set(keys).issubset(response.keys()):
        return True
    return False


@pytest.mark.slow
def test__tatum_btc__get_block_head__api_call__successful():
    get_block_head_response = api.get_block_head()
    block_head_keys = {'chain', 'blocks', 'headers', 'bestblockhash', 'difficulty'}
    assert isinstance(get_block_head_response, dict)
    assert check_general_response(get_block_head_response, block_head_keys)


@pytest.mark.slow
def test__tatum_btc__get_tx_details__api_call__successful(tx_hash):
    tx_details_keys = {'blockNumber', 'fee', 'hash', 'inputs', 'outputs', 'time'}
    tx_details_keys_types = [('blockNumber', int), ('fee', int), ('hash', str), ('inputs', list),
                             ('outputs', list), ('time', int)]
    input_keys = {'prevout', 'sequence', 'script', 'coin'}
    input_key_stypes = [('prevout', dict), ('sequence', int), ('script', str), ('coin', dict)]
    output_keys = {'value', 'script', 'address'}
    output_key_stypes = [('value', int), ('script', str), ('address', str)]
    get_tx_details_response = api.get_tx_details(tx_hash)
    assert isinstance(get_tx_details_response, dict)
    assert check_general_response(get_tx_details_response, tx_details_keys)
    for key, value in tx_details_keys_types:
        assert isinstance(get_tx_details_response.get(key), value)
    assert get_tx_details_response.get('inputs')
    assert isinstance(get_tx_details_response.get('inputs'), list)
    for input in get_tx_details_response.get('inputs'):
        assert isinstance(input, dict)
        assert check_general_response(input, input_keys)
        for key, value in input_key_stypes:
            assert isinstance(input.get(key), value)
    assert get_tx_details_response.get('outputs')
    assert isinstance(get_tx_details_response.get('outputs'), list)
    for output in get_tx_details_response.get('outputs'):
        assert isinstance(output, dict)
        assert check_general_response(output, output_keys)
        for key, value in output_key_stypes:
            assert isinstance(output.get(key), value)