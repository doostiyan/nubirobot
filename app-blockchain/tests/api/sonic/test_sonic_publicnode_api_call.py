import pytest
from exchange.blockchain.api.sonic.sonic_publicnode import SonicPublicNodeWeb3API
from hexbytes import HexBytes
from web3.datastructures import AttributeDict

# GET BLOCK HEAD API #


@pytest.mark.slow
def test__publicnode_sonic__get_block_head__api_call__successful() -> None:
    get_block_head_response = SonicPublicNodeWeb3API().get_block_head()
    assert isinstance(get_block_head_response, int)


# GET BLOCK ADDRESSES API #

@pytest.mark.slow
def test__publicnode_sonic__get_block_addresses__api_call__successful() -> None:
    get_block_addresses_response = SonicPublicNodeWeb3API().get_block_txs(block_height=3700579)

    assert isinstance(get_block_addresses_response, AttributeDict)

    keys_to_value_types_mapper: dict = {
        'baseFeePerGas': int,
        'blobGasUsed': int,
        'difficulty': int,
        'epoch': str,
        'excessBlobGas': int,
        'gasLimit': int,
        'gasUsed': int,
        'hash': HexBytes,
        'logsBloom': HexBytes,
        'miner': str,
        'mixHash': HexBytes,
        'nonce': HexBytes,
        'number': int,
        'parentHash': HexBytes,
        'proofOfAuthorityData': HexBytes,
        'receiptsRoot': HexBytes,
        'sha3Uncles': HexBytes,
        'size': int,
        'stateRoot': HexBytes,
        'timestamp': int,
        'timestampNano': str,
        'totalDifficulty': int,
        'transactions': list,
        'transactionsRoot': HexBytes,
        'uncles': list,
        'withdrawalsRoot': HexBytes,
    }
    assert set(keys_to_value_types_mapper.keys()).issubset(get_block_addresses_response.keys())
    assert all([isinstance(getattr(get_block_addresses_response, k), v) for k, v in keys_to_value_types_mapper.items()])


# GET TX DETAILS API #

@pytest.mark.slow
def test__sonicscan_sonic__get_transactions_details__api_call__successful() -> None:
    get_tx_details_response = SonicPublicNodeWeb3API().get_tx_details(
        tx_hash="0x07db627ee808d61f60872cab0c43b00083c573f6b0850e086a7c5e73002f5f83")

    assert isinstance(get_tx_details_response, AttributeDict)
    assert {
        'blobVersionedHashes',
        'blockHash',
        'blockNumber',
        'from',
        'gas',
        'gasPrice',
        'hash',
        'input',
        'maxFeePerBlobGas',
        'nonce',
        'r',
        's',
        'to',
        'transactionIndex',
        'type',
        'v',
        'value',
    }.issubset(get_tx_details_response.keys())
    required_fields_to_typing_mapper: dict = {
        "blockHash": HexBytes,
        "hash": HexBytes,
        "blockNumber": int,
        "value": int,
        "from": str,
        "to": str,
        "gas": int,
        "gasPrice": int,
    }
    assert all([isinstance(getattr(get_tx_details_response, key), value) for key, value in
                required_fields_to_typing_mapper.items()])
