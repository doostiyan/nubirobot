import random

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.models import Settings
from exchange.corporate_banking.models import CoBankAccount, CoBankCard
from exchange.corporate_banking.models.constants import ACCOUNT_TP, NOBITEX_BANK_CHOICES
from exchange.features.models import QueueItem


class GetDepositInfoTestCase(APITestCase):
    def setUp(self):
        self.url = '/cobank/card-deposit-info'

        self.user = User.objects.create_user(username=f'jane_doe_{random.randint(1, 100000)}')
        QueueItem.objects.create(user=self.user, feature=QueueItem.FEATURES.cobank_cards, status=QueueItem.STATUS.done)

    def test_get_card_deposit_infos_without_any_cards(self):
        """
        Should return empty array
        """
        self._set_user_token(self.user)
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_get_card_deposit_infos_with_cards(self):
        self._create_mock_cards()

        self._set_user_token(self.user)
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        json_response = response.json()
        assert len(json_response) == 2
        assert json_response == [
            {
                'bank': 'سامان',
                'bankCardNumber': '1234123412341200',
                'bankOwner': 'اسم کارت 0',
            },
            {
                'bank': 'ملی',
                'bankCardNumber': '1234123412341210',
                'bankOwner': 'اسم کارت 0',
            },
        ]

    def test_multiple_cards_for_one_account(self):
        multiple_cards_account = CoBankAccount.objects.create(
            provider_bank_id='11',
            bank=NOBITEX_BANK_CHOICES.saman,
            iban='IR999999999999999999999991',
            account_number='000111222',
            account_owner='راهکار فناوری نویان',
            is_active=True,
            account_tp=ACCOUNT_TP.operational,
            is_deleted=False,
        )
        signle_card_account = CoBankAccount.objects.create(
            provider_bank_id='12',
            bank=NOBITEX_BANK_CHOICES.melli,
            iban='IR999999999999999999999992',
            account_number='000111222',
            account_owner='راهکار فناوری نویان ۲',
            is_active=True,
            account_tp=ACCOUNT_TP.operational,
            is_deleted=False,
        )
        no_cards_account = CoBankAccount.objects.create(
            provider_bank_id='13',
            bank=NOBITEX_BANK_CHOICES.mellat,
            iban='IR999999999999999999999993',
            account_number='000111222',
            account_owner='راهکار فناوری نویان ۳',
            is_active=True,
            account_tp=ACCOUNT_TP.operational,
            is_deleted=False,
        )
        for idx in range(2):
            CoBankCard.objects.create(
                bank_account=multiple_cards_account,
                card_number=f'123412341234120{idx}',
                provider_card_id=f'1230{idx}',
                provider_is_active=True,
                name='اسم کارت ' + str(idx),
                is_active=True,
                is_deleted=False,
            )

        # Use bulk_create to bypass the overridden save() method so we can test an active card with an empty name
        CoBankCard.objects.bulk_create(
            [
                CoBankCard(
                    bank_account=signle_card_account,
                    card_number='1234123412341202',
                    provider_card_id='12302',
                    provider_is_active=True,
                    name='',
                    is_active=True,
                    is_deleted=False,
                )
            ]
        )

        self._set_user_token(self.user)
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        json_response = response.json()
        assert len(json_response) == 3
        assert json_response == [
            {
                'bank': 'سامان',
                'bankCardNumber': '1234123412341200',
                'bankOwner': 'اسم کارت 0',
            },
            {
                'bank': 'سامان',
                'bankCardNumber': '1234123412341201',
                'bankOwner': 'اسم کارت 1',
            },
            {
                'bank': 'ملی',
                'bankCardNumber': '1234123412341202',
                'bankOwner': 'راهکار فناوری نویان ۲',
            },
        ]

    def test_get_card_deposit_info_without_feature_flag(self):
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
            'message': 'CobankCards feature is not available for your user',
        }

    def test_get_card_deposit_info_without_feature_flag_but_check_flag_is_disabled(self):
        self._create_mock_cards()

        self._set_user_token(self.user)
        QueueItem.objects.filter(user=self.user).delete()
        Settings.set('cobank_card_check_feature_flag', 'no')
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        json_response = response.json()
        assert json_response == [
            {
                'bank': 'سامان',
                'bankCardNumber': '1234123412341200',
                'bankOwner': 'اسم کارت 0',
            },
            {
                'bank': 'ملی',
                'bankCardNumber': '1234123412341210',
                'bankOwner': 'اسم کارت 0',
            },
        ]

    def test_get_card_deposit_info_without_authentication_token(self):
        """
        Test that user cannot call the API without auth token
        """
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {'detail': 'اطلاعات برای اعتبارسنجی ارسال نشده است.'}

    def test_get_card_deposit_info_with_incorrect_authentication_token(self):
        """
        Test that user cannot call the API with a wrong auth token
        """
        self.client.credentials(HTTP_AUTHORIZATION='wrong token')
        response = self.client.get(self.url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json() == {'detail': 'اطلاعات برای اعتبارسنجی ارسال نشده است.'}

    def _set_user_token(self, user: User):
        if not hasattr(user, 'auth_token'):
            token = Token.objects.create(key=f'{user.username}Token', user=user)
            user.auth_token = token
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {user.auth_token.key}')

    def _create_mock_cards(self):
        # There are 6 bank accounts, only the first two are completely active and operational
        bank_accounts = [
            CoBankAccount.objects.create(
                provider_bank_id='11',
                bank=NOBITEX_BANK_CHOICES.saman,
                iban='IR999999999999999999999991',
                account_number='000111222',
                account_owner='راهکار فناوری نویان',
                is_active=True,
                account_tp=ACCOUNT_TP.operational,
                is_deleted=False,
            ),
            CoBankAccount.objects.create(
                provider_bank_id='15',
                bank=NOBITEX_BANK_CHOICES.melli,
                iban='IR999999999999999999999992',
                account_number='111222333',
                account_owner='راهکار فناوری نویان ۲',
                is_active=True,
                account_tp=ACCOUNT_TP.operational,
                is_deleted=False,
            ),
            CoBankAccount.objects.create(
                provider_bank_id='111',
                bank=NOBITEX_BANK_CHOICES.saman,
                iban='IR999999999999999999999993',
                account_number='222333444',
                account_owner='راهکار فناوری نویان',
                is_active=False,  # Deactivated by Admin
                account_tp=ACCOUNT_TP.operational,
                is_deleted=False,
            ),
            CoBankAccount.objects.create(
                provider_bank_id='1',
                bank=NOBITEX_BANK_CHOICES.saman,
                iban='IR999999999999999999999994',
                account_number='333444555',
                account_owner='راهکار فناوری نویان',
                is_active=True,
                provider_is_active=False,  # Deactivated by provider
                account_tp=ACCOUNT_TP.operational,
                is_deleted=False,
            ),
            CoBankAccount.objects.create(
                provider_bank_id='80',
                bank=NOBITEX_BANK_CHOICES.saman,
                iban='IR999999999999999999999995',
                account_number='444555666',
                account_owner='راهکار فناوری نویان',
                is_active=True,
                provider_is_active=True,
                account_tp=ACCOUNT_TP.operational,
                is_deleted=True,  # Deleted Account
            ),
            CoBankAccount.objects.create(
                provider_bank_id='810',
                bank=NOBITEX_BANK_CHOICES.saman,
                iban='IR999999999999999999999996',
                account_number='555666777',
                account_owner='راهکار فناوری نویان',
                is_active=True,
                provider_is_active=True,
                account_tp=ACCOUNT_TP.storage,  # non-operational account: doesn't accept deposits
                is_deleted=False,
            ),
        ]

        # For each bank account there are 4 different cards, only the first one is fully active
        # i.e. only card numbers ending in 0 for account_idx 0 and 1 are active cards
        bank_cards = []
        for account_idx, bank_account in enumerate(bank_accounts):
            bank_cards.extend(
                [
                    CoBankCard.objects.create(
                        bank_account=bank_account,
                        card_number=f'12341234123412{account_idx}{idx}',
                        provider_card_id=f'123{account_idx}{idx}',
                        provider_is_active=idx < 3,
                        name='اسم کارت ' + str(idx),
                        is_active=idx < 2,
                        is_deleted=idx >= 1,
                    )
                    for idx in range(4)
                ],
            )
