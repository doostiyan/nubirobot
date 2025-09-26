import random
from collections import defaultdict
from decimal import Decimal

from django.core.cache import cache

from django.conf import settings

from exchange.blockchain.metrics import metric_set

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
    from blockchain.parsers import parse_utc_timestamp
else:
    from exchange.base.models import Currencies
    from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class AlgorandRPC(NobitexBlockchainAPI, BlockchainUtilsMixin):
    symbol = 'ALGO'
    currency = Currencies.algo
    rate_limit = 0
    PRECISION = 6
    cache_key = 'algo'
    api_key = None
    block_tx_limit = 1000
    max_blocks_limit = 100
    transactions_limit = 25
    headers = {'content-type': 'application/json'}

    supported_requests = {
        'get_balance': 'v2/accounts/{address}',
        'get_transactions': 'v2/transactions?limit={limit}&currency-greater-than=0&address={'
                            'address}&tx-type=pay&sig-type=sig',
        'get_block_head': 'v2/transactions?limit=1',
        'get_transaction': 'v2/transactions/{tx_id}',
        'get_block': 'v2/transactions?limit=0&currency-greater-than=0&tx-type=pay&min-round={min_block}&max-round={'
                     'max_block}&sig-type=sig'
    }

    def get_balance(self, address):
        self.validate_address(address)
        response = self.request('get_balance', address=address, headers=self.headers)

        if 'message' in response.keys():
            raise APIError('algo_rpc_get_balance: error in response:' + response.get('message'))

        account_data = response.get('account', None)
        if not account_data:
            raise APIError('algo_rpc_get_balance: response is not complete')

        amount = self.from_unit(int(account_data.get('amount')))
        return {
            self.currency: {
                'symbol': self.symbol,
                'address': address,
                'amount': amount,

            }
        }

    def get_txs(self, address):
        self.validate_address(address)
        response = self.request('get_transactions', address=address, limit=self.transactions_limit,
                                headers=self.headers)

        if 'message' in response.keys():
            raise APIError('algo_rpc_get_txs: error in response:' + response.get('message'))

        transactions = response.get('transactions', None)
        block_head = response.get('current-round', None)

        if not transactions or not block_head:
            raise APIError('algo_rpc_get_txs: response is not complete')

        txs = []
        for transaction in transactions:
            confirmed_block = transaction.get('confirmed-round', None)
            if not isinstance(confirmed_block, int):
                continue

            parsed_tx = self.parse_tx(transaction, address, block_head)
            if parsed_tx:
                txs.append(parsed_tx)
        return txs

    def get_tx_details(self, tx_hash):
        response = self.request('get_transaction', tx_id=tx_hash, headers=self.headers)

        if 'message' in response.keys():
            raise APIError('algo_rpc_get_tx: error in response:' + response.get('message'))

        transaction = response.get('transaction', None)
        block_head = response.get('current-round', None)

        if not transaction or not block_head:
            raise APIError('algo_rpc_get_tx: response is not complete')

        confirmed_block = transaction.get('confirmed-round', None)
        if not isinstance(confirmed_block, int):
            raise APIError('algo_rpc_get_txs: transaction has not been confirmed yet')

        transfers = []
        is_valid = False
        if transaction.get('payment-transaction', None) is None:
            raise APIError('algo_rpc_get_tx: response is not complete')
        value = self.from_unit(int(transaction.get('payment-transaction').get('amount')))
        if transaction.get('tx-type') == 'pay' and value != Decimal(0) and transaction.get('signature').get('sig') and value >= Decimal('1'):
            is_valid = True
            transfers.append({
                'type': transaction.get('tx-type'),
                'symbol': self.symbol,
                'currency': self.currency,
                'from': transaction.get('sender'),
                'to': transaction.get('payment-transaction').get('receiver'),
                'value': value,
                'is_valid': is_valid,
            })
        return {
            'hash': transaction.get('id'),
            'is_valid': is_valid,
            'success': is_valid,
            'transfers': transfers,
            'inputs': [],
            'outputs': [],
            'block': transaction.get('confirmed-round'),
            'confirmations': block_head - transaction.get('confirmed-round'),
            'fees': self.from_unit(transaction.get('fee')),
            'date': parse_utc_timestamp(transaction.get('round-time')),
            'raw': transaction,
        }

    def parse_tx(self, tx, address, block_head):
        if tx.get('genesis-hash') != 'wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=':
            return
        if tx.get('confirmed-round') < tx.get('first-valid') or tx.get('confirmed-round') > tx.get('last-valid'):
            return
        if not tx.get('signature').get('sig'):
            return
        from_address = tx.get('sender')
        if tx.get('payment-transaction', None) is None:
            return
        to_address = tx.get('payment-transaction').get('receiver')

        value = self.from_unit(int(tx.get('payment-transaction').get('amount')))
        if value < Decimal('1'):
            return

        if (address != from_address) and (address != to_address):
            return

        direction = 'incoming'

        if from_address == to_address:
            return

        if from_address == address:
            # Transaction is from this address, so it is a withdraw
            value = -value
            direction = 'outgoing'

        return {
            self.currency: {
                'address': address,
                'hash': tx.get('id'),
                'from_address': [from_address],
                'to_address': to_address,
                'amount': value,
                'block': tx.get('confirmed-round'),
                'date': parse_utc_timestamp(tx.get('round-time')),
                'confirmations': block_head - tx.get('confirmed-round'),
                'direction': direction,
                'raw': tx,
            }
        }

    def check_block_status(self):
        response = self.request('get_block_head', headers=self.headers)

        if 'message' in response.keys():
            raise APIError('algo_rpc_get_block_head: error in response:' + response.get('message'))
        return response.get('current-round', None)

    def get_block_head(self):
        return self.check_block_status()

    def get_latest_block(self, after_block_number=None, to_block_number=None, include_inputs=False, include_info=False,
                         update_cache=True):
        if not to_block_number:
            latest_block_height_mined = self.check_block_status()
            if not latest_block_height_mined:
                raise APIError('API Not Returned block height')
        else:
            latest_block_height_mined = to_block_number

        if not after_block_number:
            latest_block_height_processed = cache.get(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}')
            if latest_block_height_processed is None:
                latest_block_height_processed = latest_block_height_mined - 5
        else:
            latest_block_height_processed = after_block_number

        if latest_block_height_mined > latest_block_height_processed:
            min_height = latest_block_height_processed + 1
        else:
            min_height = latest_block_height_mined + 1
        max_height = latest_block_height_mined + 1
        if max_height - min_height > self.max_blocks_limit:
            max_height = min_height + self.max_blocks_limit

        transactions_addresses = {'input_addresses': set(), 'output_addresses': set()}
        transactions_info = {'outgoing_txs': defaultdict(lambda: defaultdict(list)),
                             'incoming_txs': defaultdict(lambda: defaultdict(list))}
        print('Cache latest block height: {}'.format(latest_block_height_processed))

        if min_height == max_height:
            print(f'Min height {min_height} and max height {max_height} are equal!')
            return transactions_addresses, transactions_info

        response = self.request('get_block', min_block=min_height, max_block=max_height-1, headers=self.headers)
        if 'message' in response.keys():
            raise APIError('algo_rpc_get_block: error in response:' + response.get('message'))
        transactions = response.get('transactions', None)
        if not transactions:
            raise APIError('algo_rpc_get_block: response is not complete')
        for transaction in transactions:
            confirmed_block = transaction.get('confirmed-round', None)
            if not isinstance(confirmed_block, int):
                continue

            tx_hash = transaction.get('id')
            if not tx_hash:
                continue
            if transaction.get('payment-transaction', None) is None:
                continue
            from_address = transaction.get('sender')
            to_address = transaction.get('payment-transaction').get('receiver')
            value = self.from_unit(int(transaction.get('payment-transaction').get('amount')))
            currency = self.currency

            if value < Decimal('1'):
                continue

            transactions_addresses['output_addresses'].add(to_address)
            if include_inputs:
                transactions_addresses['input_addresses'].add(from_address)

            if include_info:
                if include_inputs:
                    transactions_info['outgoing_txs'][from_address][currency].append({
                        'tx_hash': tx_hash,
                        'value': value,
                    })
                transactions_info['incoming_txs'][to_address][currency].append({
                    'tx_hash': tx_hash,
                    'value': value,
                })

        if update_cache:
            metric_set(name='latest_block_processed', labels=[self.symbol.lower()], amount=max_height - 1)
            cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}',
                      max_height - 1,
                      86400)
        return transactions_addresses, transactions_info, max_height - 1


class RandLabsRPC(AlgorandRPC):
    _base_url = 'https://algoindexer.algoexplorerapi.io/'
    rate_limit = 0  # couldn't find any information over its rate limit

    def get_name(self):
        return 'rand_labs_rpc_api'


class AlgoNodeRPC(AlgorandRPC):
    _base_url = 'https://mainnet-idx.algonode.cloud/'
    rate_limit = 0.017  # 60 rps
    GET_BLOCK_ADDRESSES_MAX_NUM = 200

    def get_name(self):
        return 'node_rpc_api'


class PureStakeRPC(AlgorandRPC):
    _base_url = 'https://mainnet-algorand.api.purestake.io/idx2/'
    rate_limit = 0.1  # 10 rps

    @property
    def headers(self):
        return {'content-type': 'application/json', 'x-api-key': random.choice(settings.PURESTAKE_API_KEYS)}

    def get_name(self):
        return 'pure_stake_rpc_api'


class BloqCloudRPC(AlgorandRPC):
    _base_url = 'https://algorand.connect.bloq.cloud/indexer/'
    rate_limit = 9  # 10000 request per day
    api_key = 'hope-evil-cute' if not settings.IS_VIP else 'dove-trade-weapon'

    headers = {'content-type': 'application/json', 'x-api-key': api_key}

    def get_name(self):
        return 'bloq_cloud_rpc_api'
