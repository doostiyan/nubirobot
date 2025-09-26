import json
import math
import random
from collections import defaultdict
from decimal import Decimal
from typing import List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache

from exchange.base.models import Currencies
from exchange.base.parsers import parse_timestamp
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.metrics import metric_set
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


class SolanaRpcAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: Solana
    """

    symbol = 'SOL'
    cache_key = 'sol'
    PRECISION = 9
    currency = Currencies.sol
    rate_limit = 0.1  # 10 request per second

    max_block_in_single_request = 1
    get_txs_limit = 1
    max_blocks_limit = 160
    get_balance_limit = 100
    headers = {'content-type': 'application/json'}

    minimum_sol_in_transactions = 0.001

    SUPPORT_GET_BALANCE_BATCH = True
    MINIMUM_REQUIRED_ACCOUNTS_COUNT = 3

    def __init__(self, network: str = 'mainnet', api_key: Optional[str] = None) -> None:
        super().__init__(network, api_key)

    def get_name(self) -> str:
        return 'rpc_api'

    def get_balances(self, addresses: List[str]) -> List[dict]:
        addresses = list(set(addresses))
        if len(addresses) > self.get_balance_limit:
            raise APIError('[SolanaRpcAPI][get_balance_batch] Number of addresses are more than the limit')
        data = {'jsonrpc': '2.0',
                'id': 1,
                'method': 'getMultipleAccounts',
                'params': [addresses]
                }
        response = self.request('', body=json.dumps(data))
        if not response:
            raise APIError('[SolanaRpcAPI][get_balance_batch] response is None')
        if 'result' not in response:
            raise APIError('[SolanaRpcAPI][get_balance_batch] response without result')
        accounts_information = response.get('result').get('value')
        accounts_balances = []
        for address, account_information in zip(addresses, accounts_information):
            amount = 0 if account_information is None else account_information.get('lamports', None)
            if amount is None:
                continue
            amount = self.from_unit(amount)
            account_balance = {
                self.currency: {
                    'amount': amount,
                    'unconfirmed_amount': Decimal(0),
                    'address': address
                }
            }
            accounts_balances.append(account_balance)

        return accounts_balances

    def get_balance(self, address: str) -> dict:
        data = {'jsonrpc': '2.0',
                'id': 1,
                'method': 'getBalance',
                'params': [address]
                }

        response = self.request('', body=json.dumps(data))
        if not response:
            raise APIError('[SolanaRpcAPI][Get Balance] response is None')
        if 'result' not in response:
            raise APIError('[SolanaRpcAPI][Get Balance] response without result')
        amount = self.from_unit(response.get('result').get('value'))
        return {
            self.currency: {
                'amount': amount,
                'unconfirmed_amount': Decimal(0),
                'address': address
            }
        }

    def check_block_status(self) -> int:
        data = {'jsonrpc': '2.0',
                'id': 1,
                'method': 'getEpochInfo',
                }

        response = self.request('', body=json.dumps(data))
        if not response:
            raise APIError('[SolanaRpcAPI][Get Block Head] response is None')
        if 'result' not in response:
            raise APIError('[SolanaRpcAPI][Get Block Head] response without result')

        return int(response.get('result').get('absoluteSlot'))

    def get_block_head(self) -> int:
        return self.check_block_status()

    def get_txs(self, address: str) -> List[dict]:
        get_txs_hash_data = {
            'jsonrpc': '2.0',
            'id': 0,
            'method': 'getSignaturesForAddress',
            'params': [
                address,
                {
                    'limit': self.get_txs_limit,
                    'commitment': 'finalized'
                }
            ]
        }
        hashes = self.request('', body=json.dumps(get_txs_hash_data))
        if not hashes:
            raise APIError('[SolanaRpcAPI][GetTxs] Response is None.')
        if hashes.get('result') is None:
            raise APIError('[SolanaRpcAPI][GetTxs] Response is not complete.')

        if len(hashes.get('result')) == 0:
            return []

        txs_hash = []
        for tx_sig in hashes.get('result'):
            if tx_sig.get('err') is not None:
                continue
            txs_hash.append(tx_sig['signature'])

        batch_data = []

        index = 1
        for tx_hash in txs_hash:
            get_tx_detail_data = {
                'jsonrpc': '2.0',
                'id': index,
                'method': 'getTransaction',
                'params': [
                    tx_hash,
                    {
                        'encoding': 'jsonParsed',
                        'maxSupportedTransactionVersion': 0,
                    }
                ]
            }
            index += 1
            batch_data.append(get_tx_detail_data)

        txs_details = self.request('', body=json.dumps(batch_data))
        if not txs_details:
            raise APIError('[SolanaRpcAPI][GetTxs] Response is None.')

        transfers = []
        block_head = self.check_block_status()
        for tx in txs_details:
            if 'result' not in tx:
                continue
            tx_result = tx['result']

            if tx_result.get('meta').get('err') or tx_result.get('meta').get('status').get(
                    'Err') or 'Ok' not in tx_result.get(
                'meta').get('status'):
                continue
            if not tx_result.get('transaction').get('signatures'):
                continue

            tx_hash = tx_result.get('transaction').get('signatures')[0]
            date = parse_timestamp(tx_result.get('blockTime'))
            block = tx_result.get('slot')
            confirmation = block_head - block
            for transfer in tx_result.get('transaction').get('message').get('instructions'):
                direction = 'incoming'

                if (not transfer.get('parsed')
                        or transfer.get('program') != 'system'
                        or transfer.get('programId') != '11111111111111111111111111111111'
                        or transfer.get('parsed').get('type') not in ['transfer', 'transferChecked']):
                    continue
                transfer_info = transfer.get('parsed').get('info')
                from_address = transfer_info.get('source')
                to_address = transfer_info.get('destination')
                value = self.from_unit(transfer_info.get('lamports'))

                if from_address == to_address:
                    continue
                if address == from_address:
                    value = - value
                    direction = 'outgoing'
                elif address != to_address:
                    continue

                transfers.append({
                    'block': block,
                    'date': date,
                    'confirmations': confirmation,
                    'hash': tx_hash,
                    'from_address': from_address,
                    'to_address': to_address,
                    'amount': value,
                    'direction': direction,
                    'raw': tx_result
                })
        return transfers

    def get_latest_block(self, after_block_number: Optional[int] = None, to_block_number: Optional[int] = None,
                         include_inputs: bool = False, include_info: bool = False,
                         update_cache: bool = True) -> Tuple[dict, dict, int]:
        if not to_block_number:
            latest_block_height_mined = self.check_block_status() - 120
            if not latest_block_height_mined:
                raise APIError('API Not Returned block height')
        else:
            latest_block_height_mined = to_block_number

        if not after_block_number:
            latest_block_height_processed = cache.get(
                f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}')
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

        # input_addresses ~ outgoing_txs and output_addresses ~ incoming_txs
        transactions_addresses = {'input_addresses': set(), 'output_addresses': set()}
        transactions_info = {'outgoing_txs': defaultdict(lambda: defaultdict(list)),
                             'incoming_txs': defaultdict(lambda: defaultdict(list))}

        data = {'jsonrpc': '2.0',
                'id': 2,
                'method': 'getBlocks',
                'params': [min_height, max_height - 1]
                }
        response = self.request('', body=json.dumps(data))
        blocks = response.get('result', None)

        if blocks is None or len(blocks) == 0:
            raise APIError('[SolanaRpcAPI][get blocks] response without result')
        number_of_blocks = len(blocks)

        request_numbers = int(math.ceil(number_of_blocks / self.max_block_in_single_request))

        for i in range(request_numbers):
            block_index = i * self.max_block_in_single_request
            data = []
            for j in range(self.max_block_in_single_request):
                data.append({'jsonrpc': '2.0',
                             'id': j + 3,
                             'method': 'getBlock',
                             'params': [
                                 blocks[block_index],
                                 {'encoding': 'jsonParsed',
                                  'transactionDetails': 'accounts',
                                  'rewards': False,
                                  'maxSupportedTransactionVersion': 0
                                  }
                             ]})

                block_index += 1
                if block_index >= number_of_blocks:
                    break
            response = self.request('', body=json.dumps(data), timeout=50)
            if not response:
                raise APIError('[SolanaRpcAPI][Get Block] response is None')

            for block in response:
                if type(block) is str:
                    raise APIError('[SolanaRpcAPI][get blocks] response format is not right')
                if block.get('error'):
                    continue
                if block.get('result', None) is None:
                    continue
                if block.get('result').get('transactions', None) is None:
                    continue

                for tx in block.get('result').get('transactions'):
                    if tx.get('meta').get('err') or tx.get('meta').get('status').get('Err') or 'Ok' not in tx.get(
                            'meta').get('status'):
                        continue
                    if not tx.get('transaction').get('signatures'):
                        continue

                    if (not tx.get('transaction').get('accountKeys')
                            or len(tx.get('transaction').get('accountKeys')) != self.MINIMUM_REQUIRED_ACCOUNTS_COUNT):
                        continue

                    if tx.get('transaction').get('accountKeys')[2].get('pubkey') != '11111111111111111111111111111111':
                        continue
                    tx_hash = tx.get('transaction').get('signatures')[0]
                    from_address = tx.get('transaction').get('accountKeys')[0].get('pubkey')
                    to_address = tx.get('transaction').get('accountKeys')[1].get('pubkey')
                    post_balances = tx.get('meta').get('postBalances')
                    pre_balances = tx.get('meta').get('preBalances')
                    value = self.from_unit(post_balances[1] - pre_balances[1])

                    if from_address == to_address:
                        continue
                    if float(value) < self.minimum_sol_in_transactions:
                        continue

                    transactions_addresses['output_addresses'].add(to_address)
                    if include_inputs:
                        transactions_addresses['input_addresses'].add(from_address)

                    if include_info:
                        transactions_info['incoming_txs'][to_address][self.currency].append({
                            'tx_hash': tx_hash,
                            'value': value,
                        })
                        if include_inputs:
                            check_for_duplication = \
                                [tx for tx in transactions_info['outgoing_txs'][from_address][self.currency]
                                 if tx['tx_hash'] == tx_hash]
                            if check_for_duplication:
                                index = (transactions_info['outgoing_txs'][from_address][self.currency]
                                         .index(check_for_duplication[0]))
                                transactions_info['outgoing_txs'][from_address][self.currency][index]['value'] += value
                            else:
                                transactions_info['outgoing_txs'][from_address][self.currency].append({
                                    'tx_hash': tx_hash,
                                    'value': value,
                                })

        if update_cache:
            metric_set(name='latest_block_processed', labels=[self.symbol.lower()], amount=max_height - 1)
            cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}',
                      max_height - 1, 86400)
        return transactions_addresses, transactions_info, max_height - 1

    def get_tx_details(self, tx_hash: str) -> dict:
        response = self.request('', body=self.get_details_body(tx_hash), headers=self.headers)
        if not response:
            raise APIError('[RpcSolanaAPi][GetTxDetails] Response is None')
        if 'result' not in response:
            raise APIError('[][] Response without result')
        return self.parse_tx_details(response.get('result'))

    def parse_tx_details(self, tx: dict, _: Optional[str] = None) -> dict:
        block_head = self.get_block_head()
        if self.validate_transaction(tx):
            transfers = []
            for transfer in tx.get('transaction').get('message').get('instructions'):
                if self.validate_transfer(transfer):
                    transfers.append({
                        'hash': tx.get('transaction').get('signatures')[0],
                        'from_address': transfer.get('parsed').get('info').get('source'),
                        'to_address': transfer.get('parsed').get('info').get('destination'),
                        'amount': self.from_unit(transfer.get('parsed').get('info').get('lamports')),
                        'is_valid': True,
                        'raw': tx
                    })

            return {
                'hash': tx.get('transaction').get('signatures')[0],
                'success': True,
                'inputs': [],
                'outputs': [],
                'transfers': transfers,
                'block': tx.get('slot'),
                'confirmations': block_head - tx.get('slot'),
                'fees': tx.get('meta').get('fee'),
                'date': parse_timestamp(tx.get('blockTime')),
            }

        return {'success': False}

    def validate_transaction(self, tx: dict, _: Optional[str] = None) -> bool:
        if (tx.get('meta').get('err')
                or tx.get('meta').get('status').get('Err')
                or 'Ok' not in tx.get('meta').get('status')
                or not tx.get('transaction').get('signatures')):
            return False
        return True

    @classmethod
    def validate_transfer(cls, transfer: dict) -> bool:
        if (not transfer.get('parsed')
                or transfer.get('program') != 'system'
                or transfer.get('programId') != '11111111111111111111111111111111'
                or transfer.get('parsed').get('type') not in ['transfer', 'transferChecked']):
            return False
        return True

    def get_details_body(self, tx_hash: str) -> str:
        data = {
            'jsonrpc': '2.0',
            'id': 0,
            'method': 'getTransaction',
            'params': [
                tx_hash,
                {
                    'encoding': 'jsonParsed',
                    'maxSupportedTransactionVersion': 0,
                }
            ]
        }
        return json.dumps(data)


class SerumRPC(SolanaRpcAPI):
    _base_url = 'https://solana-api.projectserum.com'
    max_block_in_single_request = 9
    get_txs_limit = 25
    rate_limit = 0.1

    def get_name(self) -> str:
        return 'serum_api'


class AnkrRPC(SolanaRpcAPI):
    _base_url = 'https://solana.public-rpc.com'
    max_block_in_single_request = 10
    get_txs_limit = 20
    rate_limit = 0.05
    USE_PROXY = bool(not settings.IS_VIP)

    def get_name(self) -> str:
        return 'ankr_api'


class QuickNodeRPC(SolanaRpcAPI):
    # the api key should only be available in production
    _base_url = settings.SOLANA_QUICK_NODE_URLS if not settings.IS_VIP else ''
    max_block_in_single_request = 50  # it can be more, but we won't increase it for decreasing pressure on explorer
    get_txs_limit = 15
    rate_limit = 0.04

    def get_name(self) -> str:
        return 'quicknode_api'


class AlchemyRPC(SolanaRpcAPI):
    _base_url = random.choice(settings.SOLANA_ALCHEMY_URLS) if not settings.IS_VIP else ''
    max_block_in_single_request = 7
    get_txs_limit = 15
    rate_limit = 0

    def get_name(self) -> str:
        return 'alchemy_api'


class ShadowRPC(SolanaRpcAPI):
    _base_url = 'https://ssc-dao.genesysgo.net/'
    max_block_in_single_request = 30
    get_txs_limit = 25
    rate_limit = 0.005

    def get_name(self) -> str:
        return 'shadow_api'


class MainRPC(SolanaRpcAPI):
    _base_url = 'https://api.mainnet-beta.solana.com'
    # alternatively use https://explorer-api.mainnet-beta.solana.com but usually it doesn't work
    max_block_in_single_request = 1
    get_txs_limit = 1
    rate_limit = 0.1

    def get_name(self) -> str:
        return 'main_rpc_api'
