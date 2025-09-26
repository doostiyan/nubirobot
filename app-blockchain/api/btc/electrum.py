from decimal import Decimal

from exchange.base.connections import get_electrum
from exchange.base.models import Currencies
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.utils import BlockchainUtilsMixin


class BtcElectrum(NobitexBlockchainAPI, BlockchainUtilsMixin):
    symbol = 'BTC'
    PRECISION = 8
    currency = Currencies.btc
    cache_key = 'btc'

    def get_balance(self, address):
        try:
            electrum = get_electrum()
        except Exception as e:
            # report_event('Electrum Connection Error')
            return
        try:
            res = electrum.request('getaddressbalance', params={'address': address})
        except Exception as e:
            metric_incr('api_errors_count', labels=['btc', 'electrum'])
            msg = f'Failed to get BTC wallet balance from Electrum: {str(e)}'
            print(msg)
            return None
        error = res.get('error')
        result = res.get('result')
        if error or not result:
            print('Failed to get BTC wallet balance from Electrum: {}'.format(str(res)))
            # report_event('Electrum Response Error')
            return None
        balance = Decimal(result['confirmed'])
        return {
            'address': address,
            'received': balance,
            'sent': Decimal('0'),
            'balance': balance,
            'unconfirmed': Decimal(result['unconfirmed']),
        }
