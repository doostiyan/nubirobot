from decimal import Decimal

from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class CoinexplorerAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: Doge
    API Doc: https://www.coinexplorer.net/BITG/api-ref
    """

    _base_url = 'https://www.coinexplorer.net'
    symbol = 'DOGE'

    active = True

    rate_limit = 0
    max_items_per_page = 1000
    page_offset_step = None
    confirmed_num = None
    PRECISION = 8
    XPUB_SUPPORT = False

    supported_requests = {
        'get_transactions': '/api/v1/{symbol}/address/transactions?address={address}',
    }

    def get_name(self):
        return 'coinexplorer_api'

    def get_txs(self, address):
        self.validate_address(address)
        response = self.request('get_transactions', address=address, symbol=self.symbol)
        if response.get('success') == 'false':
            raise APIError("[CoinexplorerAPI][Get Transactions] unsuccessful")
        transactions = []
        for tx in response.get('result'):
            transactions.append({
                'hash': tx.get('txid'),
                'date': tx.get('time'),
                'amount': Decimal(tx.get('change')),
                'raw': tx,
            })

        return transactions
