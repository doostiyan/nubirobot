from dataclasses import dataclass
from typing import List

from exchange.accounts.models import BankAccount
from exchange.corporate_banking.models.bank_account import CoBankAccount


@dataclass
class CoBankDepositInfo:
    bank: str
    cobank_account_number: str
    cobank_owner: str
    user_accounts: List[dict]

    def __init__(self, cobank_account: CoBankAccount, user_bank_account: List[BankAccount]):
        self.bank = cobank_account.get_bank_display()
        self.cobank_account_number = cobank_account.account_number
        self.cobank_owner = cobank_account.account_owner
        self.user_accounts = [
            {
                'accountNumber': (
                    user_account.account_number
                    if user_account.account_number != '0' and user_account.account_number != ''
                    else None
                ),
                'iban': user_account.shaba_number,
            }
            for user_account in user_bank_account
        ]


@dataclass
class BluCoBankDepositInfo(CoBankDepositInfo):
    def __init__(self, cobank_account: CoBankAccount, user_bank_account: List[BankAccount]):
        super().__init__(cobank_account, user_bank_account)
        self.cobank_account_number = cobank_account.iban
