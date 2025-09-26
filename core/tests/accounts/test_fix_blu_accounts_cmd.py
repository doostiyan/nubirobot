from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import BankAccount
from exchange.wallet.models import User


def generate_valid_shaba(i: int = 0, bank_id=BankAccount.BANK_ID.saman):
    return f'IR120{bank_id}66118{str(i).zfill(14)}'


@pytest.mark.django_db
class TestUpdateBluAccountsCommand(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)

    def test_command_updates_only_eligible_accounts(self):
        eligible_account = BankAccount.objects.create(
            user=self.user,
            account_number='6118-eligible',
            shaba_number=generate_valid_shaba(),
        )

        ineligible_account_1 = BankAccount.objects.create(
            user=self.user,
            account_number='6118-ineligible',
            shaba_number='INVALID_SHABA_NUMBER',
        )

        ineligible_account_2 = BankAccount.objects.create(
            user=self.user,
            account_number='6118-ineligible',
            shaba_number=f'IR120{BankAccount.BANK_ID.saman}66119{str(0).zfill(14)}',
        )

        non_matching_account = BankAccount.objects.create(
            user=self.user,
            account_number='611812345',
            shaba_number=generate_valid_shaba(),
        )

        other_bank_account = BankAccount.objects.create(
            user=self.user,
            account_number='6118-ineligible',
            shaba_number=generate_valid_shaba(bank_id=BankAccount.BANK_ID.refah),
        )

        out = StringIO()
        call_command('fix_blu_account_numbers', stdout=out)
        output = out.getvalue()

        eligible_account.refresh_from_db()
        ineligible_account_1.refresh_from_db()
        ineligible_account_2.refresh_from_db()
        non_matching_account.refresh_from_db()
        other_bank_account.refresh_from_db()

        expected_value = eligible_account.shaba_number[-18:]

        assert eligible_account.account_number == expected_value
        assert ineligible_account_1.account_number == '6118-ineligible'
        assert ineligible_account_2.account_number == '6118-ineligible'
        assert non_matching_account.account_number == '611812345'
        assert other_bank_account.account_number == '6118-ineligible'

        assert 'Updated 1 accounts' in output

    def test_command_bulk_update_with_many_accounts(self):
        eligible_accounts = []
        for i in range(5):
            account = BankAccount.objects.create(
                user=self.user,
                bank_id=BankAccount.BANK_ID.saman,
                account_number=f'6118-acc{i}',
                shaba_number=generate_valid_shaba(i),
            )
            eligible_accounts.append(account)

        out = StringIO()
        call_command('fix_blu_account_numbers', batch_size=4, stdout=out)
        output = out.getvalue()

        for account in eligible_accounts:
            account.refresh_from_db()
            expected_value = account.shaba_number[-18:]
            assert account.account_number == expected_value

        assert 'Updated 5 accounts' in output
