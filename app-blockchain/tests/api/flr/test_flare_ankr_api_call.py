import pytest
from exchange.blockchain.api.flr.flare_ankr import FlareAnkrApi
from exchange.blockchain.tests.api.general_test.evm_based.test_routescan_api_call import \
    perform_test_on_routescan__get_tx_receipt__api_call
from exchange.blockchain.tests.base.rpc import (validate_rpc_block_head_response, validate_rpc_block_txs_response,
                                                validate_rpc_tx_detail_response)

# GET BLOCK HEAD API #


@pytest.mark.slow
def test__ankr_flare__get_block_head__api_call__successful() -> None:
    validate_rpc_block_head_response(block_head_response=FlareAnkrApi.get_block_head())


# GET BLOCK ADDRESSES API #

@pytest.mark.slow
def test__sonicscan_sonic__get_block_addresses__api_call__successful() -> None:
    get_block_addresses_response = FlareAnkrApi.get_block_txs(block_height=36655532)

    validate_rpc_block_txs_response(
        block_txs_response=get_block_addresses_response,
        should_exist_keys={
            'baseFeePerGas', 'blockExtraData', 'blockGasCost', 'difficulty', 'extDataGasUsed',
            'extDataHash', 'extraData', 'gasLimit', 'gasUsed', 'hash', 'logsBloom', 'miner',
            'mixHash', 'nonce', 'number', 'parentHash', 'receiptsRoot', 'sha3Uncles', 'size',
            'stateRoot', 'timestamp', 'totalDifficulty', 'transactions', 'transactionsRoot', 'uncles',
        },
    )


# GET TX RECEIPT API #

@pytest.mark.slow
def test__ankr_flr__get_tx_receipt__api_call__successful() -> None:
    perform_test_on_routescan__get_tx_receipt__api_call(
        api_class=FlareAnkrApi,
        tx_hash='0xac31bb0a57bc75ac0d5891ffac60f21ee6ff845d010f21a7d8a8e6244d1eb553',
        should_exist_keys={
            'blockHash',
            'blockNumber',
            'contractAddress',
            'cumulativeGasUsed',
            'effectiveGasPrice',
            'from',
            'gasUsed',
            'logs',
            'logsBloom',
            'status',
            'to',
            'transactionHash',
            'transactionIndex',
            'type',
        },
    )


# TX DETAIL API #

@pytest.mark.slow
def test__ankr_flr__get_tx_detail__api_call__successful() -> None:
    tx_detail_response = FlareAnkrApi.get_tx_details(
        tx_hash='0xac31bb0a57bc75ac0d5891ffac60f21ee6ff845d010f21a7d8a8e6244d1eb553')

    validate_rpc_tx_detail_response(
        tx_detail_response=tx_detail_response,
        expected_types={
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
            "chainId": str,
            "v": str,
            "r": str,
            "s": str,
        },
    )
