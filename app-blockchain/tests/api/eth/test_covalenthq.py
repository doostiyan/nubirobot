import pytest
from unittest import TestCase

from exchange.base.models import Currencies
from exchange.blockchain.api.eth.eth_covalent_new import ETHCovalenthqApi
from exchange.blockchain.contracts_conf import ERC20_contract_info


class TestEthCovalenthqApiCalls(TestCase):
    api = ETHCovalenthqApi
    account_address = ['0xc678D65910BdB63dFEf77c14fb1F406138D4050E']
    token_address = ['0x8d0841D393BE9aD6b4b233c2131b8154822CC571']

    txs_hash = ['0x3e3658fa39323694d8330b47e15b09d2876a2278f5e4326618ce806197cbc568']

    blocks = [20613239, 20613241]

    @pytest.mark.slow
    def test_get_balance_api(self):
        for address in self.account_address:
            get_balance_result = self.api().get_balance(address)
            assert isinstance(get_balance_result, dict)
            assert isinstance(get_balance_result.get('data'), dict)
            assert isinstance(get_balance_result.get('error'), bool)
            assert isinstance(get_balance_result.get('data').get('items'), list)
            assert isinstance(get_balance_result.get('data').get('chain_id'), int)
            key2check = [('type', str), ('is_spam', bool), ('balance', str), ('contract_address', str),
                         ('contract_ticker_symbol', str)]
            for item in get_balance_result.get('data').get('items'):
                for key, value in key2check:
                    assert isinstance(item.get(key), value)

    @pytest.mark.slow
    def test_get_token_balance_api(self):
        contract_info = ERC20_contract_info.get('mainnet').get(Currencies.usdc)
        for address in self.account_address:
            get_token_balance_result = self.api.get_token_balance(address, contract_info)
            assert isinstance(get_token_balance_result, dict)
            assert isinstance(get_token_balance_result.get('data'), dict)
            assert isinstance(get_token_balance_result.get('error'), bool)
            assert get_token_balance_result.get('error') is False
            assert isinstance(get_token_balance_result.get('data').get('items'), list)
            assert isinstance(get_token_balance_result.get('data').get('chain_id'), int)
            key2check = [('type', str), ('is_spam', bool), ('balance', str), ('contract_address', str)]
            for item in get_token_balance_result.get('data').get('items'):
                for key, value in key2check:
                    assert isinstance(item.get(key), value)

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_result = self.api().get_block_head()
        assert isinstance(get_block_head_result, dict)
        assert isinstance(get_block_head_result.get('data'), dict)
        assert isinstance(get_block_head_result.get('error'), bool)
        assert isinstance(get_block_head_result.get('data').get('items'), list)
        assert isinstance(get_block_head_result.get('data').get('chain_id'), int)
        assert isinstance(get_block_head_result.get('data').get('chain_name'), str)
        assert isinstance(get_block_head_result.get('data').get('updated_at'), str)
        key2check = [('height', int), ('signed_at', str), ('block_hash', str)]
        for item in get_block_head_result.get('data').get('items'):
            for key, value in key2check:
                assert isinstance(item.get(key), value)

    @pytest.mark.slow
    def test_get_tx_details_api(self):
        for tx_hash in self.txs_hash:
            get_details_tx_result = self.api().get_tx_details(tx_hash)
            assert isinstance(get_details_tx_result, dict)
            assert isinstance(get_details_tx_result.get('data'), dict)
            assert isinstance(get_details_tx_result.get('error'), bool)
            assert isinstance(get_details_tx_result.get('data').get('items'), list)
            assert isinstance(get_details_tx_result.get('data').get('chain_id'), int)
            assert isinstance(get_details_tx_result.get('data').get('chain_name'), str)
            assert isinstance(get_details_tx_result.get('data').get('updated_at'), str)
            key2check = [('block_height', int), ('block_signed_at', str), ('block_hash', str), ('from_address', str),
                         ('to_address', str), ('successful', bool), ('value', str), ('tx_hash', str), ('fees_paid', str)]
            for item in get_details_tx_result.get('data').get('items'):
                for key, value in key2check:
                    assert isinstance(item.get(key), value)

    @pytest.mark.slow
    def test_get_address_txs_api(self):
        for address in self.account_address:
            get_address_txs_result = self.api().get_address_txs(address)
            assert isinstance(get_address_txs_result, dict)
            assert isinstance(get_address_txs_result.get('data'), dict)
            assert isinstance(get_address_txs_result.get('error'), bool)
            assert isinstance(get_address_txs_result.get('data').get('items'), list)
            assert isinstance(get_address_txs_result.get('data').get('chain_id'), int)
            assert isinstance(get_address_txs_result.get('data').get('chain_name'), str)
            assert isinstance(get_address_txs_result.get('data').get('updated_at'), str)
            assert isinstance(get_address_txs_result.get('data').get('address'), str)
            key2check = [('block_height', int), ('block_signed_at', str), ('block_hash', str), ('from_address', str),
                         ('to_address', str), ('successful', bool), ('value', str), ('tx_hash', str), ('fees_paid', str)]
            for item in get_address_txs_result.get('data').get('items'):
                for key, value in key2check:
                    assert isinstance(item.get(key), value)

    @pytest.mark.slow
    def test_get_token_txs_api(self):
        for address in self.token_address:
            contract_info = ERC20_contract_info.get('mainnet').get(Currencies.usdc)
            get_token_txs_result = self.api.get_token_txs(address, contract_info)
            assert isinstance(get_token_txs_result, dict)
            assert isinstance(get_token_txs_result.get('data'), dict)
            assert isinstance(get_token_txs_result.get('error'), bool)
            assert isinstance(get_token_txs_result.get('data').get('items'), list)
            assert isinstance(get_token_txs_result.get('data').get('chain_id'), int)
            assert isinstance(get_token_txs_result.get('data').get('chain_name'), str)
            assert isinstance(get_token_txs_result.get('data').get('updated_at'), str)
            assert isinstance(get_token_txs_result.get('data').get('address'), str)
            key2check = [('block_height', int), ('block_signed_at', str), ('block_hash', str), ('successful', bool),
                         ('from_address', str), ('to_address', str), ('value', str), ('tx_hash', str),
                         ('transfers', list), ('gas_price', int), ('gas_spent', int)]
            key2check_transfers = [('tx_hash', str), ('block_signed_at', str), ('from_address', str),
                                   ('to_address', str), ('contract_address', str), ('contract_name', str),
                                   ('transfer_type', str), ('delta', str)]
            for item in get_token_txs_result.get('data').get('items'):
                for key, value in key2check:
                    assert isinstance(item.get(key), value)

                for transfer in item.get('transfers'):
                    for key, value in key2check_transfers:
                        assert isinstance(transfer.get(key), value)

    @pytest.mark.slow
    def test_get_block_txs_api(self):
        for block in self.blocks:
            get_block_txs_result = self.api().get_block_txs(block)
            assert isinstance(get_block_txs_result, dict)
            assert isinstance(get_block_txs_result.get('data'), dict)
            assert isinstance(get_block_txs_result.get('error'), bool)
            assert isinstance(get_block_txs_result.get('data').get('items'), list)
            assert isinstance(get_block_txs_result.get('data').get('chain_id'), int)
            assert isinstance(get_block_txs_result.get('data').get('chain_name'), str)
            assert isinstance(get_block_txs_result.get('data').get('updated_at'), str)
            key2check = [('block_height', int), ('block_signed_at', str), ('block_hash', str), ('successful', bool),
                         ('from_address', str), ('to_address', str), ('value', str), ('fees_paid', str)]
            for item in get_block_txs_result.get('data').get('items'):
                for key, value in key2check:
                    assert isinstance(item.get(key), value)
