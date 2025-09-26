import pytest
from django.conf import settings

from exchange.blockchain.api.eth.eth_blockbook_new import EthereumBlockBookApi
from exchange.blockchain.tests.api.general_test.test_api_call_utils import TestApiCallUtils

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

pytestmark = pytest.mark.slow

api = EthereumBlockBookApi()


def test__address_txs__successful():
    response = api.get_address_txs('0xd2674dA94285660c9b2353131bef2d8211369A4B')

    schema = {
        'transactions': {
            'txid': str,
            'blockHash': str,
            'blockHeight': int,
            'confirmations': int,
            'blockTime': int,
            'fees': str,
            'value': str,
            'vin': {
                'addresses': list,
                'isAddress': bool
            },
            'vout': {
                'addresses': list,
                'isAddress': bool
            },
        }
    }

    TestApiCallUtils.assert_schema(response, schema)


def test__token_txs__successful():
    response = api.get_token_txs(
        '0xd5FBDa4C79F38920159fE5f22DF9655FDe292d47',
        api.parser.contract_info_list().get(Currencies.usdt)
    )

    schema = {
        'transactions': {
            'tokenTransfers': {
                'contract': str,
                'from': str,
                'to': str,
                'value': str,
                'decimals': int,
            },
            'txid': str,
            'blockHash': str,
            'blockHeight': int,
            'confirmations': int,
            'blockTime': int,
            'fees': str,
            'value': str,
            'vin': {
                'addresses': list,
                'isAddress': bool
            },
            'vout': {
                'addresses': list,
                'isAddress': bool
            },
        }
    }

    TestApiCallUtils.assert_schema(response, schema)


def test__block_txs__successful():
    response = api.get_block_txs(20744185, 1)

    schema = {
        'txs': {
            'txid': str,
            'blockHash': str,
            'blockHeight': int,
            'confirmations': int,
            'blockTime': int,
            'fees': str,
            'value': str,
            'vin': {
                'addresses': list,
                'isAddress': bool
            },
            'vout': {
                'addresses': list,
                'isAddress': bool
            },
        }
    }

    TestApiCallUtils.assert_schema(response, schema)


def test__tx_details__successful():
    response = api.get_tx_details('0xd06e96831786c0f0f3cf4202da1e3a3de3b6d49b094caa8545d5f4629a23a3c1')

    schema = {
        'txid': str,
        'ethereumSpecific': {
            'status': int
        },
        'value': str,
        'confirmations': int,
        'blockHeight': int,
        'blockTime': int,
        'fees': str,
        'vin': {
            'addresses': list,
            'isAddress': bool
        },
        'vout': {
            'addresses': list,
            'isAddress': bool
        }
    }

    TestApiCallUtils.assert_schema(response, schema)


def test__token_tx_details__successful():
    response = api.get_token_tx_details('0x8f347e2792d771f7b73e90ccd810e2dc70e4b3be7b3a7c6a93d0b77da2842d2a')

    schema = {
        'txid': str,
        'value': str,
        'confirmations': int,
        'blockHeight': int,
        'blockTime': int,
        'fees': str,
        'tokenTransfers': {
            'contract': str,
            'from': str,
            'to': str,
            'value': str,
            'decimals': int
        },
        'ethereumSpecific': {
            'status': int,
            'data': str
        }
    }

    TestApiCallUtils.assert_schema(response, schema)


def test__block_head__successful():
    response = api.get_block_head()

    schema = {
        'backend': dict,
        'blockbook': {
            'bestHeight': int,
        }
    }

    TestApiCallUtils.assert_schema(response, schema)
