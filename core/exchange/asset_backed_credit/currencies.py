from typing import List

from exchange.asset_backed_credit.models.wallet import Wallet
from exchange.base.models import CREDIT_CURRENCIES, DEBIT_CURRENCIES, Currencies, Settings

ABC_CREDIT_CURRENCIES = {
    currency: {'order': index, 'is_active': True} for index, currency in enumerate(CREDIT_CURRENCIES)
}
ABC_DEBIT_CURRENCIES = {
    currency: {'order': index, 'is_active': True} for index, currency in enumerate(DEBIT_CURRENCIES)
}


class ABCCurrencies:
    @staticmethod
    def get_active_currencies(wallet_type: int = Wallet.WalletType.COLLATERAL) -> List[int]:
        """
        Retrieve a list of activated currencies from cache.

        Returns:
            list: A list of enum currencies retrieved from the cache or the default list.
        """
        currencies = ABCCurrencies._get_currencies_by_wallet_type(wallet_type)
        return [
            int(key)
            for key, value in sorted(currencies.items(), key=lambda item: item[1]['order'])
            if value['is_active']
        ]

    @staticmethod
    def _get_currencies_by_wallet_type(wallet_type: int):
        if wallet_type == Wallet.WalletType.COLLATERAL:
            currencies = Settings.get_cached_json('abc_currencies', ABC_CREDIT_CURRENCIES)
        elif wallet_type == Wallet.WalletType.DEBIT:
            currencies = Settings.get_cached_json('abc_debit_currencies', ABC_DEBIT_CURRENCIES)
        else:
            raise ValueError('invalid wallet type')
        return currencies

    @staticmethod
    def get_all_currencies(wallet_type: int = Wallet.WalletType.COLLATERAL) -> List[int]:
        """
        Retrieve a list of ABC currencies from cache.

        Returns:
            list: A list of enum currencies retrieved from the cache or the default list.
        """
        currencies = ABCCurrencies._get_currencies_by_wallet_type(wallet_type)
        return [int(key) for key, _ in sorted(currencies.items(), key=lambda x: x[1]['order'])]

    @staticmethod
    def get_internal_wallet_api_currencies() -> List[int]:
        all_currencies = ABCCurrencies.get_all_currencies()
        if Currencies.rls not in all_currencies:
            all_currencies.append(Currencies.rls)
        return all_currencies
