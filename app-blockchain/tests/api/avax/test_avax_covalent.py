import pytest
from unittest import TestCase
from exchange.blockchain.api.avax.avax_covalent_new import AvalancheCovalentAPI


class TestAvaxWeb3ApiCalls(TestCase):
    api = AvalancheCovalentAPI
    account_address = ['0x24e4B80b88ac05E972B5CF0c6178C06f44BBe059']

    txs_hash = ['0xdcf4e546b8c70c2ad5e5625d4942bbfeee3c3c2c9065bb3d069f9c5bc89d061b']

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
            key2check = [('contract_decimals', int), ('contract_name', str), ('contract_address', str), ('type', str),
                         ('is_spam', bool), ('balance', str)]
            for item in get_balance_result.get('data').get('items'):
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
