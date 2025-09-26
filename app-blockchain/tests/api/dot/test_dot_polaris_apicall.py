import pytest

from exchange.blockchain.api.dot.dot_polaris import DotPolarisApi
from exchange.blockchain.tests.fixtures.dot_polaris_fixtures import tx_hash_successful_transfer_all, \
    tx_hash_successful_transfer_allow_death, tx_hash_successful_transfer_keep_alive, \
    tx_hash_successful_utility_batch_all, from_block, to_block, \
    address_txs_address, tx_hash_fail

api = DotPolarisApi


def check_general_response(response, keys):
    if keys.issubset(set(response.keys())):
        return True
    return False


event_keys = {'module', 'function', 'extrinsicHash', 'extrinsicIdx', 'blockNumber', 'isTransferEvent', 'attributes'}
transfer_keys = {'extrinsicHash', 'module', 'function', 'isFinalized', 'blockNumber', 'fromAddress', 'toAddress',
                 'amount', 'fee', 'tip', 'events'}


def assert_tx_details_address_txs_request(response):
    if not (response and isinstance(response, dict)):
        return False
    if not (response.get('data') and isinstance(response.get('data'), dict)):
        return False
    if not (response.get('data').get('transfers') is not None and isinstance(
            response.get('data').get('transfers'), list)):
        return False
    for transfer in response.get('data').get('transfers'):
        if not check_general_response(transfer, transfer_keys):
            return False
        if not isinstance(transfer.get('events'), list):
            return False
        for event in transfer.get('events'):
            if not check_general_response(event, event_keys):
                return False
    return True


@pytest.mark.slow
def test__polaris_dot__get_block_head__api_call__successful():
    blockhead_keys = {'blockHash', 'blockNumber', 'timestamp'}
    get_block_head_response = api.get_block_head()
    assert (get_block_head_response and isinstance(get_block_head_response, dict))
    assert (get_block_head_response.get('data') and isinstance(get_block_head_response.get('data'), dict))
    assert (get_block_head_response.get('data').get('latestBlock') and isinstance(
        get_block_head_response.get('data').get('latestBlock'), dict))
    latest_block_data = get_block_head_response.get('data').get('latestBlock')
    assert check_general_response(latest_block_data, blockhead_keys)
    assert isinstance(latest_block_data.get('blockHash'), str)
    assert isinstance(latest_block_data.get('blockNumber'), int)
    assert isinstance(latest_block_data.get('timestamp'), str)


@pytest.mark.slow
def test__polaris_dot__get_address_txs__api_call__successful(address_txs_address):
    get_address_txs_response = api.get_address_txs(address_txs_address)
    assert assert_tx_details_address_txs_request(get_address_txs_response)


@pytest.mark.slow
def test__polaris_dot__get_tx_details__api_call__successful(tx_hash_successful_transfer_all,
                                                            tx_hash_successful_transfer_allow_death,
                                                            tx_hash_successful_utility_batch_all,
                                                            tx_hash_successful_transfer_keep_alive, tx_hash_fail):
    hash_of_transactions = [tx_hash_successful_transfer_all, tx_hash_successful_transfer_keep_alive,
                            tx_hash_successful_transfer_allow_death, tx_hash_successful_utility_batch_all, tx_hash_fail]
    for tx_hash in hash_of_transactions:
        tx_details_response = api.get_tx_details(tx_hash)
        assert assert_tx_details_address_txs_request(tx_details_response)


@pytest.mark.slow
def test__polaris_dot__get_blocks_txs__api_call__successful(from_block, to_block):
    get_block_txs_response = api.get_batch_block_txs(from_block, to_block)
    block_keys = {'blockHash', 'blockNumber', 'timestamp'}
    assert (get_block_txs_response and isinstance(get_block_txs_response, dict))
    assert (get_block_txs_response.get('data') and isinstance(get_block_txs_response.get('data'), dict))
    assert (get_block_txs_response.get('data').get('blockRange') is not None and isinstance(
        get_block_txs_response.get('data').get('blockRange'), list))
    for block in get_block_txs_response.get('data').get('blockRange'):
        assert check_general_response(block, block_keys)
        assert isinstance(block.get('blockHash'), str)
        assert isinstance(block.get('blockNumber'), int)
        assert isinstance(block.get('timestamp'), str)
        assert (block.get('transfers') is not None and isinstance(block.get('transfers'), list))
        for transfer in block.get('transfers'):
            assert check_general_response(transfer, transfer_keys)
            assert isinstance(transfer.get('events'), list)
            for event in transfer.get('events'):
                check_general_response(event, event_keys)
