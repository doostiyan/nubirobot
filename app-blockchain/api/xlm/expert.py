from decimal import Decimal

from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class ExpertAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
        coins: Stellar
        API docs: https://refractor.stellar.expert/openapi.html
        Explorer: Full Node
        :exception ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut
        """

    active = True

    currency: str = None
    rate_limit = 0
    PRECISION = 7
    max_items_per_page = 20  # 20 for get_txs
    page_offset_step = None
    confirmed_num = None

    supported_requests = {
        'get_payments': '/account/{address}/history/payments?order=desc&limit={limit}',
    }

    def get_name(self):
        return 'expert_api'

    def get_txs(self, address, offset=0, limit=20, tx_type='normal', unconfirmed=False, tx_direction_filter=''):
        self.validate_address(address)
        response = self.request('get_payments', address=address, limit=limit)
        if not response:
            raise APIError("[ExpertApi][Get Transactions] response is None")
        txs = response.get('_embedded', {}).get('records')
        if not txs:
            return []
        transactions = []
        for tx in txs:
            parsed_tx = self.parse_tx(tx, address)
            if parsed_tx:
                transactions.append(parsed_tx)
        return transactions

    def parse_tx(self, tx, address=None):
        if tx.get('assets') != ['XLM']:
            return
        if tx.get('type') != 1:
            return
        accounts = tx.get('accounts')
        if not accounts or len(accounts) != 2:
            return
        if address and (accounts[0] == address or accounts[1] != address):
            return

        value = Decimal(tx.get('amount'))
        if not value or value <= 0:
            return

        tx_memo = tx.get('memo') or ''

        return {
            'symbol': self.currency,
            'from_address': [accounts[0]],
            'date': parse_utc_timestamp(tx.get('ts')),
            'amount': value,
            # Note: This is not the actual hash (stellar has id and hash that makes things a little complicated)
            'hash': tx.get('tx'),
            'memo': tx_memo,
            'confirmations': 1,
            'confirmed': None,
            'kind': 'transaction',
            'raw': tx,
        }


class XlmExpertAPI(ExpertAPI):
    _base_url = 'https://api.stellar.expert/explorer/public'
    testnet_url = 'https://api.stellar.expert/explorer/testnet'
    symbol = 'XLM'
    currency = 'XLM'
    PRECISION = 7
