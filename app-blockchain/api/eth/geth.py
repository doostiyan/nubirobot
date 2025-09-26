from decimal import Decimal

from exchange.base.connections import get_geth
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


class GethAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):

    symbol = 'ETH'
    PRECISION = 18

    def get_balance(self, address_list):
        try:
            geth = get_geth()
        except Exception as e:
            # report_event('Geth Connection Error')
            return
        balances = []
        for addr in address_list:
            try:
                res = geth.request('eth_getBalance', [addr, 'latest'])
            except Exception as e:
                # report_event('Geth API Error')
                continue
            error = res.get('error')
            result = res.get('result')
            if error or not result:
                # report_event('Geth Response Error')
                continue
            balance = int(result, 0) / Decimal('1e18')
            balance = balance.quantize(Decimal('1e-8'))
            balances.append({
                'address': addr,
                'received': balance,
                'sent': Decimal('0'),
                'rewarded': Decimal('0'),
                'balance': balance,
            })
        return balances


