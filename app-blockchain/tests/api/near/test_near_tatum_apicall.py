import pytest
from exchange.blockchain.api.near.near_1rpc import NearTatumApi
from exchange.blockchain.tests.fixtures.near_tatum_fixtures import tx_hash_successful, tx_hash_failed


api = NearTatumApi()

def check_general_response(response, keys):
    if keys.issubset(set(response.keys())):
        return True
    return False

@pytest.mark.slow
def test__tatum_near__get_tx_details__api_call__successful(tx_hash_successful, tx_hash_failed):
    response_keys = {'jsonrpc', 'result', 'id'}
    result_keys = {'final_execution_status', 'receipts_outcome', 'status', 'transaction', 'transaction_outcome'}
    transaction_keys = {'actions', 'hash', 'nonce', 'public_key', 'receiver_id', 'signature', 'signer_id'}
    txs_hash = [tx_hash_successful, tx_hash_failed]
    for tx_hash in txs_hash:
        get_tx_details_response = api.get_tx_details(tx_hash)
        assert check_general_response(get_tx_details_response, response_keys)
        assert get_tx_details_response.get('result')
        assert isinstance(get_tx_details_response.get('result'), dict)
        result = get_tx_details_response.get('result')
        assert check_general_response(result, result_keys)
        assert result.get('transaction')
        assert isinstance(result.get('transaction'), dict)
        transaction = result.get('transaction')
        assert check_general_response(transaction, transaction_keys)
