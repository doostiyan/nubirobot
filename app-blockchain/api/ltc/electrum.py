from decimal import Decimal

from exchange.base.connections import get_electrum_ltc
from exchange.base.logging import log_event, report_exception
from exchange.base.models import Currencies
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.utils import BlockchainUtilsMixin


class ElectrumAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):

    symbol = 'LTC'
    currency = Currencies.ltc
    PRECISION = 8
    cache_key = 'ltc'

    def get_balance(self, address):
        try:
            electrum = get_electrum_ltc()
        except Exception as e:
            return
        try:
            res = electrum.request('getaddressbalance', params={'address': address})
        except Exception as e:
            return None
        error = res.get('error')
        result = res.get('result')
        if error or not result:
            return None
        balance = Decimal(result['confirmed'])
        return ({
            'address': address,
            'received': balance,
            'sent': Decimal('0'),
            'balance': balance,
            'unconfirmed': Decimal(result['unconfirmed']),
        })
