import datetime
from unittest.mock import MagicMock, patch

import pytest
import responses
from django.test import TestCase

from exchange.accounts.models import User
from exchange.accounts.verificationapi import FinnotechAPIError, JibitAPIError
from exchange.base.models import Settings
from exchange.integrations.exceptions import VerificationAPIError
from exchange.integrations.finnotech import FinnotechVerificationClient
from exchange.integrations.jibit import JibitVerificationClient
from exchange.integrations.types import IdentityVerificationClientResult, VerificationAPIProviders
from exchange.integrations.verification import VerificationClient, VerificationProviders


class TestVerificationClientInquires(TestCase):
    def setUp(self):
        self.user = User()
        self.user.national_code = '14152135235'
        self.user.first_name = 'test'
        self.user.last_name = 'test'
        self.user.birthday = datetime.date(1814, 12, 24)

    def test_get_active_providers(self):
        Settings.set(
            'verification_providers',
            f'{VerificationAPIProviders.JIBIT.value},{VerificationAPIProviders.FINNOTECH.value}',
        )
        providers = VerificationProviders.get_active_providers()
        assert len(providers) == 2
        assert isinstance(providers[0], JibitVerificationClient)
        assert isinstance(providers[1], FinnotechVerificationClient)

        Settings.set(
            'verification_providers',
            f'{VerificationAPIProviders.JIBIT.value},invalid',
        )
        providers = VerificationProviders.get_active_providers()
        assert len(providers) == 1
        assert isinstance(providers[0], JibitVerificationClient)

        Settings.set(
            'verification_providers',
            f'{VerificationAPIProviders.JIBIT.value},',
        )
        providers = VerificationProviders.get_active_providers()
        assert len(providers) == 1
        assert isinstance(providers[0], JibitVerificationClient)

    def test_is_primary_provider(self):
        Settings.set(
            'verification_providers',
            f'{VerificationAPIProviders.JIBIT.value},{VerificationAPIProviders.FINNOTECH.value}',
        )
        providers = VerificationProviders.get_active_providers()
        assert VerificationProviders.is_primary_provider(providers[0])
        assert not VerificationProviders.is_primary_provider(providers[1])

    @responses.activate
    @patch(
        'exchange.integrations.finnotech.FinnotechVerificationClient.get_token',
        MagicMock(return_value='access_token'),
    )
    @patch('exchange.integrations.jibit.JibitVerificationClient._access_token', MagicMock(return_value='access_token'))
    def test_passing_provider(self):
        Settings.set(
            'verification_providers',
            f'{VerificationAPIProviders.JIBIT.value}',
        )

        _responses = {
            VerificationAPIProviders.FINNOTECH.value: {
                'error': {'code': 'SERVICE_CALL_ERROR', 'message': 'کد ملی یا تاریخ تولد اشتباه است'},
                'responseCode': 'FN-OHKZ-40003810019',
                'status': 'FAILED',
                'trackId': '97fc95fb-b083-4c85-b8a0-eaf44b79a02b',
            },
        }

        responses.get(
            url='https://apibeta.finnotech.ir/oak/v2/clients/nobitex/nidVerification?nationalCode=14152135235&birthDate=1193%2F10%2F03&fullName=test+test&firstName=test&lastName=test',
            json=_responses[VerificationAPIProviders.FINNOTECH.value],
            status=400,
        )

        assert VerificationClient(providers=[FinnotechVerificationClient()]).check_user_identity(self.user) == {
            'apiresponse': _responses[VerificationAPIProviders.FINNOTECH.value],
            'confidence': 100,
            'err_code': 'InvalidNationalCode',
            'message': 'کد ملی کاربر اشتباه است',
            'result': False,
        }

    @responses.activate
    @patch(
        'exchange.integrations.finnotech.FinnotechVerificationClient.get_token', MagicMock(return_value='access_token')
    )
    @patch('exchange.integrations.jibit.JibitVerificationClient._access_token', MagicMock(return_value='access_token'))
    def test_get_user_identity_not_found(self) -> None:
        _responses = {
            VerificationAPIProviders.JIBIT.value: {'code': 'identity_info.not_found', 'message': 'test message'},
            VerificationAPIProviders.FINNOTECH.value: {
                'error': {'code': 'SERVICE_CALL_ERROR', 'message': 'کد ملی یا تاریخ تولد اشتباه است'},
                'responseCode': 'FN-OHKZ-40003810019',
                'status': 'FAILED',
                'trackId': '97fc95fb-b083-4c85-b8a0-eaf44b79a02b',
            },
        }

        responses.get(
            url='https://napi.jibit.ir/ide/v1/services/identity/similarity?checkAliveness=true&nationalCode=14152135235&birthDate=11931003&firstName=test&lastName=test&fullName=test%20test',
            json=_responses[VerificationAPIProviders.JIBIT.value],
            status=404,
        )
        responses.get(
            url='https://apibeta.finnotech.ir/oak/v2/clients/nobitex/nidVerification?nationalCode=14152135235&birthDate=1193%2F10%2F03&fullName=test+test&firstName=test&lastName=test',
            json=_responses[VerificationAPIProviders.FINNOTECH.value],
            status=400,
        )
        for provider in [VerificationAPIProviders.JIBIT.value, VerificationAPIProviders.FINNOTECH.value]:
            Settings.set('verification_providers', provider)

            assert VerificationClient().check_user_identity(self.user) == {
                'apiresponse': _responses[provider],
                'confidence': 100,
                'err_code': 'InvalidNationalCode',
                'message': 'کد ملی کاربر اشتباه است',
                'result': False,
            }

    @patch('exchange.integrations.jibit.JibitVerificationClient.get_user_identity', side_effect=JibitAPIError())
    @patch(
        'exchange.integrations.finnotech.FinnotechVerificationClient.get_user_identity', side_effect=FinnotechAPIError()
    )
    def test_get_user_identity_all_providers_failed(self, *args) -> None:
        Settings.set(
            'verification_providers',
            f'{VerificationAPIProviders.JIBIT.value},{VerificationAPIProviders.FINNOTECH.value}',
        )
        with pytest.raises(VerificationAPIError) as ex:
            VerificationClient().check_user_identity(self.user)

        assert ex.match('All clients failed for the service UserIdentity')

    @patch('exchange.integrations.jibit.JibitVerificationClient.get_user_identity', side_effect=JibitAPIError())
    @patch(
        'exchange.integrations.finnotech.FinnotechVerificationClient.get_user_identity',
        MagicMock(
            return_value=IdentityVerificationClientResult(
                provider='finnotech',
                father_name_similarity=90,
                first_name_similarity=90,
                last_name_similarity=90,
                api_response={
                    'trackId': '57a52048-6cc9-4a71-b1a2-b21ad25650e8',
                    'result': {
                        'nationalCode': '2980987654',
                        'birthDate': '1363/06/31',
                        'firstName': 'محمد',
                        'firstNameSimilarity': 100,
                        'lastName': 'حسنی کبوترخانی',
                        'lastNameSimilarity': 100,
                        'fullName': 'محمد حسنی کبوترخانی',
                        'fullNameSimilarity': 100,
                        'deathStatus': 'زنده',
                    },
                    'status': 'DONE',
                },
            ),
        ),
    )
    def test_get_user_identity_first_providers_failed(self, *args) -> None:
        Settings.set(
            'verification_providers',
            f'{VerificationAPIProviders.JIBIT.value},{VerificationAPIProviders.FINNOTECH.value}',
        )
        retult = VerificationClient().check_user_identity(self.user)
        assert retult == {
            'apiresponse': {
                'trackId': '57a52048-6cc9-4a71-b1a2-b21ad25650e8',
                'result': {
                    'nationalCode': '2980987654',
                    'birthDate': '1363/06/31',
                    'firstName': 'محمد',
                    'firstNameSimilarity': 100,
                    'lastName': 'حسنی کبوترخانی',
                    'lastNameSimilarity': 100,
                    'fullName': 'محمد حسنی کبوترخانی',
                    'fullNameSimilarity': 100,
                    'deathStatus': 'زنده',
                },
                'status': 'DONE',
            },
            'confidence': 100,
            'err_code': '',
            'message': 'ok',
            'result': True,
        }
