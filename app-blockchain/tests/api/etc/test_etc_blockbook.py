import pytest
import unittest

from exchange.blockchain.api.etc.etc_blockbook import EthereumClassicBlockBookApi


@pytest.mark.slow
class TestETCBlockBookApiCall(unittest.TestCase):
    api = EthereumClassicBlockBookApi
    txs_hash = ['0x4148a75cae643fdf46684a4e1c80dfac165511f1f463bffb642b6c6887fd9ccd']
    addresses = ['0xc84bB723F0D8C18093fcf8651d3957835b82492b']
    block_numbers = [20653233, 20653238]

    @classmethod
    def test_get_block_head_api(cls):
        block_head_response = cls.api.get_block_head()
        assert isinstance(block_head_response, dict)
        assert isinstance(block_head_response.get('blockbook'), dict)
        assert isinstance(block_head_response.get('blockbook').get('inSync'), bool)
        assert isinstance(block_head_response.get('backend'), dict)
        assert isinstance(block_head_response.get('blockbook').get('bestHeight'), int)

    @classmethod
    def test_get_balance_api(cls):
        for address in cls.addresses:
            balance_response = cls.api.get_balance(address)
            assert isinstance(balance_response, dict)
            keys2check = [('page', int), ('totalPages', int), ('address', str), ('balance', str),
                          ('unconfirmedBalance', str), ('txs', int), ('transactions', list)]
            for key, value in keys2check:
                assert isinstance(balance_response.get(key), value)

    @classmethod
    def test_get_tx_details_api(cls):
        for tx_hash in cls.txs_hash:
            tx_details_response = cls.api.get_tx_details(tx_hash)
            tx_key2check = [('txid', str), ('vin', list), ('vout', list),
                            ('blockHash', str), ('blockHeight', int), ('confirmations', int), ('blockTime', int),
                            ('value', str), ('fees', str)]
            for key, value in tx_key2check:
                assert isinstance(tx_details_response.get(key), value)
            for tx in tx_details_response.get('vout'):
                assert isinstance(tx.get('addresses'), list)
                assert isinstance(tx.get('value'), str)

    @classmethod
    def test_get_address_txs_api(cls):
        for address in cls.addresses:
            address_txs_response = cls.api.get_address_txs(address)
            assert isinstance(address_txs_response, dict)
            keys2check = [('page', int), ('totalPages', int), ('address', str), ('balance', str),
                          ('unconfirmedBalance', str), ('txs', int), ('transactions', list)]
            for key, value in keys2check:
                assert isinstance(address_txs_response.get(key), value)
            tx_key2check = [('txid', str), ('vin', list), ('vout', list),
                            ('blockHash', str), ('blockHeight', int), ('confirmations', int), ('blockTime', int),
                            ('value', str), ('fees', str)]
            for tx in address_txs_response.get('transactions'):
                for key, value in tx_key2check:
                    assert isinstance(tx.get(key), value)
                for output_tx in tx.get('vout'):
                    assert isinstance(output_tx.get('addresses'), list)
                    assert isinstance(output_tx.get('value'), str)

    @classmethod
    def test_get_block_txs_api(cls):
        for block_height in cls.block_numbers:
            block_txs_response = cls.api.get_block_txs(block_height, page=1)
            assert isinstance(block_txs_response, dict)
            key2ckeck = [('page', int), ('totalPages', int), ('hash', str), ('height', int), ('confirmations', int),
                         ('size', int), ('time', int), ('version', int), ('txCount', int)]
            for key, value in key2ckeck:
                assert isinstance(block_txs_response.get(key), value)
            for tx in block_txs_response.get('txs', []):
                for output_tx in tx.get('vout'):
                    if output_tx.get('isAddress'):
                        assert isinstance(output_tx.get('addresses'), list)
                        assert isinstance(output_tx.get('value'), str)
