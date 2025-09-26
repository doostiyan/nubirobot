from typing import Any, Dict

import pytest

# from exchange.blockchain.api.sui.sui_blastapi import BlastApiSuiApi # noqa: ERA001

pytestmark = pytest.mark.skip(reason='Skipping all tests in this file temporarily')


@pytest.mark.slow
def test_blastapi_sui_get_block_head_api_call_successful() -> None:
    response = BlastApiSuiApi.get_block_head()  # noqa: F821
    assert isinstance(response, dict)
    assert 'result' in response
    result = response['result']
    assert isinstance(result, str)
    assert isinstance(int(result), int)


@pytest.mark.slow
def test_blastapi_sui_get_block_txs_api_call_successful() -> None:
    response = BlastApiSuiApi.get_block_txs(block_height=115765230)  # noqa: F821

    block_txs = response.get('result', {}).get('data', [])

    assert isinstance(block_txs, list), 'The response should be a list.'
    assert len(block_txs) > 0, 'The list should not be empty.'

    expected_structure: Dict[str, Any] = {
        'checkpointCommitments': list,
        'digest': str,
        'epoch': str,
        'epochRollingGasCostSummary': dict,
        'networkTotalTransactions': str,
        'previousDigest': str,
        'sequenceNumber': str,
        'timestampMs': str,
        'transactions': list,
        'validatorSignature': str,
    }

    for tx in block_txs:
        for key, expected_type in expected_structure.items():
            assert key in tx, f'Missing key: {key}'
            assert isinstance(tx[key], expected_type), f'Key "{key}" should be of type {expected_type.__name__}.'

        effects_structure: Dict[str, Any] = {
            'computationCost': str,
            'nonRefundableStorageFee': str,
            'storageCost': str,
            'storageRebate': str,
        }
        epoch_gas_cost_summary = tx['epochRollingGasCostSummary']
        for key, expected_type in effects_structure.items():
            assert key in epoch_gas_cost_summary, f'Missing key in epochRollingGasCostSummary: {key}'
            assert isinstance(epoch_gas_cost_summary[key],
                              expected_type), (f'Key "{key}" in epochRollingGasCostSummary should be of type'
                                               f' {expected_type.__name__}.')


@pytest.mark.slow
def test_blastapi_sui_get_tx_details_api_call_successful() -> None:
    tx_hash = '4c4FVBRfUt4F7MLU5ABVHjn7VV26ev54vHDEn2H1CiDt'
    response = BlastApiSuiApi.get_tx_details(tx_hash=tx_hash)  # noqa: F821
    assert isinstance(response, dict), 'The response should be a dictionary.'
    assert 'result' in response, 'The response should contain a "result" key.'
    result = response['result']
    assert isinstance(result, dict), 'The "result" should be a dictionary.'
    expected_structure: Dict[str, Any] = {
        'digest': str,
        'transaction': dict,
        'balanceChanges': list,
        'timestampMs': str,
        'checkpoint': str,
        'effects': dict,
    }
    for key, typing in expected_structure.items():
        assert isinstance(result[key], typing), f'Missing key in result: {key}'


@pytest.mark.slow
def test_blastapi_sui_get_address_txs_api_call_successful() -> None:
    address = '0x9d2ca61484f385f4c09267267ee43d48b7eaebaccf5fbcadd4ef4acf5e56af33'
    response = BlastApiSuiApi.get_address_txs(address=address)  # noqa: F821
    assert isinstance(response, dict), 'The response should be a dictionary.'
    assert 'result' in response, 'The response should contain a "result" key.'
    result = response['result']
    assert isinstance(result, dict)
    assert 'data' in result
    data = result['data']
    assert isinstance(data, list)
    if data:  # If there are transactions, validate the structure of the first one
        tx = data[0]
        assert isinstance(tx, dict), 'Each transaction should be a dictionary.'
        expected_keys = ['digest', 'transaction', 'balanceChanges', 'checkpoint', 'timestampMs']
        for key in expected_keys:
            assert key in tx, f'Missing key in transaction: {key}'
