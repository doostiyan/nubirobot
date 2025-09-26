from requests import Response

from exchange.base.models import Currencies
from exchange.xchange.models import MarketStatus


class MockResponse(Response):
    def __init__(self, json_data, status_code):
        super().__init__()
        self.json_data = json_data
        self.status_code = status_code

    def json(self, **kwargs):
        return self.json_data


NEAR_USDT_STATUS = {
    'baseCurrency': 'near',
    'quoteCurrency': 'usdt',
    'status': 'available',
    'minBaseAmount': 0.01,
    'maxBaseAmount': 2,
    'minQuoteAmount': 0.01,
    'maxQuoteAmount': 2,
    'basePrecision': -6,
    'quotePrecision': -2,
    'baseToQuotePriceBuy': 3.36734,
    'quoteToBasePriceBuy': 0.29697030890851533,
    'baseToQuotePriceSell': 3.2996700000000003,
    'quoteToBasePriceSell': 0.30306060909121213,
}

SOL_USDT_STATUS = {
    'baseCurrency': 'sol',
    'quoteCurrency': 'usdt',
    'status': 'available',
    'minBaseAmount': 0.01,
    'maxBaseAmount': 2,
    'minQuoteAmount': 0.01,
    'maxQuoteAmount': 2,
    'basePrecision': -6,
    'quotePrecision': -2,
    'baseToQuotePriceBuy': 102.78265,
    'quoteToBasePriceBuy': 0.009729268509811723,
    'baseToQuotePriceSell': 100.74636,
    'quoteToBasePriceSell': 0.009925916926427913,
}

XRP_USDT_STATUS = {
    'baseCurrency': 'xrp',
    'quoteCurrency': 'usdt',
    'status': 'available',
    'minBaseAmount': 0.01,
    'maxBaseAmount': 2,
    'minQuoteAmount': 0.01,
    'maxQuoteAmount': 2,
    'basePrecision': -6,
    'quotePrecision': -2,
    'baseToQuotePriceBuy': 0.575801,
    'quoteToBasePriceBuy': 1.7367111206823191,
    'baseToQuotePriceSell': 0.5642999999999999,
    'quoteToBasePriceSell': 1.7721070352649302,
}

AVAX_USDT_STATUS = {
    'baseCurrency': 'avax',
    'quoteCurrency': 'usdt',
    'status': 'available',
    'minBaseAmount': 0.01,
    'maxBaseAmount': 2,
    'minQuoteAmount': 0.01,
    'maxQuoteAmount': 2,
    'basePrecision': -6,
    'quotePrecision': -2,
    'baseToQuotePriceBuy': 36.53473,
    'quoteToBasePriceBuy': 0.027371216374118542,
    'baseToQuotePriceSell': 35.81028,
    'quoteToBasePriceSell': 0.02792494222329454,
}

BAT_USDT_STATUS = {
    'baseCurrency': 'bat',
    'quoteCurrency': 'usdt',
    'status': 'available',
    'minBaseAmount': 0.01,
    'maxBaseAmount': 2,
    'minQuoteAmount': 0.01,
    'maxQuoteAmount': 2,
    'basePrecision': -6,
    'quotePrecision': -2,
    'baseToQuotePriceBuy': 0.249571,
    'quoteToBasePriceBuy': 4.006875798870863,
    'baseToQuotePriceSell': 0.24453,
    'quoteToBasePriceSell': 4.0894777736883,
}

quote_btcusdt_sell_sample = {
    'result': {
        'quoteId': 'btcusdt-sell-a7db70bd22424eb68ce2dc0e688ffeb5',
        'baseCurrency': 'btc',
        'quoteCurrency': 'usdt',
        'clientId': '3cfbc941-c4e3-4fa8-a6e0-8d08e8f62efc',
        'creationTime': 1705494878,
        'validationTTL': 60000,
        'side': 'sell',
        'referenceCurrency': 'btc',
        'referenceCurrencyOriginalAmount': 2,
        'referenceCurrencyRealAmount': 2,
        'destinationCurrencyAmount': 100000,
    },
    'message': 'Estimate quote created successfully',
    'error': None,
    'hasError': False,
}

quote_btcusdt_buy_sample = {
    'result': {
        'quoteId': 'btcusdt-buy-a7db70bd22424eb68ce2dc0e688ffeb5',
        'baseCurrency': 'btc',
        'quoteCurrency': 'usdt',
        'clientId': '3cfbc941-c4e3-4fa8-a6e0-8d08e8f62efc',
        'creationTime': 1705494878,
        'validationTTL': 60000,
        'side': 'buy',
        'referenceCurrency': 'btc',
        'referenceCurrencyOriginalAmount': 2,
        'referenceCurrencyRealAmount': 2,
        'destinationCurrencyAmount': 100000,
    },
    'message': 'Estimate quote created successfully',
    'error': None,
    'hasError': False,
}

quote_usdtrls_buy_sample = {
    'result': {
        'quoteId': 'usdtrls-buy-a7db70bd22424eb68ce2dc0e688feee5',
        'baseCurrency': 'usdt',
        'quoteCurrency': 'rls',
        'clientId': '3cfbc941-c4e3-4fa8-a6e0-8d08e8f62efc',
        'creationTime': 1705494878,
        'validationTTL': 60000,
        'side': 'buy',
        'referenceCurrency': 'usdt',
        'referenceCurrencyOriginalAmount': 2,
        'referenceCurrencyRealAmount': 2,
        'destinationCurrencyAmount': 1400000,
    },
    'message': 'Estimate quote created successfully',
    'error': None,
    'hasError': False,
}

def get_mock_exchange_side_config():
    return {
        (Currencies.near, Currencies.usdt): MarketStatus.EXCHANGE_SIDE_CHOICES.both_side,
        (Currencies.sol, Currencies.usdt): MarketStatus.EXCHANGE_SIDE_CHOICES.buy_only,
        (Currencies.xrp, Currencies.usdt): MarketStatus.EXCHANGE_SIDE_CHOICES.sell_only,
        (Currencies.avax, Currencies.usdt): MarketStatus.EXCHANGE_SIDE_CHOICES.closed,
        (Currencies.bat, Currencies.usdt): MarketStatus.EXCHANGE_SIDE_CHOICES.closed,
    }


trades_sample = {
    'error': None,
    'hasError': False,
    'message': 'success',
    'result': {
        'converts': [
            {
                'baseCurrency': 'bnt',
                'clientId': '0e3693f075644fd08c5d3c6255705489',
                'convertId': '9c7eaab824ee4871a782b7ba1078faa5',
                'createdAt': 1744105991663,
                'destinationCurrencyAmount': '7.02',
                'quoteCurrency': 'rls',
                'quoteId': 'bntrls-buy-0157050a84ed40adb00624d92038b751',
                'referenceCurrency': 'bnt',
                'referenceCurrencyAmount': '2499363.99',
                'side': 'buy',
                'status': 'waiting',
            },
            {
                'baseCurrency': 'alpha',
                'clientId': 'efc045fa4340418fb6ff57bf1fa8cd4f',
                'convertId': '7c5d60eb37ba4198af9e04a7bf5721c2',
                'createdAt': 1744106326129,
                'destinationCurrencyAmount': '89.74',
                'quoteCurrency': 'rls',
                'quoteId': 'alpharls-buy-a127c1885a5f4bbbb8a018e6b1e6d992',
                'referenceCurrency': 'alpha',
                'referenceCurrencyAmount': '2499979.03',
                'side': 'buy',
                'status': 'waiting',
            },
        ],
        'hasNextPage': False,
    },
}
