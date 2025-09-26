import datetime

import pytest

from exchange.accounts.models import User
from exchange.integrations.jibit import JibitVerificationClient


@pytest.mark.skip
def test_jibit_ide_integration_live():
    """This test should be run manually"""

    client = JibitVerificationClient()

    sorush = User(
        first_name='سروش',
        last_name='بهاریان',
        birthday=datetime.date(1993, 9, 27),
        national_code='0016589882',
    )
    get_user_identity_response = client.get_user_identity(sorush)
    assert get_user_identity_response.first_name_similarity == 100
    assert get_user_identity_response.last_name_similarity == 100
    assert get_user_identity_response.full_name_similarity == 100
    assert get_user_identity_response.father_name_similarity is None
    sorush.first_name = 'سروس'
    get_user_identity_response = client.get_user_identity(sorush)
    assert get_user_identity_response.first_name_similarity == 88
    assert get_user_identity_response.last_name_similarity == 100
    assert get_user_identity_response.full_name_similarity == 95
    assert get_user_identity_response.father_name_similarity is None

    assert client.is_national_code_owner_of_mobile_number('0016589882', '09366946395')[0] is True
    assert client.is_national_code_owner_of_mobile_number('6029729071', '09366946395')[0] is False

    assert client.is_user_owner_of_iban('سروش', 'بهاریان', 'IR210170000000217100046009')[0] is True
    assert client.is_user_owner_of_iban('سروش الدین', 'بهاریان', 'IR210170000000217100046009')[0] is False

    assert client.is_user_owner_of_bank_card('سروش بهاریان', '6037997325975721')[0] is True
    assert client.is_user_owner_of_bank_card('سروش الدین بهاریان', '6037997325975721')[0] is False

    response = client.convert_card_number_to_iban('6037997325975721')
    assert response.deposit == '0217100046009'
    assert response.iban == 'IR210170000000217100046009'

