import json
from typing import Any, Optional
from unittest.mock import patch

import responses
from django.core.cache import cache
from django.http import HttpResponse
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.custom_signals import BANK_ITEM_REJECTED
from exchange.accounts.models import BankAccount, BankCard, Notification, User
from exchange.accounts.tasks import task_convert_card_number_to_iban
from exchange.base.models import Settings
from exchange.integrations.verification import VerificationAPIProviders
from tests.base.utils import mock_on_commit


class TestCardBank(APITestCase):
    @classmethod
    def setUpTestData(cls):
        Settings.set('verification_providers', VerificationAPIProviders.FINNOTECH.value)
        cls.user = User.objects.get(pk=201)
        cls.user.national_code = '0010010010'
        cls.user.mobile = '09100100100'
        cls.user.email = 'test@test.com'
        cls.user.national_serial_number = 'sd5sad4656d'
        cls.user.first_name = 'علی'
        cls.user.last_name = 'آقایی'
        cls.user.save()
        cls.vp = cls.user.get_verification_profile()
        cls.vp.identity_confirmed = True
        cls.vp.save()

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        Settings.set('verification_providers', VerificationAPIProviders.FINNOTECH.value)
        Settings.set('finnotech_verification_api_token', 'XXX')

    def _post_request(self, data: dict) -> HttpResponse:
        return self.client.post('/users/cards-add', data)

    def _check_api_response_in_bank_account_record(self, verification: bool, description: Optional[str] = None):
        bank_account = BankAccount.objects.last()
        api_verification = json.loads(bank_account.api_verification)
        assert api_verification['verification'] == verification
        if description:
            assert api_verification['result']['depositDescription'] == description

    def _check_response(
        self,
        response: HttpResponse,
        status_code: int,
        status_data: Optional[str] = None,
        code: Optional[str] = None,
        message: Optional[str] = None,
    ) -> Any:
        assert response.status_code == status_code
        data = response.json()
        if status_data:
            assert data['status'] == status_data
        if code:
            assert data['code'] == code
        if message:
            assert data['message'] == message
        return data

    def _check_bank_card(self, bank_card: BankCard, bank_account: BankAccount = None, number_of_bank_account: int = 0):
        card = BankCard.objects.last()
        assert card.card_number == bank_card.card_number
        assert card.user == bank_card.user
        assert card.confirmed == bank_card.confirmed

        iban = BankAccount.objects.last()
        if bank_account:
            assert iban.account_number == bank_account.account_number
            assert iban.bank_id == bank_account.bank_id
            assert iban.user == bank_account.user
            assert iban.confirmed == bank_account.confirmed
            assert iban.is_from_bank_card
        elif number_of_bank_account == 0:
            assert iban is None
        else:
            assert BankAccount.objects.count() == number_of_bank_account

    def _check_notifs(self, first_notif_count, diff, in_notifs, not_in_notifs):
        assert Notification.objects.filter(user=self.user).count() - first_notif_count == diff
        merged_notifs = '\n'.join(
            Notification.objects.filter(user=self.user).order_by('-id')[:diff].values_list('message', flat=True),
        )
        for msg in in_notifs:
            assert msg in merged_notifs
        for msg in not_in_notifs:
            assert msg not in merged_notifs

    def test_with_wrong_number(self):
        response = self._post_request({'number': '60377015225129421'})
        self._check_response(
            response=response,
            status_code=status.HTTP_200_OK,
            status_data='failed',
            code='ValidationError',
            message='Validation Failed',
        )

    @responses.activate
    @override_settings(IS_PROD=True)
    def test_correct(self):
        card_number = '6037991522518822'
        cache.set('user_{}_bank_info'.format(self.user.pk), {'cards': ['badData']}, 3600)
        with self.captureOnCommitCallbacks(execute=True) as callbacks:

            responses.get(
                url=f'https://apibeta.finnotech.ir/mpg/v2/clients/nobitex/cards/{card_number}?sandbox=true',
                json={
                    'result': {
                        'destCard': 'xxxx-xxxx-xxxx-3899',
                        'name': 'علی آقایی',
                        'result': '0',
                        'description': 'موفق',
                        'doTime': '1396/06/15 12:32:04',
                        'bankName': 'بانک تجارت',
                    },
                    'status': 'DONE',
                    'trackId': 'get-cardInfo-0232',
                },
                status=200,
            )
            response = self._post_request({'number': card_number})
        self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_bank_card(BankCard(user=self.user, card_number=card_number, confirmed=True))
        assert cache.has_key('user_{}_bank_info'.format(self.user.pk))
        assert cache.get('user_{}_bank_info'.format(self.user.pk)) is None

    @responses.activate
    @override_settings(IS_PROD=True)
    @patch.object(task_convert_card_number_to_iban, 'delay', task_convert_card_number_to_iban)
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_with_iban_request(self, _):
        card_number = '6037991522518822'
        shaba_number = 'IR910800005000115426432001'
        account_number = '1064234991'

        responses.get(
            url=f'https://apibeta.finnotech.ir/mpg/v2/clients/nobitex/cards/{card_number}?sandbox=true',
            json={
                'result': {
                    'destCard': 'xxxx-xxxx-xxxx-3899',
                    'name': 'علی آقایی',
                    'result': '0',
                    'description': 'موفق',
                    'doTime': '1396/06/15 12:32:04',
                    'bankName': 'بانک تجارت',
                },
                'status': 'DONE',
                'trackId': 'get-cardInfo-0232',
            },
            status=200,
        )
        responses.get(
            url=f'https://apibeta.finnotech.ir/facility/v2/clients/nobitex/cardToIban?version=2&card={card_number}',
            json={
                'trackId': 'cardToIban-029',
                'result': {
                    'IBAN': 'IR910800005000115426432001',
                    'bankName': 'بانک تجارت',
                    'deposit': '1064234991',
                    'card': '6037991522518822',
                    'depositStatus': '02',
                    'depositOwners': 'علی آقایی / فعال',
                },
                'status': 'DONE',
            },
            status=200,
        )

        first_notif_count = Notification.objects.filter(user=self.user).count()
        response = self._post_request({'number': card_number})
        self._check_notifs(
            first_notif_count,
            2,
            ['شماره شبای مربوط به کارت 6037991522518822 با موفقیت', 'شماره کارت 6037991522518822 با موفقیت'],
            [],
        )
        self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_bank_card(
            BankCard(user=self.user, card_number=card_number, confirmed=True),
            BankAccount(
                user=self.user,
                shaba_number=shaba_number,
                account_number=account_number,
                confirmed=True,
                bank_id=80,
            ),
        )
        self._check_api_response_in_bank_account_record(verification=True, description='حساب فعال است')

    @responses.activate
    @override_settings(IS_PROD=True)
    @patch.object(task_convert_card_number_to_iban, 'delay', task_convert_card_number_to_iban)
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_with_iban_request_different_deposit_owners(self, _):
        card_number = '6037991522518822'
        shaba_number = 'IR910800005000115426432001'
        account_number = '1064234991'

        responses.get(
            url=f'https://apibeta.finnotech.ir/mpg/v2/clients/nobitex/cards/{card_number}?sandbox=true',
            json={
                'result': {
                    'destCard': 'xxxx-xxxx-xxxx-3899',
                    'name': 'علی آقایی',
                    'result': '0',
                    'description': 'موفق',
                    'doTime': '1396/06/15 12:32:04',
                    'bankName': 'بانک تجارت',
                },
                'status': 'DONE',
                'trackId': 'get-cardInfo-0232',
            },
            status=200,
        )
        responses.get(
            url=f'https://apibeta.finnotech.ir/facility/v2/clients/nobitex/cardToIban?version=2&card={card_number}',
            json={
                'trackId': 'cardToIban-029',
                'result': {
                    'IBAN': 'IR910800005000115426432001',
                    'bankName': 'بانک تجارت',
                    'deposit': '1064234991',
                    'card': '6037991522518822',
                    'depositStatus': '02',
                    'depositOwners': 'علی آقایی',
                },
                'status': 'DONE',
            },
            status=200,
        )

        first_notif_count = Notification.objects.filter(user=self.user).count()
        response = self._post_request({'number': card_number})
        self._check_notifs(
            first_notif_count,
            2,
            ['شماره شبای مربوط به کارت 6037991522518822 با موفقیت', 'شماره کارت 6037991522518822 با موفقیت'],
            [],
        )
        self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_bank_card(
            BankCard(user=self.user, card_number=card_number, confirmed=True),
            BankAccount(
                user=self.user,
                shaba_number=shaba_number,
                account_number=account_number,
                confirmed=True,
                bank_id=80,
            ),
        )

    @responses.activate
    @override_settings(IS_PROD=True)
    @patch.object(task_convert_card_number_to_iban, 'delay', task_convert_card_number_to_iban)
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_with_inactive_bank_account_iban_request(self, _):
        card_number = '6037991522518822'

        responses.get(
            url=f'https://apibeta.finnotech.ir/mpg/v2/clients/nobitex/cards/{card_number}?sandbox=true',
            json={
                'result': {
                    'destCard': 'xxxx-xxxx-xxxx-3899',
                    'name': 'علی آقایی',
                    'result': '0',
                    'description': 'موفق',
                    'doTime': '1396/06/15 12:32:04',
                    'bankName': 'بانک تجارت',
                },
                'status': 'DONE',
                'trackId': 'get-cardInfo-0232',
            },
            status=200,
        )

        responses.get(
            url=f'https://apibeta.finnotech.ir/facility/v2/clients/nobitex/cardToIban?version=2&card={card_number}',
            json={
                'responseCode': 'FN-FYJT-40000140354',
                'trackId': '2649a11a-6abc-4741-8016-91ca204f16f9',
                'status': 'FAILED',
                'error': {
                    'code': r'VALIDATION\_ERROR',
                    'message': 'کارت غیرفعال است',
                },
            },
            status=200,
        )

        first_notif_count = Notification.objects.filter(user=self.user).count()
        response = self._post_request({'number': card_number})
        self._check_notifs(
            first_notif_count,
            2,
            [
                'شماره شبای مربوط به کارت 6037991522518822 رد',
                'کارت غیرفعال است',
                'شماره کارت 6037991522518822 با موفقیت',
            ],
            ['شماره شبای مربوط به کارت 6037991522518822 با موفقیت'],
        )
        self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_bank_card(BankCard(user=self.user, card_number=card_number, confirmed=True))

    @responses.activate
    @override_settings(IS_PROD=True)
    @patch.object(task_convert_card_number_to_iban, 'delay', task_convert_card_number_to_iban)
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_with_wrong_name_iban_request(self, _):
        card_number = '6037991522518822'
        shaba_number = 'IR910800005000115426432001'
        account_number = '1064234991'

        responses.get(
            url=f'https://apibeta.finnotech.ir/mpg/v2/clients/nobitex/cards/{card_number}?sandbox=true',
            json={
                'result': {
                    'destCard': 'xxxx-xxxx-xxxx-3899',
                    'name': 'علی آقایی',
                    'result': '0',
                    'description': 'موفق',
                    'doTime': '1396/06/15 12:32:04',
                    'bankName': 'بانک تجارت',
                },
                'status': 'DONE',
                'trackId': 'get-cardInfo-0232',
            },
            status=200,
        )

        responses.get(
            url=f'https://apibeta.finnotech.ir/facility/v2/clients/nobitex/cardToIban?version=2&card={card_number}',
            json={
                'trackId': 'cardToIban-029',
                'result': {
                    'IBAN': shaba_number,
                    'bankName': 'بانک تجارت',
                    'deposit': account_number,
                    'card': '6037991522518822',
                    'depositStatus': '02',
                    'depositOwners': 'علیییی آقایی',
                },
                'status': 'DONE',
            },
            status=200,
        )

        first_notif_count = Notification.objects.filter(user=self.user).count()
        response = self._post_request({'number': card_number})
        self._check_notifs(
            first_notif_count,
            2,
            [
                'شماره شبای مربوط به کارت 6037991522518822 رد',
                'نام کاربر با صاحب حساب مطابقت ندارد.',
                'شماره کارت 6037991522518822 با موفقیت',
            ],
            ['شماره شبای مربوط به کارت 6037991522518822 با موفقیت'],
        )
        self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_bank_card(
            BankCard(user=self.user, card_number=card_number, confirmed=True),
            BankAccount(
                user=self.user,
                shaba_number=shaba_number,
                account_number=account_number,
                confirmed=False,
                bank_id=80,
            ),
            1,
        )
        self._check_api_response_in_bank_account_record(verification=False)

    @responses.activate
    @override_settings(IS_PROD=True)
    @patch.object(task_convert_card_number_to_iban, 'delay', task_convert_card_number_to_iban)
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_check_duplicate_iban(self, _):
        card_number = '6037991522518822'
        shaba_number = 'IR910800005000115426432001'
        account_number = '1064234991'
        BankAccount.objects.create(
            user=self.user,
            shaba_number=shaba_number,
            account_number=account_number,
            confirmed=True,
            bank_id=80,
        )

        responses.get(
            url=f'https://apibeta.finnotech.ir/mpg/v2/clients/nobitex/cards/{card_number}?sandbox=true',
            json={
                'result': {
                    'destCard': 'xxxx-xxxx-xxxx-3899',
                    'name': 'علی آقایی',
                    'result': '0',
                    'description': 'موفق',
                    'doTime': '1396/06/15 12:32:04',
                    'bankName': 'بانک تجارت',
                },
                'status': 'DONE',
                'trackId': 'get-cardInfo-0232',
            },
            status=200,
        )

        responses.get(
            url=f'https://apibeta.finnotech.ir/facility/v2/clients/nobitex/cardToIban?version=2&card={card_number}',
            json={
                'trackId': 'cardToIban-029',
                'result': {
                    'IBAN': shaba_number,
                    'bankName': 'بانک تجارت',
                    'deposit': account_number,
                    'card': card_number,
                    'depositStatus': '02',
                    'depositOwners': 'علی آقایی',
                },
                'status': 'DONE',
            },
            status=200,
        )

        first_notif_count = Notification.objects.filter(user=self.user).count()
        response = self._post_request({'number': card_number})
        self._check_notifs(
            first_notif_count,
            1,
            ['شماره کارت 6037991522518822 با موفقیت'],
            ['شماره شبای مربوط به کارت 6037991522518822 با موفقیت'],
        )
        self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_bank_card(
            BankCard(user=self.user, card_number=card_number, confirmed=True),
            number_of_bank_account=1,
        )


class TestUserAccountsDeleteBug(APITestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user.national_code = '0010010010'
        self.user.mobile = '09100100100'
        self.user.email = 'test@test.com'
        self.user.national_serial_number = 'sd5sad4656d'
        self.user.first_name = 'علی'
        self.user.last_name = 'آقایی'
        self.user.save()
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        Settings.set('finnotech_verification_api_token', 'XXX')
        shaba_number = 'IR910800005000115426432001'
        account_number = '1064234991'
        self.bank_account = BankAccount.objects.create(
            user=self.user,
            shaba_number=shaba_number,
            account_number=account_number,
            confirmed=True,
            bank_id=80,
        )

    @patch.object(BANK_ITEM_REJECTED, 'send')
    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    def test_delete_account(self, _, patch_event):
        BankAccount.objects.filter(id=self.bank_account.id).update(is_from_bank_card=True)
        self.client.post('/users/accounts-delete', {'id': self.bank_account.id})
        self.bank_account.refresh_from_db()
        assert self.bank_account.is_deleted
        assert patch_event.call_count == 0
