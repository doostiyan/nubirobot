from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import responses
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from exchange.accounts.models import BankAccount, Tag, User, UserTag
from exchange.base.models import Settings
from exchange.features.models import QueueItem
from exchange.shetab.handlers import JibitPip
from exchange.shetab.models import JibitAccount, JibitPaymentId


class PaymentTests(APITestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.iban = f'IR{"1" * 24}'
        self.url = '/users/payments/create-id'
        self.api_url = f'{JibitPip.base_address}paymentIds'
        self.user.user_type = User.USER_TYPES.verified
        self.user.save()

    def tearDown(self) -> None:
        cache.clear()
        return super().tearDown()

    def create_bank_account(self):
        return BankAccount.objects.create(
            user=self.user,
            account_number='78' * 6,
            shaba_number=self.iban,
            owner_name=self.user.get_full_name(),
            bank_name=BankAccount.BANK_ID[10],
            bank_id=10,
            confirmed=True,
            status=BankAccount.STATUS.confirmed,
        )

    def test_user_payments_ids_create_fail_eligibility(self):
        QueueItem.objects.create(
            user=self.user,
            feature=QueueItem.FEATURES.jibit_pip,
            status=QueueItem.STATUS.failed,
        )
        response = self.client.post(path=self.url, data={'iban': self.iban}).json()
        assert response == {
            'status': 'failed',
            'code': 'UserLevelRestriction',
            'message': 'UserLevelRestriction',
        }

    def test_user_payments_ids_create_fail_eligibility_with_no_queue_item_before(self):
        tag, _ = Tag.objects.get_or_create(name='استعلام')
        self.user.tags.add(tag)

        response = self.client.post(path=self.url, data={'iban': self.iban}).json()
        assert response == {
            'status': 'failed',
            'code': 'UserLevelRestriction',
            'message': 'UserLevelRestriction',
        }

    def test_user_payments_ids_create_fail_invalid_iban(self):
        iban = self.iban[2:]
        response = self.client.post(path=self.url, data={'iban': iban}).json()
        assert response == {
            'status': 'failed',
            'code': 'InvalidIBAN',
            'message': f'Invalid IBAN: "{iban}"',
        }

    def test_user_payments_ids_create_fail_unknown_bank(self):
        response = self.client.post(path=self.url, data={'iban': self.iban}).json()
        assert response == {
            'status': 'failed',
            'code': 'UnknownIBAN',
            'message': 'Unknown IBAN',
        }

    def test_user_payments_ids_create_fail_jibit_disabled(self):
        Settings.set('jibit_id_deposit_feature_status', 'disabled')
        response = self.client.post(path=self.url, data={'iban': self.iban, 'type': 'jibit'}).json()
        assert response == {
            'status': 'failed',
            'code': 'FeatureUnavailable',
            'message': 'Jibit ID deposit is disabled',
        }

    @patch('exchange.shetab.handlers.jibit.JibitPip.get_payment_id')
    def test_user_payments_ids_create_fail_payment_object(self, mock):
        self.bank_account = BankAccount.objects.create(
            user=self.user,
            account_number='78' * 6,
            shaba_number=self.iban,
            owner_name=self.user.get_full_name(),
            bank_name=BankAccount.BANK_ID[10],
            bank_id=10,
            confirmed=True,
            status=BankAccount.STATUS.confirmed,
        )
        mock.return_value = None
        response = self.client.post(path=self.url, data={'iban': self.iban}).json()
        assert response == {
            'status': 'failed',
            'code': 'JibitAPIFailed',
            'message': 'Jibit API failed',
        }

    @patch('exchange.shetab.handlers.jibit.JibitPip.get_payment_id')
    def test_user_payments_ids_create_fail_jibit_object(self, mock):
        self.bank_account = BankAccount.objects.create(
            user=self.user,
            account_number='78' * 6,
            shaba_number=self.iban,
            owner_name=self.user.get_full_name(),
            bank_name=BankAccount.BANK_ID[10],
            bank_id=10,
            confirmed=True,
            status=BankAccount.STATUS.confirmed,
        )
        mock.return_value = {
            'payId': 1,
            'destinationBank': 'MELIIR',
            'destinationIban': None,
            'destinationDepositNumber': '78' * 6,
            'destinationOwnerName': 'Nobitex',
        }
        response = self.client.post(path=self.url, data={'iban': self.iban}).json()
        assert response == {
            'status': 'failed',
            'code': 'JibitAPIInvalid',
            'message': 'Jibit API invalid',
        }
        with pytest.raises(JibitAccount.DoesNotExist):
            JibitAccount.objects.get(bank=JibitAccount.BANK_CHOICES.MELIIR,
                                     iban=mock.return_value['destinationIban'],
                                     account_number=mock.return_value['destinationDepositNumber'],
                                     owner_name=mock.return_value['destinationOwnerName'])

    @patch('exchange.shetab.handlers.jibit.JibitPip.get_payment_id')
    def test_user_payments_ids_create_success(self, mock):
        bank_account = self.create_bank_account()
        mock.return_value = {
            'payId': 1,
            'destinationBank': 'MELIIR',
            'destinationIban': f'IR{"2" * 24}',
            'destinationDepositNumber': '78' * 6,
            'destinationOwnerName': 'Nobitex',
        }
        response = self.client.post(path=self.url, data={'iban': self.iban, 'type': 'jibit'}).json()
        response['paymentId'].pop('id')
        response['paymentId'].pop('accountId')
        assert response == {
            'status': 'ok',
            'paymentId': {
                'bank': None,
                'destinationAccountNumber': '787878787878',
                'destinationBank': 'ملی',
                'destinationIban': 'IR222222222222222222222222',
                'destinationOwnerName': 'Nobitex',
                'iban': 'IR111111111111111111111111',
                'paymentId': 1,
                'type': 'jibit',
            },
        }

        jibit_account = JibitAccount.objects.filter(
            bank=JibitAccount.BANK_CHOICES.MELIIR,
            iban=mock.return_value['destinationIban'],
            account_number=mock.return_value['destinationDepositNumber'],
            owner_name=mock.return_value['destinationOwnerName'],
        ).first()
        assert jibit_account

        payment_id_obj = JibitPaymentId.objects.filter(
            bank_account=bank_account,
            jibit_account=jibit_account,
            payment_id=1,
        ).first()
        assert payment_id_obj
        user_queue_item = QueueItem.objects.filter(
            user=self.user,
            feature=QueueItem.FEATURES.jibit_pip,
            status=QueueItem.STATUS.done,
        ).first()
        assert user_queue_item

    @override_settings(IS_TESTNET=True)
    def test_user_payments_ids_create_success_on_testnet(self):
        bank_account = self.create_bank_account()
        response = self.client.post(path=self.url, data={'iban': self.iban, 'type': 'jibit'}).json()
        assert response['paymentId']
        payment_id = response['paymentId']['paymentId']
        assert payment_id.startswith('test')

        jibit_account = JibitAccount.objects.filter(
            bank=JibitAccount.BANK_CHOICES.BKMTIR,
            iban='IR760120020000008992439961',
            account_number='8992439961',
            owner_name='ايوان رايان پيام',
        ).first()
        assert jibit_account
        payment_id_obj = JibitPaymentId.objects.filter(
            bank_account=bank_account,
            jibit_account=jibit_account,
            payment_id=payment_id,
        ).first()
        assert payment_id_obj

    def test_user_payments_ids_create_fail_ineligible_for_nobitex_jibit(self):
        self.user.user_type = User.USER_TYPES.level0
        self.user.save()

        response = self.client.post(
            path=self.url,
            data={
                'iban': self.iban,
                'type': 'nobitex_jibit',
            },
        ).json()
        assert response == {
            'status': 'failed',
            'code': 'PaymentTypeError',
            'message': 'User is not eligible to request this type of destination party',
        }

    @responses.activate
    @override_settings(IS_PROD=True)
    @patch('exchange.shetab.handlers.jibit.cache')
    def test_user_payments_ids_create_auto_switch_to_nobitex_jibit(self, cache_mock):
        cache_mock.get.return_value = 'access_token'
        bank_account = self.create_bank_account()
        responses.post(
            self.api_url,
            status=200,
            json={
                'payId': f'test{bank_account.id}',
                'destinationBank': 'BKMTIR',
                'destinationIban': 'IR760120020000008992439961',
                'destinationDepositNumber': '8992439961',
                'destinationOwnerName': 'ايوان رايان پيام',
            },
        )

        QueueItem.objects.create(
            user=self.user,
            feature=QueueItem.FEATURES.nobitex_jibit_ideposit,
            status=QueueItem.STATUS.done,
        )
        assert not JibitPaymentId.objects.filter(
            jibit_account__account_type=JibitAccount.ACCOUNT_TYPES.nobitex_jibit,
        ).exists()

        # the data can also have type='jibit', it does not affect on the result
        # user request a PayId on jibit, but cuz of having active flag (nobitex_jibit_ideposit) get nobitex PayId
        response = self.client.post(
            path=self.url,
            data={
                'iban': self.iban,
            },
        ).json()

        assert response['status'] == 'ok'
        payment_id = response['paymentId']
        assert payment_id['accountId'] == bank_account.id
        assert payment_id['bank'] is None
        assert payment_id['iban'] == bank_account.shaba_number
        assert payment_id['destinationBank'] == 'ملت'
        assert payment_id['destinationIban'] == 'IR760120020000008992439961'
        assert payment_id['destinationOwnerName'] == 'ايوان رايان پيام'
        assert payment_id['destinationAccountNumber'] == '8992439961'
        assert payment_id['paymentId'] == f'test{bank_account.id}'
        assert payment_id['type'] == 'nobitex_jibit'

        jibit_payment_id = JibitPaymentId.objects.filter(
            jibit_account__account_type=JibitAccount.ACCOUNT_TYPES.nobitex_jibit,
        ).first()
        assert jibit_payment_id
        assert jibit_payment_id.bank_account == bank_account
        assert jibit_payment_id.bank_account.user == self.user

        jibit_account = JibitAccount.objects.filter(
            account_number='8992439961',
            iban='IR760120020000008992439961',
            account_type=JibitAccount.ACCOUNT_TYPES.nobitex_jibit,
        ).first()
        assert jibit_payment_id.jibit_account == jibit_account

    @responses.activate
    @patch('exchange.shetab.handlers.jibit.cache')
    def test_user_payments_ids_create_auto_switch_to_nobitex_jibit_with_account_type(self, cache_mock):
        cache_mock.get.return_value = 'access_token'
        bank_account = self.create_bank_account()
        responses.post(
            self.api_url,
            status=200,
            json={
                'payId': f'test{bank_account.id}',
                'destinationBank': 'BKMTIR',
                'destinationIban': 'IR760120000000007565000016',
                'destinationDepositNumber': '7565000016',
                'destinationOwnerName': 'راهکار فناوری نویان',
            },
        )

        QueueItem.objects.create(
            user=self.user,
            feature=QueueItem.FEATURES.nobitex_jibit_ideposit,
            status=QueueItem.STATUS.done,
        )
        assert not JibitPaymentId.objects.filter(
            jibit_account__account_type=JibitAccount.ACCOUNT_TYPES.nobitex_jibit,
        ).exists()

        # the data can also have type='jibit', it does not affect on the result
        # user request a PayId on jibit, but cuz of having active flag (nobitex_jibit_ideposit) get nobitex PayId
        response = self.client.post(
            path=self.url,
            data={
                'iban': self.iban,
                'destinatinParty': 'nobitex_jibit',
            },
        ).json()

        assert response['status'] == 'ok'
        payment_id = response['paymentId']
        assert payment_id['accountId'] == bank_account.id
        assert payment_id['bank'] is None
        assert payment_id['iban'] == bank_account.shaba_number
        assert payment_id['destinationBank'] == 'ملت'
        assert payment_id['destinationIban'] == 'IR760120000000007565000016'
        assert payment_id['destinationOwnerName'] == 'راهکار فناوری نویان'
        assert payment_id['destinationAccountNumber'] == '7565000016'
        assert payment_id['paymentId'] == f'test_nobitex_jibit_{bank_account.id}'
        assert payment_id['type'] == 'nobitex_jibit'

    @responses.activate
    @patch('exchange.shetab.handlers.jibit.cache')
    def test_user_payments_ids_create_auto_switch_to_nobitex_jibit_level1_new_joiner(self, cache_mock):
        cache_mock.get.return_value = 'access_token'
        bank_account = self.create_bank_account()
        responses.post(
            self.api_url,
            status=200,
            json={
                'payId': f'test{bank_account.id}',
                'destinationBank': 'BKMTIR',
                'destinationIban': 'IR760120000000007565000016',
                'destinationDepositNumber': '7565000016',
                'destinationOwnerName': 'راهکار فناوری نویان',
            },
        )

        self.user.user_type = User.USER_TYPE_LEVEL1
        self.user.date_joined = datetime(2025, 1, 5, tzinfo=timezone.utc)
        self.user.save()

        assert not JibitPaymentId.objects.filter(
            jibit_account__account_type=JibitAccount.ACCOUNT_TYPES.nobitex_jibit,
        ).exists()

        # the data can also have type='jibit', it does not affect on the result
        # user request a PayId on jibit, but cuz of having active flag (nobitex_jibit_ideposit) get nobitex PayId
        response = self.client.post(
            path=self.url,
            data={
                'iban': self.iban,
                'destinatinParty': 'nobitex_jibit',
            },
        ).json()

        assert response['status'] == 'ok'
        payment_id = response['paymentId']
        assert payment_id['accountId'] == bank_account.id
        assert payment_id['bank'] is None
        assert payment_id['iban'] == bank_account.shaba_number

    def test_user_payments_ids_create_fail_no_pip_queue_item_and_ineligible(self):
        tag = Tag.objects.create(name='استعلام')
        UserTag.objects.create(user=self.user, tag=tag)
        response = self.client.post(path=self.url, data={'iban': self.iban}).json()
        assert response == {
            'status': 'failed',
            'code': 'UserLevelRestriction',
            'message': 'UserLevelRestriction',
        }

    @responses.activate
    @patch('exchange.shetab.handlers.jibit.cache')
    def test_user_payments_ids_create_success_with_auto_created_pip_queue_item(self, cache_mock):
        assert not QueueItem.objects.filter(user=self.user, feature=QueueItem.FEATURES.jibit_pip).exists()

        self.user.user_type = User.USER_TYPES.verified
        self.user.save(update_fields=['user_type'])
        cache_mock.get.return_value = 'access_token'
        bank_account = self.create_bank_account()
        responses.post(
            self.api_url,
            status=200,
            json={
                'payId': f'test{bank_account.id}',
                'destinationBank': 'BKMTIR',
                'destinationIban': 'IR760120020000008992439961',
                'destinationDepositNumber': '8992439961',
                'destinationOwnerName': 'ايوان رايان پيام',
            },
        )

        response = self.client.post(path=self.url, data={'iban': self.iban, 'type': 'jibit'}).json()
        assert response['status'] == 'ok'
        assert response['paymentId']['paymentId'] == f'test_jibit_{bank_account.id}'

        assert QueueItem.objects.filter(
            user=self.user,
            feature=QueueItem.FEATURES.jibit_pip,
            status=QueueItem.STATUS.done,
        ).exists()

    def test_jibit_payment_id_reference_id(self):
        jibit_account = JibitAccount.objects.create(
            bank=JibitAccount.BANK_CHOICES.BKMTIR,
            iban=self.iban,
            account_number='123456789',
            owner_name='Test Testzadeh pour',
            account_type=JibitAccount.ACCOUNT_TYPES.jibit,
        )
        bank_account = self.create_bank_account()
        jibit_pay_id = JibitPaymentId.objects.create(
            bank_account=bank_account,
            jibit_account=jibit_account,
            payment_id='123456789',
        )
        assert jibit_pay_id.reference_number == f'NA{bank_account.id}'

        jibit_account.account_type = JibitAccount.ACCOUNT_TYPES.nobitex_jibit
        assert jibit_pay_id.reference_number == f'NJ{bank_account.id}'

    def test_create_payment_id_bad_type(self):
        response = self.client.post(
            path=self.url,
            data={
                'iban': self.iban,
                'type': 'nobitex_vandar',
            },
        ).json()

        assert response['status'] == 'failed'
        assert response['code'] == 'ParseError'
        assert response['message'] == 'Invalid choices: "nobitex_vandar"'
