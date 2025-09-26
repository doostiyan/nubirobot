from datetime import datetime, timezone

from django.core.cache import cache
from rest_framework.test import APITestCase

from exchange.accounts.models import BankAccount, User
from exchange.base.models import Settings
from exchange.features.models import QueueItem
from exchange.shetab.models import JibitAccount, JibitPaymentId, VandarAccount, VandarPaymentId
from tests.features.utils import BetaFeatureTestMixin


class DepositPaymentIdAPITest(BetaFeatureTestMixin, APITestCase):
    feature = 'vandar_deposit'

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user1 = User.objects.get(pk=202)
        self.request_feature(self.user, 'done')
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

        self.bank_account = BankAccount.objects.create(
            bank_id=999,
            user=self.user,
        )
        self.bank_account_2 = BankAccount.objects.create(
            bank_id=998,
            user=self.user,
        )
        self.bank_account_3 = BankAccount.objects.create(
            bank_id=997,
            user=self.user1,
        )
        self.vandar_account = VandarAccount.objects.create(uuid='35e431e0-210c-11ec-9200-79b42496d8e0', user=self.user)
        self.vandar_payment_id = VandarPaymentId.objects.create(
            bank_account=self.bank_account,
            vandar_account=self.vandar_account,
            payment_id='990008091172',
        )
        self.jibit_account = JibitAccount.objects.create(
            bank=JibitAccount.BANK_CHOICES.BKMTIR,
            iban='IR760120020000008992439951',
            account_number='8992439961',
            owner_name='ایوان رایان پیام',
            account_type=JibitAccount.ACCOUNT_TYPES.jibit,
        )
        self.nobitex_jibit_account = JibitAccount.objects.create(
            bank=JibitAccount.BANK_CHOICES.BKMTIR,
            iban='IR760120000000007565000016',
            account_number='7565000016',
            owner_name='راهکار فناوری نویان',
            account_type=JibitAccount.ACCOUNT_TYPES.nobitex_jibit,
        )
        self.jibit_payment_id = JibitPaymentId.objects.create(
            bank_account=self.bank_account,
            jibit_account=self.jibit_account,
            payment_id='990008091172',
        )
        self.nobitex_jibit_payment_id = JibitPaymentId.objects.create(
            bank_account=self.bank_account,
            jibit_account=self.nobitex_jibit_account,
            payment_id='990008091173',
        )
        self.jibit_payment_id_2 = JibitPaymentId.objects.create(
            bank_account=self.bank_account_2,
            jibit_account=self.jibit_account,
            payment_id='990008091174',
        )
        self.jibit_payment_id_3 = JibitPaymentId.objects.create(
            bank_account=self.bank_account_3,
            jibit_account=self.jibit_account,
            payment_id='990008091175',
        )

        self.deposit_payment_ids = sorted(
            [
                self.jibit_payment_id,
                self.vandar_payment_id,
                self.jibit_payment_id_2,
            ],
            key=lambda x: x.id,
        )

        self.nobitex_deposit_payment_ids = sorted(
            [
                self.nobitex_jibit_payment_id,
                self.jibit_payment_id,
                self.vandar_payment_id,
                self.jibit_payment_id_2,
            ],
            key=lambda x: x.id,
        )

        self.payments_except_bank_deleted = sorted(
            [
                self.nobitex_jibit_payment_id,
                self.vandar_payment_id,
                self.jibit_payment_id,
            ],
            key=lambda x: x.id,
        )

    def tearDown(self) -> None:
        cache.clear()
        return super().tearDown()

    def assert_successful(self, response, expected_response):
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert len(result['paymentIds']) == len(expected_response)
        for actual, expected in zip(sorted(result['paymentIds'], key=lambda x: x['id']), expected_response):
            assert actual['id'] == expected.id
            assert actual['accountId'] == expected.bank_account.id
            assert actual['bank'] == expected.bank_account.get_bank_id_display()
            assert actual['iban'] == expected.bank_account.shaba_number
            assert actual['destinationBank'] == expected.deposit_account.get_bank_display()
            assert actual['destinationIban'] == expected.deposit_account.iban
            assert actual['destinationOwnerName'] == expected.deposit_account.owner_name
            assert actual['destinationAccountNumber'] == expected.deposit_account.account_number
            assert actual['paymentId'] == expected.payment_id
            assert actual['type'] == expected.type

    def test_deposit_payments_list(self):
        # suppose feature flag "nobitex_jibit_ideposit" is not activated
        # so self.nobitex_jibit_payment_id dont list
        response = self.client.get('/users/payments/ids-list')
        self.assert_successful(response, self.deposit_payment_ids)

    def test_deposit_payments_list_with_different_types(self):
        # Here should see the self.nobitex_jibit_payment_id
        # but should not list the self.jibit_payment_id
        QueueItem.objects.create(
            user=self.user, feature=QueueItem.FEATURES.nobitex_jibit_ideposit, status=QueueItem.STATUS.done
        )
        response = self.client.get('/users/payments/ids-list')
        self.assert_successful(response, self.nobitex_deposit_payment_ids)

    def test_deposit_payments_list_nobitex_level1_new_joiner(self):
        self.user.user_type = User.USER_TYPE_LEVEL1
        self.user.date_joined = datetime(2025, 1, 5, tzinfo=timezone.utc)
        self.user.save()
        response = self.client.get('/users/payments/ids-list')
        self.assert_successful(response, self.nobitex_deposit_payment_ids)

    def test_deposit_payments_list_with_deleted_bank_account(self):
        # Here should not see the self.nobitex_jibit_payment_id cuz the bank id deleted
        QueueItem.objects.create(
            user=self.user, feature=QueueItem.FEATURES.nobitex_jibit_ideposit, status=QueueItem.STATUS.done
        )
        self.bank_account_2.is_deleted = True
        self.bank_account_2.save()

        response = self.client.get('/users/payments/ids-list')
        self.assert_successful(response, self.payments_except_bank_deleted)

    def test_user_payments_ids_list_fail_jibit_disabled(self):

        Settings.set('jibit_id_deposit_feature_status', 'disabled')
        response = self.client.get('/users/payments/ids-list').json()
        assert len(response['paymentIds']) == 1
        assert response['paymentIds'] == [
            {
                'accountId': self.vandar_payment_id.bank_account.id,
                'bank': 'وندار',
                'destinationAccountNumber': '0203443585001',
                'destinationBank': 'آینده',
                'destinationIban': 'IR260620000000203443585001',
                'destinationOwnerName': 'تجارت الکترونیک ارسباران',
                'iban': '',
                'id': self.vandar_payment_id.id,
                'paymentId': '990008091172',
                'type': 'vandar',
            },
        ]
