import unittest
import pytest

from exchange.blockchain.api.ltc.ltc_blockbook_new import LiteCoinBlockBookAPI, LiteCoinHeatWalletBlockbookAPI


@pytest.mark.slow
class TestLiteCoinBlockBookApiCall(unittest.TestCase):
    api = LiteCoinBlockBookAPI
    txs_hash = ['a9e13035052225a65ed7d9fd400d65a57e471d1d1fbf7121207f803e4e9681ef',
                '83b41ceb8e79209bec1c82aa0ae8c9a83db87e6e199f764a167b6ee5e01a3026',
                '29c38cc2b50b6da5d42f2af92325ea1295fce613b3bd10f6c8205d35f16a9f2d']
    addresses = ['MTQHeDv2U8XnkkxsnwKWRaGRDKPr1QS5aw', 'ltc1qlehlqrsatnv4d8k5kxjkwut2dsk4gxmxlwyam8']
    block_numbers = [2733734, 2733733]

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
            tx_key2check = [('txid', str), ('version', int), ('vin', list), ('vout', list),
                            ('blockHash', str), ('blockHeight', int), ('confirmations', int), ('blockTime', int),
                            ('value', str), ('fees', str), ('hex', str)]
            for key, value in tx_key2check:
                assert isinstance(tx_details_response.get(key), value)
            for tx in tx_details_response.get('vin'):
                assert isinstance(tx.get('addresses'), list)
                assert isinstance(tx.get('value'), str)
            for tx in tx_details_response.get('vout'):
                assert isinstance(tx.get('addresses'), list)
                assert isinstance(tx.get('value'), str)

    @classmethod
    def test_get_address_txs_api(cls):
        for address in cls.addresses:
            address_txs_response = cls.api.get_address_txs(address)
            assert isinstance(address_txs_response, dict)
            keys2check = [('page', int), ('totalPages', int), ('address', str), ('balance', str),
                          ('unconfirmedBalance', str), ('txs', int)]
            for key, value in keys2check:
                assert isinstance(address_txs_response.get(key), value)
            tx_key2check = [('txid', str), ('version', int), ('vin', list), ('vout', list),
                            ('blockHeight', int), ('confirmations', int), ('blockTime', int),
                            ('value', str), ('fees', str), ('hex', str)]
            if address_txs_response.get('transactions'):
                for tx in address_txs_response.get('transactions'):
                    for key, value in tx_key2check:
                        assert isinstance(tx.get(key), value)
                    for input_tx in tx.get('vin'):
                        assert isinstance(input_tx.get('addresses'), list)
                        assert isinstance(input_tx.get('value'), str)
                    for output_tx in tx.get('vout'):
                        assert isinstance(output_tx.get('addresses'), list)
                        assert isinstance(output_tx.get('value'), str)

    @classmethod
    def test_get_block_txs_api(cls):
        for block_height in cls.block_numbers:
            block_txs_response = cls.api.get_block_txs(block_height, page=1)
            assert isinstance(block_txs_response, dict)
            key2ckeck = [('page', int), ('totalPages', int), ('hash', str), ('height', int), ('confirmations', int),
                         ('size', int), ('time', int), ('version', int), ('txCount', int), ('txs', list)]
            for key, value in key2ckeck:
                assert isinstance(block_txs_response.get(key), value)
            for tx in block_txs_response.get('txs'):
                for input_tx in tx.get('vin'):
                    if input_tx.get('isAddress'):
                        assert isinstance(input_tx.get('addresses'), list)
                        assert isinstance(input_tx.get('value'), str)
                for output_tx in tx.get('vout'):
                    if input_tx.get('isAddress'):
                        assert isinstance(output_tx.get('addresses'), list)
                        assert isinstance(output_tx.get('value'), str)


@pytest.mark.slow
class TestLiteCoinHeatWalletApiCall(unittest.TestCase):
    api = LiteCoinHeatWalletBlockbookAPI
    txs_hash = ['a9e13035052225a65ed7d9fd400d65a57e471d1d1fbf7121207f803e4e9681ef',
                '83b41ceb8e79209bec1c82aa0ae8c9a83db87e6e199f764a167b6ee5e01a3026',
                '29c38cc2b50b6da5d42f2af92325ea1295fce613b3bd10f6c8205d35f16a9f2d']
    addresses = ['MTQHeDv2U8XnkkxsnwKWRaGRDKPr1QS5aw', 'ltc1qlehlqrsatnv4d8k5kxjkwut2dsk4gxmxlwyam8']
    block_numbers = [2733734, 2733733]

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
            tx_key2check = [('txid', str), ('version', int), ('vin', list), ('vout', list),
                            ('blockHash', str), ('blockHeight', int), ('confirmations', int), ('blockTime', int),
                            ('value', str), ('fees', str), ('hex', str)]
            for key, value in tx_key2check:
                assert isinstance(tx_details_response.get(key), value)
            for tx in tx_details_response.get('vin'):
                assert isinstance(tx.get('addresses'), list)
                assert isinstance(tx.get('value'), str)
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
            tx_key2check = [('txid', str), ('version', int), ('vin', list), ('vout', list),
                            ('blockHeight', int), ('confirmations', int), ('blockTime', int),
                            ('value', str), ('fees', str), ('hex', str)]
            for tx in address_txs_response.get('transactions'):
                for key, value in tx_key2check:
                    assert isinstance(tx.get(key), value)
                for input_tx in tx.get('vin'):
                    assert isinstance(input_tx.get('addresses'), list)
                    assert isinstance(input_tx.get('value'), str)
                for output_tx in tx.get('vout'):
                    assert isinstance(output_tx.get('addresses'), list)
                    assert isinstance(output_tx.get('value'), str)

    @classmethod
    def test_get_block_txs_api(cls):
        for block_height in cls.block_numbers:
            block_txs_response = cls.api.get_block_txs(block_height, page=1)
            assert isinstance(block_txs_response, dict)
            key2ckeck = [('page', int), ('totalPages', int), ('hash', str), ('height', int), ('confirmations', int),
                         ('size', int), ('time', int), ('version', int), ('txCount', int), ('txs', list)]
            for key, value in key2ckeck:
                assert isinstance(block_txs_response.get(key), value)
            for tx in block_txs_response.get('txs'):
                for input_tx in tx.get('vin'):
                    if input_tx.get('isAddress'):
                        assert isinstance(input_tx.get('addresses'), list)
                        assert isinstance(input_tx.get('value'), str)
                for output_tx in tx.get('vout'):
                    if input_tx.get('isAddress'):
                        assert isinstance(output_tx.get('addresses'), list)
                        assert isinstance(output_tx.get('value'), str)
