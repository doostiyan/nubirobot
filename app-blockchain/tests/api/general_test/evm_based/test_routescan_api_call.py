from exchange.blockchain.tests.base.rpc import (validate_rpc_address_txs_response, validate_rpc_block_head_response,
                                                validate_rpc_block_txs_response, validate_rpc_tx_detail_response,
                                                validate_rpc_tx_receipt_response)


def perform_test_on_routescan__get_block_head__api_call__successful(api_class) -> None:
    block_addresses_response = api_class.get_block_head()

    validate_rpc_block_head_response(block_head_response=block_addresses_response)


def perform_test_on_routescan__get_block_txs__api_call__successful(api_class, block_height: int,
                                                                   should_exist_keys: set) -> None:
    block_txs_response = api_class.get_block_txs(block_height=block_height)

    validate_rpc_block_txs_response(
        block_txs_response=block_txs_response,
        should_exist_keys=should_exist_keys,
    )


def perform_test_on_routescan__get_tx_receipt__api_call(api_class, tx_hash: str, should_exist_keys: set):
    get_tx_receipt_response = api_class.get_tx_receipt(tx_hash=tx_hash)

    validate_rpc_tx_receipt_response(
        tx_receipt_response=get_tx_receipt_response,
        should_exist_keys=should_exist_keys,
        nullable_keys={'contractAddress'},
    )


def perform_test_on_routescan__get_tx_details__api_call(api_class, tx_hash: str):
    tx_details_response = api_class.get_tx_details(tx_hash=tx_hash)

    validate_rpc_tx_detail_response(
        tx_detail_response=tx_details_response,
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


def perform_test_on_routescan__get_address_txs__api_call(api_class, address: str):
    address_txs_response = api_class.get_address_txs(address=address)

    validate_rpc_address_txs_response(
        address_txs_response=address_txs_response,
        expected_types={
            "blockNumber": str,
            "timeStamp": str,
            "hash": str,
            "nonce": str,
            "blockHash": str,
            "transactionIndex": str,
            "from": str,
            "to": str,
            "value": str,
            "gas": str,
            "gasPrice": str,
            "isError": str,
            "txreceipt_status": str,
            "input": str,
            "contractAddress": str,
            "cumulativeGasUsed": str,
            "gasUsed": str,
            "confirmations": str,
            "methodId": str,
            "functionName": str,
        },
    )
