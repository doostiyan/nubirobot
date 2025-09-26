from datetime import datetime

from rest_framework.test import APITestCase

from exchange.accounts.models import BankAccount, User
from exchange.base.calendar import as_ir_tz, ir_now
from exchange.base.models import Currencies
from exchange.corporate_banking.models.accounting import CoBankStatement
from exchange.corporate_banking.models.bank_account import CoBankAccount
from exchange.corporate_banking.models.constants import (
    ACCOUNT_TP,
    NOBITEX_BANK_CHOICES,
    STATEMENT_STATUS,
    STATEMENT_TYPE,
)
from exchange.wallet.models import Wallet
from exchange.wallet.views import CoBankUserDeposit


class CobankListDepositsAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.get(id=201)
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.user_bank_account = BankAccount.objects.create(
            user=self.user,
            account_number='78' * 6,
            shaba_number='IR1234567890',
            owner_name=self.user.get_full_name(),
            bank_name=BankAccount.BANK_ID[10],
            bank_id=10,
            confirmed=True,
            status=BankAccount.STATUS.confirmed,
        )
        self.cobank_account = CoBankAccount.objects.create(
            provider_bank_id=11,
            bank=NOBITEX_BANK_CHOICES.saman,
            iban='IR999999999999999999999991',
            account_number='000111222',
            account_owner='راهکار فناوری نویان',
            is_active=True,
            account_tp=ACCOUNT_TP.operational,
            is_deleted=False,
        )
        self.wallet = Wallet.get_user_wallet(
            self.user,
            Currencies.rls,
        )

    def test_deposit_list_none(self):
        data = self.client.get('/users/wallets/deposits/list').json()
        assert not data.get('deposits')

    def test_deposit_list(self):
        statement1 = CoBankStatement.objects.create(
            amount=10_000_000_0,
            tp=STATEMENT_TYPE.deposit,
            tracing_number='abcd1234',
            transaction_datetime=ir_now(),
            status=STATEMENT_STATUS.executed,
            destination_account=self.cobank_account,
            payment_id='12345',
        )

        cobank_deposit = CoBankUserDeposit.objects.create(
            amount=statement1.amount,
            user=self.user,
            user_bank_account=self.user_bank_account,
            cobank_statement=statement1,
        )

        data = self.client.get('/users/wallets/deposits/list').json()

        deposits = data.get('deposits')
        assert len(deposits) == 1
        deposit = deposits[0]

        # Assert userBankAccount details
        assert deposit['userBankAccount']['id'] == cobank_deposit.user_bank_account.id
        assert deposit['userBankAccount']['number'] == '787878787878'
        assert deposit['userBankAccount']['shaba'] == 'IR1234567890'
        assert deposit['userBankAccount']['bank'] is None
        assert deposit['userBankAccount']['owner'] == 'User One'
        assert deposit['userBankAccount']['confirmed'] is True
        assert deposit['userBankAccount']['status'] == 'confirmed'

        # Assert deposit details
        assert deposit['id'] == cobank_deposit.id
        assert deposit['depositType'] == 'cobankDeposit'
        assert deposit['amount'] == '100000000'
        assert deposit['fee'] == '10000'
        assert as_ir_tz(datetime.fromisoformat(deposit['createdAt'])) == cobank_deposit.created_at

        # Assert statement details
        statement = deposit['statement']
        assert statement['amount'] == '100000000'
        assert statement['tp'] == 'deposit'
        assert as_ir_tz(datetime.fromisoformat(statement['createdAt'])) == statement1.created_at
        assert statement['tracingNumber'] == 'abcd1234'
        assert as_ir_tz(datetime.fromisoformat(statement['transactionDatetime'])) == statement1.transaction_datetime
        assert statement['paymentId'] == '12345'
        assert statement['status'] == 'executed'
        assert statement['rejection_reason'] is None
