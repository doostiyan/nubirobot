from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytz
from django.test import TestCase

from exchange.base.calendar import ir_now
from exchange.corporate_banking.exceptions import ThirdPartyClientUnavailable
from exchange.corporate_banking.integrations.jibit.dto import StatementItemDTO as JibitStatementItemDTO
from exchange.corporate_banking.integrations.jibit.statements import JibitBankStatementClient
from exchange.corporate_banking.integrations.toman.dto import StatementItemDTO as TomanStatementDTO
from exchange.corporate_banking.integrations.toman.statements import TomanBankStatementClient
from exchange.corporate_banking.models import (
    ACCOUNT_TP,
    COBANK_PROVIDER,
    NOBITEX_BANK_CHOICES,
    STATEMENT_STATUS,
    STATEMENT_TYPE,
    CoBankAccount,
    CoBankStatement,
    ThirdpartyLog,
)
from exchange.corporate_banking.services.banker import Banker


class TestBanker(TestCase):
    def setUp(self):
        self.bank_account = CoBankAccount.objects.create(
            provider=COBANK_PROVIDER.toman,
            provider_bank_id=4,
            bank=NOBITEX_BANK_CHOICES.saderat,
            iban='IR999999999999999999999991',
            account_number='111222333',
            account_tp=ACCOUNT_TP.operational,
        )
        self.jibit_bank_account = CoBankAccount.objects.create(
            provider=COBANK_PROVIDER.jibit,
            provider_bank_id=5,
            bank=NOBITEX_BANK_CHOICES.mellat,
            iban='IR999999999999999999999992',
            account_number='111222334',
            account_tp=ACCOUNT_TP.operational,
        )

        self.from_time = datetime(2025, 1, 1, 0, 0, 0)
        self.to_time = datetime(2025, 1, 5, 23, 59, 59)
        self.banker = Banker(provider=COBANK_PROVIDER.toman, from_time=self.from_time, to_time=self.to_time)
        self.jibit_banker = Banker(provider=COBANK_PROVIDER.jibit, from_time=self.from_time, to_time=self.to_time)

    @patch.object(TomanBankStatementClient, 'get_statements')
    def test_get_bank_statements_success(self, mock_get_statements):
        """
        Test a successful scenario where the TomanBankStatementClient returns some statements.
        We verify that:
          - The statements are stored in CoBankStatement (valid statements).
          - If any statement is missing required fields, it's stored in ThirdpartyLog (invalid).
        """
        mock_get_statements.return_value = iter(
            [
                (
                    [
                        TomanStatementDTO(  # A fully "valid" statement
                            id=101,
                            amount=1000,
                            side=True,  # deposit
                            tracing_number='TRC-101',
                            transaction_datetime='2055-01-05T03:33:13Z',
                            created_at='2025-01-05T02:37:22.414085Z',
                            payment_id=None,
                            source_account='SRC-ACCT',
                            destination_account=self.bank_account.pk,
                            source_iban='IR1119999999999999999992',
                            source_card='77777-77777',
                            api_response={
                                'id': 101,
                                'amount': 1000,
                                'side': True,  # deposit
                                'tracing_number': 'TRC-101',
                                'transaction_datetime': '2055-01-05T03:33:13Z',
                                'created_at': '2025-01-05T02:37:22.414085Z',
                                'payment_id': None,
                                'source_account': 'SRC-ACCT',
                                'source_iban': 'IR1119999999999999999992',
                                'source_card': '77777-77777',
                            },
                        ),
                        # Another statement missing required data => invalid
                        TomanStatementDTO(
                            id=103,
                            amount=None,  # Missing amount
                            side=True,
                            tracing_number='TRC-103',
                            transaction_datetime='2025-01-05T03:32:22Z',
                            created_at='2025-01-03T03:37:22.414156Z',
                            destination_account=self.bank_account.pk,
                            api_response={
                                'id': 103,
                                'amount': None,
                                'side': True,
                                'tracing_number': 'TRC-103',
                                'transaction_datetime': '2025-01-05T03:32:22Z',
                                'created_at': '2025-01-03T03:37:22.414156Z',
                            },
                        ),
                        # Another statement with invalid source account => invalid
                        TomanStatementDTO(
                            id=103,
                            amount=10000,
                            side=True,
                            source_account='1' * 26,
                            tracing_number='TRC-103',
                            transaction_datetime='2025-01-05T03:32:22Z',
                            created_at='2025-01-03T03:37:22.414156Z',
                            destination_account=self.bank_account.pk,
                            api_response={
                                'id': 103,
                                'amount': None,
                                'side': True,
                                'tracing_number': 'TRC-103',
                                'transaction_datetime': '2025-01-05T03:32:22Z',
                                'created_at': '2025-01-03T03:37:22.414156Z',
                            },
                        ),
                    ],
                    2,
                )
            ]
        )

        self.banker.get_bank_statements(self.bank_account)

        assert mock_get_statements.call_count == 1
        all_statements = CoBankStatement.objects.all()
        assert len(all_statements) == 1  # Only one statement was valid and therefore, created

        # The first item is valid, so it becomes a CoBankStatement
        valid_statement = all_statements.first()
        assert valid_statement.amount == Decimal(1000)
        assert valid_statement.tp == STATEMENT_TYPE.deposit
        assert valid_statement.tracing_number == 'TRC-101'
        assert valid_statement.transaction_datetime == datetime.strptime('2055-01-05T03:33:13Z', '%Y-%m-%dT%H:%M:%S%z')
        assert valid_statement.payment_id is None
        assert valid_statement.source_account == 'SRC-ACCT'
        assert valid_statement.destination_account == self.bank_account
        assert valid_statement.provider_statement_id == '101'
        assert valid_statement.status == STATEMENT_STATUS.new
        assert valid_statement.rejection_reason is None
        assert valid_statement.source_iban == 'IR1119999999999999999992'
        assert valid_statement.source_card == '77777-77777'
        assert valid_statement.api_response == {
            'id': 101,
            'amount': 1000,
            'side': True,  # deposit
            'tracing_number': 'TRC-101',
            'transaction_datetime': '2055-01-05T03:33:13Z',
            'created_at': '2025-01-05T02:37:22.414085Z',
            'payment_id': None,
            'source_account': 'SRC-ACCT',
            'source_iban': 'IR1119999999999999999992',
            'source_card': '77777-77777',
        }
        # This is toman's time, we fill our own created_at with ir_now
        assert valid_statement.created_at != datetime.strptime('2025-01-05T02:37:22.414085Z', '%Y-%m-%dT%H:%M:%S.%f%z')

        # The second and third items were missing fields => stored in ThirdpartyLog
        all_logs = ThirdpartyLog.objects.all()
        assert len(all_logs) == 2
        log = all_logs.first()
        assert log.status == ThirdpartyLog.STATUS.failure
        assert log.provider == ThirdpartyLog.PROVIDER.toman
        assert log.service == ThirdpartyLog.SERVICE.cobank_statements
        # Check the response_details
        assert log.response_details['destination_account'] == self.bank_account.pk
        assert log.response_details['id'] == 103
        assert log.response_details['amount'] is None
        assert log.response_details['side'] is True
        assert log.response_details['tracing_number'] == 'TRC-103'
        assert log.response_details['transaction_datetime'] == '2025-01-05T03:32:22Z'
        assert log.response_details['created_at'] == '2025-01-03T03:37:22.414156Z'
        assert log.response_details['payment_id'] is None
        assert log.response_details['source_account'] is None
        assert log.response_details['is_normalized'] is None
        # Check the request_details
        assert log.request_details['from_time'] == self.from_time.isoformat()
        assert log.request_details['to_time'] == self.to_time.isoformat()
        assert log.request_details['page'] == 2

    @patch.object(TomanBankStatementClient, 'get_statements')
    def test_get_bank_statements_multiple_pages(self, mock_get_statements):
        mock_get_statements.return_value = iter(
            [
                (
                    [
                        # Two fully 'valid' statements
                        TomanStatementDTO(
                            id=101,
                            amount=1000,
                            side=True,  # deposit
                            tracing_number='TRC-101',
                            source_account='SRC-ACCT-1',
                            destination_account=self.bank_account.pk,
                            api_response={},
                        ),
                        # We will consider empty tracing number as valid as well
                        TomanStatementDTO(
                            id=102,
                            amount=500,
                            side=True,
                            tracing_number='',
                            source_account='SRC-ACCT-2',
                            destination_account=self.bank_account.pk,
                            api_response={},
                        ),
                        # We consider empty amount as invalid statement
                        TomanStatementDTO(
                            id=103,
                            amount=None,
                            side=True,
                            tracing_number='',
                            source_account='SRC-ACCT-2',
                            destination_account=self.bank_account.pk,
                            api_response={},
                        ),
                    ],
                    1,
                ),
                (
                    [
                        # One fully 'valid' statement
                        TomanStatementDTO(
                            id=104,
                            amount=1500,
                            side=True,  # deposit
                            tracing_number='TRC-104',
                            source_account='SRC-ACCT-1',
                            destination_account=self.bank_account.pk,
                            api_response={},
                        ),
                    ],
                    2,
                ),
                ([], 3),
            ]
        )

        self.banker.get_bank_statements(self.bank_account)

        assert mock_get_statements.call_count == 1
        assert len(CoBankStatement.objects.all()) == 3
        assert len(ThirdpartyLog.objects.all()) == 1

    @patch.object(TomanBankStatementClient, 'get_statements')
    def test_get_bank_statements_failure(self, mock_get_statements):
        """
        If the underlying client raises ThirdPartyClientUnavailable,
        we expect plan_failed_statement_request to create a ThirdpartyLog,
        and the exception is re-raised.
        """
        mock_get_statements.side_effect = ThirdPartyClientUnavailable(
            code='Timeout', message='Client Currently Unavailable: Timeout occurred', status_code=408
        )

        try:
            self.banker.get_bank_statements(self.bank_account)
            # If no exception is raised, fail the test
            assert False, 'Expected ThirdPartyClientUnavailable but none was raised.'
        except ThirdPartyClientUnavailable as ex:
            assert len(CoBankStatement.objects.all()) == 0
            # Check the exception details
            assert ex.code == 'Timeout'
            assert ex.status_code == 408
            # Confirm we created a ThirdpartyLog with failure status
            log_entry = ThirdpartyLog.objects.first()
            assert log_entry is None

    @patch.object(TomanBankStatementClient, 'get_statements')
    def test_get_statements_multiple_accounts(self, mock_get_statements):
        """
        If multiple CoBankAccount objects exist, get_statements() should call get_bank_statements for each.
        """
        # Create another bank account with the same provider
        second_bank = CoBankAccount.objects.create(
            provider_bank_id=6,
            bank=NOBITEX_BANK_CHOICES.saman,
            iban='IR999999999999999999999992',
            account_number='222333444',
            account_tp=ACCOUNT_TP.operational,
        )

        mock_get_statements.side_effect = [
            iter(
                [
                    (
                        [
                            # A fully "valid" statement
                            TomanStatementDTO(
                                id=101,
                                amount=1000,
                                side=True,
                                tracing_number='TRC-101',
                                destination_account=bank.pk,
                                api_response={},
                            ),
                            # A statement missing required data => invalid
                            TomanStatementDTO(
                                id=102,
                                amount=None,
                                side=True,
                                tracing_number='TRC-101',
                                destination_account=bank.pk,
                                api_response={},
                            ),
                        ],
                        1,
                    )
                ]
            )
            for bank in [self.bank_account, second_bank]
        ]

        self.banker.get_statements()

        assert mock_get_statements.call_count == 2
        # Because destination_account is different in each call to Toman, both statements are considered different
        # and are inserted into DB (although having the same tracing number and amount etc)
        assert CoBankStatement.objects.count() == 2
        # Because banks are different in each call to Toman, we'll have different api_urls and so both ThirdpartyLogs
        # are considered different and are inserted into DB (although having the same response)
        assert ThirdpartyLog.objects.count() == 2

    def test_store_statements_with_no_statements(self):
        """
        Test store_statements with an empty statement list.
        No CoBankStatement or ThirdpartyLog should be created.
        """
        self.banker.store_statements(self.bank_account, statement_dtos=[], page=1)
        assert CoBankStatement.objects.count() == 0
        assert ThirdpartyLog.objects.count() == 0

    @patch.object(TomanBankStatementClient, 'get_statements')
    def test_not_inserting_repetitive_data_into_database(self, mock_get_statements):
        mock_get_statements.return_value = iter(
            (
                [
                    # A valid statement but with repetitive data after the first call
                    TomanStatementDTO(
                        id=101,
                        amount=1000,
                        side=True,  # deposit
                        tracing_number='TRC-101',
                        destination_account=self.bank_account.pk,
                        source_account='SRC-ACCT',
                        api_response={},
                    ),
                    # A valid and unique statement
                    TomanStatementDTO(
                        id=201 + i,
                        amount=500,
                        side=True,
                        tracing_number=f'TRC-1010{i}',  # Missing tracing_number
                        transaction_datetime='2025-01-05T03:32:38Z',
                        created_at='2025-01-05T03:37:22.414121Z',
                        destination_account=self.bank_account.pk,
                        api_response={},
                    ),
                ],
                i + 1,
            )
            for i in range(3)
        )

        self.banker.get_statements()

        assert mock_get_statements.call_count == 1
        tracing_numbers = CoBankStatement.objects.all().values_list('tracing_number', flat=True)
        assert len(tracing_numbers) == 4
        assert sorted(tracing_numbers) == ['TRC-101', 'TRC-10100', 'TRC-10101', 'TRC-10102']

    @patch.object(TomanBankStatementClient, 'get_statements')
    def test_create_or_update(self, mock_get_statements):
        statement_needing_update = CoBankStatement.objects.create(
            provider_statement_id='102',
            amount=10_000_000_0,
            tp=STATEMENT_TYPE.deposit,
            transaction_datetime=ir_now(),
            status=STATEMENT_STATUS.new,
            destination_account=self.bank_account,
            source_iban=None,
        )

        duplicate_statement = CoBankStatement.objects.create(
            provider_statement_id='103',
            amount=10_000_000_0,
            tp=STATEMENT_TYPE.deposit,
            transaction_datetime=ir_now(),
            status=STATEMENT_STATUS.executed,
            destination_account=self.bank_account,
            source_iban='SRC-ACCT',
        )

        non_empty_iban_statement = CoBankStatement.objects.create(
            provider_statement_id='104',
            amount=10_000_000_0,
            tp=STATEMENT_TYPE.deposit,
            transaction_datetime=ir_now(),
            status=STATEMENT_STATUS.executed,
            destination_account=self.bank_account,
            source_iban='ALREADY_FILLED',
        )

        non_iban_change_statement = CoBankStatement.objects.create(
            provider_statement_id='105',
            amount=10_000_000_0,
            tp=STATEMENT_TYPE.deposit,
            transaction_datetime=ir_now(),
            status=STATEMENT_STATUS.executed,
            destination_account=self.bank_account,
            source_iban=None,
        )

        mock_get_statements.side_effect = [
            iter(
                [
                    (
                        [
                            TomanStatementDTO(  # New
                                id=101,
                                amount=1000,
                                side=True,  # deposit
                                destination_account=self.bank_account.pk,
                                source_account='SRC-ACCT',
                                tracing_number='TRC-101',
                                api_response={},
                            ),
                            TomanStatementDTO(  # Needs Update
                                id=102,
                                amount=1000,
                                side=True,  # deposit
                                destination_account=self.bank_account.pk,
                                source_iban='SRC-ACCT',
                                tracing_number='TRC-102',
                                api_response={},
                            ),
                            TomanStatementDTO(  # Duplicate
                                id=103,
                                amount=1000,
                                side=True,  # deposit
                                destination_account=self.bank_account.pk,
                                source_iban='SRC-ACCT',
                                tracing_number='TRC-103',
                                api_response={},
                            ),
                            TomanStatementDTO(  # Duplicate
                                id=104,
                                amount=1000,
                                side=True,  # deposit
                                destination_account=self.bank_account.pk,
                                source_iban='SRC-ACCT',  # Existing iban should not be updated
                                tracing_number='TRC-103',
                                api_response={},
                            ),
                            TomanStatementDTO(  # Duplicate
                                id=105,
                                amount=1000,  # Non-updatable fields should not be changed
                                side=True,  # deposit
                                destination_account=self.bank_account.pk,
                                source_iban=None,
                                tracing_number='TRC-103',
                                api_response={},
                            ),
                        ],
                        1,
                    )  # Ensure the second element is a page number
                ]
            )
        ]

        self.banker.get_statements()

        assert mock_get_statements.call_count == 1
        statements = CoBankStatement.objects.order_by('provider_statement_id')
        assert len(statements) == 5

        assert statements[0].provider_statement_id == '101'
        assert statements[0].tracing_number == 'TRC-101'

        statement_needing_update.refresh_from_db()
        assert statement_needing_update.provider_statement_id == '102'
        assert statement_needing_update.tracing_number is None  # Not changed
        assert statement_needing_update.source_iban == 'SRC-ACCT'  # Changed

        duplicate_statement.refresh_from_db()
        assert duplicate_statement.provider_statement_id == '103'
        assert duplicate_statement.tracing_number is None  # Not changed
        assert duplicate_statement.source_iban == 'SRC-ACCT'  # Not changed

        non_empty_iban_statement.refresh_from_db()
        assert non_empty_iban_statement.provider_statement_id == '104'
        assert non_empty_iban_statement.tracing_number is None  # Not changed
        assert non_empty_iban_statement.source_iban == 'ALREADY_FILLED'  # Not changed

        non_iban_change_statement.refresh_from_db()
        assert non_iban_change_statement.provider_statement_id == '105'
        assert non_iban_change_statement.tracing_number is None  # Not changed
        assert non_iban_change_statement.source_iban is None  # Not changed
        assert non_iban_change_statement.amount == Decimal(10_000_000_0)  # Not changed

    @patch.object(JibitBankStatementClient, 'get_statements')
    def test_jibit_get_bank_statements_success(self, mock_get_statements):
        """
        Test a successful scenario where the JibitBankStatementClient returns some statements.
        """
        mock_get_statements.side_effect = [
            iter(
                [
                    (
                        [
                            JibitStatementItemDTO(
                                destinationAccount=self.jibit_bank_account.pk,
                                referenceNumber='101',
                                accountIban='IR050120000000000000011111',
                                bankReferenceNumber='1011',
                                bankTransactionId='101111',
                                balance=10_000_000_0,
                                timestamp='2025-02-15T10:03:43.492Z',
                                creditAmount=10_000_000,
                                sourceIdentifier='SRC-ACCT',
                                destinationIdentifier='84730',
                                sourceIban='IR050120000000000000022223',
                                destinationIban='IR050120000000000000011111',
                                merchantVerificationStatus='TO_BE_DECIDED',
                                apiResponse={
                                    'destinationAccount': self.jibit_bank_account.pk,
                                    'referenceNumber': '101',
                                    'accountIban': 'IR050120000000000000011111',
                                    'bankReferenceNumber': '1011',
                                    'bankTransactionId': '101111',
                                    'balance': 10_000_000_0,
                                    'timestamp': '2025-02-15T10:03:43.492Z',
                                    'debitAmount': 10_000_000,
                                    'sourceIdentifier': 'SRC-ACCT',
                                    'destinationIdentifier': '84730',
                                    'sourceIban': 'IR050120000000000000022223',
                                    'destinationIban': 'IR050120000000000000011111',
                                    'merchantVerification_status': 'TO_BE_DECIDED',
                                    'refundType': None,
                                },
                            ),
                            # Also a valid statement but sourceIdentifier is iban
                            JibitStatementItemDTO(
                                destinationAccount=self.jibit_bank_account.pk,
                                referenceNumber='102',
                                bankReferenceNumber='1022',
                                bankTransactionId='1022222',
                                accountIban='IR050120000000000000022222',
                                balance=20_000_000_0,
                                timestamp='2025-02-15T10:04:43.492Z',
                                debitAmount=20_000_000,
                                sourceIdentifier='IR050120000000000000022222',
                                destinationIdentifier='84730',
                                sourceIban='IR050120000000000000022222',
                                destinationIban='IR050120000000000000011111',
                                merchantVerificationStatus='TO_BE_DECIDED',
                                apiResponse={
                                    'destinationAccount': self.jibit_bank_account.pk,
                                    'referenceNumber': '102',
                                    'accountIban': 'IR050120000000000000022222',
                                    'bankReferenceNumber': '1022222',
                                    'bankTransactionId': '10',
                                    'balance': 20_000_000_0,
                                    'timestamp': '2025-02-15T10:04:43.492Z',
                                    'debitAmount': 20_000_000,
                                    'sourceIdentifier': 'IR050120000000000000022222',
                                    'destinationIdentifier': '84730',
                                    'sourceIban': 'IR050120000000000000022222',
                                    'destinationIban': 'IR050120000000000000011111',
                                    'merchantVerification_status': 'TO_BE_DECIDED',
                                    'refundType': None,
                                },
                            ),
                        ],
                        1,
                    )
                ]
            )
        ]

        self.jibit_banker.get_bank_statements(self.jibit_bank_account)

        assert mock_get_statements.call_count == 1
        all_statements = CoBankStatement.objects.all()
        assert len(all_statements) == 2

        # Only the first statement's source_account should be filled
        regular_statement = all_statements.get(source_account__isnull=False)
        assert regular_statement.source_iban == 'IR050120000000000000022223'
        assert regular_statement.amount == Decimal(10000000)
        assert regular_statement.tp == STATEMENT_TYPE.deposit
        assert regular_statement.tracing_number == '1011'
        assert regular_statement.transaction_datetime == datetime(2025, 2, 15, 10, 3, 43, 492000, tzinfo=pytz.UTC)
        assert regular_statement.payment_id is None
        assert regular_statement.source_account == 'SRC-ACCT'
        assert regular_statement.destination_account == self.jibit_bank_account
        assert regular_statement.status == STATEMENT_STATUS.new
        assert regular_statement.rejection_reason is None
        assert regular_statement.api_response == {
            'destinationAccount': self.jibit_bank_account.pk,
            'referenceNumber': '101',
            'accountIban': 'IR050120000000000000011111',
            'bankReferenceNumber': '1011',
            'bankTransactionId': '101111',
            'balance': 10_000_000_0,
            'timestamp': '2025-02-15T10:03:43.492Z',
            'debitAmount': 10_000_000,
            'sourceIdentifier': 'SRC-ACCT',
            'destinationIdentifier': '84730',
            'sourceIban': 'IR050120000000000000022223',
            'destinationIban': 'IR050120000000000000011111',
            'merchantVerification_status': 'TO_BE_DECIDED',
            'refundType': None,
        }
        # This is jibit's time, we fill our own created_at with ir_now
        assert regular_statement.created_at != datetime.strptime(
            '2025-01-05T02:37:22.414085Z', '%Y-%m-%dT%H:%M:%S.%f%z'
        )

    @patch.object(JibitBankStatementClient, 'get_statements')
    def test_jibit_create_or_update_statements(self, mock_get_statements):
        """
        Test Jibit Client can also .
        """
        mock_get_statements.side_effect = [
            iter(
                [
                    (
                        [
                            JibitStatementItemDTO(
                                destinationAccount=self.jibit_bank_account.pk,
                                referenceNumber='101',
                                accountIban='IR050120000000000000011111',
                                bankReferenceNumber='1011',
                                bankTransactionId='101111',
                                balance=10_000_000_0,
                                timestamp='2025-02-15T10:03:43.492Z',
                                creditAmount=10_000_000,
                                sourceIdentifier='SRC-ACCT',
                                destinationIdentifier='84730',
                                sourceIban='',  # Empty source Iban
                                destinationIban='IR050120000000000000011111',
                                merchantVerificationStatus='TO_BE_DECIDED',
                                apiResponse={
                                    'someField': 100,
                                },
                            ),
                            JibitStatementItemDTO(
                                destinationAccount=self.jibit_bank_account.pk,
                                referenceNumber='102',
                                accountIban='IR050120000000000000011111',
                                bankReferenceNumber='1012',
                                bankTransactionId='101112',
                                balance=10_000_000_0,
                                timestamp='2025-02-15T10:03:43.492Z',
                                creditAmount=10_000_000,
                                sourceIdentifier='SRC-ACCT',
                                destinationIdentifier='84730',
                                sourceIban=None,  # Null source Iban
                                destinationIban='IR050120000000000000011111',
                                merchantVerificationStatus='TO_BE_DECIDED',
                                apiResponse={
                                    'someField': 100,
                                },
                            ),
                            JibitStatementItemDTO(
                                destinationAccount=self.jibit_bank_account.pk,
                                referenceNumber='103',
                                accountIban='IR050120000000000000011111',
                                bankReferenceNumber='1013',
                                bankTransactionId='101113',
                                balance=10_000_000_0,
                                timestamp='2025-02-15T10:03:43.492Z',
                                creditAmount=10_000_000,
                                sourceIdentifier='SRC-ACCT',
                                destinationIdentifier='84730',
                                sourceIban='IR05012',  # Filled Iban
                                destinationIban='IR050120000000000000011111',
                                merchantVerificationStatus='TO_BE_DECIDED',
                                apiResponse={
                                    'someField': 100,
                                },
                            ),
                        ],
                        3,
                    )
                ]
            )
        ]

        self.jibit_banker.get_bank_statements(self.jibit_bank_account)

        assert mock_get_statements.call_count == 1
        all_statements = CoBankStatement.objects.all()
        assert len(all_statements) == 3

        assert CoBankStatement.objects.get(provider_statement_id=101).source_iban == ''
        assert CoBankStatement.objects.get(provider_statement_id=102).source_iban is None
        assert CoBankStatement.objects.get(provider_statement_id=103).source_iban == 'IR05012'

        # Test updating Iban only
        mock_get_statements.side_effect = [
            iter(
                [
                    (
                        [
                            JibitStatementItemDTO(
                                destinationAccount=self.jibit_bank_account.pk,
                                referenceNumber='101',
                                accountIban='IR050120000000000000011111',
                                bankReferenceNumber='1011',
                                bankTransactionId='101111',
                                balance=10_000_000_0,
                                timestamp='2025-02-15T10:03:43.492Z',
                                creditAmount=10_000_000,
                                sourceIdentifier='SRC',  # Changed
                                destinationIdentifier='84730',
                                sourceIban='filled iban',  # Changed
                                destinationIban='IR050120000000000000011111',
                                merchantVerificationStatus='TO_BE_DECIDED',
                                apiResponse={
                                    'someField': 100,
                                },
                            ),
                            JibitStatementItemDTO(
                                destinationAccount=self.jibit_bank_account.pk,
                                referenceNumber='102',
                                accountIban='IR050120000000000000011111',
                                bankReferenceNumber='1012000',  # Changed
                                bankTransactionId='1011120000000',  # Changed
                                balance=10_000_000_0,
                                timestamp='2025-01-15T10:03:43.492Z',  # Changed
                                creditAmount=10_000,  # Changed
                                sourceIdentifier='SRC-ACCT',
                                destinationIdentifier='84730',
                                sourceIban='filled',  # Changed
                                destinationIban='IR050120000000000000011111',
                                merchantVerificationStatus='TO_BE_DECIDED',
                                apiResponse={
                                    'someField': 100,
                                },
                            ),
                            JibitStatementItemDTO(
                                destinationAccount=self.jibit_bank_account.pk,
                                referenceNumber='103',
                                accountIban='IR050120000000000000011111',
                                bankReferenceNumber='1013',
                                bankTransactionId='101113',
                                balance=10_000_000_0,
                                timestamp='2025-02-15T10:03:43.492Z',
                                creditAmount=10_000_000,
                                sourceIdentifier='SRC-ACCT',
                                destinationIdentifier='84730',
                                sourceIban='',  # Changed
                                destinationIban='IR050120000000000000011111',
                                merchantVerificationStatus='TO_BE_DECIDED',
                                apiResponse={
                                    'someField': 100,
                                },
                            ),
                            JibitStatementItemDTO(
                                destinationAccount=self.jibit_bank_account.pk,
                                referenceNumber='104',
                                accountIban='IR050120000000000000011111',
                                bankReferenceNumber='1014',
                                bankTransactionId='101114',
                                balance=10_000_000_0,
                                timestamp='2025-02-15T10:03:43.492Z',
                                creditAmount=10_000_000,
                                sourceIdentifier='SRC-ACCT',
                                destinationIdentifier='84730',
                                sourceIban='source_iban',
                                destinationIban='IR050120000000000000011111',
                                merchantVerificationStatus='TO_BE_DECIDED',
                                apiResponse={
                                    'someField': 100,
                                },
                            ),
                        ],
                        4,
                    )
                ]
            )
        ]

        self.jibit_banker.get_bank_statements(self.jibit_bank_account)

        assert mock_get_statements.call_count == 2
        all_statements = CoBankStatement.objects.all()
        assert len(all_statements) == 4

        assert CoBankStatement.objects.get(provider_statement_id=101).source_iban == 'filled iban'  # Updated
        assert CoBankStatement.objects.get(provider_statement_id=101).source_account == 'SRC-ACCT'  # Unchanged

        assert CoBankStatement.objects.get(provider_statement_id=102).source_iban == 'filled'  # Updated
        assert CoBankStatement.objects.get(provider_statement_id=102).tracing_number == '1012'  # Unchanged
        assert CoBankStatement.objects.get(provider_statement_id=102).transaction_datetime == (
            datetime.fromisoformat('2025-02-15T10:03:43.492Z'.replace('Z', '+00:00'))
        )  # Unchanged
        assert CoBankStatement.objects.get(provider_statement_id=102).amount == Decimal(10_000_000)  # Unchanged

        assert CoBankStatement.objects.get(provider_statement_id=103).source_iban == 'IR05012'  # Unchanged

        assert CoBankStatement.objects.get(provider_statement_id=104).source_iban == 'source_iban'  # Created

    @patch.object(Banker, 'get_bank_statements')
    def test_get_statements_filters_by_provider(self, mock_get_bank_statements):
        """
        Ensure get_statements only processes bank accounts with the specified provider.
        """
        # Create additional bank accounts with different providers
        toman_bank_2 = CoBankAccount.objects.create(
            provider=COBANK_PROVIDER.toman,
            provider_bank_id=6,
            bank=NOBITEX_BANK_CHOICES.saman,
            iban='IR999999999999999999999993',
            account_number='222333445',
            account_tp=ACCOUNT_TP.operational,
        )

        jibit_bank = CoBankAccount.objects.create(
            provider=COBANK_PROVIDER.jibit,
            provider_bank_id=7,
            bank=NOBITEX_BANK_CHOICES.melli,
            iban='IR999999999999999999999994',
            account_number='333444555',
            account_tp=ACCOUNT_TP.operational,
        )

        self.banker.get_statements()

        # Assert get_bank_statements was called exactly twice (for the two Toman accounts)
        assert mock_get_bank_statements.call_count == 2

        # Assert that calls were made for the correct accounts
        called_accounts = {call.args[0] for call in mock_get_bank_statements.call_args_list}
        assert self.bank_account in called_accounts  # First Toman account
        assert toman_bank_2 in called_accounts  # Second Toman account
        assert jibit_bank not in called_accounts  # Jibit account should be ignored
