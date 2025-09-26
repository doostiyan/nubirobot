from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from django.utils.timezone import make_aware, utc
from pytest_mock import MockerFixture

ADA_TX_HASH: str = '8d5057bdaf6117621641b5f737a800286c00616b24d93cb68e166d4fb6851d38'


@pytest.fixture
def ada_explorer_interface(mocker: MockerFixture) -> MagicMock:
    mock_data = MagicMock()
    mock_data.hash = ADA_TX_HASH
    mock_data.success = True
    mock_data.block = 6828440
    mock_data.confirmations = 4897413
    mock_data.fees = Decimal('0.0001')
    mock_data.date = datetime(2024, 4, 1, 12, 30, 0, tzinfo=timezone.utc)
    mock_data.transfers = [
        {
            'currency': 21,
            'from': 'addr1qxx7ps9egm77zws7rvf3mk56kcgsvye4mlxfdr2gsetdgx20wep2023z0nydf2m'
                    'gfkxll7hs4fet7uxdr9vh8ufg95ys6tuttr',
            'is_valid': True,
            'memo': None,
            'symbol': 'ADA',
            'to': '',
            'token': None,
            'type': 'MainCoin',
            'value': Decimal('1.344798'),
        },
    ]

    mocker.patch(
        'exchange.blockchain.api.ada.cardano_explorer_interface.CardanoExplorerInterface.get_tx_details',
        return_value=mock_data
    )
    return mock_data
