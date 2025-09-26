from django.conf import settings
from django.db.models import Q

from exchange.wallet.deposit import update_address_balances_for_currency
from exchange.wallet.models import AvailableHotWalletAddress, SystemColdAddress


class BalanceChecker:
    @classmethod
    def update_system_wallets_balance(cls):
        """ Update balances for all system cold & hot wallet addresses
        """
        for wallet in AvailableHotWalletAddress.get_outdated_queryset()[:100]:
            update_address_balances_for_currency([wallet])
        for wallet in SystemColdAddress.get_outdated_queryset().filter(is_disabled=False)[:100]:
            update_address_balances_for_currency([wallet])
