from datetime import datetime
from decimal import Decimal
from typing import Any, Dict

import pytest

from exchange.explorer.networkproviders.models import Network, Operation
from exchange.explorer.transactions.models import Transfer


@pytest.fixture
def persisted_transfer() -> Transfer:
    return Transfer.objects.create(
        tx_hash='tx_hash',
        success=True,
        from_address_str='0x7Cb027917b27BCb5963C548657a008BF45b25BDc',
        to_address_str='0x7Cb027917b27BCb5963C548657a008BF45b25BDa',
        value='12.64649',
        network=Network.objects.filter(name='ETH').get(),
        symbol='USDT',
        block_height=123456,
        block_hash='block_hash',
        date=datetime.fromisoformat('2025-03-04 17:23:03.123456'),
        memo='',
        tx_fee='0.1313',
        token='token_address',
        source_operation=Operation.ADDRESS_TXS,
        created_at=datetime.fromisoformat('2025-03-04 17:23:03.123456'),
    )


@pytest.fixture
def address() -> str:
    return '0x7cb027917b27bcb5963c548657a008bf45b25bdc'


@pytest.fixture
def get_txs_incoming_tx(address: str) -> Dict[str, Any]:
    return {
        'amount': Decimal('0.6093049649208180'),
        'from_address': '0xd09a63071296b4e422fd7f72f6f3c76df7b80ba2',
        'to_address': address,
        'hash': '0x326696f1d2aee09970d0cba08082da3791fc95b93a2c5c3fc7262fdb55fe833d',
        'block': 22266580,
        'date': datetime.now(),
        'memo': None,
        'confirmations': 6,
        'address': address,
        'direction': 'incoming',
        'raw': None
    }


@pytest.fixture
def get_txs_incoming_tx_different_hash(address: str) -> Dict[str, Any]:
    return {
        'amount': Decimal('0.6093049649208180'),
        'from_address': '0xd09a63071296b4e422fd7f72f6f3c76df7b80ba2',
        'to_address': address,
        'hash': '0x326696f1d2aee09970d0cba08082da3791fc95b93a2c5c3fc7262fdb55fe833x',
        'block': 22266580,
        'date': datetime.now(),
        'memo': None,
        'confirmations': 6,
        'address': address,
        'direction': 'incoming',
        'raw': None
    }


@pytest.fixture
def get_txs_outgoing_tx(address: str) -> Dict[str, Any]:
    return {
        'amount': Decimal('0.6093049649208180'),
        'from_address': address,
        'to_address': '0xd09a63071296b4e422fd7f72f6f3c76df7b80ba2',
        'hash': '0x326696f1d2aee09970d0cba08082da3791fc95b93a2c5c3fc7262fdb55fe833d',
        'block': 22266580,
        'date': datetime.now(),
        'memo': None,
        'confirmations': 6,
        'address': address,
        'direction': 'outgoing',
        'raw': None
    }


@pytest.fixture
def get_txs_incoming_tx__less_then_min_value(address: str) -> Dict[str, Any]:
    return {
        'amount': Decimal('0.000006093049649208180'),
        'from_address': '0xd09a63071296b4e422fd7f72f6f3c76df7b80ba2',
        'to_address': address,
        'hash': '0x326696f1d2aee09970d0cba08082da3791fc95b93a2c5c3fc7262fdb55fe833d',
        'block': 22266580,
        'date': datetime.now(),
        'memo': None,
        'confirmations': 6,
        'address': address,
        'direction': 'incoming',
        'raw': None
    }
