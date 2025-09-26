import json
from io import StringIO
from typing import Optional
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import BankAccount, User, VerificationProfile


class CommandsTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)
        self.user3 = User.objects.get(pk=203)

    def test_create_verification_profile_command(self):
        VerificationProfile.objects.all().delete()
        assert VerificationProfile.objects.count() == 0
        user_one_vp_before_command = VerificationProfile.objects.create(user=self.user1, mobile_confirmed=True)

        call_command('create_verification_profile_command')
        vps = sorted(
            list(VerificationProfile.objects.filter(user__in=[self.user1, self.user2, self.user3]).order_by('pk')),
            key=lambda vp: vp.user_id,
        )
        assert vps[0] == user_one_vp_before_command
        assert len(vps) == 3
        for vp in vps[1:]:
            for attr in VerificationProfile.confirmative_fields:
                assert not getattr(vp, attr)


class FillAccountNumbersCommandTest(TestCase):
    def setUp(self):
        self.test_accounts_setting_key = 'fill_account_numbers_test_emails'
        self.user1 = User.objects.create_user(username='account_number_test_user1@example.com')

        self.account1 = self._create_bank_account(
            user=self.user1,
            account_number='0',
            api_verification={
                'trackId': 'trackId',
                'result': {
                    'IBAN': 'IR500160000000300000000001',
                    'bankName': 'بانک کشاورزی ',
                    'deposit': '0300000010001',
                    'card': '6037000020090110',
                    'depositStatus': '02',
                    'depositOwners': 'علی آقایی',
                },
                'status': 'DONE',
            },
        )

        self.account2 = self._create_bank_account(
            user=self.user1,
            account_number='',
            api_verification={
                'ibanInfo': {
                    'iban': 'IR500160000000300000000001',
                    'depositNumber': '0987654321',
                    'owners': [
                        {
                            'firstName': 'علی',
                            'lastName': 'آقایی',
                        },
                    ],
                },
                'status': 'DONE',
            },
        )

        self.account3 = self._create_bank_account(
            user=self.user1,
            account_number='',
            api_verification={
                'trackId': 'trackId',
                'result': {
                    'IBAN': 'IR500160000000300000000001',
                    'bankName': 'بانک کشاورزی ',
                    'deposit': '',
                    'card': '6037000020090110',
                    'depositStatus': '02',
                    'depositOwners': 'علی آقایی',
                },
                'status': 'DONE',
            },
        )

        user2 = User.objects.create_user(username='account_number_test_user2@example.com')

        self.account4 = self._create_bank_account(
            user=user2,
            account_number='0',
        )

        self.account5 = self._create_bank_account(
            user=user2,
            account_number='',
            api_verification={'matched': True, 'verification': True},
        )

        self.account6 = self._create_bank_account(
            user=user2,
            account_number='123-123-55555-1',
            api_verification={
                'ibanInfo': {
                    'iban': 'IR500160000000300012300001',
                    'owners': [
                        {
                            'firstName': 'حسن',
                            'lastName': 'کچل',
                        },
                    ],
                },
                'status': 'DONE',
            },
        )

        self.account7 = self._create_bank_account(
            user=user2,
            account_number='0',
            api_verification={
                'ibanInfo': {
                    'iban': 'IR500160000000300012300001',
                    'depositNumber': '1234@56789',
                    'owners': [
                        {
                            'firstName': 'حسن',
                            'lastName': 'کچل',
                        },
                    ],
                },
                'status': 'DONE',
            },
        )

        self.account8 = self._create_bank_account(
            user=user2,
            account_number='0',
            api_verification={
                'trackId': 'trackId',
                'result': {
                    'IBAN': 'IR500160000000300000000001',
                    'bankName': 'بانک ملی ',
                    'deposit': '123456789',
                    'card': '6037000020090110',
                    'depositStatus': '02',
                    'depositOwners': ' حسن کچا',
                },
                'status': 'DONE',
            },
        )

        BankAccount.objects.bulk_create(
            [
                self.account1,
                self.account2,
                self.account3,
                self.account4,
                self.account5,
                self.account6,
                self.account7,
                self.account8,
            ],
        )

    @patch('exchange.accounts.management.commands.fill_account_numbers.report_exception')
    def test_fill_account_numbers(self, mock_report_exception: MagicMock):
        assert self.account1.account_number == '0'
        assert self.account2.account_number == ''
        assert self.account3.account_number == ''
        assert self.account4.account_number == '0'
        assert self.account5.account_number == ''
        assert self.account6.account_number == '123-123-55555-1'
        assert self.account7.account_number == '0'
        assert self.account8.account_number == '0'

        out = StringIO()
        call_command('fill_account_numbers', '--batch-size', '3', stdout=out)

        self.account1.refresh_from_db()
        self.account2.refresh_from_db()
        self.account3.refresh_from_db()
        self.account4.refresh_from_db()
        self.account5.refresh_from_db()
        self.account6.refresh_from_db()
        self.account7.refresh_from_db()
        self.account8.refresh_from_db()

        assert self.account1.account_number == '0300000010001'
        assert self.account2.account_number == '0987654321'
        assert self.account3.account_number == ''
        assert self.account4.account_number == '0'
        assert self.account5.account_number == ''
        assert self.account6.account_number == '123-123-55555-1'
        assert self.account7.account_number == '0'
        assert self.account8.account_number == '123456789'

        assert 'Successfully filled 3 account numbers' in out.getvalue()
        mock_report_exception.assert_not_called()

    @patch('exchange.accounts.management.commands.fill_account_numbers.report_exception')
    def test_stop_on_error(self, mock_report_exception: MagicMock):
        self.account1.api_verification = 'invalid_json'
        self.account1.save()

        assert self.account1.account_number == '0'
        assert self.account2.account_number == ''
        assert self.account3.account_number == ''
        assert self.account4.account_number == '0'
        assert self.account5.account_number == ''
        assert self.account6.account_number == '123-123-55555-1'
        assert self.account7.account_number == '0'
        assert self.account8.account_number == '0'

        out = StringIO()
        err = StringIO()
        call_command('fill_account_numbers', '--batch-size', '3', '--stop-on-error', stdout=out, stderr=err)

        self.account1.refresh_from_db()
        self.account2.refresh_from_db()
        self.account3.refresh_from_db()
        self.account4.refresh_from_db()
        self.account5.refresh_from_db()
        self.account6.refresh_from_db()
        self.account7.refresh_from_db()
        self.account8.refresh_from_db()

        assert self.account1.account_number == '0'
        assert self.account2.account_number == ''
        assert self.account3.account_number == ''
        assert self.account4.account_number == '0'
        assert self.account5.account_number == ''
        assert self.account6.account_number == '123-123-55555-1'
        assert self.account7.account_number == '0'
        assert self.account8.account_number == '0'

        assert 'Error processing account ID' in err.getvalue()
        assert 'Stopping due to error as requested.' in out.getvalue()
        assert 'Successfully filled' not in out.getvalue()
        mock_report_exception.assert_called()

    @patch('exchange.accounts.management.commands.fill_account_numbers.report_exception')
    def test_fail_without_stopping(self, mock_report_exception: MagicMock):
        self.account1.api_verification = 'invalid_json'
        self.account1.save()

        assert self.account1.account_number == '0'
        assert self.account2.account_number == ''
        assert self.account3.account_number == ''
        assert self.account4.account_number == '0'
        assert self.account5.account_number == ''
        assert self.account6.account_number == '123-123-55555-1'
        assert self.account7.account_number == '0'
        assert self.account8.account_number == '0'

        out = StringIO()
        err = StringIO()
        call_command('fill_account_numbers', '--batch-size', '3', stdout=out, stderr=err)

        self.account1.refresh_from_db()
        self.account2.refresh_from_db()
        self.account3.refresh_from_db()
        self.account4.refresh_from_db()
        self.account5.refresh_from_db()
        self.account6.refresh_from_db()
        self.account7.refresh_from_db()
        self.account8.refresh_from_db()

        assert self.account1.account_number == '0'
        assert self.account2.account_number == '0987654321'
        assert self.account3.account_number == ''
        assert self.account4.account_number == '0'
        assert self.account5.account_number == ''
        assert self.account6.account_number == '123-123-55555-1'
        assert self.account7.account_number == '0'
        assert self.account8.account_number == '123456789'

        assert 'Error processing account ID' in err.getvalue()
        assert 'Successfully filled 2 account numbers' in out.getvalue()
        mock_report_exception.assert_called()

    def test_first_batch_without_update(self):
        """
        We shouldn't miss bank accounts that are after a batch without update
        """
        BankAccount.objects.all().delete()

        account1 = self._create_bank_account(
            user=self.user1,
            account_number='',
            api_verification={'matched': True, 'verification': True},
        )
        account2 = self._create_bank_account(
            user=self.user1,
            account_number='0',
            api_verification={
                'ibanInfo': {
                    'iban': 'IR500160000000300012300001',
                    'depositNumber': '1234@56789',
                    'owners': [
                        {
                            'firstName': 'حسن',
                            'lastName': 'کچل',
                        },
                    ],
                },
                'status': 'DONE',
            },
        )
        account3 = self._create_bank_account(
            user=self.user1,
            account_number='0',
            api_verification={
                'trackId': 'trackId',
                'result': {
                    'IBAN': 'IR500160000000300000000001',
                    'bankName': 'بانک کشاورزی ',
                    'deposit': '0300000010001',
                    'card': '6037000020090110',
                    'depositStatus': '02',
                    'depositOwners': 'علی آقایی',
                },
                'status': 'DONE',
            },
        )
        account4 = self._create_bank_account(
            user=self.user1,
            account_number='',
            api_verification={
                'ibanInfo': {
                    'iban': 'IR500160000000300000000001',
                    'depositNumber': '0987654321',
                    'owners': [
                        {
                            'firstName': 'علی',
                            'lastName': 'آقایی',
                        },
                    ],
                },
                'status': 'DONE',
            },
        )

        BankAccount.objects.bulk_create([account1, account2, account3, account4])

        out = StringIO()
        call_command('fill_account_numbers', '--batch-size', '2', stdout=out)

        account1.refresh_from_db()
        account2.refresh_from_db()
        account3.refresh_from_db()
        account4.refresh_from_db()

        assert account1.account_number == ''
        assert account2.account_number == '0'
        assert account3.account_number == '0300000010001'
        assert account4.account_number == '0987654321'

        assert 'Successfully filled 2 account numbers' in out.getvalue()

    def test_fill_account_numbers_test_mode(self):
        self.user1.email = 'm.a.taqvazadeh@gmail.com'
        self.user1.save()

        assert self.account1.account_number == '0'
        assert self.account2.account_number == ''
        assert self.account3.account_number == ''
        assert self.account4.account_number == '0'
        assert self.account5.account_number == ''
        assert self.account6.account_number == '123-123-55555-1'
        assert self.account7.account_number == '0'
        assert self.account8.account_number == '0'

        out = StringIO()
        call_command('fill_account_numbers', '--test', stdout=out)

        self.account1.refresh_from_db()
        self.account2.refresh_from_db()
        self.account3.refresh_from_db()
        self.account4.refresh_from_db()
        self.account5.refresh_from_db()
        self.account6.refresh_from_db()
        self.account7.refresh_from_db()
        self.account8.refresh_from_db()

        assert self.account1.account_number == '0300000010001'
        assert self.account2.account_number == '0987654321'
        assert self.account3.account_number == ''
        assert self.account4.account_number == '0'
        assert self.account5.account_number == ''
        assert self.account6.account_number == '123-123-55555-1'
        assert self.account7.account_number == '0'
        assert self.account8.account_number == '0'

        assert 'Running in test mode' in out.getvalue()
        assert 'Successfully filled 2 account numbers' in out.getvalue()

    def test_fill_account_numbers_test_mode_no_emails(self):
        self.user1.email = 'none_test_email@example.com'
        self.user1.save()

        assert self.account1.account_number == '0'
        assert self.account2.account_number == ''
        assert self.account3.account_number == ''
        assert self.account4.account_number == '0'
        assert self.account5.account_number == ''
        assert self.account6.account_number == '123-123-55555-1'
        assert self.account7.account_number == '0'
        assert self.account8.account_number == '0'

        out = StringIO()
        call_command('fill_account_numbers', '--test', stdout=out)

        self.account1.refresh_from_db()
        self.account2.refresh_from_db()
        self.account3.refresh_from_db()
        self.account4.refresh_from_db()
        self.account5.refresh_from_db()
        self.account6.refresh_from_db()
        self.account7.refresh_from_db()

        assert self.account1.account_number == '0'
        assert self.account2.account_number == ''
        assert self.account3.account_number == ''
        assert self.account4.account_number == '0'
        assert self.account5.account_number == ''
        assert self.account6.account_number == '123-123-55555-1'
        assert self.account7.account_number == '0'
        assert self.account8.account_number == '0'

        assert 'Running in test mode' in out.getvalue()
        assert 'No records to update' in out.getvalue()

    @staticmethod
    def _create_bank_account(user: User, account_number: str, api_verification: Optional[dict] = None):
        return BankAccount(
            user=user,
            account_number=account_number,
            bank_id=BankAccount.BANK_ID.saman,
            confirmed=True,
            status=BankAccount.STATUS.confirmed,
            api_verification=json.dumps(api_verification) if api_verification else None,
        )
