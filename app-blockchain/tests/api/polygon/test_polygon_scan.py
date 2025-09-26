import pytest
from unittest import TestCase
from exchange.base.models import Currencies
from exchange.blockchain.contracts_conf import polygon_ERC20_contract_info
from exchange.blockchain.api.polygon.polygon_scan_new import PolygonBlockScanAPI


class TestPolygonBlockScanApiCalls(TestCase):
    api = PolygonBlockScanAPI
    account_address = ['0x67B94473D81D0cd00849D563C94d0432Ac988B49']

    txs_hash = ['0x017cc3e5da105e3882c70bdf82512226b4afdef89e279efddb830ae066630f76']

    blocks = [48092650, 48092661]

    @pytest.mark.slow
    def test_get_balance_api(self):
        for address in self.account_address:
            get_balance_result = self.api().get_balance(address)
            assert isinstance(get_balance_result, dict)
            assert isinstance(get_balance_result.get('message'), str)
            assert isinstance(get_balance_result.get('result'), str)
            assert isinstance(get_balance_result.get('status'), str)

    @pytest.mark.slow
    def test_get_token_balance_api(self):
        contract_info = polygon_ERC20_contract_info.get('mainnet').get(Currencies.usdc)
        for address in self.account_address:
            get_token_balance_result = self.api.get_token_balance(address, contract_info)
            assert isinstance(get_token_balance_result, dict)
            assert isinstance(get_token_balance_result.get('message'), str)
            assert isinstance(get_token_balance_result.get('result'), str)
            assert isinstance(get_token_balance_result.get('status'), str)

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_result = self.api().get_block_head()
        assert isinstance(get_block_head_result, dict)
        assert isinstance(get_block_head_result.get('result'), str)
        assert isinstance(get_block_head_result.get('id'), int)
        assert isinstance(get_block_head_result.get('jsonrpc'), str)

    @pytest.mark.slow
    def test_get_tx_details_api(self):
        for tx_hash in self.txs_hash:
            get_details_tx_result = self.api().get_tx_details(tx_hash)
            assert isinstance(get_details_tx_result, dict)
            assert isinstance(get_details_tx_result.get('id'), int)
            assert isinstance(get_details_tx_result.get('jsonrpc'), str)
            assert isinstance(get_details_tx_result.get('result'), dict)
            key2check = [('blockHash', str), ('blockNumber', str), ('from', str), ('gas', str), ('gasPrice', str),
                         ('hash', str), ('to', str), ('value', str), ('type', str)]
            for key, value in key2check:
                assert isinstance(get_details_tx_result.get('result').get(key), value)

    @pytest.mark.slow
    def test_get_address_txs_api(self):
        for address in self.account_address:
            get_address_txs_result = self.api().get_address_txs(address)
            assert isinstance(get_address_txs_result, dict)
            assert isinstance(get_address_txs_result.get('status'), str)
            assert isinstance(get_address_txs_result.get('message'), str)
            assert isinstance(get_address_txs_result.get('result'), list)
            key2check = [('blockHash', str), ('blockNumber', str), ('from', str), ('gas', str), ('gasPrice', str),
                         ('hash', str), ('to', str), ('value', str), ('timeStamp', str), ('confirmations', str)]
            for tx in get_address_txs_result.get('result'):
                for key, value in key2check:
                    assert isinstance(tx.get(key), value)

    @pytest.mark.slow
    def test_get_token_txs_api(self):
        for address in self.account_address:
            contract_info = polygon_ERC20_contract_info.get('mainnet').get(Currencies.usdc)
            get_token_txs_result = self.api.get_token_txs(address, contract_info)
            assert isinstance(get_token_txs_result, dict)
            assert isinstance(get_token_txs_result.get('status'), str)
            assert isinstance(get_token_txs_result.get('message'), str)
            assert isinstance(get_token_txs_result.get('result'), list)
            key2check = [('blockHash', str), ('blockNumber', str), ('from', str), ('gas', str), ('gasPrice', str),
                         ('hash', str), ('to', str), ('value', str), ('timeStamp', str), ('confirmations', str),
                         ('contractAddress', str)]
            for tx in get_token_txs_result.get('result'):
                for key, value in key2check:
                    assert isinstance(tx.get(key), value)

    @pytest.mark.slow
    def test_get_block_txs_api(self):
        for block in self.blocks:
            get_block_txs_result = self.api().get_block_txs(block)
            assert isinstance(get_block_txs_result, dict)
            assert isinstance(get_block_txs_result.get('id'), int)
            assert isinstance(get_block_txs_result.get('jsonrpc'), str)
            assert isinstance(get_block_txs_result.get('result'), dict)
            key2check_result = [('hash', str), ('parentHash', str), ('timestamp', str), ('transactions', list)]
            key2check_transaction = [('blockHash', str), ('blockNumber', str), ('from', str), ('gas', str), ('to', str),
                                     ('gasPrice', str), ('hash', str), ('value', str)]

            for key, value in key2check_result:
                assert isinstance(get_block_txs_result.get('result').get(key), value)
            for tx in get_block_txs_result.get('result').get('transactions'):
                for key, value in key2check_transaction:
                    assert isinstance(tx.get(key), value)
