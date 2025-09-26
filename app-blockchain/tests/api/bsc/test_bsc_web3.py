import pytest
from unittest import TestCase
from hexbytes import HexBytes
from web3.datastructures import AttributeDict
from exchange.blockchain.api.bsc.bsc_web3_new import BSCWeb3Api
from exchange.base.models import Currencies
from exchange.blockchain.contracts_conf import BEP20_contract_info


class TestPolygonWeb3ApiCalls(TestCase):
    api = BSCWeb3Api
    account_address = ['0xf4c21a1cB819E5F7ABe6dEFde3d118D8F3D61FA7']

    txs_hash = ['0xf6869d62122c9d7a48dd78892788be0a2b2c4a90f2bd0329121b7bcf1bc0ec73']

    blocks = [41133333, 41156001, 40057005, 39057645]

    @pytest.mark.slow
    def test_get_balance_api(self):
        for address in self.account_address:
            get_balance_result = self.api().get_balance(address)
            assert isinstance(get_balance_result, int)

    @pytest.mark.slow
    def test_get_token_balance_api(self):
        contract_info = BEP20_contract_info.get('mainnet').get(Currencies.usdc)
        for address in self.account_address:
            get_token_balance_result = self.api().get_token_balance(address, contract_info)
            assert isinstance(get_token_balance_result, int)

    @pytest.mark.slow
    def test_get_block_head_api(self):
        get_block_head_result = self.api().get_block_head()
        assert isinstance(get_block_head_result, int)

    @pytest.mark.slow
    def test_get_tx_details_api(self):
        for tx_hash in self.txs_hash:
            get_details_tx_result = self.api().get_tx_details(tx_hash)
            assert isinstance(get_details_tx_result, AttributeDict)
            key2check = [('blockHash', HexBytes), ('blockNumber', int), ('from', str), ('to', str), ('value', int),
                         ('hash', HexBytes), ('input', str)]
            for key, value in key2check:
                assert isinstance(get_details_tx_result.get(key), value)

    @pytest.mark.slow
    def test_get_block_txs_api(self):
        for block in self.blocks:
            get_block_txs_result = self.api().get_block_txs(block)
            assert isinstance(get_block_txs_result, AttributeDict)
            key2check = [('hash', HexBytes), ('number', int), ('parentHash', HexBytes), ('timestamp', int),
                         ('transactions', list), ]
            for key, value in key2check:
                assert isinstance(get_block_txs_result.get(key), value)
            key2check_transaction = [('blockHash', HexBytes), ('blockNumber', int), ('from', str), ('gas', int),
                                     ('to', str), ('value', int), ('hash', HexBytes)]
            for tx in get_block_txs_result.get('transactions'):
                assert isinstance(tx, AttributeDict)
                for key, value in key2check_transaction:
                    assert isinstance(tx.get(key), value)
