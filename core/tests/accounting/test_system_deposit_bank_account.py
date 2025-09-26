from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounting.models import DepositSystemBankAccount
from exchange.accounts.models import BankAccount, User


class DepositSystemBankAccountTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        User.objects.filter(id=cls.user.id).update(user_type=User.USER_TYPES.verified)
        bank = BankAccount.BANK_ID.melli
        cls.system_deposit = DepositSystemBankAccount.objects.create(
            iban_number=f'IR000{bank:2<21}',
            account_number='12345777',
            bank_id=DepositSystemBankAccount.BANK_ID.centralbank,
        )
        cls.system_deposit_vandar = DepositSystemBankAccount.objects.create(
            iban_number=f'31202{bank:2<21}',
            account_number='1234985777',
            bank_id=DepositSystemBankAccount.BANK_ID.vandar,
        )
        cls.system_deposit_pay = DepositSystemBankAccount.objects.create(
            iban_number=f'23491{bank:2<21}',
            account_number='1277768345777',
            bank_id=DepositSystemBankAccount.BANK_ID.pay,
        )

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def test_system_deposit_account_list(self):
        response = self.client.get('/accounting/system/deposits')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert data['accounts']
        for account in data['accounts']:
            if account['id'] in (self.system_deposit_vandar.id, self.system_deposit_pay.id):
                assert account['shaba'] == '****'
            else:
                assert (
                    account['shaba']
                    == f'{self.system_deposit.iban_number[:7]} **** {self.system_deposit.iban_number[-4:]}'
                )
