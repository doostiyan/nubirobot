import pytest

from exchange.corporate_banking.helpers import (
    get_nobitex_bank_choice_from_jibit_name,
    get_nobitex_bank_choice_from_toman_choice,
)
from exchange.corporate_banking.models import TOMAN_BANKS


class TestBankFunctions:
    @pytest.mark.parametrize(
        'jibit_input, expected_bank_id',
        [
            # Valid known mappings
            ('MARKAZI', 10),  # => BANK_ID.centralbank
            ('MELLAT', 12),  # => BANK_ID.mellat
            ('SHAHR', 61),  # => BANK_ID.shahr
            ('NOOR', 80),  # => BANK_ID.noor
            # An invalid input
            ('UNKNOWN', None),
            ('', None),
        ],
    )
    def test_get_bank_id_from_jibit_name(self, jibit_input, expected_bank_id):
        """
        Test get_bank_id_from_jibit_name with known valid and invalid inputs.
        """
        returned_choice = get_nobitex_bank_choice_from_jibit_name(jibit_input)

        if expected_bank_id is None:
            assert returned_choice is None
        else:
            # returned_choice is an integer code from BANK_ID
            assert returned_choice == expected_bank_id

    @pytest.mark.parametrize(
        'toman_input, expected_bank_id',
        [
            # Valid known mappings
            (TOMAN_BANKS.Shahr, 61),  # => BANK_ID.shahr
            (TOMAN_BANKS.Melli, 17),  # => BANK_ID.melli
            (TOMAN_BANKS.Mellat, 12),  # => BANK_ID.mellat
            (TOMAN_BANKS.Parsian, 54),  # => BANK_ID.parsian
            (TOMAN_BANKS.Maskan, 14),  # => BANK_ID.maskan
            # An invalid input
            ('SomNonExistentBank', None),
            ('', None),
        ],
    )
    def test_get_bank_id_from_toman_choice(self, toman_input, expected_bank_id):
        """
        Test get_bank_id_from_toman_choice with known valid and invalid inputs.
        """
        returned_choice = get_nobitex_bank_choice_from_toman_choice(toman_input)

        if expected_bank_id is None:
            assert returned_choice is None
        else:
            assert returned_choice == expected_bank_id
