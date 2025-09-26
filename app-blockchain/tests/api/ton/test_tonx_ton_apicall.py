import pytest
from exchange.blockchain.api.ton.ton_tonx import TonXTonApi
from exchange.blockchain.tests.fixtures.ton_tonx_fixtures import tx_hash_successful_in_msg, tx_hash_successful_out_msg

api = TonXTonApi()


def check_general_response(response, keys):
    if keys.issubset(set(response.keys())):
        return True
    return False


@pytest.mark.slow
def test__tonx_ton__get_tx_details__api_call__successful(tx_hash_successful_in_msg, tx_hash_successful_out_msg):
    response_keys = {'jsonrpc', 'result', 'id'}
    result_keys = {'hash', 'now', 'lt', 'orig_status', 'end_status', 'description', 'in_msg', 'out_msgs'}
    description_keys = {'type', 'action', 'aborted', 'destroyed', 'compute_ph'}
    in_out_msg_keys = {'source_friendly', 'source', 'destination', 'destination_friendly', 'value', 'opcode', 'fwd_fee',
                       'message_content'}
    txs_hash = [tx_hash_successful_out_msg, tx_hash_successful_in_msg]
    for tx_hash in txs_hash:
        get_tx_details_response = api.get_tx_details(tx_hash)
        assert check_general_response(get_tx_details_response, response_keys)
        assert get_tx_details_response.get('result')
        assert isinstance(get_tx_details_response.get('result'), list)
        result = get_tx_details_response.get('result')[0]
        assert check_general_response(result, result_keys)
        assert result.get('description')
        assert isinstance(result.get('description'), dict)
        description = result.get('description')
        assert check_general_response(description, description_keys)
        if not result.get('in_msg').get('source_friendly'):
            out_msg = result.get('out_msgs').get('out_msgs')[0]
            assert check_general_response(out_msg, in_out_msg_keys)
        else:
            in_msg = result.get('in_msg')
            assert check_general_response(in_msg, in_out_msg_keys)
