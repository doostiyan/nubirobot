import pytest
from exchange.blockchain.api.doge.doge_tatum import DogeTatumApi
from exchange.blockchain.tests.fixtures.doge_tatum_fixtures import tx_hash, tx_hash_aggregation

api = DogeTatumApi()


def check_general_response(response, keys):
    if set(keys).issubset(response.keys()):
        return True
    return False


@pytest.mark.slow
def test__tatum_doge__get_block_head__api_call__successful():
    get_block_head_response = api.get_block_head()
    block_head_keys = {'chain', 'blocks', 'headers', 'bestblockhash', 'difficulty'}
    assert isinstance(get_block_head_response, dict)
    assert check_general_response(get_block_head_response, block_head_keys)


@pytest.mark.slow
def test__tatum_btc__get_tx_details__api_call__successful(tx_hash, tx_hash_aggregation):
    txs_hash = [tx_hash, tx_hash_aggregation]
    tx_details_keys = {'hash', 'vin', 'vout'}
    tx_details_keys_types = [('hash', str), ('vin', list), ('vout', list)]
    input_keys = {'txid', 'vout', 'scriptSig'}
    input_key_types = [('txid', str), ('vout', int), ('scriptSig', dict)]
    output_keys = {'value', 'scriptPubKey'}
    output_key_stypes = [('scriptPubKey', dict)]

    for tx_hash in txs_hash:
        get_tx_details_response = api.get_tx_details(tx_hash)
        assert isinstance(get_tx_details_response, dict)
        assert check_general_response(get_tx_details_response, tx_details_keys)
        for key, value in tx_details_keys_types:
            assert isinstance(get_tx_details_response.get(key), value)
        assert get_tx_details_response.get('vin')
        assert isinstance(get_tx_details_response.get('vin'), list)
        for input in get_tx_details_response.get('vin'):
            assert isinstance(input, dict)
            assert check_general_response(input, input_keys)
            for key, value in input_key_types:
                assert isinstance(input.get(key), value)
        assert get_tx_details_response.get('vout')
        assert isinstance(get_tx_details_response.get('vout'), list)
        for output in get_tx_details_response.get('vout'):
            assert isinstance(output, dict)
            assert check_general_response(output, output_keys)
            for key, value in output_key_stypes:
                assert isinstance(output.get(key), value)
