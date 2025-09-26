import datetime
import json
import random
from decimal import Decimal

from django.conf import settings

from exchange.base.parsers import parse_iso_date
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class EOSBitqueryAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    active = True
    _base_url = 'https://graphql.bitquery.io/'
    testnet_url = 'https://graphql.bitquery.io/'
    symbol = 'EOS'
    TRANSACTION_DETAILS_BATCH = True

    supported_requests = {
        'get_tx_details': ''
    }

    queries = {
        'get_tx_details': '''
        query ($hashes: [String!], $from: ISO8601DateTime!) {
            eos {
                blocks(options: {desc: "height", limit: 1}, date: {since: $from}) {
                    height
                }
                transactions(txHash: {in: $hashes}) {
                hash
                block {
                    height
                    timestamp {
                    time(format: "%Y-%m-%dT%H:%M:%SZ")
                    }
                }
                success
                }
                transfers(txHash: {in: $hashes}) {
                txHash
                sender {
                    address
                    annotation
                }
                receiver {
                    address
                    annotation
                }
                amount
                memo
                currency {
                    symbol
                    address
                }
                  success
                external
                }
            }
        }
        '''
    }

    def get_name(self):
        return 'bitquery_api'

    def get_api_key(self):
        return random.choice(settings.BITQUERY_API_KEY)

    # this API does not return memo properly
    def get_tx_details_batch(self, tx_hashes):
        data = {
            'query': self.queries.get('get_tx_details'),
            'variables': {
                'hashes': tx_hashes,
                'from': datetime.datetime.now().strftime("%Y-%m-%d"),
            }
        }
        response = self.request('', headers={'Content-Type': 'application/json', 'X-API-KEY': self.get_api_key()},
                                body=json.dumps(data))

        if (not response) or response.get('errors'):
            raise APIError(f'EOS BITQUERY failed with getting tx details.\ntxhash:{tx_hashes}')

        txs = response.get('data').get('eos')
        if not txs:
            raise APIError(f'EOS BITQUERY failed with getting tx details.\ntxhash:{tx_hashes}')
        transactions = {}
        if not txs.get('transactions'):
            for tx in response.get('tx_hashes'):
                transactions.update({
                    tx: {
                        'hash': tx,
                        'success': False,
                        'is_valid': False,
                        'inputs': [],
                        'outputs': [],
                        'transfers': [],
                        'block': txs.get('blocks').get('height'),
                        'date': None
                    }
                })
            return transactions
        for tx in txs.get('transactions'):
            parsed_tx = self.parse_tx_details(tx)
            transactions.update(parsed_tx)
        transactions = self.parse_transfers(txs.get('transfers'), transactions)
        return transactions

    def parse_tx_details(self, transaction):
        return {
            transaction.get('hash'): {
                'hash': transaction.get('hash'),
                'success': transaction.get('success'),
                'is_valid': False,
                'inputs': [],
                'outputs': [],
                'transfers': [],
                'block': transaction.get('block').get('height'),
                'date': parse_iso_date(transaction.get('block').get('timestamp').get('time')),
            }
        }

    def parse_transfers(self, transfers, transactions):
        for transfer in transfers:
            is_valid = False
            if transfer.get('currency').get('symbol') == 'EOS' and\
               transfer.get('currency').get('address') == 'eosio.token' and\
               transfer.get('amount') > Decimal('0.0005'):
                    is_valid = True
            is_valid = is_valid and transfer.get('success')
            if is_valid:
                parsed_transfer = {
                    'symbol': transfer.get('currency').get('symbol'),
                    'from': transfer.get('sender').get('address'),
                    'to': transfer.get('receiver').get('address'),
                    'token': transfer.get('currency').get('address'),
                    'value': transfer.get('amount'),
                    'success': transfer.get('success'),
                    'is_valid': is_valid,
                }
                transactions.get(transfer.get('txHash')).get('transfers').append(parsed_transfer)
                transactions.get(transfer.get('txHash'))['is_valid'] = True
        return transactions
