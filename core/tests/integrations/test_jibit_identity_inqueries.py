import datetime
from unittest.mock import MagicMock, patch

import responses
from django.test import TestCase

from exchange.accounts.models import User
from exchange.integrations.jibit import JibitVerificationClient
from exchange.integrations.types import (
    CardToIbanAPICallResultV2,
    IdentityVerificationClientResult,
    VerificationAPIProviders,
)


class TestJibitIdentityInquires(TestCase):

    @responses.activate
    @patch('exchange.integrations.jibit.JibitVerificationClient._access_token', MagicMock(return_value='access_token'))
    def test_get_user_identity(self) -> None:
        user = User()
        user.national_code = '14152135235'
        user.first_name = 'test'
        user.last_name = 'test'
        user.birthday = datetime.date(1814, 12, 24)
        jibit_response = {
            'firstNameSimilarityPercentage': 45,
            'lastNameSimilarityPercentage': 88,
            'fullNameSimilarityPercentage': 87,
            'fatherNameSimilarityPercentage': 0,
        }
        responses.get(
            url='https://napi.jibit.ir/ide/v1/services/identity/similarity?checkAliveness=true&nationalCode=14152135235&birthDate=11931003&firstName=test&lastName=test&fullName=test%20test',
            json=jibit_response,
            status=200,
        )
        assert JibitVerificationClient().get_user_identity(user) == IdentityVerificationClientResult(
            provider=VerificationAPIProviders.JIBIT,
            api_response=jibit_response,
            first_name_similarity=45,
            last_name_similarity=88,
            full_name_similarity=87,
            father_name_similarity=None,
        )

    @responses.activate
    @patch('exchange.integrations.jibit.JibitVerificationClient._access_token', MagicMock(return_value='access_token'))
    def test_is_national_code_owner_of_mobile_number(self) -> None:
        national_code = '123421521'
        mobile = '64564654564'
        dummy_response = 'dummy response'
        responses.get(
            url=f'https://napi.jibit.ir/ide/v1/services/matching?nationalCode={national_code}&mobileNumber={mobile}',
            json={'matched': dummy_response},
            status=200,
        )
        assert JibitVerificationClient().is_national_code_owner_of_mobile_number(
            national_code,
            mobile,
        ) == (dummy_response, {'matched': dummy_response})

    @responses.activate
    @patch('exchange.integrations.jibit.JibitVerificationClient._access_token', MagicMock(return_value='access_token'))
    def test_is_user_owner_of_iban(self) -> None:
        first_name = 'kdlasgnls'
        last_name = '3tg2t'
        iban = '64564654564'
        dummy_response = 'dummy response'
        responses.get(
            url=f'https://napi.jibit.ir/ide/v1/services/matching?iban={iban}&name={first_name}%20{last_name}',
            json={'matched': dummy_response},
            status=200,
        )
        assert JibitVerificationClient().is_user_owner_of_iban(
            first_name,
            last_name,
            iban,
        ) == (dummy_response, {'matched': dummy_response})

    @responses.activate
    @patch('exchange.integrations.jibit.JibitVerificationClient._access_token', MagicMock(return_value='access_token'))
    def test_is_user_owner_of_bank_card(self) -> None:
        full_name = 'kdlasgnls'
        card_number = '64564654564'
        dummy_response = 'dummy response'
        responses.get(
            url=f'https://napi.jibit.ir/ide/v1/services/matching?cardNumber={card_number}&name={full_name}',
            json={'matched': dummy_response},
            status=200,
        )
        assert JibitVerificationClient().is_user_owner_of_bank_card(
            full_name,
            card_number,
        ) == (dummy_response, {'matched': dummy_response})

    @responses.activate
    @patch('exchange.integrations.jibit.JibitVerificationClient._access_token', MagicMock(return_value='access_token'))
    def test_convert_card_number_to_iban(self) -> None:
        card_number = '64564654564'
        response = {
            'number': '603712345678abcd',
            'type': 'DEBIT',
            'depositInfo': 'a message containing deposit information',
            'bank': 'bankId',
            'ibanInfo': {
            'depositNumber': 'af213tg2gy232tg2gh',
            'iban': 'af213tg2gy2h',
            'owners': [
                {'firstName': 'a', 'lastName': 'b'},
                {'firstName': 'x', 'lastName': 'y'},
            ]},
        }
        responses.get(
            url=f'https://napi.jibit.ir/ide/v1/cards?number={card_number}&iban=true',
            json=response,
            status=200,
        )

        assert JibitVerificationClient().convert_card_number_to_iban(card_number) == CardToIbanAPICallResultV2(
            provider=VerificationAPIProviders.JIBIT,
            api_response=response,
            deposit='af213tg2gy232tg2gh',
            iban='af213tg2gy2h',
            owners=['a b', 'x y'],
        )
