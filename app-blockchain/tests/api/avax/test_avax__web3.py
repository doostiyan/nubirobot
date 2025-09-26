import pytest
from unittest import TestCase
from hexbytes import HexBytes
from web3.datastructures import AttributeDict
from exchange.blockchain.api.avax.avax_web3_new import AvalancheWeb3API


class TestAvaxWeb3ApiCalls(TestCase):
    api = AvalancheWeb3API
    account_address = ['0x24e4B80b88ac05E972B5CF0c6178C06f44BBe059']

    txs_hash = ['0xdcf4e546b8c70c2ad5e5625d4942bbfeee3c3c2c9065bb3d069f9c5bc89d061b']

    blocks = [48092650, 48092661]

    @pytest.mark.slow
    def test_get_balance_api(self):
        for address in self.account_address:
            get_balance_result = self.api().get_balance(address)
            assert isinstance(get_balance_result, int)

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
                         ('hash', HexBytes)]
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
