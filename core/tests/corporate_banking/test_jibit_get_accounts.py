import datetime
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import requests
import responses
from django.test import TestCase

from exchange.accounts.models import BankAccount
from exchange.base.models import Settings
from exchange.corporate_banking.crons import GetAccountsCron
from exchange.corporate_banking.exceptions import (
    ThirdPartyAuthenticationException,
    ThirdPartyClientUnavailable,
    ThirdPartyDataParsingException,
)
from exchange.corporate_banking.integrations.dto import AccountData
from exchange.corporate_banking.integrations.jibit.accounts_list import CobankJibitAccountsList
from exchange.corporate_banking.integrations.toman.dto import PaginationDTO
from exchange.corporate_banking.models import ACCOUNT_TP, COBANK_PROVIDER, NOBITEX_BANK_CHOICES, CoBankAccount
from exchange.corporate_banking.models.constants import JIBIT_BANKS


class TestCobankJibitAccountsList(TestCase):
    def setUp(self):
        self.jibit_client = CobankJibitAccountsList()
        self.base_url = 'https://napi.jibit.ir/cobank/v1/accounts/'
        self.default_access_token = 'some_access_token'
        Settings.set('cobank_jibit_access_token', self.default_access_token)
        self.sample_response = [
            {
                'id': 945209546081599504,
                'active': True,
                'bank': 'MARKAZI',
                'accountNumber': '123456789',
                'iban': 'IR12345678901234567890',
                'ownerFirstName': 'Llama',
                'ownerLastName': 'Llama zadeh',
                'clientCode': 'string',
                'merchantId': 0,
                'systemAccountIban': 'string',
                'cif': 'string',
                'manualBalanceActive': True,
                'autoBalanceActive': True,
                'manualCollectActive': True,
                'autoCollectActive': True,
                'autoCollectMinBalance': 0,
                'autoCollectSettleableBalanceThresholdActive': True,
                'autoCollectMaximumSettleableBalanceThreshold': 0,
                'autoCollectMinimumSettleableBalanceThreshold': 0,
                'collectMaximumAmount': 0,
                'collectMinimumAmount': 0,
                'manualRawStatementActive': True,
                'manualStatementCrawlerDuration': 0,
                'manualStatementCrawlerLength': 0,
                'augmentedStatementActive': True,
                'augmentedStatementFetchNameActive': True,
                'augmentedStatementKytActive': True,
                'settlementActive': True,
                'settlementAutoSourceActive': True,
                'preferNormalBatchTransfer': True,
                'preferAchBatchTransfer': True,
                'preferRtgsBatchTransfer': True,
                'refundActive': True,
                'balanceActive': True,
                'rawStatementActive': True,
                'normalTransferActive': True,
                'normalTransferInquiryActive': True,
                'achTransferActive': True,
                'achTransferInquiryActive': True,
                'rtgsTransferActive': True,
                'rtgsTransferInquiryActive': True,
                'normalBatchTransferActive': True,
                'normalBatchTransferInquiryActive': True,
                'achBatchTransferActive': True,
                'achBatchTransferInquiryActive': True,
                'rtgsBatchTransferActive': True,
                'rtgsBatchTransferInquiryActive': True,
                'description': 'some random description',
                'createdAt': '2025-02-04T17:56:59.862Z',
                'updatedAt': '2025-02-04T17:57:59.862Z',
            }
        ]

    @responses.activate
    def test_get_bank_accounts_success(self):
        responses.add(
            responses.GET,
            self.base_url,
            json=self.sample_response,
            status=200,
        )

        result = self.jibit_client.get_bank_accounts().results

        assert len(result) == 1
        assert result[0].opening_date == datetime.datetime(2025, 2, 4, 17, 56, 59, 862000, tzinfo=datetime.timezone.utc)
        assert result[0].account_number == '123456789'
        assert result[0].iban == 'IR12345678901234567890'
        assert result[0].account_owner == 'Llama Llama zadeh'
        assert result[0].details == self.sample_response[0]

    @responses.activate
    def test_get_bank_accounts_failure(self):
        responses.add(
            responses.GET,
            self.base_url,
            json={},
            status=500,
        )

        with pytest.raises(ThirdPartyClientUnavailable):
            self.jibit_client.get_bank_accounts()

    @responses.activate
    def test_get_bank_accounts_invalid_json(self):
        responses.add(
            responses.GET,
            self.base_url,
            json={
                'invalid_key': 'invalid_value',
            },
            status=200,
        )

        with pytest.raises(ThirdPartyDataParsingException):
            self.jibit_client.get_bank_accounts()

    @responses.activate
    @patch('exchange.corporate_banking.integrations.jibit.authenticator.CobankJibitAuthenticator.get_auth_token')
    def test_get_bank_accounts_fetch_new_token(self, mock_get_access_token: MagicMock):
        Settings.set('cobank_jibit_access_token', '')
        mock_get_access_token.return_value = 'new_access_token'

        responses.add(
            responses.GET,
            self.base_url,
            json=self.sample_response,
            status=200,
        )

        result = self.jibit_client.get_bank_accounts().results
        assert len(result) == 1
        mock_get_access_token.assert_called()

    @responses.activate
    @patch('exchange.corporate_banking.integrations.jibit.authenticator.CobankJibitAuthenticator.get_auth_token')
    def test_get_bank_accounts_authenticator_error_by_thirdparty(self, mock_get_access_token):
        Settings.set('cobank_jibit_access_token', '')

        mock_get_access_token.side_effect = ThirdPartyAuthenticationException('invalid_grant', 'you do not have access')

        with pytest.raises(ThirdPartyAuthenticationException):
            self.jibit_client.get_bank_accounts()

    @responses.activate
    @patch('exchange.corporate_banking.integrations.jibit.authenticator.CobankJibitAuthenticator.get_auth_token')
    def test_get_bank_accounts_authenticator_error_by_network(self, mock_get_access_token):
        Settings.set('cobank_jibit_access_token', '')

        mock_get_access_token.side_effect = requests.ConnectionError()

        with pytest.raises(ThirdPartyClientUnavailable):
            self.jibit_client.get_bank_accounts()


class TestGetJibitAccountsCron(TestCase):
    def setUp(self):
        self.cron_job = GetAccountsCron()

        self.sample_account_data = AccountData(
            id=0,
            active=True,
            bank_id=BankAccount.BANK_ID.centralbank,
            account_number='123456789',
            iban='IR12345678901234567890',
            account_owner='Llama Llama zadeh',
            opening_date=datetime.datetime.fromisoformat('2025-02-04T17:56:59.862+00:00'),
            balance=Decimal(0),
            provider=COBANK_PROVIDER.jibit,
            details={'description': 'some random description'},
        )

    @patch.object(GetAccountsCron, 'clients', new_callable=lambda: [CobankJibitAccountsList])
    @patch('exchange.corporate_banking.integrations.jibit.accounts_list.CobankJibitAccountsList.get_bank_accounts')
    def test_cron_creates_new_account(self, mock_get_accounts, _):
        mock_get_accounts.return_value = PaginationDTO[AccountData](
            count=0,
            next=None,
            previous=None,
            results=[self.sample_account_data],
        )

        self.cron_job.run()
        new_account = CoBankAccount.objects.filter(
            provider=COBANK_PROVIDER.jibit,
            bank=NOBITEX_BANK_CHOICES.centralbank,
        ).first()
        assert new_account
        assert new_account.iban == 'IR12345678901234567890'

    @patch.object(GetAccountsCron, 'clients', new_callable=lambda: [CobankJibitAccountsList])
    @patch('exchange.corporate_banking.integrations.jibit.accounts_list.CobankJibitAccountsList.get_bank_accounts')
    def test_cron_updates_existing_account(self, mock_get_accounts, _):
        mock_get_accounts.return_value = PaginationDTO[AccountData](
            count=0,
            next=None,
            previous=None,
            results=[self.sample_account_data],
        )

        existing_account = CoBankAccount.objects.create(
            account_tp=ACCOUNT_TP.operational,
            provider=COBANK_PROVIDER.jibit,
            provider_bank_id=JIBIT_BANKS.MARKAZI,
            bank=NOBITEX_BANK_CHOICES.centralbank,
            provider_is_active=False,
            iban='IR00000000000000000000',
            account_number='987654321',
            account_owner='Old Owner',
            opening_date='2025-01-01T00:00:00Z',
            deails={'description': 'old description'},
        )

        self.cron_job.run()

        existing_account.refresh_from_db()

        assert existing_account.account_number == '123456789'
        assert existing_account.iban == 'IR12345678901234567890'
        assert existing_account.account_owner == 'Llama Llama zadeh'
        assert json.loads(existing_account.deails)['description'] == 'some random description'
