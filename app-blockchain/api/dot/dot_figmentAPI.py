import json
import random

from django.conf import settings

from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.dot.dot_figmentRPC import DotFigmentRPC
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError, ParseError
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI


class DotFigmentAPI(NobitexBlockchainBlockAPI, BlockchainUtilsMixin):
    """
    Subscan API explorer.

    supported coins: dot
    API docs: https://docs.figment.io/network-documentation/polkadot/enriched-apis/transaction-search
    Explorer: https://polkadot.api.subscan.io
    """

    _base_url = 'https://polkadot--search.datahub.figment.io'
    testnet_url = 'https://polkadot-westend--search.datahub.figment.io'
    symbol = 'DOT'
    currency = Currencies.dot
    active = True
    rate_limit = 1.15  # 3m request per month, 10 request per second, 10 concurrent request
    PRECISION = 10
    cache_key = 'dot'

    supported_requests = {
        'get_tx_details': '/transactions_search',
    }

    def get_name(self):
        return 'figment_api'

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.DOT_FIGMENT_API_KEY)

    def get_header(self):
        return {
            'Authorization': self.get_api_key(),
        }

    @staticmethod
    def get_block_head():
        return DotFigmentRPC().get_block_head()

    def get_tx_details(self, tx_hash):
        try:
            payload = {
                'network': 'polkadot',
                'hash': tx_hash
            }
            response = self.request('get_tx_details', headers=self.get_header(), body=json.dumps(payload))
        except ConnectionError:
            raise APIError(f'{self.symbol} API: Failed to get_tx_details, connection error')
        if not response:
            raise APIError(f'{self.symbol}: get_tx_detail Response is none')
        tx_details = self.parse_tx_details(response[0])
        return tx_details

    def parse_tx_details(self, tx):
        success = False
        transfers = []
        try:
            block_head = self.get_block_head()
            tx_hash = tx.get('hash')
            block_height = tx.get('height')
            sub_events = tx.get('events')[0].get('sub')
            for event in sub_events:
                if event.get('type')[0] == 'extrinsicsuccess':
                    success = True
                if self.validate_transaction(event):
                    sender = event.get('sender')[0].get('account').get('id')
                    receiver = event.get('recipient')[0].get('account').get('id')
                    amount = event.get('recipient')[0].get('amounts')[0].get('numeric')
                    transfers.append({
                        'currency': self.currency,
                        'from': sender,
                        'to': receiver,
                        'value': self.from_unit(amount),
                        'is_valid': True
                    })
        except AttributeError:
            raise ParseError(f'Dot parse tx details error, Tx: {tx}.')
        return {
            'hash': tx_hash,
            'success': success and not tx.get('has_errors'),
            'inputs': [],
            'outputs': [],
            'transfers': transfers,
            'block': block_height,
            'confirmations': block_head - block_height,
            'fees': self.from_unit(int(tx.get('transaction_fee')[0].get('numeric'))),
            'date': parse_iso_date(tx.get('time')),
        }

    @staticmethod
    def validate_transaction(event):
        if event.get('module') != 'balances' or event.get('type')[0] != 'transfer':
            return False
        if event.get('sender')[0].get('amounts')[0].get('currency') != 'DOT':
            return False
        sender_amount = event.get('sender')[0].get('amounts')[0].get('numeric')
        reciever_amount = event.get('recipient')[0].get('amounts')[0].get('numeric')
        if sender_amount != reciever_amount:
            return False
        return True

    def get_latest_block(self):
        pass
