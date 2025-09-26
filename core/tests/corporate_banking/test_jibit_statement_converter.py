from datetime import datetime
from decimal import Decimal

import pytz
from django.test.testcases import TestCase

from exchange.base.constants import MONETARY_DECIMAL_PLACES
from exchange.corporate_banking.exceptions import InvalidTimestampException, StatementDataInvalidAmountException
from exchange.corporate_banking.integrations.jibit.converters import JibitStatementConverter
from exchange.corporate_banking.integrations.jibit.dto import StatementItemDTO
from exchange.corporate_banking.models import STATEMENT_TYPE, CoBankStatement
from exchange.wallet.constants import DEPOSIT_MAX_DIGITS


class JibitStatementConverterTests(TestCase):
    def setUp(self):
        self.converter = JibitStatementConverter

    def test_validate_amount_both_set_raises_exception(self):
        with self.assertRaises(StatementDataInvalidAmountException):
            self.converter._validate_amount(10, 5)

    def test_validate_amount_valid_credit(self):
        amount = self.converter._validate_amount(None, 100)
        assert amount == 100

    def test_validate_amount_valid_debit(self):
        amount = self.converter._validate_amount(50, None)
        assert amount == -50

    def test_validate_amount_too_large_returns_none(self):
        max_value = Decimal(f'1e{DEPOSIT_MAX_DIGITS - MONETARY_DECIMAL_PLACES}')
        amount = self.converter._validate_amount(max_value, None)
        self.assertIsNone(amount)

    def test_parse_iso_datetime_valid(self):
        timestamp = '2024-02-17T12:34:56Z'
        expected_dt = datetime(2024, 2, 17, 12, 34, 56, tzinfo=pytz.UTC)
        assert self.converter._parse_iso_datetime(timestamp) == expected_dt

    def test_parse_iso_datetime_invalid_raises_exception(self):
        with self.assertRaises(InvalidTimestampException):
            self.converter._parse_iso_datetime('invalid-date')

    def test_get_source_account_same_as_iban_returns_none(self):
        self.assertIsNone(
            self.converter._get_source_account('IR12345678901234567890', 'IR12345678901234567890', 'VARIZ_UNKNOWN')
        )

    def test_get_tp_debit(self):
        assert self.converter._get_tp(100) == STATEMENT_TYPE.deposit

    def test_get_tp_credit(self):
        assert self.converter._get_tp(None) == STATEMENT_TYPE.withdraw

    def test_convert_valid_dto(self):
        dto = StatementItemDTO(
            destinationAccount=123456,
            referenceNumber='REF123',
            accountIban='IR12345678901234567890',
            bankReferenceNumber='ABC123',
            bankTransactionId='TXN123',
            timestamp='2024-02-17T12:34:56Z',
            sourceIdentifier='source01234567890123456789',
            destinationIdentifier='dest123',
            sourceIban='IR12345678901234567890',
            destinationIban='IR11345678901234567890',
            apiResponse={},
            creditAmount=50,
            debitAmount=None,
            merchantVerificationStatus=None,
            refundType=None,
            refundTrackId=None,
            createdAt='2024-02-17T12:34:56Z',
            recordType='SOME_TYPE',  # Not 'VARIZ_CARD'
        )

        statement = self.converter(dto).convert()
        self.assertIsInstance(statement, CoBankStatement)
        assert statement.amount == 50
        assert statement.tp == STATEMENT_TYPE.deposit
        assert statement.tracing_number == 'ABC123'
        assert statement.source_account == 'source0123456789012345678'
        assert len(dto.sourceIdentifier) == 26
        assert len(statement.source_account) == 25
        assert statement.source_iban == 'IR12345678901234567890'
        assert statement.source_card is None

    def test_source_card_when_record_type_is_variz_card(self):
        dto = StatementItemDTO(
            destinationAccount=123456,
            referenceNumber='REF123',
            bankReferenceNumber='ABC123',
            bankTransactionId='TXN123',
            timestamp='2024-02-17T12:34:56Z',
            sourceIdentifier='1234-5678-9012-3456',
            sourceIban='IR12345678901234567890',
            recordType='VARIZ_CARD',
            debitAmount=50,
            apiResponse={},
        )

        statement = self.converter(dto).convert()
        self.assertIsInstance(statement, CoBankStatement)
        assert statement.source_card == '1234567890123456'
