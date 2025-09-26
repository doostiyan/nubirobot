from django.conf import settings
from django.core.cache import cache

from exchange.base.models import get_currency_codename_binance
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.utils import APIError


class BinancePublicAPI(NobitexBlockchainAPI):
    """
    Binance Public API.

    supported requests:
        get_all_coins_info
    """

    _base_url = 'https://www.binance.com/bapi/capital/v1/public/capital'
    headers = {'accept-encoding': 'gzip'}

    USE_PROXY = True if not settings.IS_VIP else False

    supported_requests = {
        'get_all_coins_info': '/getNetworkCoinAll?lang=en&ignoreDex={ignore_dex}',
    }

    def get_all_coins_info(self, ignore_dex=True):

        response = self.request('get_all_coins_info', ignore_dex=ignore_dex, headers=self.headers)

        if response is None:
            raise APIError(f'[{self.__class__.__name__}][Get Coins Info] response is None')

        return response

    def get_all_coins_info_dict(self):
        all_coins_info = self.get_all_coins_info()['data']
        all_coins_info_dict = {}
        for coin_info in all_coins_info:
            all_coins_info_dict[coin_info['coin'].lower()] = coin_info
        return all_coins_info_dict

    def get_available_coins_info(self, available_currencies=None):
        if available_currencies is None:
            from exchange.base.models import ALL_CRYPTO_CURRENCIES, Currencies
            # exclude pmn from available_currencies
            available_currencies = ALL_CRYPTO_CURRENCIES
        all_coin_info = self.get_all_coins_info_dict()
        currencies_keys = [
            (get_currency_codename_binance(currency, ignore_logical_changes=False), currency) for currency in available_currencies
        ]
        # PMN is not supported by binance so exclude them in conditional statement
        return {(k, c): all_coin_info[k] for k, c in currencies_keys if k in all_coin_info}



