from decimal import Decimal
import datetime

from django.conf import settings

from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class BtcAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: Bitcoin
    """

    _base_url = 'https://chain.api.btc.com'
    testnet_url = 'https://tchain.api.btc.com'
    symbol = 'BTC'

    active = True

    rate_limit = 0
    max_items_per_page = 1000
    page_offset_step = None
    confirmed_num = None
    PRECISION = 8
    XPUB_SUPPORT = False
    USE_PROXY = True

    headers = {
            'User-Agent': 'Mozilla/5.0' if not settings.IS_VIP else
            'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0'
        }

    supported_requests = {
        'get_balances': '/v3/address/{addresses}',
        'get_transactions': '/v3/address/{address}/tx?verbose=1',
        'get_tx_details': '/v3/tx/{tx_hash}?verbose=3',
    }

    def get_name(self):
        return 'btc_api'

    def get_balances(self, addresses):
        for address in addresses:
            self.validate_address(address)
        joined_addresses = ','.join(addresses)

        response = self.request('get_balances', addresses=joined_addresses,  headers=self.headers)
        if response is None:
            raise APIError("[BtcAPI][Get Balances] response is None")
        if response['status'] != 'success':
            raise APIError("[BtcAPI][Get Balances] request is unsuccessful")
        data = response['data']
        if not isinstance(data, list):
            # if only one address is queried, a dict is returned instead of a list of dicts
            data = [data]
        balances = []
        for balance in data:
            if not balance:
                # API returns None for wallets with no transaction
                continue
            addr = balance['address']
            received = Decimal(balance['received']) / Decimal('1e8') - Decimal(
                balance['unconfirmed_received']) / Decimal('1e8')
            sent = Decimal(balance['sent']) / Decimal('1e8') - Decimal(balance['unconfirmed_sent']) / Decimal('1e8')
            balances.append({
                'address': addr,
                'received': received,
                'sent': sent,
                'amount': received - sent,
            })
        return balances

    def get_txs(self, address):
        response = self.request('get_transactions', address=address, headers=self.headers)
        if response is None:
            raise APIError("[BtcAPI][Get Balances] response is None")
        if response['status'] != 'success':
            raise APIError("[BtcAPI][Get Balances] request is unsuccessful")

        info = response.get('data')
        if not info:
            return []
        info = info.get('list') or []

        transactions = []
        for tx_info in info:
            tx_timestamp = max(int(tx_info.get('created_at', 0)), int(tx_info.get('block_time', 0)))
            transactions.append({
                'hash': tx_info.get('hash'),
                'date': parse_utc_timestamp(tx_timestamp),
                'amount': Decimal(str(round(tx_info.get('balance_diff', 0)))) / Decimal('1e8'),
                'confirmations': int(tx_info.get('confirmations', 0)),
                'is_double_spend': bool(tx_info.get('is_double_spend')),
                'raw': tx_info,
            })
        return transactions

    def get_tx_details(self, tx_hash):
        try:
            response = self.request('get_tx_details', tx_hash=tx_hash)
        except:
            raise APIError("[BTC chain.api.btc API][Get Transaction details] unsuccessful")

        tx = self.parse_tx_details(response, tx_hash)
        return tx

    def parse_tx_details(self, tx_info, tx_hash):
        confirmations = tx_info.get('data').get('confirmations')
        timestamp = datetime.datetime.fromtimestamp(tx_info.get('data').get('block_time'))
        block = tx_info.get('data').get('block_height')
        inputs = []
        outputs = []
        for input in tx_info.get('data').get('inputs'):
            inputs.append({
                'address': input.get('prev_addresses')[0],
                'value': self.from_unit(input.get('prev_value')),
                'type': input.get('prev_type'),
            })
        for output in tx_info.get('data').get('outputs'):
            outputs.append({
                'address': output.get('addresses')[0],
                'value': self.from_unit(output.get('value')),
                'type': output.get('type'),
            })

        return {
            'hash': tx_hash,
            'success': tx_info.get('status') == 'success',
            'is_coinbase':  tx_info.get('data').get('is_coinbase'),
            'inputs': inputs,
            'outputs': outputs,
            'transfers': tx_info.get('data').get('transfers'), # No transfers in this api
            'block': block,
            'confirmations': confirmations,
            'fees': self.from_unit(tx_info.get('data').get('fee')),
            'date': timestamp,
            'raw': tx_info,
        }
