from datetime import datetime, timedelta
from decimal import Decimal
from random import randint
from typing import List
from unittest.mock import patch

from dateutil.utils import today
from django.test import TestCase

from exchange.asset_backed_credit.crons import ABCDebitWeeklyInvoiceEmail
from exchange.asset_backed_credit.models import Card, Service, SettlementTransaction, UserService
from exchange.asset_backed_credit.services.debit.invoice import _get_settlement_transactions, send_debit_invoices_emails
from exchange.base.calendar import DateTimeHelper, get_start_and_end_of_jalali_week, ir_now, ir_today
from exchange.base.formatting import convert_to_persian_digits, format_money
from exchange.base.models import Currencies, Settings
from tests.asset_backed_credit.helper import ABCMixins


def create_test_settlements(
    user_service: UserService,
    num: int = 5,
    created_at: datetime = None,
    status: int = SettlementTransaction.STATUS.confirmed,
) -> List[SettlementTransaction]:
    settlements = []
    for _ in range(num):
        transaction = ABCMixins().create_settlement(Decimal(100000) * randint(1, 20), user_service)
        transaction.status = status
        transaction.remaining_rial_wallet_balance = randint(100_000, 200_0000)
        if created_at:
            transaction.created_at = created_at
        transaction.save()
        settlements.append(transaction)
    return settlements


class DebitInvoiceEmailTest(ABCMixins, TestCase):
    def setUp(self):
        self.valid_transactions_created_at = ir_now()
        self.user = self.create_user()
        self.active_debit_service = self.create_service(tp=Service.TYPES.debit)
        self.inactive_credit_service = self.create_service(tp=Service.TYPES.credit, is_active=False)

        self.user_active_debit_service = self.create_user_service(user=self.user, service=self.active_debit_service)
        self.user_active_debit_card = self.create_card(
            pan='6037731000023456', user_service=self.user_active_debit_service
        )
        self.user_inactive_active_credit_service = self.create_user_service(
            user=self.user, service=self.inactive_credit_service
        )

        self.valid_debit_transactions = create_test_settlements(
            self.user_active_debit_service,
            3,
            created_at=self.valid_transactions_created_at,
        )
        self.valid_debit_transactions.extend(
            create_test_settlements(
                self.user_active_debit_service,
                3,
                created_at=self.valid_transactions_created_at,
                status=SettlementTransaction.STATUS.unknown_confirmed,
            )
        )
        self.number_of_valid_transactions = len(self.valid_debit_transactions)

        # create some invalid transactions
        create_test_settlements(self.user_inactive_active_credit_service)
        # create some older transactions
        create_test_settlements(self.user_active_debit_service, created_at=ir_now() - timedelta(days=20))
        # create some transaction in the future
        create_test_settlements(self.user_active_debit_service, created_at=ir_now() + timedelta(days=10))

        self.from_time, self.to_time = get_start_and_end_of_jalali_week(ir_today())
        self.from_time = self.from_time.togregorian()
        self.to_time = self.to_time.togregorian()

    def test_get_settlements_transactions_returns_correct_transactions(self):
        transactions = _get_settlement_transactions(
            self.user_active_debit_service, ir_now() - timedelta(days=2), ir_now()
        )

        assert transactions.count() == self.number_of_valid_transactions
        self.assertListEqual(list(transactions), self.valid_debit_transactions)

    def test_get_settlement_transactions_success_when_having_transactions_on_different_days_of_the_week(self):
        SettlementTransaction.objects.all().delete()
        start_of_week, end_of_week = get_start_and_end_of_jalali_week(today())
        middle_of_the_week_transactions = create_test_settlements(
            self.user_active_debit_service,
            2,
            created_at=start_of_week.togregorian() + timedelta(days=2),
        )

        end_of_week_transactions = create_test_settlements(
            self.user_active_debit_service,
            3,
            created_at=end_of_week.togregorian(),
        )
        first_of_week_transactions = create_test_settlements(
            self.user_active_debit_service,
            5,
            created_at=start_of_week.togregorian(),
        )

        transactions = _get_settlement_transactions(
            self.user_active_debit_service, start_of_week.togregorian(), end_of_week.togregorian()
        )

        assert (
            list(transactions)
            == first_of_week_transactions + middle_of_the_week_transactions + end_of_week_transactions
        )

    @patch('exchange.asset_backed_credit.externals.notification.notification_provider.send_email')
    def test_send_debit_invoice_email_success(self, mock_send_email):
        send_debit_invoices_emails(self.from_time, self.to_time)

        _, mock_email_call_data = mock_send_email.call_args
        mock_send_email.assert_called_once()

        assert mock_email_call_data['to_email'] == self.user.email
        assert len(mock_email_call_data['data']['transactions']) == self.number_of_valid_transactions
        assert mock_email_call_data['template'] == 'abc/abc_debit_weekly_invoice'
        assert mock_email_call_data['data']['transactions'] is not None
        assert mock_email_call_data['data']['from_date'] is not None
        assert mock_email_call_data['data']['to_date'] is not None
        transaction_ids = [convert_to_persian_digits(str(t.id)) for t in self.valid_debit_transactions]
        for transaction in mock_email_call_data['data']['transactions']:
            assert transaction['id'] in transaction_ids

        total_transactions_amount = sum([int(t.amount) for t in self.valid_debit_transactions])
        assert mock_email_call_data['data']['total_amount'] == convert_to_persian_digits(
            format_money(total_transactions_amount, thousand_separators=True, currency=Currencies.rls)
        )

    @patch('exchange.asset_backed_credit.externals.notification.notification_provider.send_email')
    def test_send_debit_invoice_format_dates_correctly(self, mock_send_email):
        send_debit_invoices_emails(self.from_time, self.to_time)
        _, mock_email_call_data = mock_send_email.call_args
        mock_send_email.assert_called_once()

        start_of_week, end_of_week = get_start_and_end_of_jalali_week(self.valid_transactions_created_at)
        assert mock_email_call_data['data']['from_date'] == convert_to_persian_digits(
            DateTimeHelper.to_jalali_str(start_of_week, "%Y/%m/%d")
        )
        assert mock_email_call_data['data']['to_date'] == convert_to_persian_digits(
            DateTimeHelper.to_jalali_str(end_of_week, "%Y/%m/%d")
        )

    @patch('exchange.asset_backed_credit.externals.notification.notification_provider.send_email')
    @patch('exchange.asset_backed_credit.services.debit.invoice._send_card_invoices_email')
    def test_send_invoice_email_when_user_has_no_active_debit_service_then_does_not_send_any_email(
        self, mock_send_email, send_card_invoice_email
    ):
        self.active_debit_service.is_active = False
        self.active_debit_service.save()

        send_debit_invoices_emails(self.from_time, self.to_time)
        assert len(mock_send_email.mock_calls) == 0
        assert len(send_card_invoice_email.mock_calls) == 0

    @patch('exchange.asset_backed_credit.externals.notification.notification_provider.send_email')
    @patch('exchange.asset_backed_credit.services.debit.invoice._send_card_invoices_email')
    def test_send_invoice_email_when_user_has_no_active_debit_card_then_does_not_send_any_email(
        self, mock_send_email, send_card_invoice_email
    ):
        self.user_active_debit_card.status = Card.STATUS.expired
        self.user_active_debit_card.save()

        send_debit_invoices_emails(self.from_time, self.to_time)
        assert len(mock_send_email.mock_calls) == 0
        assert len(send_card_invoice_email.mock_calls) == 0

    @patch('exchange.asset_backed_credit.externals.notification.notification_provider.send_email')
    @patch('exchange.asset_backed_credit.services.debit.invoice._send_card_invoices_email')
    def test_send_invoice_email_when_user_service_is_closed_then_does_not_send_any_email(
        self, mock_send_email, send_card_invoice_email
    ):
        self.user_active_debit_service.closed_at = datetime.now()
        self.user_active_debit_service.save()

        send_debit_invoices_emails(self.from_time, self.to_time)
        assert len(mock_send_email.mock_calls) == 0
        assert len(send_card_invoice_email.mock_calls) == 0


class DebitWeeklyInvoiceEmailCronTest(TestCase, ABCMixins):
    def setUp(self):
        self.user = self.create_user()
        self.debit_service = self.create_service(tp=Service.TYPES.debit)
        self.user_service = self.create_user_service(user=self.user, service=self.debit_service)
        self.user_debit_card = self.create_card(pan='6033431000023456', user_service=self.user_service)

        self.this_week_start = get_start_and_end_of_jalali_week(ir_today())[0].togregorian()
        self.previous_week_start, self.previous_week_end = get_start_and_end_of_jalali_week(
            self.this_week_start - timedelta(days=5)
        )

        self.previous_week_transactions_confirmed = create_test_settlements(
            self.user_service,
            created_at=self.this_week_start - timedelta(4),
            status=SettlementTransaction.STATUS.confirmed,
            num=5,
        )
        self.previous_week_transactions_unknown_confirmed = create_test_settlements(
            self.user_service,
            created_at=self.this_week_start - timedelta(5),
            status=SettlementTransaction.STATUS.unknown_confirmed,
            num=5,
        )
        self.this_week_transactions_confirmed = create_test_settlements(
            self.user_service,
            created_at=self.this_week_start + timedelta(2),
            status=SettlementTransaction.STATUS.confirmed,
            num=3,
        )
        self.this_week_transactions_unknown_confirmed = create_test_settlements(
            self.user_service,
            created_at=self.this_week_start + timedelta(2),
            status=SettlementTransaction.STATUS.unknown_confirmed,
            num=3,
        )

        Settings.set('abc_enable_debit_weekly_invoice_cron', 'yes')

    @patch('exchange.asset_backed_credit.crons.send_debit_invoices_emails')
    def test_debit_cron_calls_send_function_with_previous_week_dates(self, mock_send_invoice_emails):
        ABCDebitWeeklyInvoiceEmail().run()

        mock_send_invoice_emails.assert_called_once_with(
            self.previous_week_start.togregorian(), self.previous_week_end.togregorian()
        )

    @patch('exchange.asset_backed_credit.externals.notification.notification_provider.send_email')
    def test_debit_cron_sends_previous_weeks_transactions(self, mock_send_email):
        ABCDebitWeeklyInvoiceEmail().run()

        assert mock_send_email.call_count == 1
        email_data = mock_send_email.call_args_list[0][1]
        assert len(email_data['data']['transactions']) == len(self.previous_week_transactions_confirmed) + len(
            self.previous_week_transactions_unknown_confirmed
        )
        assert email_data['data']['from_date'] == convert_to_persian_digits(
            self.previous_week_start.__format__('%Y/%m/%d')
        )
        assert email_data['data']['to_date'] == convert_to_persian_digits(self.previous_week_end.__format__('%Y/%m/%d'))

    @patch('exchange.asset_backed_credit.externals.notification.notification_provider.send_email')
    def test_when_service_is_not_active_then_no_email_is_sent(self, mock_send_email):
        self.debit_service.is_active = False
        self.debit_service.save()

        ABCDebitWeeklyInvoiceEmail().run()

        mock_send_email.assert_not_called()

    @patch('exchange.asset_backed_credit.crons.send_debit_invoices_emails')
    def test_when_flag_is_disabled_then_no_email_is_sent(self, mock_send_invoice_emails):
        Settings.set('abc_enable_debit_weekly_invoice_cron', 'no')

        ABCDebitWeeklyInvoiceEmail().run()

        mock_send_invoice_emails.assert_not_called()
