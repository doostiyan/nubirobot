import datetime
import json
import random
from collections import defaultdict
from decimal import Decimal

import pytz
from django.conf import settings
from django.core.cache import cache

from exchange.base.models import Currencies
from exchange.blockchain.metrics import metric_set
from exchange.blockchain.ss58 import is_valid_ss58_address, ss58_encode
from exchange.blockchain.staking.staking_models import StakingInfo
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError, ValidationError
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI


class SubscanAPI(NobitexBlockchainBlockAPI, BlockchainUtilsMixin):
    """
    Subscan API explorer.

    supported coins: dot
    API docs: https://docs.api.subscan.io/
    Explorer: https://polkadot.api.subscan.io
    """

    _base_url = 'https://polkadot.api.subscan.io'
    testnet_url = 'https://westend.api.subscan.io/'
    symbol = 'DOT'
    currency = Currencies.dot
    active = True
    rate_limit = 0.2
    PRECISION = 10
    cache_key = 'dot'
    max_items_per_page = 100
    USE_PROXY = True
    timeout = 60

    supported_requests = {
        'get_balance': '/api/open/account',
        'get_staking_data': '/api/v2/scan/search',
        'get_txs': '/api/scan/transfers',
        'get_status': '/api/scan/metadata',
        'get_block': '/api/scan/block',
        'get_tx': '/api/scan/extrinsic',
    }

    def get_name(self):
        return 'subscan_api'

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.SUBSCAN_API_KEY)

    @property
    def headers(self):
        return {'Content-Type': 'application/json', 'x-api-key': self.get_api_key()}

    def validate_address(self, address):
        address_format = 0 if self.network == 'mainnet' else 42
        if not is_valid_ss58_address(address, valid_ss58_format=address_format):
            raise ValidationError('Address not valid')

    def pub_key_to_address(self, pub_key):
        address_format = 0 if self.network == 'mainnet' else 42
        return ss58_encode(pub_key, ss58_format=address_format)

    def get_staking_info(self, address):
        data = {
            'key': address,
        }
        response = self.request('get_staking_data', headers=self.headers, body=json.dumps(data))
        if not response:
            raise APIError('[SubscanAPI][GetStakingInfo] Response is None.')
        if response.get('message') != 'Success':
            raise APIError(f'[SubscanAPI][GetStakingInfo] Unsuccessful:{response.get("message")}')

        try:
            account_data = (response.get('data') or {}).get('account')
        except AttributeError:
            raise APIError(f'[SubscanAPI][GetStakingInfo] Account data is None')
        parsed_data = self.parse_staking_info(account_data)
        return parsed_data

    def parse_staking_info(self, data):
        return StakingInfo(
            staked_balance=Decimal(data.get('balance_lock')),
            total_balance=Decimal(data.get('balance')),
            free_balance=Decimal(data.get('balance')) - Decimal(data.get('balance_lock')),
            delegated_balance=self.from_unit(int(data.get('bonded'))),
        )

    def get_tx_details(self, tx_hash):
        data = {
            'hash': tx_hash,
        }
        response = self.request('get_tx', headers=self.headers, body=json.dumps(data))
        if not response:
            raise APIError('[SubscanAPI][GetTransactionDetails] Response is None.')
        if response.get('message') != 'Success':
            raise APIError('[SubscanAPI][GetTransactionDetails] Unsuccessful.')
        parsed_tx = self.parse_tx_details(response.get('data'))
        return parsed_tx

    def parse_tx_details(self, tx):
        inputs = []
        outputs = []
        transfers = []
        block_head = int(self.check_block_status().get('blockNum'))
        if tx.get('params'):
            transfers.append({
                'currency': self.currency,
                'to': self.pub_key_to_address(tx.get('params')[0].get('value').get('Id')),
                'from': tx.get('account_id'),
                'value': self.from_unit(int(tx.get('params')[1].get('value'))),
            })
        return {
            'hash': tx.get('extrinsic_hash'),
            'success': tx.get('success'),
            'inputs': inputs,
            'outputs': outputs,
            'transfers': transfers,
            'block': tx.get('block_num'),
            'confirmations': block_head - tx.get('block_num'),
            'fees': self.from_unit(int(tx.get('fee'))),
            'date': datetime.datetime.fromtimestamp(tx.get('block_timestamp'), pytz.utc),
        }

    def get_balance(self, address):
        self.validate_address(address)
        data = {
            'address': address,
        }
        response = self.request('get_balance', headers=self.headers, body=json.dumps(data))
        if not response:
            raise APIError('[SubscanAPI][GetBalance] Response is None.')
        if response.get('message') != 'Success':
            raise APIError('[SubscanAPI][GetBalance] Unsuccessful.')
        balances = {
            self.currency: {
                'symbol': self.symbol,
                'balance': Decimal(response.get('data').get('balance')),
                'unconfirmed_balance': Decimal('0'),
                'address': address,
                'lock': Decimal(response.get('data').get('lock')),
            }
        }
        return balances

    def get_txs(self, address, limit=25, offset=0):
        self.validate_address(address)
        limit = min(limit, self.max_items_per_page)  # because limit can't be greater than 100
        transactions = []
        data = {
            'row': limit,
            'page': offset,
            'address': address,
        }
        response = self.request('get_txs', headers=self.headers, body=json.dumps(data))
        if not response:
            raise APIError('[SubscanAPI][GetTxs] Response is None.')
        if response.get('message') != 'Success':
            raise APIError(f'[SubscanAPI][GetBalance] Unsuccessful:{response.get("message")}')
        txs = response.get('data').get('transfers')
        if not txs:
            return []
        block_head = int(self.check_block_status().get('blockNum'))
        for tx in txs:
            if not tx.get('success'):
                continue
            value = Decimal(tx.get('amount'))
            if tx.get('from') == address:
                value = - value
            elif tx.get('to') != address:
                continue
            transactions.append({
                'address': address,
                'from_address': tx.get('from'),
                'block': tx.get('block_num'),
                'hash': tx.get('hash'),
                'date': datetime.datetime.fromtimestamp(tx.get('block_timestamp'), pytz.utc),
                'amount': value,
                'confirmations': block_head - tx.get('block_num'),
                'raw': tx,
            })
        return transactions

    def check_block_status(self):
        info = self.request('get_status', headers=self.headers, force_post=True)
        if not info:
            raise APIError('Empty info')
        if info.get('message') != 'Success':
            raise APIError('Unsuccessful')
        return info.get('data')

    def get_block_head(self):
        info = self.check_block_status()
        return int(info.get('blockNum'))

    def get_latest_block(self, after_block_number=None, to_block_number=None, include_inputs=False, include_info=False):
        info = self.check_block_status()
        if not to_block_number:
            latest_block_height_mined = int(info.get('blockNum'))
            if not latest_block_height_mined:
                raise APIError('API Not Return block height')
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
        max_height = min(max_height, min_height + 10)

        transactions_addresses = {'input_addresses': set(), 'output_addresses': set()}
        transactions_info = {'outgoing_txs': defaultdict(lambda: defaultdict(list)),
                             'incoming_txs': defaultdict(lambda: defaultdict(list))}
        print('Cache latest block height: {}'.format(latest_block_height_processed))
        for block_height in range(min_height, max_height):
            data = {
                'block_num': block_height
            }
            response = self.request('get_block', headers=self.headers, body=json.dumps(data), timeout=60)
            if not response:
                raise APIError('Get block API returns empty response')
            if response.get('message') != 'Success':
                raise APIError(f'Get block API error: {response.get("message")}')

            events = (response.get('data') or {}).get('events')
            if not events:
                continue

            for event in events:
                if event.get('module_id') != 'balances' or event.get('event_id') != 'Transfer':
                    continue

                event_info = json.loads(event.get('params'))
                try:
                    from_address = self.pub_key_to_address(event_info[0].get('value'))
                    to_address = self.pub_key_to_address(event_info[1].get('value'))
                except Exception as e:
                    continue
                tx_hash = event.get('extrinsic_hash')
                value = self.from_unit(int(event_info[2].get('value')))

                transactions_addresses['output_addresses'].add(to_address)
                if include_inputs:
                    transactions_addresses['input_addresses'].add(from_address)
                if include_info:
                    transactions_info['incoming_txs'][to_address][self.currency].append({
                        'tx_hash': tx_hash,
                        'value': value,
                    })
                    if include_inputs:
                        # this may be confusing but the logic is simple: to aggregate values when hash is the same
                        # like 0x24f0f12d781258afad2e67f07e01f5e327772d7fe6f1525387bb39bc9a1111a5 which has two
                        # transfers and causes duplication without this check.
                        check_for_duplication = [tx for tx in
                                                 transactions_info['outgoing_txs'][from_address][self.currency] if
                                                 tx['tx_hash'] == tx_hash]
                        if check_for_duplication:
                            index = transactions_info['outgoing_txs'][from_address][self.currency].index(
                                check_for_duplication[0])
                            transactions_info['outgoing_txs'][from_address][self.currency][index]['value'] += value
                        else:
                            transactions_info['outgoing_txs'][from_address][self.currency].append({
                                'tx_hash': tx_hash,
                                'value': value,
                            })

        metric_set(name='latest_block_processed', labels=[self.symbol.lower()], amount=max_height - 1)
        cache.set(cache_key, max_height - 1, 86400)
        return transactions_addresses, transactions_info, max_height - 1
