import pytest

from exchange.blockchain.api.base.basescan_base import BaseScanAPI
from exchange.blockchain.tests.fixtures.base_fixtures import (
    block_number,
    tx_hash_failed,
    tx_hash_successful,
    wallet,
)

api = BaseScanAPI


def check_general_response(response, keys):
    if keys.issubset(set(response.keys())):
        return True
    return False


@pytest.mark.slow
def test__scan_base__get_tx_details__api_call__successful(tx_hash_successful, tx_hash_failed):
    response_keys = {'blockHash', 'chainId', 'from', 'to', 'blockNumber',
                     'gas', 'gasPrice', 'hash', 'input', 'nonce',
                     'transactionIndex', 'type', 'value', }
    txs_hash = [tx_hash_successful, tx_hash_failed]
    for tx_hash in txs_hash:
        get_tx_details_response = api.get_tx_details(tx_hash)
        assert check_general_response(get_tx_details_response.get('result'), response_keys)


@pytest.mark.slow
def test__scan_base__get_wallet_txs__api_call__successful(wallet):
    expected_keys = {
        'blockNumber', 'timeStamp', 'hash', 'nonce', 'blockHash',
        'transactionIndex', 'from', 'to', 'value', 'gas', 'gasPrice',
        'isError', 'txreceipt_status', 'input', 'contractAddress',
        'cumulativeGasUsed', 'gasUsed', 'confirmations', 'methodId',
        'functionName'
    }

    wallet_txs_response = api.get_address_txs(wallet)

    assert isinstance(wallet_txs_response, dict)
    assert wallet_txs_response.get('status') == '1'
    assert wallet_txs_response.get('message') == 'OK'
    assert 'result' in wallet_txs_response
    assert isinstance(wallet_txs_response['result'], list)

    for tx in wallet_txs_response['result']:
        assert expected_keys.issubset(tx.keys()), f'Missing keys in tx: {tx}'


@pytest.mark.slow
def test__scan_base__get_block_txs__api_call__successful(block_number):
    required_keys = {
        'blockNumber', 'hash', 'nonce', 'blockHash',
        'transactionIndex', 'from', 'to', 'value',
        'gas', 'gasPrice', 'input'
    }

    block_txs_response = api.get_block_txs(block_number)

    assert isinstance(block_txs_response, dict), 'Response is not a dictionary'
    assert 'result' in block_txs_response, "'result' not found in response"
    assert isinstance(block_txs_response['result'], dict), "'result' should be a dictionary"

    transactions = block_txs_response['result'].get('transactions')
    assert transactions is not None, "'transactions' missing in result"
    assert isinstance(transactions, list), "'transactions' is not a list"

    for i, tx in enumerate(transactions):
        assert isinstance(tx, dict), f'Transaction at index {i} is not a dict'

        missing_keys = required_keys - tx.keys()
        assert not missing_keys, f'Missing required keys in tx[{i}]: {missing_keys}'

        hex_fields = ['gas', 'gasPrice', 'nonce', 'blockNumber', 'transactionIndex']
        for key in hex_fields:
            if key in tx:
                try:
                    _ = int(tx[key], 16)
                except Exception as e:
                    raise AssertionError(f"Field '{key}' in tx[{i}] is not valid hex: {tx[key]}") from e

        for key in ['hash', 'from', 'blockHash']:
            assert tx.get(key), f"Field '{key}' is empty or missing in tx[{i}]"

        assert 'to' in tx, f"Field 'to' is missing in tx[{i}]"
