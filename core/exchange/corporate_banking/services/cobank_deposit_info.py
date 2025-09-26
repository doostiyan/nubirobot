from typing import List

from django.db.models import QuerySet

from exchange.accounts.models import BankAccount, User
from exchange.corporate_banking.data_models import BluCoBankDepositInfo, CoBankDepositInfo
from exchange.corporate_banking.models import ACCOUNT_TP, NOBITEX_BANK_CHOICES, CoBankAccount, CoBankCard


def get_cobank_deposit_info(user: User) -> List[CoBankDepositInfo]:
    active_cobank_accounts = (
        CoBankAccount.objects.filter(
            provider_is_active=True, is_active=True, account_tp=ACCOUNT_TP.operational, is_deleted=False
        )
        .distinct('bank', 'account_number')
        .order_by('account_number')
    )
    banks = [bank_account.bank for bank_account in active_cobank_accounts]
    user_bank_accounts = BankAccount.objects.filter(
        user=user, bank_id__in=banks, is_deleted=False, confirmed=True
    ).order_by('id')

    blu_accounts = [acc for acc in user_bank_accounts if acc.is_blu]
    blu_deposit_info = [
        BluCoBankDepositInfo(cobank_account, blu_accounts)
        for cobank_account in active_cobank_accounts
        if cobank_account.bank == NOBITEX_BANK_CHOICES.saman
    ]

    return blu_deposit_info + [  # Non Blu accounts
        CoBankDepositInfo(
            cobank_account,
            list(
                filter(
                    lambda user_account: user_account.bank_id == cobank_account.bank and not user_account.is_blu,
                    user_bank_accounts,
                )
            ),
        )
        for cobank_account in active_cobank_accounts
    ]


def get_cobank_card_deposit_info() -> QuerySet:
    return (
        CoBankCard.objects.filter(
            provider_is_active=True,
            is_active=True,
            is_deleted=False,
            bank_account__provider_is_active=True,
            bank_account__is_active=True,
            bank_account__is_deleted=False,
            bank_account__account_tp=ACCOUNT_TP.operational,
        )
        .order_by('card_number')
        .select_related('bank_account')
    )
