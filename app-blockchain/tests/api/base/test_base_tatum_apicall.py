import pytest

from exchange.blockchain.api.base.tatum_base import BaseTatumApi
from exchange.blockchain.tests.fixtures.base_fixtures import tx_hash_failed, tx_hash_successful

api = BaseTatumApi


def check_general_response(response, keys):
    if keys.issubset(set(response.keys())):
        return True
    return False


@pytest.mark.slow
def test__tatum_base__get_tx_details__api_call__successful(tx_hash_successful, tx_hash_failed):
    response_keys = {'blockHash', 'chainId', 'contractAddress', 'from', 'to', 'blockNumber', 'cumulativeGasUsed',
                     'effectiveGasPrice', 'gas', 'gasPrice', 'gasUsed', 'hash', 'input', 'logs', 'logsBloom', 'nonce',
                     'status', 'transactionHash', 'transactionIndex', 'type', 'value', }
    txs_hash = [tx_hash_successful, tx_hash_failed]
    for tx_hash in txs_hash:
        get_tx_details_response = api.get_tx_details(tx_hash)
        assert check_general_response(get_tx_details_response, response_keys)
