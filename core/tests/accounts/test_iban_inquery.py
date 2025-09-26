from datetime import timedelta

import responses
from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import BankAccount, Confirmed, User
from exchange.accounts.tasks import task_convert_iban_to_account_number


class TestIBANInQuery(TestCase):
    @responses.activate
    def test_iban_inquery(self):
        responses.add(
            responses.GET,
            'https://napi.jibit.ir/ide/v1/ibans?value=IR360180000000008930967050',
            json={
                'value': 'IR360180000000008930967050',
                'ibanInfo': {
                    'bank': 'MELI',
                    'depositNumber': '008930967050',
                    'iban': 'IR360180000000008930967050',
                    'status': 'ACTIVE',
                    'owners': [{'firstName': 'ali', 'lastName': 'kafy'}],
                },
            },
            status=200,
        )
        responses.add(
            responses.GET,
            'https://napi.jibit.ir/ide/v1/ibans?value=IR850700001000116248268001',
            json={
                'value': 'IR850700001000116248268001',
                'ibanInfo': {
                    'bank': 'MELI',
                    'depositNumber': '116248268001',
                    'iban': 'IR850700001000116248268001',
                    'status': 'ACTIVE',
                    'owners': [{'firstName': 'abas', 'lastName': 'fatahzadeh'}],
                },
            },
            status=200,
        )

        # For old account
        responses.add(
            responses.GET,
            'https://napi.jibit.ir/ide/v1/ibans?value=IR850700001000116248268003',
            json={
                'value': 'IR850700001000116248268003',
                'ibanInfo': {
                    'bank': 'MELI',
                    'depositNumber': '008930967050',
                    'iban': 'IR850700001000116248268003',
                    'status': 'ACTIVE',
                    'owners': [{'firstName': 'ali', 'lastName': 'kafy'}],
                },
            },
            status=200,
        )

        user = User.objects.create_user(username='sdlhibnsaaligsdkafytr', password='<PASSWORD>')
        account_1 = BankAccount.objects.create(
            user=user,
            owner_name='alikafy',
            bank_name='test',
            bank_id=BankAccount.BANK_ID.vandar,
            shaba_number='IR360180000000008930967050',
            account_number='0',
            confirmed=True,
            status=Confirmed.STATUS.confirmed,
        )
        account_2 = BankAccount.objects.create(
            user=user,
            owner_name='alikafy',
            bank_name='test',
            bank_id=BankAccount.BANK_ID.vandar,
            shaba_number='IR850700001000116248268001',
            account_number='0',
            confirmed=True,
            status=Confirmed.STATUS.confirmed,
        )
        old_account = BankAccount.objects.create(
            user=user,
            owner_name='alikafy',
            bank_name='test',
            bank_id=BankAccount.BANK_ID.vandar,
            shaba_number='IR850700001000116248268003',
            account_number='0',
            confirmed=True,
            status=Confirmed.STATUS.confirmed,
        )
        old_account.created_at -= timedelta(days=1, minutes=1)
        old_account.save()

        call_command('iban_inquery', batch_size=1, from_days_ago=1)

        account_1.refresh_from_db()
        account_2.refresh_from_db()
        assert account_1.shaba_number == 'IR360180000000008930967050'
        assert account_2.shaba_number == 'IR850700001000116248268001'
        assert account_1.account_number == '008930967050'
        assert account_2.account_number == '116248268001'

        old_account.refresh_from_db()
        assert old_account.account_number == '0'


class TestIbanToAccountNumberTask(TestCase):
    @responses.activate
    def test_task_convert_iban_to_account_number(self):
        responses.add(
            responses.GET,
            'https://napi.jibit.ir/ide/v1/ibans?value=IR360180000000008930967050',
            json={
                'value': 'IR360180000000008930967050',
                'ibanInfo': {
                    'bank': 'MELI',
                    'depositNumber': '008930967050',
                    'iban': 'IR360180000000008930967050',
                    'status': 'ACTIVE',
                    'owners': [{'firstName': 'ali', 'lastName': 'kafy'}],
                },
            },
            status=200,
        )

        user = User.objects.get(pk=201)
        account_1 = BankAccount.objects.create(
            user=user,
            owner_name='alikafy',
            bank_name='test',
            bank_id=BankAccount.BANK_ID.vandar,
            shaba_number='IR360180000000008930967050',
            account_number='0',
            confirmed=True,
            status=Confirmed.STATUS.confirmed,
        )

        task_convert_iban_to_account_number(account_1.pk)

        account_1.refresh_from_db()
        assert account_1.shaba_number == 'IR360180000000008930967050'
        assert account_1.account_number == '008930967050'
