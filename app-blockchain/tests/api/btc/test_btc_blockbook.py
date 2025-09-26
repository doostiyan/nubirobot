import pytest
from unittest import TestCase

from exchange.blockchain.api.btc.btc_blockbook_new import BitcoinBlockBookAPI


class BitcoinBlockBookApisCall(TestCase):
    API = BitcoinBlockBookAPI
    addresses = ['bc1qan7fcs73tf6v2fnuf9alyzvv0w87k9nxsd9je6', '1K6KoYC69NnafWJ7YgtrpwJxBLiijWqwa6']
    hashes = ['79b6a6c911761da96362478b03a735af38c5c97a0c28813abf6c46c9a0612430',
              'efd9ed7fd458ab8877939e99fb7ddddea0d8dd0db332f2ca827c5805ae71edeb']
    blocks = [840000, 857000]

    def check_transaction_keys(self, transaction):
        key2check = [('txid', str), ('vin', list), ('vout', list), ('blockHash', str), ('blockHeight', int),
                     ('confirmations', int), ('blockTime', int), ('value', str), ('valueIn', str), ('fees', str)]
        for key, value in key2check:
            assert isinstance(transaction.get(key), value)
        key2check_utxo = [('addresses', list), ('isAddress', bool), ('value', str)]
        for input_ in transaction.get('vin'):
            if input_.get('isAddress'):
                for key, value in key2check_utxo:
                    assert isinstance(input_.get(key), value)
        for output_ in transaction.get('vout'):
            if output_.get('isAddress'):
                for key, value in key2check_utxo:
                    assert isinstance(output_.get(key), value)

    @pytest.mark.slow
    def test_get_block_head_api(self):
        block_head_response = self.API.get_block_head()
        assert isinstance(block_head_response, dict)
        assert isinstance(block_head_response.get('blockbook'), dict)
        assert isinstance(block_head_response.get('backend'), dict)
        key2check = [('chain', str), ('blocks', int), ('headers', int), ('bestBlockHash', str), ('difficulty', str),
                     ('version', str)]
        for key, value in key2check:
            assert isinstance(block_head_response.get('backend').get(key), value)

    @pytest.mark.slow
    def test_get_balance_api(self):
        for address in self.addresses:
            balance_response = self.API.get_balance(address)
            assert isinstance(balance_response, dict)
            key2check = [('address', str), ('balance', str), ('totalReceived', str), ('totalSent', str),
                         ('unconfirmedBalance', str)]
            for key, value in key2check:
                assert isinstance(balance_response.get(key), value)

    @pytest.mark.slow
    def test_get_tx_details_api(self):
        for tx_hash in self.hashes:
            tx_details_response = self.API.get_tx_details(tx_hash)
            assert isinstance(tx_details_response, dict)
            self.check_transaction_keys(tx_details_response)

    @pytest.mark.slow
    def test_get_address_txs_api(self):
        for address in self.addresses:
            address_txs_response = self.API.get_address_txs(address)
            assert isinstance(address_txs_response, dict)
            key2check = [('txs', int), ('transactions', list), ('address', str)]
            for key, value in key2check:
                assert isinstance(address_txs_response.get(key), value)
            for transaction in address_txs_response.get('transactions'):
                self.check_transaction_keys(transaction)

    @pytest.mark.slow
    def test_get_txs_blocks_api(self):
        for block in self.blocks:
            block_txs_response = self.API.get_block_txs(block, page=-1)
            assert isinstance(block_txs_response, dict)
            key2check = [('hash', str), ('height', int), ('confirmations', int), ('time', int),
                         ('difficulty', str), ('txCount', int), ('txs', list)]
            for key, value in key2check:
                assert (block_txs_response.get(key), value)
            for transaction in block_txs_response.get('txs'):
                self.check_transaction_keys(transaction)
