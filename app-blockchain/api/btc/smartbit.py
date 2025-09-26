from decimal import Decimal

from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


# unreliable API, better not to use
class SmartbitAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: Bitcoin
    """

    _base_url = 'https://api.smartbit.com.au'
    testnet_url = 'https://testnet-api.smartbit.com.au'
    symbol = 'BTC'

    active = True

    min_valid_tx_amount = Decimal('0.0005')
    rate_limit = 0
    max_items_per_page = 1000
    page_offset_step = None
    confirmed_num = None
    PRECISION = 8
    XPUB_SUPPORT = False

    supported_requests = {
        'get_balance': '/v1/blockchain/address/{address}',
        'get_transactions': '/v1/blockchain/address/{address}'
    }

    def get_name(self):
        return 'smartbit_api'

    def get_balance(self, addresses):
        for address in addresses:
            self.validate_address(address)
        param = ','.join(addresses)
        response = self.request('get_balance', address=param)
        if response is None:
            raise APIError("[SmartbitAPI][Get Balance] response is None")
        response_info = response['address'] if len(addresses) == 1 else response['addresses']
        if not isinstance(response_info, list):
            # if only one address is queried, a dict is returned instead of a list of dicts
            response_info = [response_info]
        balances = []
        for addr_info in response_info:
            if not addr_info:
                # API returns None for wallets with no transaction
                continue
            confirmed_info = addr_info['confirmed']
            balances.append({
                'address': addr_info['address'],
                'received': Decimal(confirmed_info['received']),
                'sent': Decimal(confirmed_info['spent']),
                'amount': Decimal(confirmed_info['balance']),
            })
        return balances

    def get_txs(self, address):
        self.validate_address(address)
        response = self.request('get_transactions', address=address)
        if response is None:
            raise APIError("[SmartbitAPI][Get Transaction] response is None")
        info = response.get('address')
        if not info:
            return []
        info = info.get('transactions') or []

        transactions = []
        for tx_info in info:
            value = Decimal('0')
            from_addresses = set()
            for txo in tx_info.get('outputs', []):
                if txo.get('addresses') != [address]:
                    continue
                value += Decimal(txo.get('value'))

            for txo in tx_info.get('inputs', []):
                from_addresses.update(txo.get('addresses'))
                if txo.get('addresses') == [address]:
                    value -= Decimal(txo.get('value'))

            if value <= Decimal('0'):
                continue
            transactions.append({
                'address': address,
                'from_address': from_addresses,
                'hash': tx_info.get('txid'),
                'date': parse_utc_timestamp(tx_info['time']),
                'amount': value,
                'confirmations': int(tx_info.get('confirmations', 0)),
                'is_double_spend': bool(tx_info.get('double_spend')),
                'raw': tx_info,
            })
        return transactions
