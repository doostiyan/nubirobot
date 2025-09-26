from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounting.models import DepositSystemBankAccount
from exchange.accounts.models import User, BankAccount
from exchange.base.models import Currencies
from exchange.wallet.models import Wallet, BankDeposit
from tests.features.utils import BetaFeatureTestMixin


class BankDepositTest(BetaFeatureTestMixin, APITestCase):
    feature = 'bank_manual_deposit'

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        User.objects.filter(id=cls.user.id).update(user_type=User.USER_TYPES.verified)
        cls.request_feature(cls.user, 'done')
        bank = BankAccount.BANK_ID.melli
        cls.bank_account = BankAccount.objects.create(
            user=cls.user,
            account_number='78'*6,
            shaba_number=f'IR000{bank:2<19}',
            owner_name=cls.user.get_full_name(),
            bank_name=BankAccount.BANK_ID[bank],
            bank_id=bank,
            confirmed=True,
            status=BankAccount.STATUS.confirmed,
        )
        cls.system_deposit = DepositSystemBankAccount.objects.create(
            iban_number=f'IR000{bank:2<19}',
            account_number='12345777',
            bank_id=DepositSystemBankAccount.BANK_ID.centralbank,
        )

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def test_bank_deposit_fee(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.rls)
        assert wallet.balance == 0
        amount = 100_000_0
        expected_fee = 12_0
        response = self.client.post('/users/wallets/deposit/bank', {
            'srcBankAccount': self.bank_account.id,
            'amount': amount,
            'receiptID': '12345',
            'depositedAt': '1399/09/10',
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        deposit = BankDeposit.objects.filter(id=data['bankDeposit']['id']).first()
        assert deposit
        assert deposit.amount == amount
        assert deposit.fee == expected_fee
        deposit.confirmed = True
        deposit.save(update_fields=('confirmed',))
        wallet.refresh_from_db()
        assert wallet.balance == amount - expected_fee

    def test_bank_deposit_min_amount(self):
        response = self.client.post('/users/wallets/deposit/bank', {
            'srcBankAccount': self.bank_account.id,
            'amount': 3_000_0,
            'receiptID': '12345',
            'depositedAt': '1399/09/10',
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == 'AmountTooLow'

    def test_bank_deposit_max_amount(self):
        response = self.client.post('/users/wallets/deposit/bank', {
            'srcBankAccount': self.bank_account.id,
            'amount': 10 ** 11,
            'receiptID': '12345',
            'depositedAt': '1399/09/10',
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == 'AmountTooHigh'

    def test_create_bank_deposit_without_dst_account(self):
        response = self.client.get('/users/wallets/deposit/bank', {
            'srcBankAccount': self.bank_account.id,
            'amount': '100_000',
            'receiptID': '1234523',
            'depositedAt': '1399/09/10',
            'dstAccountID': '',
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        deposit = BankDeposit.objects.filter(id=data['bankDeposit']['id']).exists()
        assert deposit

    def test_create_bank_deposit_with_fake_dst_account(self):
        response = self.client.get('/users/wallets/deposit/bank', {
            'srcBankAccount': self.bank_account.id,
            'amount': '100_000',
            'receiptID': '1234523',
            'depositedAt': '1399/09/10',
            'dstAccountID': self.system_deposit.id + 1,
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'failed'

    def test_create_bank_deposit_with_correct_dst_account(self):
        response = self.client.get('/users/wallets/deposit/bank', {
            'srcBankAccount': self.bank_account.id,
            'amount': '100_000',
            'receiptID': '1234523',
            'depositedAt': '1399/09/10',
            'dstAccountID': self.system_deposit.id,
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        deposit = BankDeposit.objects.filter(id=data['bankDeposit']['id']).first()
        assert deposit
        assert deposit.dst_system_account == self.system_deposit
