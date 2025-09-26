import re

from exchange.accounts.models import User
from exchange.base.models import TAG_NEEDED_CURRENCIES
from exchange.recovery.models import RecoveryRequest
from exchange.wallet.models import (
    AvailableDepositAddress,
    ConfirmedWalletDeposit,
    ManualDepositRequest,
    WalletDepositAddress,
)



def validate_alphanumeric(name: str) -> bool:
    """
        Validate that the name contains only English letters and numbers
    """
    regex_pattern = r'^[a-zA-Z0-9]+$'
    return bool(re.fullmatch(regex_pattern, name))


def validate_user_deposit_address(user: User, address: str) -> bool:
    """
        Validate deposit_address of user.
    """
    if WalletDepositAddress.objects.filter(address=address, wallet__user=user).exists() or \
        AvailableDepositAddress.objects.filter(
            address=address,
            currency__in=TAG_NEEDED_CURRENCIES,
            ).exists():
        return True
    return False


def validate_return_address(address: str) -> bool:
    """
        Validate return_address of user.
    """
    regex_pattern = r'^[a-zA-Z0-9\-_\.]+$'
    if not bool(re.fullmatch(regex_pattern, address)):
        return False
    if (
        WalletDepositAddress.objects.filter(address=address).exists()
        or AvailableDepositAddress.objects.filter(
            address=address,
            currency__in=TAG_NEEDED_CURRENCIES,
        ).exists()
    ):
        return False
    return True


def is_duplicate_tx_hash(tx_hash: str) -> bool:
    """
         Validates whether a transaction hash (`tx_hash`) is associated with any active recovery requests,
         confirmed deposits, or pending manual deposit requests.
     """
    recovery_exists = RecoveryRequest.objects.filter(
        deposit_hash=tx_hash).exclude(
        status__in=[RecoveryRequest.STATUS.rejected,
                    RecoveryRequest.STATUS.canceled,
                    ]).exists()
    confirmed_deposit_exists = ConfirmedWalletDeposit.objects.filter(
        tx_hash=tx_hash
    ).exists()
    manual_deposit_exists = ManualDepositRequest.objects.filter(
        tx_hash=tx_hash
    ).exclude(
        status=ManualDepositRequest.STATUS.rejected
    ).exists()
    return recovery_exists or manual_deposit_exists or confirmed_deposit_exists
