import pytest

from exchange.blockchain.api.hedera.hedera_mirrornode import QuickNodeHederaApi
from exchange.blockchain.tests.fixtures.hbar_quicknode_fixtures import tx_details_fail_transaction, \
    tx_details_invalid_transaction, tx_details_successful_transaction, account_address

api = QuickNodeHederaApi


def check_general_response(response, keys):
    if keys.issubset(set(response.keys())):
        return True
    return False


@pytest.mark.slow
def test__quick_node_hbar__get_balance__api_call__successful(account_address):
    keys = {'timestamp', 'balances', 'links'}
    balances_keys = {'account', 'balance', 'tokens'}
    get_balance_result = api.get_balance(account_address)
    assert check_general_response(get_balance_result, keys)
    assert len(get_balance_result.get('balances')) > 0
    assert check_general_response(get_balance_result.get('balances')[0], balances_keys)
    assert isinstance(get_balance_result.get('balances')[0].get('balance'), int)


@pytest.mark.slow
def test__quick_node_hbar__get_txs__api_call__successful(account_address):
    address_keys = {'transactions', 'links'}
    transaction_keys = {'bytes', 'charged_tx_fee', 'consensus_timestamp', 'entity_id', 'max_fee', 'memo_base64',
                        'name',
                        'nft_transfers', 'node', 'nonce', 'parent_consensus_timestamp', 'result', 'scheduled',
                        'staking_reward_transfers', 'token_transfers', 'transaction_hash', 'transaction_id',
                        'transfers',
                        'valid_duration_seconds', 'valid_start_timestamp'}
    transfer_keys = {'account', 'amount', 'is_approval'}
    get_address_txs_response = api.get_address_txs(account_address)
    assert check_general_response(get_address_txs_response, address_keys)
    assert len(get_address_txs_response) > 0
    if get_address_txs_response.get('transactions'):
        for transaction in get_address_txs_response.get('transactions'):
            if len(transaction.get('transfers')) != 0:
                assert check_general_response(transaction, transaction_keys)
                for transfer in transaction.get('transfers'):
                    assert check_general_response(transfer, transfer_keys)


@pytest.mark.slow
def test__quick_node_hbar__get_tx_details__api_call__successful(tx_details_successful_transaction,
                                                                tx_details_invalid_transaction,
                                                                tx_details_fail_transaction):
    transaction_keys = {'bytes', 'charged_tx_fee', 'consensus_timestamp', 'entity_id', 'max_fee', 'memo_base64',
                        'name',
                        'nft_transfers', 'node', 'nonce', 'parent_consensus_timestamp', 'result', 'scheduled',
                        'staking_reward_transfers', 'token_transfers', 'transaction_hash', 'transaction_id',
                        'transfers',
                        'valid_duration_seconds', 'valid_start_timestamp'}
    transfer_keys = {'account', 'amount', 'is_approval'}
    hash_of_transactions = [tx_details_successful_transaction, tx_details_invalid_transaction,
                            tx_details_fail_transaction]
    for tx_hash in hash_of_transactions:
        get_tx_details_response = api.get_tx_details(tx_hash)
        assert len(get_tx_details_response.get('transactions')) != 0
        assert len(get_tx_details_response.get('transactions')[0]) != 0
        if len(get_tx_details_response.get('transactions')[0].get('transfers')) != 0:
            assert check_general_response(get_tx_details_response.get('transactions')[0], transaction_keys)
            for transfer in get_tx_details_response.get('transactions')[0].get('transfers'):
                assert check_general_response(transfer, transfer_keys)
