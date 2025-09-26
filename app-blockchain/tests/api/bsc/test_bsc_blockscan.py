import pytest
from unittest import TestCase
from exchange.base.models import Currencies
from exchange.blockchain.contracts_conf import BEP20_contract_info
from exchange.blockchain.api.bsc.bsc_scan_new import BSCBlockScanAPI


class TestPolygonBlockScanApiCalls(TestCase):
    api = BSCBlockScanAPI
    account_address = ['0xf4c21a1cB819E5F7ABe6dEFde3d118D8F3D61FA7']

    txs_hash = ['0xf6869d62122c9d7a48dd78892788be0a2b2c4a90f2bd0329121b7bcf1bc0ec73']

    blocks = [41133333, 41156001, 40057005, 39057645]

    def check_general_response(self, response):
        assert isinstance(response, dict)
        assert isinstance(response.get('status'), str)
        assert isinstance(response.get('message'), str)

    @pytest.mark.slow
    def test_get_balance_api(self):
        for address in self.account_address:
            get_balance_result = self.api().get_balance(address)
            self.check_general_response(get_balance_result)
            assert isinstance(get_balance_result.get('result'), str)

    @pytest.mark.slow
    def test_get_token_balance_api(self):
        contract_info = BEP20_contract_info.get('mainnet').get(Currencies.usdc)
        for address in self.account_address:
            get_token_balance_result = self.api.get_token_balance(address, contract_info)
            self.check_general_response(get_token_balance_result)
            assert isinstance(get_token_balance_result.get('result'), str)


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
            self.check_general_response(get_address_txs_result)
            key2check = [('blockHash', str), ('blockNumber', str), ('from', str), ('gas', str), ('gasPrice', str),
                         ('hash', str), ('to', str), ('value', str), ('timeStamp', str), ('confirmations', str),
                         ('txreceipt_status', str), ('isError', str)]
            for tx in get_address_txs_result.get('result'):
                for key, value in key2check:
                    assert isinstance(tx.get(key), value)

    @pytest.mark.slow
    def test_get_token_txs_api(self):
        for address in self.account_address:
            contract_info = BEP20_contract_info.get('mainnet').get(Currencies.usdc)
            get_token_txs_result = self.api.get_token_txs(address, contract_info)
            self.check_general_response(get_token_txs_result)
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
