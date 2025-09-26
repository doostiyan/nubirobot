import json
import math
from collections import defaultdict
from decimal import Decimal
from typing import List, Optional, Tuple

from django.conf import settings
from django.core.cache import cache

from exchange.base.models import Currencies
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.metrics import metric_set
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


class SolanaGetBlockAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: Solana
    """

    _base_url = 'https://sol.getblock.io/mainnet/'
    symbol = 'SOL'
    cache_key = 'sol'
    PRECISION = 9
    currency = Currencies.sol
    x_api_key = 'e473c695-0fb9-4886-b816-8c74a82d20d7' if settings.IS_VIP else ''
    rate_limit = 2  # 0.5 request per second

    SUPPORT_GET_BALANCE_BATCH = True

    max_number_of_addresses_in_normal_request = 100

    max_number_of_requests_in_single_batch_request = 10

    # we can send batch of 10 requests that each one of them can get balance of 100 accounts,so we can get 1000 accounts
    # in 1 request
    get_balance_limit = max_number_of_addresses_in_normal_request * max_number_of_requests_in_single_batch_request

    def get_name(self) -> str:
        return 'get_block_api'

    def get_api_key(self) -> str:
        return self.x_api_key

    def get_balances(self, addresses: List[str]) -> List[dict]:

        if len(addresses) > (self.max_number_of_addresses_in_normal_request
                             * self.max_number_of_requests_in_single_batch_request):
            raise APIError('[SolanaRpcAPI][get_balance_batch] Number of addresses are more than the limit')
        data_list = []
        for i in range(int(math.ceil(len(addresses) / self.max_number_of_addresses_in_normal_request))):
            start_position = i * self.max_number_of_addresses_in_normal_request
            end_position = min(start_position + self.max_number_of_addresses_in_normal_request, len(addresses))
            addresses_slice = addresses[start_position:end_position]
            data = {'jsonrpc': '2.0',
                    'id': 1,
                    'method': 'getMultipleAccounts',
                    'params': [addresses_slice]
                    }
            data_list.append(data)
        headers = {'content-type': 'application/json', 'x-api-key': self.get_api_key()}
        response = self.request('', body=json.dumps(data_list), headers=headers)
        if not response:
            raise APIError('[SolanaRpcAPI][get_balance_batch] response is None')
        accounts_balances = []
        for resp in response:
            if 'result' not in resp:
                raise APIError('[SolanaRpcAPI][get_balance_batch] response without result')
            accounts_information = resp.get('result').get('value')

            for address, account_information in zip(addresses, accounts_information):
                if account_information is None:
                    continue
                amount = account_information.get('lamports', None)
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

        headers = {'content-type': 'application/json', 'x-api-key': self.get_api_key()}
        response = self.request('', body=json.dumps(data), headers=headers)
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

        headers = {'content-type': 'application/json', 'x-api-key': self.get_api_key()}
        response = self.request('', body=json.dumps(data), headers=headers)
        if not response:
            raise APIError('[SolanaRpcAPI][Get Block Head] response is None')
        if 'result' not in response:
            raise APIError('[SolanaRpcAPI][Get Block Head] response without result')

        return response.get('result').get('absoluteSlot')

    def get_block_head(self) -> int:
        return self.check_block_status()

    def get_latest_block(self, after_block_number: Optional[int] = None, to_block_number: Optional[int] = None,
                         include_inputs: bool = False, include_info: bool = False, update_cache: bool = True) -> Tuple[
        dict, dict, int]:
        if not to_block_number:
            latest_block_height_mined = self.check_block_status()
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

        if max_height - min_height > 100: # noqa: PLR2004
            max_height = min_height + 100

        # input_addresses ~ outgoing_txs and output_addresses ~ incoming_txs
        transactions_addresses = {'input_addresses': set(), 'output_addresses': set()}
        transactions_info = {'outgoing_txs': defaultdict(lambda: defaultdict(list)),
                             'incoming_txs': defaultdict(lambda: defaultdict(list))}
        for block_height in range(min_height, max_height):

            transactions = self.get_block_txs(block_height)
            for tx in transactions:
                if tx.get('meta').get('err') or tx.get('meta').get('status').get('Err') or 'Ok' not in tx.get(
                        'meta').get('status'):
                    continue
                if not tx.get('transaction').get('signatures'):
                    continue

                tx_hash = tx.get('transaction').get('signatures')[0]
                for transfer in tx.get('transaction').get('message').get('instructions'):

                    if not transfer.get('parsed') or transfer.get('program') != 'system' or transfer.get(
                            'programId') != '11111111111111111111111111111111' or transfer.get('parsed').get(
                        'type') not in ['transfer', 'transferChecked']:
                        continue
                    transfer_info = transfer.get('parsed').get('info')
                    from_address = transfer_info.get('source')
                    to_address = transfer_info.get('destination')
                    value = self.from_unit(transfer_info.get('lamports'))

                    transactions_addresses['output_addresses'].add(to_address)
                    if include_inputs:
                        transactions_addresses['input_addresses'].add(from_address)

                    if include_info:
                        if include_inputs:
                            transactions_info['outgoing_txs'][from_address][self.currency].append({
                                'tx_hash': tx_hash,
                                'value': value,
                            })
                        transactions_info['incoming_txs'][to_address][self.currency].append({
                            'tx_hash': tx_hash,
                            'value': value,
                        })
        if update_cache:
            metric_set(name='latest_block_processed', labels=[self.symbol.lower()], amount=max_height - 1)
            cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}',
                      max_height - 1, 86400)
        return transactions_addresses, transactions_info, max_height - 1

    def get_block_txs(self, block_height: int) -> List[dict]:
        data = {'jsonrpc': '2.0',
                'id': 1,
                'method': 'getBlock',
                'params': [
                    block_height,
                    {'encoding': 'jsonParsed', 'transactionDetails': 'full', 'rewards': False}
                ]}

        headers = {'content-type': 'application/json', 'x-api-key': self.get_api_key()}
        response = self.request('', body=json.dumps(data), headers=headers)
        if not response:
            raise APIError('[SolanaRpcAPI][Get Block] response is None')
        if 'result' not in response:
            raise APIError('[SolanaRpcAPI][Get Block] response without result')

        return response.get('result').get('transactions')
