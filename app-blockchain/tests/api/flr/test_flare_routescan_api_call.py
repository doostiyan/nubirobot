import pytest
from exchange.blockchain.api.flr.flare_ankr import FlareAnkrApi
from exchange.blockchain.api.flr.flare_routescan import FlareRoutescanApi
from exchange.blockchain.tests.api.general_test.evm_based.test_routescan_api_call import (
    perform_test_on_routescan__get_address_txs__api_call,
    perform_test_on_routescan__get_block_head__api_call__successful,
    perform_test_on_routescan__get_block_txs__api_call__successful, perform_test_on_routescan__get_tx_details__api_call,
    perform_test_on_routescan__get_tx_receipt__api_call)

# BLOCK HEAD API #

@pytest.mark.slow
def test__flare_routescan__get_block_head__api_call__successful() -> None:
    perform_test_on_routescan__get_block_head__api_call__successful(api_class=FlareRoutescanApi)


# BLOCK ADDRESSES API #

@pytest.mark.slow
def test__flare_routescan__get_block_txs__api_call__successful() -> None:
    perform_test_on_routescan__get_block_txs__api_call__successful(
        api_class=FlareRoutescanApi,
        block_height=36655532,
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
def test__flare_routescan__get_tx_receipt__api_call__successful() -> None:
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


# TX DETAILS API #

@pytest.mark.slow
def test__flare_routescan__get_transactions_details__api_call__successful() -> None:
    perform_test_on_routescan__get_tx_details__api_call(
        api_class=FlareRoutescanApi,
        tx_hash="0xac31bb0a57bc75ac0d5891ffac60f21ee6ff845d010f21a7d8a8e6244d1eb553",
    )


# ADDRESS TXS API #

@pytest.mark.slow
def test__flare_routescan__get_address_txs__api_call__successful() -> None:
    perform_test_on_routescan__get_address_txs__api_call(
        api_class=FlareRoutescanApi,
        address="0x1e429358db3949c20fd49a0212f5cec7a731a500",
    )
