import json
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.core.cache import cache

from exchange.base.models import Currencies
from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.common_apis.blockscan import are_addresses_equal
from exchange.blockchain.api.ftm.ftm_ftmscan import FtmScanAPI
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI
from exchange.blockchain.contracts_conf import opera_ftm_contract_currency, opera_ftm_contract_info
from exchange.blockchain.metrics import metric_set
from exchange.blockchain.staking.staking_models import StakingInfo
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


class FantomGraphQlAPI(NobitexBlockchainBlockAPI, BlockchainUtilsMixin):
    """
    Fantom GraphQl API explorer.

    supported coins: FTM

    API docs: https://docs.fantom.foundation/api/graphql-schema-basics
    Explorer: https://explorer.fantom.network/
    """

    _base_url = 'https://xapi.fantom.network/'
    testnet_url = ''
    symbol = 'FTM'
    currency = Currencies.ftm
    USE_PROXY = False

    PRECISION = 18
    cache_key = 'ftm'

    queries = {
        'get_staking_info': """
            query AccountByAddress($address: Address!) {
                account(address: $address) {
                    address
                    balance
                    totalValue
                    txCount
                    delegations {
                        totalCount
                        edges {
                            delegation {
                                createdTime
                                amountDelegated
                                lockedUntil
                                createdTime
                                claimedReward
                                pendingRewards {
                                    amount
                                }
                            }
                            cursor
                        }
                    }
                }
            }
        """
    }

    def get_name(self) -> str:
        return 'graphql_api'

    @property
    def contract_currency_list(self) ->  Dict[str, int]:
        return opera_ftm_contract_currency.get(self.network)

    @property
    def contract_info_list(self) -> Dict[int, Dict[str, Union[str, int]]]:
        return opera_ftm_contract_info.get(self.network)

    def get_balance(self, address: str) -> Dict[str, Any]:
        query = """
            query getAddressBalance ($address: Address!) {
                account (address: $address) {
                    address
                    balance
                    totalValue
                }
            }
        """
        data = {
            'query': query,
            'variables': {
                'address': address
            }
        }

        response = self.request('', headers={'Content-Type': 'application/json'}, body=json.dumps(data))

        if not response:
            raise APIError('[FantomGraphQLAPI][GetBalance] Response is None.')
        if response.get('errors'):
            raise APIError('[FantomGraphQLAPI][GetBalance] Unsuccessful.')

        balance = response.get('data').get('account').get('balance')

        return {
            'address': address,
            'balance': self.from_unit(int(balance, 16))
        }

    def get_txs(self, address: str, limit: int = 60) -> List[Dict[str, Any]]:
        query = """
            query getAddressTransactions ($address: Address!, $limit: Int!) {
                account (address: $address) {
                    txCount
                    txList (count: $limit) {
                        edges {
                            cursor
                            transaction {
                                hash
                                status
                                from
                                to
                                value
                                nonce
                                index
                                inputData
                                blockNumber
                                block {
                                    timestamp
                                }
                            }
                        }
                    }
                }
            }
        """
        data = {
            'query': query,
            'variables': {
                'address': address,
                'limit': limit,
            }
        }
        response = self.request('', headers={'Content-Type': 'application/json'}, body=json.dumps(data))
        if not response:
            raise APIError('[FantomGraphQLAPI][GetBalance] Response is None.')
        if response.get('errors'):
            raise APIError('[FantomGraphQLAPI][GetBalance] Unsuccessful.')

        transactions = response.get('data').get('account').get('txList').get('edges')
        block_head = self.check_block_status()
        txs = []
        for tx in transactions:
            if self.validate_transaction(tx.get('transaction')):
                parsed_tx = self.parse_tx(tx.get('transaction'), address, block_head)
                if parsed_tx is not None:
                    txs.append(parsed_tx)
        return txs

    @staticmethod
    def validate_transaction(tx: Dict[str, Any]) -> Optional[bool]:
        if tx.get('status') == '0x1' and tx.get('inputData') == '0x':
            return True
        return None

    def parse_tx(
        self,
        tx: Dict[str, Any],
        address: str,
        block_head: int
    ) -> Dict[str, Dict[str, Any]]:
        direction = 'incoming'
        currency = self.currency
        value = self.from_unit(int(tx.get('value'), 16))

        if are_addresses_equal(tx.get('from'), address):
            # Transaction is from this address, so it is a withdraw
            value = -value
            direction = 'outgoing'
        elif not are_addresses_equal(tx.get('to'), address):
            # Transaction is not to this address, and is not a withdraw, so no deposit should be made
            #  this is a special case and should not happen, so we ignore such special transaction (value will be zero)
            value = Decimal('0')

        return {
            currency: {
                'address': address,
                'hash': tx.get('hash'),
                'from_address': [tx.get('from')],
                'to_address': tx.get('to'),
                'amount': value,
                'block': int(tx.get('blockNumber'), 16),
                'date': parse_utc_timestamp(int(tx.get('block').get('timestamp'), 16)),
                'confirmations': block_head - int(tx.get('blockNumber'), 16),
                'direction': direction,
                'raw': tx,
            }
        }

    def check_block_status(self) -> int:
        query = """
            query blockStatus {
                block {
                    number
                }
            }
        """

        data = {
            'query': query
        }
        response = self.request('', headers={'Content-Type': 'application/json'}, body=json.dumps(data))
        if not response:
            raise APIError('[FantomGraphQLAPI][CheckStatus] Response is None.')
        if response.get('errors'):
            raise APIError('[FantomGraphQLAPI][CheckStatus] Unsuccessful.')
        return int(response.get('data').get('block').get('number'), 16)

    def get_block_head(self) -> int:
        return self.check_block_status()

    def get_latest_block(
        self,
        after_block_number: Optional[int] = None,
        to_block_number: Optional[int] = None,
        include_inputs: bool = False,
        include_info: bool = False
    ) -> Tuple[Dict[str, Any], Dict[str, Any], int]:
        block_info = self.check_block_status()
        if not to_block_number:
            latest_block_height_mined = block_info
            if not latest_block_height_mined:
                raise APIError('API Not Return block height')
        else:
            latest_block_height_mined = to_block_number

        cache_key = f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}'

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
        count = max_height - min_height
        # input_addresses ~ outgoing_txs and output_addresses ~ incoming_txs
        transactions_addresses = {'input_addresses': set(), 'output_addresses': set()}
        transactions_info = {'outgoing_txs': defaultdict(lambda: defaultdict(list)),
                             'incoming_txs': defaultdict(lambda: defaultdict(list))}
        query = """
            query BlocksList($min_height: Cursor!, $count: Int!) {
                blocks (cursor: $min_height, count: $count) {
                    totalCount
                    pageInfo {
                        first
                        last
                        hasNext
                        hasPrevious
                    }
                    edges {
                        cursor
                        block {
                            number
                            timestamp
                            transactionCount
                            txList {
                                status
                                hash
                                from
                                to
                                value
                                nonce
                                index
                                inputData
                            }
                        }
                    }
                }
            }
        """
        data = {
            'query': query,
            'variables': {
                'min_height': hex(max_height),
                'count': count
            }
        }
        response = self.request('', headers={'Content-Type': 'application/json'}, body=json.dumps(data))
        if not response:
            raise APIError('[FantomGraphQLAPI][GetBlock] Response is None.')
        if response.get('errors'):
            raise APIError('[FantomGraphQLAPI][GetBlock] Unsuccessful.')

        for block in response.get('data').get('blocks').get('edges'):
            transactions = block.get('block').get('txList')

            if transactions is None:
                continue
            for tx in transactions:
                if tx.get('status', '') != '0x1':  # This means tx was failed in network (for any reason)
                    continue
                tx_hash = tx.get('hash')
                if not tx_hash:
                    continue
                if not self.validate_transaction(tx):
                    continue
                if tx.get('value') == '0x0':
                    continue
                tx_data = FtmScanAPI.get_api().get_transaction_data(tx, tx.get('inputData'))
                if tx_data is None:
                    continue
                from_address = tx_data.get('from')
                to_address = tx_data.get('to')
                value = tx_data.get('amount')
                currency = tx_data.get('currency')

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
        metric_set(name='latest_block_processed', labels=[self.symbol.lower()], amount=max_height - 1)
        cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}',
                  max_height - 1,
                  86400)
        return transactions_addresses, transactions_info, max_height - 1

    def get_staking_info(self, address: str) -> StakingInfo:
        data = {
            'query': self.queries.get('get_staking_info'),
            'variables': {
                'address': address
            }
        }
        try:
            response = self.request('', body=json.dumps(data))
        except ConnectionError as err:
            raise APIError(f'{self.symbol} API: Failed to get txs, connection error') from err
        if not response:
            raise APIError(f'{self.symbol} API: Get Txs response is None')
        try:
            parsed_info = self.parse_staking_info(response, address)
        except AttributeError as err:
            raise APIError(f'{self.symbol} API: Failed to parse staking_info response:{response}') from err

        return parsed_info

    def parse_staking_info(self, response: Dict[str, Any], address: str) -> StakingInfo:
        edges = response.get('data').get('account').get('delegations').get('edges')
        if not edges:
            raise APIError(f'{self.symbol} API: Failed to parse staking_info response,'
                           f' There No delegations for this account!')
        balance = self.from_unit(int(response.get('data').get('account').get('balance'), 16))
        pending_rewards, _, delegated_balances = Decimal('0'), Decimal('0'), Decimal('0')
        for edge in edges:
            pending_reward = edge.get('delegation').get('pendingRewards').get('amount')
            delegated_balance = edge.get('delegation').get('amountDelegated')
            pending_rewards += self.from_unit(int(pending_reward, 16))
            delegated_balances += self.from_unit(int(delegated_balance, 16))
        total_balance = balance + delegated_balances
        end_date = int(edges[0].get('delegation').get('lockedUntil'), 16)
        return StakingInfo(
            address=address,
            total_balance=total_balance,
            staked_balance=delegated_balances,
            end_staking_plan=parse_utc_timestamp(end_date),
            rewards_balance=pending_rewards,
        )
