import random
from decimal import Decimal

from django.conf import settings

from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class EtcCryptoAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
        coins: EthereumClassic
        API docs: https://docs.cryptoapis.io/
        :exception ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut
        """

    active = True
    _base_url = 'https://api.cryptoapis.io/v1/bc/etc/mainnet'
    testnet_url = 'https://api.cryptoapis.io/v1/bc/etc/mordor'
    symbol = 'ETC'
    rate_limit = 0.34
    PRECISION = 18
    max_items_per_page = 20  # 20 for get_txs
    page_offset_step = None
    confirmed_num = None

    api_key_header = {'X-API-Key': f'{random.choice(settings.CRYPTOAPIS_API_KEYS)}'}

    supported_requests = {
        'get_transactions': '/address/{address}/transactions',
        'get_balance': '/address/{address}',
    }

    def get_name(self):
        return 'cryptoapis_api'

    def get_balance(self, address):
        """ Get ETC account balance
            Ratelimit: 500 request per day & 3 request per sec
        """
        self.validate_address(address)
        response = self.request('get_balance', address=address)
        if not response:
            raise APIError("[EtcCryptoAPI][Get Transactions] response is None")
        info = response.get('payload')
        if info.get('address') != address:
            return
        if settings.IS_PROD and info.get('chain') != 'ETC.mainnet':
            return
        balance = info.get('balance')
        if not balance:
            return
        balance = Decimal(balance)
        return {
            'address': address,
            'amount': balance,
        }

    def get_txs(self, address, offset=None, limit=15, unconfirmed=False):
        """ The free plan is discontinued, not used anymore """
        self.validate_address(address)
        response = self.request('get_transactions', address=address, limit=limit)
        if not response:
            raise APIError("[EtcCryptoAPI][Get Transactions] response is None")
        txs = response.get('payload')
        if not txs:
            return []

        transactions = []
        for tx in txs:
            raw_value = Decimal(tx.get('value')) / Decimal(1e18)
            if tx.get('from').lower() == address.lower():
                value = -raw_value
            elif tx.get('to').lower() == address.lower():
                value = raw_value
            else:
                value = Decimal('0')
            transactions.append({
                'address': address,
                'hash': tx.get('hash'),
                'date': parse_utc_timestamp(tx.get('date')),
                'amount': value,
                'confirmations': tx.get('confirmations'),
                'block': tx.get('block'),
                'raw': tx,
            })
        return transactions
