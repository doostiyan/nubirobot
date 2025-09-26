import pytest
from unittest import TestCase
from exchange.base.models import Currencies
from exchange.blockchain.contracts_conf import BEP20_contract_info
from exchange.blockchain.api.bsc.bsc_covalent_new import BSCCovalentApi


class TestPolygonWeb3ApiCalls(TestCase):
    api = BSCCovalentApi
    account_address = ['0xf4c21a1cB819E5F7ABe6dEFde3d118D8F3D61FA7', '0xd4C6555cEb45813C054DA996483dF718a36e4Da4']

    txs_hash = ['0xf6869d62122c9d7a48dd78892788be0a2b2c4a90f2bd0329121b7bcf1bc0ec73']

    blocks = [41133333, 41156001, 40057005, 39057645]

    def check_general_response(self, response):
        assert isinstance(response, dict)
        assert isinstance(response.get('data'), dict)
        assert isinstance(response.get('error'), bool)
        assert isinstance(response.get('data').get('items'), list)
        assert isinstance(response.get('data').get('updated_at'), str)

    def check_key_response(self, response, keys):
        for item in response.get('data').get('items'):
            for key, value in keys:
                assert isinstance(item.get(key), value)

    @pytest.mark.slow
    def test_get_balance_api(self):
        for address in self.account_address:
            get_balance_result = self.api().get_balance(address)
            self.check_general_response(get_balance_result)
            key2check = [('type', str), ('is_spam', bool), ('balance', str)]
            self.check_key_response(get_balance_result, key2check)

    @pytest.mark.slow
    def test_get_token_balance_api(self):
        contract_info = BEP20_contract_info.get('mainnet').get(Currencies.usdc)
        for address in self.account_address:
            get_token_balance_result = self.api.get_token_balance(address, contract_info)
            assert isinstance(get_token_balance_result, dict)
            self.check_general_response(get_token_balance_result)
            key2check = [('type', str), ('is_spam', bool), ('balance', str), ('contract_address', str),
                         ('native_token', bool)]
            self.check_key_response(get_token_balance_result, key2check)

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_result = self.api().get_block_head()
        assert isinstance(get_block_head_result, dict)
        self.check_general_response(get_block_head_result)
        key2check = [('height', int), ('signed_at', str), ('block_hash', str)]
        self.check_key_response(get_block_head_result, key2check)

    @pytest.mark.slow
    def test_get_tx_details_api(self):
        for tx_hash in self.txs_hash:
            get_details_tx_result = self.api().get_tx_details(tx_hash)
            assert isinstance(get_details_tx_result, dict)
            self.check_general_response(get_details_tx_result)
            key2check = [('block_height', int), ('block_signed_at', str), ('block_hash', str), ('value', str),
                         ('to_address', str), ('from_address', str), ('successful', bool), ('tx_hash', str),
                         ('gas_price', int), ('log_events', list)]
            self.check_key_response(get_details_tx_result, key2check)

    @pytest.mark.slow
    def test_get_address_txs_api(self):
        for address in self.account_address:
            get_address_txs_result = self.api().get_address_txs(address)
            assert isinstance(get_address_txs_result, dict)
            self.check_general_response(get_address_txs_result)
            assert isinstance(get_address_txs_result.get('data').get('address'), str)
            key2check = [('block_height', int), ('block_signed_at', str), ('block_hash', str), ('successful', bool),
                         ('from_address', str), ('to_address', str), ('value', str), ('tx_hash', str)]
            self.check_key_response(get_address_txs_result, key2check)

    @pytest.mark.slow
    def test_get_token_txs_api(self):
        contract_info = BEP20_contract_info.get('mainnet').get(Currencies.usdc)
        for address in self.account_address:
            get_token_txs_result = self.api.get_token_txs(address, contract_info)
            self.check_general_response(get_token_txs_result)
            key2check = [('block_height', int), ('block_signed_at', str), ('block_hash', str), ('successful', bool),
                         ('from_address', str), ('to_address', str), ('value', str)]
            self.check_key_response(get_token_txs_result, key2check)

    @pytest.mark.slow
    def test_get_block_txs_api(self):
        for block in self.blocks:
            get_block_txs_result = self.api().get_block_txs(block)
            assert isinstance(get_block_txs_result, dict)
            self.check_general_response(get_block_txs_result)
            key2check = [('block_height', int), ('block_signed_at', str), ('block_hash', str), ('successful', bool),
                         ('from_address', str), ('to_address', str), ('value', str)]
            self.check_key_response(get_block_txs_result, key2check)
