from datetime import datetime
from decimal import Decimal

from django.db.models import QuerySet

from exchange.asset_backed_credit.externals.notification import notification_provider
from exchange.asset_backed_credit.models import Card, Service, SettlementTransaction, UserService
from exchange.base.calendar import DateTimeHelper, to_shamsi_date
from exchange.base.decorators import measure_time_cm
from exchange.base.formatting import convert_to_persian_digits, format_money
from exchange.base.models import Currencies


@measure_time_cm(metric='abc_debit_invoice')
def send_debit_invoices_emails(transaction_start_time: datetime, transaction_end_time: datetime):
    debit_cards = Card.objects.filter(
        status=Card.STATUS.activated,
        user_service__service__tp=Service.TYPES.debit,
        user_service__closed_at__isnull=True,
        user_service__service__is_active=True,
    ).select_related('user_service', 'user')
    for card in debit_cards:
        _send_card_invoices_email(card, transaction_start_time, transaction_end_time)


@measure_time_cm(metric='abc_debit_invoice_email')
def _send_card_invoices_email(card: Card, transactions_start_date: datetime, transactions_end_date: datetime):
    transactions = _get_settlement_transactions(
        user_service=card.user_service, start_date=transactions_start_date, end_date=transactions_end_date
    )
    if transactions.count() == 0:
        return

    start_date_str_formatted = convert_to_persian_digits(
        DateTimeHelper.to_jalali_str(transactions_start_date, "%Y/%m/%d")
    )
    end_date_str_formatted = convert_to_persian_digits(
        DateTimeHelper.to_jalali_str(transactions_end_date, "%Y/%m/%d")
    )

    data = _get_transactions_email_data(transactions)
    data['from_date'] = start_date_str_formatted
    data['to_date'] = end_date_str_formatted
    notification_provider.send_email(
        to_email=card.user.email,
        template='abc/abc_debit_weekly_invoice',
        data=data,
    )


def _get_settlement_transactions(
    user_service: UserService, start_date: datetime, end_date: datetime
) -> QuerySet[SettlementTransaction]:
    return SettlementTransaction.objects.filter(
        user_service=user_service,
        created_at__gte=start_date,
        created_at__lte=end_date,
        status__in=[SettlementTransaction.STATUS.confirmed, SettlementTransaction.STATUS.unknown_confirmed],
        remaining_rial_wallet_balance__isnull=False,
    ).order_by('created_at', 'pk')


def _get_transactions_email_data(user_settlements_transactions: QuerySet[SettlementTransaction]) -> dict:
    total_amount = 0
    transactions = []
    for i, transaction in enumerate(user_settlements_transactions, start=1):
        total_amount += transaction.amount
        created_at = convert_to_persian_digits(to_shamsi_date(transaction.created_at, format_="%Y/%m/%d - %H:%M"))
        amount = convert_to_persian_digits(
            format_money(transaction.amount, thousand_separators=True, currency=Currencies.rls)
        )
        remaining_amount = convert_to_persian_digits(
            format_money(
                Decimal(transaction.remaining_rial_wallet_balance), thousand_separators=True, currency=Currencies.rls
            ),
        )
        index = convert_to_persian_digits(str(i))
        trx_id = convert_to_persian_digits(str(transaction.id))

        transactions.append(
            {
                'index': index,
                'created_at': created_at,
                'amount': amount,
                'remaining_amount': remaining_amount,
                'id': trx_id,
            }
        )

    total_amount = convert_to_persian_digits(
        format_money(total_amount, thousand_separators=True, currency=Currencies.rls)
    )
    return {'transactions': transactions, 'total_amount': total_amount}
