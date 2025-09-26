import random

from django.core.cache import cache
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from exchange.accounts.models import BankAccount, User
from exchange.base.models import Settings
from exchange.corporate_banking.models import CoBankAccount
from exchange.corporate_banking.models.constants import ACCOUNT_TP, COBANK_PROVIDER, NOBITEX_BANK_CHOICES
from exchange.features.models import QueueItem


class GetDepositInfoTestCase(APITestCase):
    url = '/cobank/deposit-info'

    def setUp(self):
        cache.clear()

        self.user = User.objects.create_user(username=f'jane_doe_{random.randint(1, 100000)}')
        QueueItem.objects.create(user=self.user, feature=QueueItem.FEATURES.cobank, status=QueueItem.STATUS.done)

        self.bank_account1 = CoBankAccount.objects.create(
            provider_bank_id=11,
            bank=NOBITEX_BANK_CHOICES.saman,
            iban='IR999999999999999999999991',
            account_number='000111222',
            account_owner='راهکار فناوری نویان',
            is_active=True,
            account_tp=ACCOUNT_TP.operational,
            is_deleted=False,
        )
        self.bank_account2 = CoBankAccount.objects.create(
            provider_bank_id=15,
            bank=NOBITEX_BANK_CHOICES.melli,
            iban='IR999999999999999999999992',
            account_number='111222333',
            account_owner='راهکار فناوری نویان ۲',
            is_active=True,
            account_tp=ACCOUNT_TP.operational,
            is_deleted=False,
        )
        self.bank_account3 = CoBankAccount.objects.create(
            provider_bank_id=3,
            bank=NOBITEX_BANK_CHOICES.melli,
            iban='IR999999999999999999999992',
            account_number='111222333',             # Same bank accounts (bank_account2 and 3) appear only once in API
            account_owner='راهکار فناوری نویان ۲',
            provider=COBANK_PROVIDER.jibit,
            is_active=True,
            account_tp=ACCOUNT_TP.operational,
            is_deleted=False,
        )
        self.bank_account4 = CoBankAccount.objects.create(
            provider_bank_id=111,
            bank=NOBITEX_BANK_CHOICES.saman,
            iban='IR999999999999999999999993',
            account_number='222333444',
            account_owner='راهکار فناوری نویان',
            is_active=False,                    # Should not be visible in API because admin has deactivated it
            account_tp=ACCOUNT_TP.operational,
            is_deleted=False,
        )
        self.bank_account5 = CoBankAccount.objects.create(
            provider_bank_id=1,
            bank=NOBITEX_BANK_CHOICES.saman,
            iban='IR999999999999999999999994',
            account_number='333444555',
            account_owner='راهکار فناوری نویان',
            is_active=True,
            provider_is_active=False,           # Should not be visible in API because provider has deactivated it
            account_tp=ACCOUNT_TP.operational,
            is_deleted=False,
        )
        self.bank_account6 = CoBankAccount.objects.create(
            provider_bank_id=80,
            bank=NOBITEX_BANK_CHOICES.saman,
            iban='IR999999999999999999999995',
            account_number='444555666',
            account_owner='راهکار فناوری نویان',
            is_active=True,
            provider_is_active=True,
            account_tp=ACCOUNT_TP.operational,
            is_deleted=True,                    # Should not be visible in API because it's soft-deleted
        )
        self.bank_account7 = CoBankAccount.objects.create(
            provider_bank_id=810,
            bank=NOBITEX_BANK_CHOICES.saman,
            iban='IR999999999999999999999996',
            account_number='555666777',
            account_owner='راهکار فناوری نویان',
            is_active=True,
            provider_is_active=True,
            account_tp=ACCOUNT_TP.storage,      # Should not be visible in API because it's not depositable
            is_deleted=False,
        )

    def test_get_deposit_infos_without_any_user_accounts(self):
        """
        Should only get bank_account1 and bank_account2, and all user info should be None because user has no accounts
        """
        self._set_user_token(self.user)
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        json_response = response.json()
        assert len(json_response) == 3
        assert json_response == [
            {
                'bank': 'بلو',
                'bankAccountNumber': 'IR999999999999999999999991',
                'bankOwner': 'راهکار فناوری نویان',
                'userBankAccounts': [],
            },
            {
                'bank': 'سامان',
                'bankAccountNumber': '000111222',
                'bankOwner': 'راهکار فناوری نویان',
                'userBankAccounts': [],
            },
            {
                'bank': 'ملی',
                'bankAccountNumber': '111222333',
                'bankOwner': 'راهکار فناوری نویان ۲',
                'userBankAccounts': [],
            },
        ]

    def test_get_deposit_infos_with_user_accounts(self):
        """
        For each of our cobank accounts we need to show if user has accounts in that bank or not
        so we list all the user's account corresponding to a bank type in the list of our cobank accounts
        """
        for account_number in ['1234', '0', '']:
            self._create_user_bank_account(account_number, self.user)

        self._set_user_token(self.user)
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        json_response = response.json()
        assert len(json_response) == 3
        assert json_response == [
            {
                'bank': 'بلو',
                'bankAccountNumber': 'IR999999999999999999999991',
                'bankOwner': 'راهکار فناوری نویان',
                'userBankAccounts': [],
            },
            {
                'bank': 'سامان',
                'bankAccountNumber': '000111222',
                'bankOwner': 'راهکار فناوری نویان',
                'userBankAccounts': [
                    {'accountNumber': '1234', 'iban': 'IR230560084077703567647001'},
                    {'accountNumber': None, 'iban': 'IR230560084077703567647001'},
                    {'accountNumber': None, 'iban': 'IR230560084077703567647001'},
                ],
            },
            {
                'bank': 'ملی',
                'bankAccountNumber': '111222333',
                'bankOwner': 'راهکار فناوری نویان ۲',
                'userBankAccounts': [],
            },
        ]

    def test_get_deposit_infos_with_uncorfirmed_user_accounts(self):
        self._create_user_bank_account('1234', self.user, confirmed=False)
        self._create_user_bank_account('1234', self.user, is_deleted=True)

        self._set_user_token(self.user)
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        json_response = response.json()
        assert len(json_response) == 3
        assert json_response == [
            {
                'bank': 'بلو',
                'bankAccountNumber': 'IR999999999999999999999991',
                'bankOwner': 'راهکار فناوری نویان',
                'userBankAccounts': [],
            },
            {
                'bank': 'سامان',
                'bankAccountNumber': '000111222',
                'bankOwner': 'راهکار فناوری نویان',
                'userBankAccounts': [],
            },
            {
                'bank': 'ملی',
                'bankAccountNumber': '111222333',
                'bankOwner': 'راهکار فناوری نویان ۲',
                'userBankAccounts': [],
            },
        ]

    def test_get_deposit_info_without_cobank_accounts(self):
        CoBankAccount.objects.all().delete()
        self._set_user_token(self.user)
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        json_response = response.json()
        assert json_response == []

    def test_get_deposit_info_without_feature_flag(self):
        """
        Test that user cannot call the API without cobank feature flag
        """
        self._set_user_token(self.user)
        QueueItem.objects.filter(user=self.user).delete()
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'status': 'failed',
            'code': 'FeatureUnavailable',
            'message': 'CorporateBanking feature is not available for your user',
        }

    def test_get_deposit_info_without_feature_flag_but_check_flag_is_disabled(self):
        self._set_user_token(self.user)
        QueueItem.objects.filter(user=self.user).delete()
        Settings.set('cobank_check_feature_flag', 'no')
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        json_response = response.json()
        assert len(json_response) == 3
        assert json_response == [
            {
                'bank': 'بلو',
                'bankAccountNumber': 'IR999999999999999999999991',
                'bankOwner': 'راهکار فناوری نویان',
                'userBankAccounts': [],
            },
            {
                'bank': 'سامان',
                'bankAccountNumber': '000111222',
                'bankOwner': 'راهکار فناوری نویان',
                'userBankAccounts': [],
            },
            {
                'bank': 'ملی',
                'bankAccountNumber': '111222333',
                'bankOwner': 'راهکار فناوری نویان ۲',
                'userBankAccounts': [],
            },
        ]

    def test_get_deposit_info_with_another_user_bank_accounts(self):
        another_user = User.objects.create_user(username=f'john_doe_{random.randint(1, 100000)}')
        self._create_user_bank_account('1234', another_user, confirmed=False)
        self._create_user_bank_account('1234', another_user, st=BankAccount.STATUS.rejected)
        self._create_user_bank_account('1234', another_user, is_deleted=True)

        self._set_user_token(self.user)
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        json_response = response.json()
        assert len(json_response) == 3
        assert json_response == [
            {
                'bank': 'بلو',
                'bankAccountNumber': 'IR999999999999999999999991',
                'bankOwner': 'راهکار فناوری نویان',
                'userBankAccounts': [],
            },
            {
                'bank': 'سامان',
                'bankAccountNumber': '000111222',
                'bankOwner': 'راهکار فناوری نویان',
                'userBankAccounts': [],
            },
            {
                'bank': 'ملی',
                'bankAccountNumber': '111222333',
                'bankOwner': 'راهکار فناوری نویان ۲',
                'userBankAccounts': [],
            },
        ]

    def test_get_deposit_infos_saman_deleted(self):
        """
        Verifies that if Saman is deleted, Saman account and Blu shaba
        are excluded from the response.
        """
        self._set_user_token(self.user)
        self.bank_account1.delete()
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        json_response = response.json()
        assert json_response == [
            {
                'bank': 'ملی',
                'bankAccountNumber': '111222333',
                'bankOwner': 'راهکار فناوری نویان ۲',
                'userBankAccounts': [],
            },
        ]

    def test_get_deposit_info_without_authentication_token(self):
        """
        Test that user cannot call the API without auth token
        """
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {'detail': 'اطلاعات برای اعتبارسنجی ارسال نشده است.'}

    def test_get_deposit_info_with_incorrect_authentication_token(self):
        """
        Test that user cannot call the API with a wrong auth token
        """
        self.client.credentials(HTTP_AUTHORIZATION=f'wrong token')
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {'detail': 'اطلاعات برای اعتبارسنجی ارسال نشده است.'}

    def _set_user_token(self, user: User):
        if not hasattr(user, 'auth_token'):
            token = Token.objects.create(key=f'{user.username}Token', user=user)
            user.auth_token = token
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {user.auth_token.key}')

    def _create_user_bank_account(
        self,
        account_number: str,
        user: User,
        confirmed: bool = True,
        st: int = BankAccount.STATUS.confirmed,
        is_deleted: bool = False,
        bank_id: int = BankAccount.BANK_ID.saderat,
        shaba_number: str = 'IR230560084077703567647001',
    ):
        BankAccount.objects.create(
            user=user,
            account_number=account_number,
            shaba_number=shaba_number,  # bank_id = shaba_number[4:7]
            owner_name='صغری خانم',
            bank_name='سامثینگ',
            confirmed=confirmed,
            status=st,
            is_deleted=is_deleted,
            bank_id=bank_id,
        )
