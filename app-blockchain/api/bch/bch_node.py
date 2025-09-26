from decimal import Decimal

from exchange.base.connections import get_electron_cash
from exchange.base.models import Currencies
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.utils import BlockchainUtilsMixin


class BchElectronNode(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
        github: https://github.com/Electron-Cash/Electron-Cash
    """

    symbol = 'BCH'
    PRECISION = 8
    currency = Currencies.bch
    cache_key = 'bch'

    def get_balance(self, address):
        try:
            electron = get_electron_cash()
        except Exception as e:
            print('ElectronCash Connection Error: {}'.format(str(e)))
            # report_event('ElectronCash Connection Error')
            return None
        try:
            res = electron.request('getaddressbalance', params=[address])
        except Exception as e:
            raise Exception(f'Failed to get BCH wallet balance from ElectronCash, Error:{e}')
        error = res.get('error')
        result = res.get('result')
        if error or not result:
            raise Exception('ElectronCash Get Balance Response Error')
        balance = Decimal(result['confirmed'])
        if balance is None:
            return None
        return {
            'address': address,
            'received': balance,
            'sent': Decimal('0'),
            'balance': balance,
            'unconfirmed': Decimal(result['unconfirmed']),
        }
