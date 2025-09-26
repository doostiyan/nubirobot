from datetime import datetime
from decimal import Decimal

import pytest

from exchange.explorer.networkproviders.models import Network, Operation
from exchange.explorer.transactions.models import Transfer


@pytest.fixture
def tx_hash() -> str:
    return '0x326696f1d2aee09970d0cba08082da3791fc95b93a2c5c3fc7262fdb55fe833d'


@pytest.fixture
def tx_hash_second() -> str:
    return '0x326696f1d2aee09970d0cba08082da3791fc95b93a2c5c3fc7262fdb55fe8321'


@pytest.fixture
def address() -> str:
    return '0xd5fbda4c79f38920159fe5f22df9655fde292d47'


@pytest.fixture
def persisted_transfer(tx_hash: str, address: str) -> Transfer:
    return Transfer.objects.create(
        tx_hash=tx_hash,
        success=True,
        from_address_str='0x7Cb027917b27BCb5963C548657a008BF45b25BDc',
        to_address_str=address,
        value='12.64649',
        network=Network.objects.filter(name='ETH').get(),
        symbol='USDT',
        block_height=123456,
        block_hash='block_hash',
        date=datetime.fromisoformat('2025-03-04 17:23:03.123456'),
        memo='',
        tx_fee='0.1313',
        token='token_address',
        source_operation=Operation.TOKEN_TXS,
        created_at=datetime.fromisoformat('2025-03-04 17:23:03.123456'),
    )


@pytest.fixture
def persisted_transfer__same_to_address__different_hash(address: str) -> Transfer:
    return Transfer.objects.create(
        tx_hash='0x672d61dedf100e083924bd18dfff4a68dbf6ab7057b37998d07e5ba51abd6d12',
        success=True,
        from_address_str='0x7Cb027917b27BCb5963C548657a008BF45b25BDc',
        to_address_str=address,
        value='12.64649',
        network=Network.objects.filter(name='ETH').get(),
        symbol='USDT',
        block_height=123456,
        block_hash='block_hash',
        date=datetime.fromisoformat('2025-03-04 17:23:03.123456'),
        memo='',
        tx_fee='0.1313',
        token='token_address',
        source_operation=Operation.TOKEN_TXS,
        created_at=datetime.fromisoformat('2025-03-04 17:23:03.123456'),
    )


@pytest.fixture
def tx_details(tx_hash: str, address: str) -> dict:
    return {
        'hash': tx_hash,
        'success': True,
        'block': 22316555,
        'date': datetime.fromisoformat('2025-03-04 17:23:03.123456'),
        'fees': None,
        'memo': None,
        'confirmations': 5,
        'raw': None,
        'inputs': [],
        'outputs': [],
        'transfers': [
            {
                'type': 'MainCoin',
                'symbol': 'ETH',
                'currency': 11,
                'from': '0x4b158f48b9483ea86198669880e6ea025342bc22',
                'to': address,
                'value': Decimal('0.139652144607470000'),
                'is_valid': True,
                'token': None,
                'memo': None
            }
        ]
    }


@pytest.fixture
def tx_details_with_second_hash(tx_hash_second: str, address: str) -> dict:
    return {
        'hash': tx_hash_second,
        'success': True,
        'block': 22316555,
        'date': datetime.fromisoformat('2025-03-04 17:23:03.123456'),
        'fees': None,
        'memo': None,
        'confirmations': 5,
        'raw': None,
        'inputs': [],
        'outputs': [],
        'transfers': [
            {
                'type': 'MainCoin',
                'symbol': 'ETH',
                'currency': 11,
                'from': '0x4b158f48b9483ea86198669880e6ea025342bc22',
                'to': address,
                'value': Decimal('0.139652144607470000'),
                'is_valid': True,
                'token': None,
                'memo': None
            }
        ]
    }


@pytest.fixture
def tx_details_without_date(tx_hash: str, address: str) -> dict:
    return {
        'hash': tx_hash,
        'success': True,
        'block': 22316555,
        'date': None,
        'fees': None,
        'memo': None,
        'confirmations': 5,
        'raw': None,
        'inputs': [],
        'outputs': [],
        'transfers': [
            {
                'type': 'MainCoin',
                'symbol': 'ETH',
                'currency': 11,
                'from': '0x4b158f48b9483ea86198669880e6ea025342bc22',
                'to': address,
                'value': Decimal('0.139652144607470000'),
                'is_valid': True,
                'token': None,
                'memo': None
            }
        ]
    }


@pytest.fixture
def token_tx_details(tx_hash: str, address: str) -> dict:
    return {
        'hash': tx_hash,
        'success': True,
        'block': 22316555,
        'date': datetime.fromisoformat('2025-03-04 17:23:03.123456'),
        'fees': None,
        'memo': None,
        'confirmations': 15,
        'raw': None,
        'inputs': [],
        'outputs': [],
        'transfers': [
            {
                'type': 'Token',
                'symbol': 'USDT',
                'currency': 13,
                'from': '0x4f051fe53673e824d734f02000d4efe50dec75f7',
                'to': address,
                'value': Decimal('1150.000000'),
                'is_valid': True,
                'token': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                'memo': None
            }
        ]
    }


@pytest.fixture
def token_tx_details_with_second_hash(tx_hash_second: str, address: str) -> dict:
    return {
        'hash': tx_hash_second,
        'success': True,
        'block': 22316555,
        'date': datetime.fromisoformat('2025-03-04 17:23:03.123456'),
        'fees': None,
        'memo': None,
        'confirmations': 15,
        'raw': None,
        'inputs': [],
        'outputs': [],
        'transfers': [
            {
                'type': 'Token',
                'symbol': 'USDT',
                'currency': 13,
                'from': '0x4f051fe53673e824d734f02000d4efe50dec75f7',
                'to': address,
                'value': Decimal('1150.000000'),
                'is_valid': True,
                'token': '0xdac17f958d2ee523a2206206994597c13d831ec7',
                'memo': None
            }
        ]
    }


@pytest.fixture
def get_txs_incoming_tx(address: str, tx_hash: str) -> dict:
    return {
        'amount': Decimal('1150.000000'),
        'from_address': '0x4f051fe53673e824d734f02000d4efe50dec75f7',
        'to_address': address,
        'hash': tx_hash,
        'block': 22316555,
        'date': datetime.fromisoformat('2025-03-04 17:23:03.123456'),
        'memo': None,
        'confirmations': 15,
        'address': address,
        'direction': 'incoming',
        'raw': None
    }
