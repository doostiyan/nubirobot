import datetime
from decimal import Decimal

import pytest
import pytz
from rest_framework.reverse import reverse

from exchange.blockchain.api.general.dtos import TransferTx


@pytest.fixture
def batch_tx_detail_url_dynamic() -> str:
    return reverse(
        'transactions:batch_transaction_details',
        kwargs={'network': 'ADA'},
    ) + '?provider=test_provider&base_url=https://some.api'


@pytest.fixture
def batch_tx_detail_url_static() -> str:
    return reverse(
        'transactions:batch_transaction_details',
        kwargs={'network': 'ADA'},
    )


@pytest.fixture
def valid_batch_tx_detail_payload() -> dict:
    return {'tx_hashes': ['abc123', 'def456']}


@pytest.fixture
def valid_transfer() -> TransferTx:
    return TransferTx(
        tx_hash='d7ff7b0e9da6048b2c9aa103bc396f1eebe96b6cf076971f4a47f6c066af810e',
        success=True,
        from_address='EQCW9JCezZp01q0g5vSCbDnEjytQqD-9sL3yghMduOcN_w24',
        to_address='',
        value=Decimal('-42910.000000000'),
        symbol='DOGS',
        confirmations=591,
        block_height=0,
        block_hash=None,
        date=datetime.datetime(2025, 2, 2, 6, 3, 21, tzinfo=pytz.UTC),
        memo='1258333387',
        tx_fee=None,
        token=None,
        index=0,
    )
