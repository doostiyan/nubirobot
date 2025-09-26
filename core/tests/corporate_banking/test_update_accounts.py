import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import responses
from django.test import TestCase

from exchange.accounts.models import BankAccount
from exchange.corporate_banking.crons import GetAccountsCron
from exchange.corporate_banking.exceptions import ThirdPartyAuthenticationException, ThirdPartyClientUnavailable
from exchange.corporate_banking.integrations.dto import AccountData
from exchange.corporate_banking.integrations.toman.dto import PaginationDTO
from exchange.corporate_banking.models import ACCOUNT_TP, COBANK_PROVIDER, TOMAN_BANKS, TRANSFER_MODE, CoBankAccount
from tests.corporate_banking.test_toman_get_accounts import CobankTomanAccountsList


class TestCorporateBankingUpdateAccountsCron(TestCase):
    def setUp(self):
        self.toman_account1 = AccountData(
            id='3',
            bank_id=BankAccount.BANK_ID.melli,
            iban='IR460170000000111111130003',
            account_number='0111111130003',
            account_owner='elecom 3',
            active=True,
            opening_date=datetime(year=2024, month=8, day=7, tzinfo=timezone.utc),
            balance=200000,
            provider=COBANK_PROVIDER.toman,
            details=dict(
                credential=[1, 2, 3],
                pinned=True,
                last_update_balance_at=datetime(year=2024, month=12, day=7, hour=12, tzinfo=timezone.utc).isoformat(),
            ),
        )

        self.toman_account2 = AccountData(
            id='4',
            bank_id=TOMAN_BANKS.Mellat,
            iban='IR460170000000111111130004',
            account_number='0111111130004',
            account_owner='elecom 4',
            active=False,
            opening_date=datetime(year=2024, month=9, day=7, tzinfo=timezone.utc),
            balance=300000,
            provider=COBANK_PROVIDER.toman,
            details=dict(
                credential=[4, 5],
                pinned=False,
                last_update_balance_at=datetime(year=2024, month=12, day=8, hour=12, tzinfo=timezone.utc).isoformat(),
            ),
        )

        self.mock_bank_accounts = PaginationDTO[AccountData](
            count=2,
            next=None,
            previous=None,
            results=[
                self.toman_account1,
                self.toman_account2,
            ],
        )

    @patch.object(GetAccountsCron, 'clients', new_callable=lambda: [CobankTomanAccountsList])
    @patch('exchange.corporate_banking.crons.CobankTomanAccountsList.get_bank_accounts')
    def test_add_new_item(self, mock_get_bank_accounts, _):
        mock_get_bank_accounts.return_value = self.mock_bank_accounts

        GetAccountsCron().run()

        assert CoBankAccount.objects.count() == 2

        account = CoBankAccount.objects.get(provider_bank_id=self.toman_account1.id)
        self._assert_toman_account_equal(account, self.toman_account1)

        account = CoBankAccount.objects.get(provider_bank_id=self.toman_account2.id)
        self._assert_toman_account_equal(account, self.toman_account2)

    @patch.object(GetAccountsCron, 'clients', new_callable=lambda: [CobankTomanAccountsList])
    @patch('exchange.corporate_banking.crons.CobankTomanAccountsList.get_bank_accounts')
    def test_update_old_item(self, mock_get_bank_accounts, _):
        CoBankAccount.objects.create(
            provider=COBANK_PROVIDER.toman,
            provider_bank_id=self.toman_account1.id,
            bank=self.toman_account1.bank_id,
            provider_is_active=not self.toman_account1.active,
            iban=self.toman_account1.iban,
            account_number=self.toman_account1.account_number,
            account_owner=self.toman_account1.account_owner,
            opening_date=self.toman_account1.opening_date,
            balance=self.toman_account1.balance - 10,
            account_tp=ACCOUNT_TP.storage,
            is_active=True,
        )

        mock_get_bank_accounts.return_value = self.mock_bank_accounts

        assert CoBankAccount.objects.count() == 1

        GetAccountsCron().run()

        assert CoBankAccount.objects.count() == 2
        account = CoBankAccount.objects.get(provider_bank_id=self.toman_account1.id)
        self._assert_toman_account_equal(account, self.toman_account1, is_active=True, account_tp=ACCOUNT_TP.storage)

    @responses.activate
    def test_network_error(self):
        responses.add(
            responses.GET,
            'https://dbank-staging.qcluster.org/api/v1/account/?page=1&page_size=50',
            json={},
            status=500,
        )

        with pytest.raises(ThirdPartyClientUnavailable):
            GetAccountsCron().run()

    @responses.activate
    @patch.object(GetAccountsCron, 'clients', new_callable=lambda: [CobankTomanAccountsList])
    @patch('exchange.corporate_banking.crons.CobankTomanAccountsList.get_bank_accounts')
    def test_authentication_error(self, mock_get_bank_accounts, _):
        mock_get_bank_accounts.side_effect = ThirdPartyAuthenticationException('invalid_grant', 'you have not access')

        with pytest.raises(ThirdPartyAuthenticationException):
            GetAccountsCron().run()

    def _assert_toman_account_equal(self, account: CoBankAccount, toman_account: AccountData, **kwargs):
        assert account.provider == COBANK_PROVIDER.toman

        assert account.provider_bank_id == toman_account.id
        assert account.iban == toman_account.iban
        assert account.account_number == toman_account.account_number
        assert account.account_owner == toman_account.account_owner
        assert account.provider_is_active == toman_account.active
        assert account.balance == toman_account.balance
        assert account.bank == toman_account.bank_id
        assert account.opening_date == toman_account.opening_date
        assert json.loads(account.deails) == toman_account.details

        assert account.is_active == kwargs.get('is_active', False)
        assert account.account_tp == kwargs.get('account_tp', ACCOUNT_TP.operational)
        assert account.is_deleted == kwargs.get('is_deleted', False)
        assert account.transfer_mode == kwargs.get('transfer_mode', TRANSFER_MODE.intra_bank)
