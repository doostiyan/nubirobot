import pytest
from exchange.blockchain.api.dydx.dydx_node import DydxPublicRpc
from exchange.blockchain.tests.fixtures.dydx_fixtures import addresses, tx_hash_successful

api = DydxPublicRpc

transaction_important_fields = {'value', 'from', 'to', 'hash', 'blockNumber', 'memo'}


@pytest.mark.slow
def test__public_rpc_dydx__get_block_head__api_call__successful():
    get_block_head_response = api.get_block_head()
    assert isinstance(get_block_head_response, dict)
    assert isinstance(get_block_head_response.get('block'), dict)
    assert isinstance(get_block_head_response.get('block').get('header'), dict)
    assert isinstance(get_block_head_response.get('block').get('header').get('height'), str or int)


@pytest.mark.slow
def test__public_rpc_dydx__get_balance__api_call__successful(addresses):
    for address in addresses:
        get_balance_response = api.get_balance(address)
        assert isinstance(get_balance_response, dict)
        keys2check = [('denom', str), ('amount', str)]
        if 'balance' in get_balance_response:
            assert isinstance(get_balance_response.get('balance'), dict)
            for key, value in keys2check:
                assert isinstance(get_balance_response.get('balance').get(key), value)
        else:
            assert isinstance(get_balance_response.get('balances'), list)
            for key, value in keys2check:
                assert isinstance(get_balance_response.get('balances')[0].get(key), value)


@pytest.mark.slow
def test__public_rpc_dydx__get_tx_details__api_call__successful(tx_hash_successful):
    get_tx_details_response = api.get_tx_details(tx_hash_successful)
    assert isinstance(get_tx_details_response, dict)
    assert isinstance(get_tx_details_response.get('tx'), dict)
    assert isinstance(get_tx_details_response.get('tx').get('body'), dict)
    assert isinstance(get_tx_details_response.get('tx').get('body').get('messages'), list)
    for tx in get_tx_details_response.get('tx').get('body').get('messages'):
        keys2check = [('amount', list), ('from_address', str), ('to_address', str)]
        for key, value in keys2check:
            assert isinstance(tx.get(key), value)
    if 'tx_response' in get_tx_details_response:
        assert isinstance(get_tx_details_response.get('tx_response'), dict)
        keys2check2 = [('tx', dict), ('txhash', str), ('code', int)]
        for key, value in keys2check2:
            assert isinstance(get_tx_details_response.get('tx_response').get(key), value)
        assert isinstance(get_tx_details_response.get('tx_response').get('tx').get('body'), dict)
        assert isinstance(get_tx_details_response.get('tx_response').get('tx').get('body').get('memo'), str)
    else:
        assert isinstance(get_tx_details_response.get('tx'), dict)
        keys2check2 = [('tx', dict), ('txhash', str), ('code', int)]
        for key, value in keys2check2:
            assert isinstance(get_tx_details_response.get('tx').get(key), value)
        assert isinstance(get_tx_details_response.get('tx').get('body'), dict)
        assert isinstance(get_tx_details_response.get('tx').get('body').get('memo'), str)


@pytest.mark.slow
def test__public_rpc_dydx__get_address_txs__api_call__successful(addresses):
    for address in addresses:
        get_address_txs_response = api.get_address_txs(address, 'incoming')
        assert isinstance(get_address_txs_response, dict)
        assert isinstance(get_address_txs_response.get('tx_responses'), list)
        for tx in get_address_txs_response.get('tx_responses'):
            assert isinstance(tx.get('tx'), dict)
            assert isinstance(tx.get('tx').get('body'), dict)
            assert isinstance(tx.get('tx').get('body').get('messages'), list)
            for item in tx.get('tx').get('body').get('messages'):
                if 'amount' and 'from_address' and 'to_address' in item:
                    keys2check = [('amount', list), ('from_address', str), ('to_address', str)]
                    for key, value in keys2check:
                        assert isinstance(item.get(key), value)
            if 'tx_response' in tx:
                assert isinstance(tx.get('tx_response'), dict)
                keys2check2 = [('tx', dict), ('txhash', str), ('code', int)]
                for key, value in keys2check2:
                    assert isinstance(tx.get('tx_response').get(key), value)
                assert isinstance(tx.get('tx_response').get('tx').get('body'), dict)
                assert isinstance(tx.get('tx_response').get('tx').get('body').get('memo'), str)
            else:
                assert isinstance(tx.get('tx'), dict)
                assert isinstance(tx.get('tx').get('body'), dict)
                assert isinstance(tx.get('tx').get('body').get('memo'), str)
