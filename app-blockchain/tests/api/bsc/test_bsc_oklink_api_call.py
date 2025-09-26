import pytest

from exchange.blockchain.api.bsc.bsc_oklink import OkLinkBscApi

MAX_TRANSACTION_LIMIT = 100


def validate_general_response(response: dict) -> None:
    assert isinstance(response, dict)
    assert response.get('code') == '0'
    assert response.get('msg') == ''
    assert response.get('data')
    assert isinstance(response.get('data'), list)


# GET BLOCK HEAD API #

@pytest.mark.slow
def test__oklink_bsc__get_block_head__api_call__successful() -> None:
    get_block_head_response = OkLinkBscApi.get_block_head()

    validate_general_response(response=get_block_head_response)
    assert len(get_block_head_response.get('data')) == 1

    block_data = get_block_head_response['data'][0]
    required_fields = {
        'chainFullName',
        'chainShortName',
        'blockList',
    }

    assert required_fields.issubset(block_data.keys())
    assert block_data['chainFullName'] == 'BNB Chain'
    assert block_data['chainShortName'] == 'BSC'
    assert len(block_data['blockList']) == 1
    last_block: dict = block_data['blockList'][0]
    assert isinstance(last_block.get('height'), str)
    assert int(last_block.get('height'))


# GET ADDRESS TXS API #

@pytest.mark.slow
def test__oklink_bsc__get_address_transactions__api_call__successful() -> None:
    get_address_txs_response = OkLinkBscApi.get_address_txs(
        address='0x8894E0a0c962CB723c1976a4421c95949bE2D4E3'  # Binance hot wallet
    )

    validate_general_response(response=get_address_txs_response)
    assert len(get_address_txs_response.get('data')) == 1

    data = get_address_txs_response['data'][0]
    required_fields = {
        'page',
        'limit',
        'totalPage',
        'chainFullName',
        'chainShortName',
        'transactionLists'
    }

    assert required_fields.issubset(data.keys())
    assert data['page'] == '1'
    assert data['limit'] == '20'
    assert isinstance(data['totalPage'], str)
    assert data['chainFullName'] == 'BNB Chain'
    assert data['chainShortName'] == 'BSC'

    transaction_lists = data['transactionLists']
    assert isinstance(transaction_lists, list)
    assert len(transaction_lists) <= MAX_TRANSACTION_LIMIT  # Maximum limit is 100

    tx_required_fields = {
        'txId',
        'methodId',
        'blockHash',
        'height',
        'transactionTime',
        'from',
        'to',
        'isFromContract',
        'isToContract',
        'amount',
        'transactionSymbol',
        'txFee',
        'state',
        'tokenId',
        'tokenContractAddress',
        'challengeStatus',
        'l1OriginHash'
    }

    for tx in transaction_lists:
        assert tx_required_fields.issubset(tx.keys())
        assert isinstance(tx['txId'], str)
        assert isinstance(tx['height'], str)
        assert int(tx['height'])  # Verify it's a valid number
        assert isinstance(tx['transactionTime'], str)
        assert isinstance(tx['from'], str)
        assert isinstance(tx['to'], str)
        assert isinstance(tx['amount'], str)
        assert isinstance(tx['txFee'], str)
        assert isinstance(tx['state'], str)
        assert tx['transactionSymbol'] == 'BNB'
