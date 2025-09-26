import datetime
from decimal import Decimal

import pytz

from exchange.blockchain.models import Currencies
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.tests.fixtures.sol_fixtures import sol_parsed_multi_transfer_address_txs, sol_multi_transfer_address


def test__convert_transfers2list_of_address_txs_dict__should_filter_other_addresses_transfers(
        sol_parsed_multi_transfer_address_txs,
        sol_multi_transfer_address):
    result = ExplorerInterface.convert_transfers2list_of_address_txs_dict(
        address=sol_multi_transfer_address,
        transfers=sol_parsed_multi_transfer_address_txs,
        currency=Currencies.sol)

    expected_result = [
        {
            Currencies.sol: {
                'address': 'H6CnHUQ3ZBi3AmeQhrQtfx2mo2YEghStkbX4KdLnVvrQ',
                'amount': Decimal('0.001000000'),
                'block': 316514709,
                'confirmations': 183732,
                'date': datetime.datetime(2025, 1, 26, 18, 57, tzinfo=pytz.UTC),
                'direction': 'incoming',
                'from_address': 'GagXj5rERPBfiaEEdJ87trQrdmo2i7tLWq17vMJ7q8xv',
                'hash': '4gS19hrer6Cx6H2f6wEM594vS5qsFTHZ3Ci36rgDL9Z4HZcnYsqPLupoHcW6xQXmrkh7ZEqB9dAxZ1huUcs7uBCc',
                'memo': None,
                'raw': None,
                'to_address': 'H6CnHUQ3ZBi3AmeQhrQtfx2mo2YEghStkbX4KdLnVvrQ'
            }
        }
    ]

    assert result == expected_result
