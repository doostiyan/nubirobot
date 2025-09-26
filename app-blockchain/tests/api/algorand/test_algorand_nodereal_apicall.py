import pytest
from exchange.blockchain.api.algorand.algorand_algonode import NodeRealAlgorandApi
from exchange.blockchain.tests.fixtures.algo_algonode_fixtures import tx_hash_successful, tx_hash_fail, address, \
    from_block, to_block

api = NodeRealAlgorandApi


def check_general_response(response, keys):
    if set(keys).issubset(response.keys()):
        return True
    return False


@pytest.mark.slow
def test__node_real_algo__get_balance__api_call__successful(address):
    keys = {'address', 'amount', 'amount-without-pending-rewards', 'created-at-round', 'deleted', 'min-balance',
            'pending-rewards', 'reward-base', 'rewards', 'round', 'sig-type', 'status',
            'total-apps-opted-in', 'total-assets-opted-in', 'total-created-apps', 'total-created-assets',
            'total-box-bytes', 'total-boxes'}
    get_balance_result = api.get_balance(address)
    assert isinstance(get_balance_result.get('account'), dict)
    assert check_general_response(get_balance_result.get('account'), keys)
    assert isinstance(get_balance_result.get('current-round'), int)


@pytest.mark.slow
def test__node_real_algo__get_block_head__api_call__successful():
    blockhead_keys = {'transactions', 'current-round', 'next-token'}
    get_block_head_response = api.get_block_head()
    assert check_general_response(get_block_head_response, blockhead_keys)
    assert isinstance(get_block_head_response.get('current-round'), int)


@pytest.mark.slow
def test__node_real_algo__get_tx_details__api_call__successful(tx_hash_successful, tx_hash_fail):
    tx_details_keys = {'transaction', 'current-round'}
    transaction_keys = {'close-rewards', 'closing-amount', 'confirmed-round', 'fee', 'first-valid', 'genesis-hash',
                        'genesis-id', 'id', 'intra-round-offset', 'last-valid', 'payment-transaction',
                        'receiver-rewards', 'round-time', 'sender', 'sender-rewards', 'signature', 'tx-type'}
    payment_transaction_keys = {'amount', 'close-amount', 'receiver'}
    txs = [tx_hash_successful, tx_hash_fail]
    for tx_hash in txs:
        get_tx_details_response = api.get_tx_details(tx_hash)
        assert len(get_tx_details_response) != 0
        assert check_general_response(get_tx_details_response, tx_details_keys)
        if not get_tx_details_response.get('transaction'):
            continue
        if get_tx_details_response.get('transaction').get('tx-type') == 'pay':
            assert check_general_response(get_tx_details_response.get('transaction'), transaction_keys)
            assert check_general_response(
                get_tx_details_response.get('transaction').get('payment-transaction'), payment_transaction_keys)


@pytest.mark.slow
def test__node_real_algo__get_blocks_txs__api_call__successful(from_block, to_block):
    blocks_txs_keys = {'current-round', 'next-token', 'transactions'}
    transaction_keys = {'close-rewards', 'closing-amount', 'confirmed-round', 'fee', 'first-valid', 'genesis-hash',
                        'genesis-id', 'id', 'intra-round-offset', 'last-valid', 'payment-transaction',
                        'receiver-rewards', 'round-time', 'sender', 'sender-rewards', 'signature', 'tx-type'}
    payment_transaction_keys = {'amount', 'close-amount', 'receiver'}
    get_blocks_txs_response = api.get_batch_block_txs(from_block, to_block)
    assert len(get_blocks_txs_response) != 0
    assert check_general_response(get_blocks_txs_response, blocks_txs_keys)
    for transaction in get_blocks_txs_response.get('transactions'):
        if transaction.get('tx-type') == 'pay':
            assert check_general_response(transaction, transaction_keys)
            assert check_general_response(transaction.get('payment-transaction'), payment_transaction_keys)
