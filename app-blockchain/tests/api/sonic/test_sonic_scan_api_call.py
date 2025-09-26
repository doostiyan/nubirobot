from typing import Optional

import pytest
from exchange.blockchain.api.sonic.sonic_scan import SonicScanApi
from exchange.blockchain.tests.base.rpc import (validate_rpc_block_head_response, validate_rpc_block_txs_response,
                                                validate_rpc_tx_detail_response)

# BLOCK HEAD API #


@pytest.mark.slow
def test__sonicscan_sonic__get_block_head__api_call__successful() -> None:
    validate_rpc_block_head_response(SonicScanApi.get_block_head())


# BLOCK ADDRESSES API #

@pytest.mark.slow
def test__sonicscan_sonic__get_block_addresses__api_call__successful() -> None:
    get_block_addresses_response = SonicScanApi.get_block_txs(block_height=3700579)

    validate_rpc_block_txs_response(
        block_txs_response=get_block_addresses_response,
        should_exist_keys={'parentHash', 'sha3Uncles', 'miner', 'stateRoot', 'transactionsRoot', 'receiptsRoot',
                           'logsBloom',
                           'difficulty', 'number', 'gasLimit', 'gasUsed', 'timestamp', 'timestampNano', 'extraData',
                           'mixHash',
                           'nonce', 'baseFeePerGas', 'hash', 'epoch', 'totalDifficulty', 'withdrawalsRoot',
                           'blobGasUsed',
                           'excessBlobGas', 'transactions', 'size', 'uncles'},
    )


# TX DETAILS API #

@pytest.mark.slow
def test__sonicscan_sonic__get_transactions_details__api_call__successful() -> None:
    get_tx_details_response = SonicScanApi.get_tx_details(
        tx_hash="0x07db627ee808d61f60872cab0c43b00083c573f6b0850e086a7c5e73002f5f83")

    validate_rpc_tx_detail_response(
        tx_detail_response=get_tx_details_response,
        expected_types={
            "blobVersionedHashes": Optional[None],
            "blockHash": str,
            "blockNumber": str,
            "from": str,
            "gas": str,
            "gasPrice": str,
            "hash": str,
            "input": str,
            "nonce": str,
            "to": str,
            "transactionIndex": str,
            "value": str,
            "type": str,
            "v": str,
            "r": str,
            "s": str,
            "maxFeePerBlobGas": Optional[None],
        }
    )


# ADDRESS TXS API #

@pytest.mark.slow
def test__sonicscan_sonic__get_address_transactions__api_call__successful() -> None:
    get_tx_details_response = SonicScanApi.get_address_txs(address="0xf310b07583a5515d25384a82df027124d54aaf26")

    assert isinstance(get_tx_details_response, dict)
    assert get_tx_details_response.get('result')
    assert isinstance(get_tx_details_response.get('result'), list)
    assert len(get_tx_details_response.get('result')) == 50
    required_fields = {
        'blockNumber',
        'timeStamp',
        'hash',
        'nonce',
        'blockHash',
        'transactionIndex',
        'from',
        'to',
        'value',
        'gas',
        'gasPrice',
        'isError',
        'txreceipt_status',
        'input',
        'contractAddress',
        'cumulativeGasUsed',
        'gasUsed',
        'confirmations',
        'methodId',
        'functionName',
    }
    assert all(
        required_fields.issubset(x.keys()) and all(isinstance(x[key], str) for key in required_fields)
        for x in get_tx_details_response['result']
    )
