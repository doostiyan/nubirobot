from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache

from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI


class BinanceAPI(NobitexBlockchainBlockAPI, BlockchainUtilsMixin):
    """
    Binance API explorer.

    API docs: https://docs.binance.org/api-swagger/
    Explorer: https://explorer.binance.org/
    """

    rate_limit = 1

    currency = Currencies.bnb
    symbol = 'BNB'
    PRECISION = 8
    cache_key = 'bnb'

    # _base_url = 'https://dex-atlantic.binance.org'
    # _base_url = 'https://dex-asiapacific.binance.org'
    _base_url = 'https://dex-european.binance.org'
    testnet_url = 'https://testnet-dex.binance.org'

    supported_requests = {
        'get_balance': '/api/v1/account/{address}',
        'get_txs': '/api/v1/transactions?address={address}&limit={limit}&txType=TRANSFER&offset=0',
        'get_block_head': '/api/v1/node-info',
        'get_tx_details': '/api/v1/tx/{tx_hash}?format=json',
        'get_block': '/api/v1/transactions-in-block/{block}'
    }

    def get_name(self):
        return 'binance_api'

    def get_balance(self, address):
        self.validate_address(address=address)
        response = self.request('get_balance', address=address, with_rate_limit=True)
        if not response:
            raise APIError('DEX Binance Api error, Could not get balance of this address.')
        balances = response.get('balances', [])
        bnb_item = list(filter(lambda item: item.get('symbol') == 'BNB', balances))  # just bnb balance matters
        amount = Decimal(bnb_item[0].get('free')) if bnb_item else Decimal('0')

        return {
            self.currency: {
                'symbol': self.symbol,
                'amount': amount,
                'unconfirmed_amount': Decimal(0),
                'address': address,
            }
        }

    def get_tx_details(self, tx_hash):
        response = self.request('get_tx_details', tx_hash=tx_hash)
        if not response:
            raise APIError('Response is none')
        tx = self.parse_tx_details(response)
        return tx

    def parse_tx_details(self, tx):
        transfers = []
        inputs = []
        outputs = []
        tx_info = tx.get('tx', {}).get('value', {}).get('msg')[0]
        if tx_info.get('type') == 'cosmos-sdk/Send':
            outputs_ = tx_info.get('value').get('outputs')
            for output in outputs_:
                if output.get('coins')[0].get('denom') == 'BNB':
                    outputs.append({
                        'address': output.get('address'),
                        'value': self.from_unit(int(output.get('coins')[0].get('amount'))),
                        'denom': output.get('coins')[0].get('denom'),
                        'currency': Currencies.bnb,
                        'is_valid': True
                    })

        return {
            'hash': tx.get('hash'),
            'success': tx.get('ok') and tx.get('code') == 0,
            'is_valid': True if outputs and tx.get('ok') else False,
            'inputs': inputs,
            'outputs': outputs,
            'transfers': transfers,
            'memo': tx.get('tx').get('value').get('memo') or '',
            'block': tx.get('height'),
            'confirmations': 0,
            'raw': tx,
        }

    def get_txs(self, address, offset=None, limit=100, unconfirmed=False, tx_direction_filter=''):
        self.validate_address(address=address)
        response = self.request('get_txs', address=address, limit=limit, with_rate_limit=True)
        if not response:
            raise APIError('DEX Binance Api error, Could not get transactions of this address.')
        transactions = response.get('tx', [])
        txs = []
        for tx_info in transactions[:limit]:
            if self.validate_transaction(tx_info, address):
                parsed_tx = self.parse_tx(tx_info, address)
                if not parsed_tx:
                    continue
                txs.append(parsed_tx)
        return txs

    def parse_tx(self, tx_info, address):
        raw_value = Decimal(tx_info.get('value'))
        if tx_info.get('fromAddr') == address:
            value = -raw_value
        elif tx_info.get('toAddr') == address:
            value = raw_value
        else:
            value = Decimal('0')
        return {
            self.currency: {
                'date': parse_iso_date(tx_info.get('timeStamp')),
                'from_address': [tx_info.get('fromAddr')],
                'to_address': tx_info.get('toAddr'),
                'amount': value,
                'block': tx_info.get('blockHeight'),
                'fee': Decimal(tx_info.get('txFee')),
                'hash': tx_info.get('txHash'),
                'confirmations': int(tx_info.get('confirmBlocks')),
                'memo': tx_info.get('memo'),
                'raw': tx_info,
            }
        }

    def validate_transaction(self, tx, address=None):
        if tx.get('txType') != 'TRANSFER':
            return False
        if tx.get('code') != 0:
            return False
        if tx.get('txAsset') != 'BNB':
            return False
        if tx.get('toAddr') == address and tx.get('fromAddr') == address:
            return False
        raw_value = Decimal(tx.get('value'))
        if raw_value <= Decimal('0'):
            return False
        return True

    def check_block_status(self):
        response = self.request('get_block_head', with_rate_limit=True)
        if not response:
            raise APIError('DEX Binance Api error, Could not get head block number.')
        block_number = self.parse_block_status(response)
        if not block_number:
            raise APIError('DEX Binance Api error, Could not get head block number.')
        return block_number

    @staticmethod
    def parse_block_status(data):
        return data.get('sync_info', {}).get('latest_block_height')

    def get_block_head(self):
        return self.check_block_status()

    def get_latest_block(self, after_block_number=None, to_block_number=None, include_inputs=False, include_info=False):
        if not to_block_number:
            latest_block_height_mined = self.check_block_status()
            if not latest_block_height_mined:
                raise APIError('DEX Binance Api error, API doesnt return block height')
        else:
            latest_block_height_mined = to_block_number

        cache_key = f'latest_block_height_processed_{self.cache_key}'

        if not after_block_number:
            latest_block_height_processed = cache.get(cache_key)
            if latest_block_height_processed is None:
                latest_block_height_processed = latest_block_height_mined - 5
        else:
            latest_block_height_processed = after_block_number

        if latest_block_height_mined > latest_block_height_processed:
            min_height = latest_block_height_processed + 1
        else:
            min_height = latest_block_height_mined + 1
        max_height = latest_block_height_mined + 1
        max_height = min(max_height, min_height + 100)

        transactions_addresses = set()
        transactions_info = defaultdict(lambda: defaultdict(list))
        print('Cache latest block height: {}'.format(latest_block_height_processed))
        for block_height in range(min_height, max_height):
            response = self.request('get_block', block=block_height, with_rate_limit=True)
            if not response:
                raise APIError('Get block API returns empty response')

            txs = response.get('tx', [])
            for tx in txs:
                if tx.get('txType') != 'TRANSFER':
                    continue
                tx_hash = tx.get('txHash')
                from_address = tx.get('fromAddr')
                to_address = tx.get('toAddr')
                value = Decimal(tx.get('value'))

                transactions_addresses.update([to_address])
                if include_inputs:
                    transactions_addresses.update([from_address])

                if include_info:
                    if include_inputs:
                        transactions_info[from_address][self.currency].append({
                            'tx_hash': tx_hash,
                            'value': value,
                            'direction': 'outgoing',
                        })
                    transactions_info[to_address][self.currency].append({
                        'tx_hash': tx_hash,
                        'value': value,
                        'direction': 'incoming',
                    })
        cache.set(cache_key, max_height - 1, 86400)
        return set(transactions_addresses), transactions_info, max_height - 1
