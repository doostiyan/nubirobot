import json

from django.test import TestCase

from exchange.accounts.models import BankAccount, User


class TestBankAccount(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)

    def test_bank_account_fill_account_number_finnotech(self):
        bank_account_finnotech = BankAccount.objects.create(
            user=self.user,
            account_number='0',
            bank_id=BankAccount.BANK_ID.saman,
            confirmed=True,
            status=BankAccount.STATUS.confirmed,
            api_verification=json.dumps(
                {
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
                }
            ),
        )
        assert bank_account_finnotech.account_number == '0300000010001'

    def test_bank_account_fill_account_number_jibit(self):
        bank_account_finnotech = BankAccount.objects.create(
            user=self.user,
            account_number='',
            bank_id=BankAccount.BANK_ID.saman,
            confirmed=True,
            status=BankAccount.STATUS.confirmed,
            api_verification=json.dumps(
                {
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
                }
            ),
        )
        assert bank_account_finnotech.account_number == '0987654321'

    def test_bank_account_fill_account_number_invalid_response(self):
        bank_account = BankAccount.objects.create(
            user=self.user,
            account_number='0',
            bank_id=BankAccount.BANK_ID.saman,
            confirmed=True,
            status=BankAccount.STATUS.confirmed,
            api_verification='invalid_json',
        )
        assert bank_account.account_number == '0'

        bank_account = BankAccount.objects.create(
            user=self.user,
            account_number='0',
            bank_id=BankAccount.BANK_ID.saman,
            confirmed=True,
            status=BankAccount.STATUS.confirmed,
            api_verification='{}',
        )
        assert bank_account.account_number == '0'
