import pytest
from exchange.blockchain.api.eth.eth_web3_new import ETHWeb3Api
from exchange.blockchain.tests.fixtures.eth_web3_fixtures import addresses, addresses_for_usdt, txs_hash_api_call, \
    block_height

api = ETHWeb3Api.get_instance()

contracts_info = {'address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                  'decimals': 6,
                  'symbol': 'USDT',
                  }

transaction_important_fields = {'input', 'value', 'from', 'to', 'hash', 'blockNumber'}


@pytest.mark.slow
def test__web3_eth__get_balance__api_call__successful(addresses):
    for address in addresses:
        get_balance_result = api.get_balance(address)
        assert isinstance(get_balance_result, int)


@pytest.mark.slow
def test__web3_eth__get_block_head__api_call__successful():
    get_block_head_response = api.get_block_head()
    assert isinstance(get_block_head_response, int)


@pytest.mark.slow
def test__web3_eth__get_tx_details__api_call__successful(txs_hash_api_call):
    for tx_hash in txs_hash_api_call:
        get_tx_details_response = api.get_tx_details(tx_hash)
        assert transaction_important_fields.issubset(set(get_tx_details_response.keys()))


@pytest.mark.slow
def test__web3_eth__get_tx_receipt__api_call__successful(txs_hash_api_call):
    for tx_hash in txs_hash_api_call:
        get_tx_receipt_response = api.get_tx_receipt(tx_hash)
        assert {'status'}.issubset(get_tx_receipt_response.keys())


@pytest.mark.slow
def test__web3_eth__get_block_txs__api_call__successful(block_height):
    get_block_txs_response = api.get_block_txs(block_height)
    assert {'transactions'}.issubset(get_block_txs_response.keys())
    for transaction in get_block_txs_response.get('transactions'):
        assert transaction_important_fields.issubset(transaction.keys())


@pytest.mark.slow
def test__web3_eth__get_token_balance__api_call__successful(addresses_for_usdt):
    for address in addresses_for_usdt:
        get_balance_result = api.get_token_balance(address, contract_info=contracts_info)
        assert isinstance(get_balance_result, int)
