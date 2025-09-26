import pytest

from exchange.blockchain.api.base.routescan_base import BaseRouteScanAPI
from exchange.blockchain.tests.api.general_test.evm_based.test_routescan_api_call import (
    perform_test_on_routescan__get_address_txs__api_call,
    perform_test_on_routescan__get_block_txs__api_call__successful,
    perform_test_on_routescan__get_tx_details__api_call,
    perform_test_on_routescan__get_tx_receipt__api_call,
)

api = BaseRouteScanAPI

# GET BLOCK TXS API

@pytest.mark.slow
def test__base_routescan__get_block_txs__api_call__successful() -> None:
    perform_test_on_routescan__get_block_txs__api_call__successful(
        api_class=api,
        block_height=30050052,
        should_exist_keys={
            'baseFeePerGas',
            'blockExtraData',
            'blockGasCost',
            'difficulty',
            'extDataGasUsed',
            'extDataHash',
            'extraData',
            'gasLimit',
            'gasUsed',
            'hash',
            'logsBloom',
            'miner',
            'mixHash',
            'nonce',
            'number',
            'parentHash',
            'receiptsRoot',
            'sha3Uncles',
            'size',
            'stateRoot',
            'timestamp',
            'totalDifficulty',
            'transactions',
            'transactionsRoot',
            'uncles',
        }
    )


# TX RECEIPT API #

@pytest.mark.slow
def test__base_routescan__get_tx_receipt__api_call__successful() -> None:
    perform_test_on_routescan__get_tx_receipt__api_call(
        api_class=api,
        tx_hash='0xfc2e852ad8244483ee8cb13ba075944f85570b0f628c37c7fa7abc4e513d5104',
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


# TX DETAILS API #

@pytest.mark.slow
def test__base_routescan__get_transactions_details__api_call__successful() -> None:
    perform_test_on_routescan__get_tx_details__api_call(
        api_class=api,
        tx_hash='0xfc2e852ad8244483ee8cb13ba075944f85570b0f628c37c7fa7abc4e513d5104',
    )


# ADDRESS TXS API #

@pytest.mark.slow
def test__base_routescan__get_address_txs__api_call__successful() -> None:
    perform_test_on_routescan__get_address_txs__api_call(
        api_class=api,
        address='0xe09F33f3c9ED2a2DDce39EB302DAC95eD8829687',
    )
