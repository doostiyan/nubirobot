import pytest
from unittest import TestCase

from exchange.base.models import Currencies
from exchange.blockchain.api.polygon.polygon_covalent_new import PolygonCovalentAPI
from exchange.blockchain.contracts_conf import polygon_ERC20_contract_info


class TestPolygonWeb3ApiCalls(TestCase):
    api = PolygonCovalentAPI
    account_address = ['0x67B94473D81D0cd00849D563C94d0432Ac988B49']

    txs_hash = ['0x017cc3e5da105e3882c70bdf82512226b4afdef89e279efddb830ae066630f76']

    blocks = [48092650, 48092661]

    @pytest.mark.slow
    def test_get_balance_api(self):
        for address in self.account_address:
            get_balance_result = self.api().get_balance(address)
            assert isinstance(get_balance_result, dict)
            assert isinstance(get_balance_result.get('data'), dict)
            assert isinstance(get_balance_result.get('error'), bool)
            assert isinstance(get_balance_result.get('data').get('items'), list)
            assert isinstance(get_balance_result.get('data').get('chain_id'), int)
            key2check = [('type', str), ('is_spam', bool), ('balance', str), ('contract_address', str)]
            for item in get_balance_result.get('data').get('items'):
                for key, value in key2check:
                    assert isinstance(item.get(key), value)

    @pytest.mark.slow
    def test_get_token_balance_api(self):
        contract_info = polygon_ERC20_contract_info.get('mainnet').get(Currencies.usdc)
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
            key2check = [('block_height', int), ('block_signed_at', str), ('block_hash', str)]
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
            key2check = [('block_height', int), ('block_signed_at', str), ('block_hash', str), ('successful', bool),
                         ('from_address', str), ('to_address', str), ('value', str), ('tx_hash', str)]
            for item in get_address_txs_result.get('data').get('items'):
                for key, value in key2check:
                    assert isinstance(item.get(key), value)

    @pytest.mark.slow
    def test_get_token_txs_api(self):
        for address in self.account_address:
            contract_info = polygon_ERC20_contract_info.get('mainnet').get(Currencies.usdc)
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
                         ('transfers', list)]
            key2check_transfers = [('tx_hash', str), ('block_signed_at', str), ('from_address', str),
                                   ('to_address', str), ('contract_address', str), ('contract_name', str),
                                   ('transfer_type', str)]
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
                         ('from_address', str), ('to_address', str), ('value', str)]
            for item in get_block_txs_result.get('data').get('items'):
                for key, value in key2check:
                    assert isinstance(item.get(key), value)
