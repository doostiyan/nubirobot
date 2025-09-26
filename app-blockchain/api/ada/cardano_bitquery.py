import datetime
import json
import random
from collections import defaultdict
from decimal import Decimal
from typing import Any, Optional

from django.conf import settings
from django.core.cache import cache

from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI
from exchange.blockchain.metrics import metric_set
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


class CardanoBitqueryAPI(NobitexBlockchainBlockAPI, BlockchainUtilsMixin):
    """
    Cardano API explorer.

    supported coins: ada
    API docs: https://graphql.bitquery.io/
    Explorer: https://explorer.bitquery.io/cardano
    """

    _base_url = 'https://graphql.bitquery.io/'
    symbol = 'ADA'
    currency = Currencies.ada
    active = True

    PRECISION = 6
    cache_key = 'ada'
    rate_limit = 6

    TRANSACTION_DETAILS_BATCH = True

    queries = {
        'get_blocks': """
            query getBlockTxs($min_height: Int!, $max_height: Int!, $from: ISO8601DateTime) {
              cardano(network: cardano) {
                inputs(height: {between: [$min_height, $max_height]}, currency: {is: "ADA"}) {
                  transaction {
                    hash
                  }
                  value
                  inputAddress {
                    address
                  }
                  block {
                    height
                    timestamp {
                      time(format: "%Y-%m-%dT%H:%M:%SZ")
                    }
                  }
                }
                outputs(height: {between: [$min_height, $max_height]}, currency: {is: "ADA"}) {
                  transaction {
                    hash
                  }
                  value
                  outputAddress {
                    address
                  }
                  block {
                    height
                    timestamp {
                      time(format: "%Y-%m-%dT%H:%M:%SZ")
                    }
                  }
                }
                blocks(options: {desc: "height", limit: 1}, date: {since: $from}) {
                  height
                }
              }
            }

        """,
        'get_txs': """
            query ($address: String!, $from: ISO8601DateTime) {
              cardano(network: cardano) {
                outputs(
                  outputAddress: {is: $address}
                  options: {desc: ["block.height"]}
                  currency: {is: "ADA"}
                ) {
                  block {
                    height
                    timestamp {
                      time(format: "%Y-%m-%dT%H:%M:%SZ")
                    }
                  }
                  transaction {
                    hash
                  }
                  outputAddress {
                    address
                  }
                  value
                }
                inputs(
                  inputAddress: {is: $address}
                  options: {desc: ["block.height"]}
                  currency: {is: "ADA"}
                ) {
                  block {
                    height
                    timestamp {
                      time(format: "%Y-%m-%dT%H:%M:%SZ")
                    }
                  }
                  transaction {
                    hash
                  }
                  inputAddress {
                    address
                  }
                  value
                }
                blocks(options: {desc: "height", limit: 1}, date: {since: $from}) {
                  height
                }
              }
            }
        """,
        'get_balance': """
            query ($address: String!) {
              cardano(network: cardano)  {
                address(address: {is: $address}) {
                  balance {
                    currency {
                      address
                      symbol
                      tokenType
                    }
                    value
                  }
                }
              }
            }
        """,
        'get_block_head': """
            query ($from: ISO8601DateTime) {
              cardano(network: cardano) {
                blocks(
                  options: {desc: "height", limit: 1}
                  date: {since: $from}
                ) {
                  height
                }
              }
            }
        """,
        'get_tx_details': """
            query ($network: CardanoNetwork!, $hashes: [String!], $limit: Int!, $offset: Int!,$from: ISO8601DateTime) {
                cardano(network: $network) {
                    blocks(options: {desc: "height", limit: 1}, date: {since: $from}) {
                        height
                    }
                    transactions(txHash: {in: $hashes}) {
                        block {
                            height
                            timestamp {
                            time(format: "%Y-%m-%dT%H:%M:%SZ")
                            }
                        }
                        index
                        hash
                        feeValue
                        includedAt {
                            time(format: "%Y-%m-%dT%H:%M:%SZ")
                        }
                    }
                    outputs(
                    txHash: {in: $hashes}
                    options: {asc: "outputIndex", limit: $limit, offset: $offset}
                    currency: {is: "ADA"}
                    ) {
                        outputIndex
                        transaction{
                            hash
                        }
                        block {
                            height
                            timestamp {
                              time(format: "%Y-%m-%dT%H:%M:%SZ")
                            }
                        }
                        outputAddress {
                            address
                        }
                        value
                        currency {
                            symbol
                        }
                    }
                    inputs(
                    txHash: {in: $hashes}
                    options: {asc: "inputIndex", limit: $limit, offset: $offset}
                    currency: {is: "ADA"}
                    ) {
                        inputIndex
                        transaction{
                            hash
                        }
                        block {
                            height
                            timestamp {
                              time(format: "%Y-%m-%dT%H:%M:%SZ")
                            }
                        }
                        inputAddress {
                            address
                            annotation
                        }
                        value
                        currency {
                            symbol
                        }
                    }
                }
            }

        """
    }

    def get_name(self) -> str:
        return 'bitquery_api'

    def check_block_status(self) -> dict:
        data = {
            'query': self.queries.get('get_block_head'),
            'variables': {
                'from': datetime.datetime.now().strftime('%Y-%m-%d')
            }
        }
        response = self.request('', headers={'Content-Type': 'application/json', 'X-API-KEY': self.get_api_key()},
                                body=json.dumps(data))
        if not response:
            raise APIError('[CardanoBitqueryAPI][CheckBlockStatus] Response is None')
        if not response.get('data'):
            raise APIError('[CardanoBitqueryAPI][CheckBlockStatus] Data is None')
        blocks = response.get('data', {}).get('cardano', {}).get('blocks', {})
        if not blocks:
            raise APIError('[CardanoBitqueryAPI][CheckBlockStatus] Blocks is None')
        return {'blockNum': blocks[0].get('height')}

    def get_block_head(self) -> Any:
        block = self.check_block_status()
        return block.get('blockNum')

    def get_txs(self, address: str, limit: int = 25) -> list:
        data = {
            'query': self.queries.get('get_txs'),
            'variables': {
                'address': address,
                'from': datetime.datetime.now().strftime('%Y-%m-%d')
            }
        }
        response = self.request('', headers={'Content-Type': 'application/json', 'X-API-KEY': self.get_api_key()},
                                body=json.dumps(data))
        if not response:
            raise APIError('[CardanoBitqueryAPI][GetTransactions] Response is None.')
        if response.get('errors'):
            raise APIError('[CardanoBitqueryAPI][GetTransactions] Unsuccessful.')
        data = response.get('data').get('cardano')
        if not data:
            raise APIError('[CardanoBitquryAPI][GetTransactions] Data is None.')

        transactions = list(self.parse_inputs_outputs(data).values())
        txs = []
        for tx_info in transactions[:limit]:
            parsed_tx = self.parse_tx(tx_info, address)
            if not parsed_tx:
                continue
            txs.append(parsed_tx)
        return txs

    def parse_tx(self, tx_info: dict, address: str) -> dict:
        direction = 'outgoing'
        tx_hash = tx_info.get('txid')
        input_output_info = self.get_input_output_tx(tx_info, include_info=True)
        if input_output_info is None:
            return None
        input_addresses, inputs_info, output_addresses, outputs_info = input_output_info

        addresses = set(output_addresses).difference(input_addresses)

        if address.lower() in map(str.lower, addresses):
            direction = 'incoming'

        tx_output_info = outputs_info.get(address)
        tx_input_info = inputs_info.get(address)
        transactions_info = defaultdict(lambda: Decimal('0'))
        if tx_input_info:
            for currency, value in tx_input_info.items():
                transactions_info[currency] = value
        if tx_output_info:
            for currency, value in tx_output_info.items():
                if direction == 'outgoing':
                    transactions_info[currency] -= value
                else:
                    transactions_info[currency] = value
        tx_date = parse_iso_date(tx_info['date'])
        return {currency: {
            'hash': tx_hash,
            'amount': transactions_info.get(currency),
            'confirmations': tx_info.get('confirmations'),
            'block': tx_info.get('block'),
            'date': tx_date,
            'from_address': list(input_addresses),
            'to_address': list(addresses),
            'direction': direction,
            'raw': tx_info
        } for currency in transactions_info}

    def get_input_tx(self, tx_info: dict, include_info: bool = False) -> tuple:
        input_addresses = set()
        inputs = tx_info.get('inputs') or []
        inputs_details = defaultdict(lambda: defaultdict(Decimal))
        for input_tx in inputs:
            address = input_tx.get('address') or []
            if not address:
                continue
            input_addresses.update([address])
            if include_info:
                inputs_details[address][self.currency] += input_tx['value']

        return input_addresses, inputs_details

    def get_output_tx(self, tx_info: dict, include_info: bool = False) -> tuple:
        output_addresses = set()
        outputs = tx_info.get('outputs') or []
        outputs_details = defaultdict(lambda: defaultdict(Decimal))
        for output_tx in outputs:
            address = output_tx.get('address')
            if not address:
                continue
            output_addresses.update([address])
            if include_info:
                outputs_details[address][self.currency] += output_tx['value']

        return output_addresses, outputs_details

    def get_input_output_tx(self, tx_info: dict, include_info: bool = False) -> tuple:
        input_addresses, inputs_info = self.get_input_tx(tx_info, include_info=include_info)
        output_addresses, outputs_info = self.get_output_tx(tx_info, include_info=include_info)
        return input_addresses, inputs_info, output_addresses, outputs_info

    def get_latest_block(self,
                         after_block_number: Optional[int] = None,
                         to_block_number: Optional[int] = None,
                         include_inputs: bool = False,
                         include_info: bool = False) -> tuple:
        if not to_block_number:
            info = self.check_block_status()
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
        max_height = min(max_height, min_height + 100)

        transactions_addresses = set()
        transactions_info = defaultdict(lambda: defaultdict(list))
        data = {
            'query': self.queries.get('get_blocks'),
            'variables': {
                'min_height': min_height,
                'max_height': max_height - 1,
                'from': datetime.datetime.now().strftime('%Y-%m-%d')
            }}

        response = self.request('', headers={'Content-Type': 'application/json', 'X-API-KEY': self.get_api_key()},
                                body=json.dumps(data))
        if not response:
            raise APIError('[CardanoBitquryAPI][GetLatestBlock] Response is None.')
        if response.get('errors'):
            raise APIError('[CardanoBitquryAPI][GetLatestBlock] Unsuccessful.')

        data = response.get('data').get('cardano')
        if not data:
            raise APIError('[CardanoBitquryAPI][GetLatestBlock] Data is None.')

        transactions = self.parse_inputs_outputs(data)
        for tx_hash, tx_info in transactions.items():
            input_output_info = self.get_input_output_tx(tx_info, include_info=include_info)
            if input_output_info is None:
                continue
            input_addresses, inputs_info, output_addresses, outputs_info = input_output_info
            addresses = set(output_addresses).difference(input_addresses)
            transactions_addresses.update(addresses)

            if include_inputs:
                transactions_addresses.update(input_addresses)

            if include_info:
                for address in transactions_addresses:
                    tx_output_info = outputs_info[address]

                    if include_inputs:
                        tx_input_info = inputs_info[address]
                        for token, value in tx_input_info.items():
                            transactions_info[address][token].append({
                                'tx_hash': tx_hash,
                                'value': value - tx_output_info[token],
                                'direction': 'outgoing',
                            })
                    for token, value in tx_output_info.items():
                        transactions_info[address][token].append({
                            'tx_hash': tx_hash,
                            'value': value,
                            'direction': 'incoming',
                        })
        last_cache_value = cache.get(cache_key) or 0
        if latest_block_height_mined > last_cache_value:
            metric_set(name='latest_block_processed', labels=[self.symbol.lower()], amount=max_height - 1)
            cache.set(cache_key, max_height - 1, 86400)
        return set(transactions_addresses), transactions_info, max_height - 1

    def parse_inputs_outputs(self, data: dict, transactions: Optional[dict] = None) -> dict:
        if transactions is None:
            transactions = {}
        for input_ in data.get('inputs'):
            tx_hash = input_.get('transaction').get('hash')
            if transactions.get(tx_hash):
                transactions.get(tx_hash).get('inputs').append({
                    'address': input_.get('inputAddress').get('address'),
                    'currency': self.currency,
                    'value': Decimal(str(input_.get('value'))),
                })
            else:
                transactions[tx_hash] = {
                    'txid': tx_hash,
                    'block': input_.get('block').get('height'),
                    'confirmations': data.get('blocks')[0].get('height') - input_.get('block').get('height'),
                    'date': input_.get('block').get('timestamp').get('time'),
                    'inputs': [{
                        'address': input_.get('inputAddress').get('address'),
                        'currency': self.currency,
                        'value': Decimal(str(input_.get('value'))),
                    }],
                    'outputs': [],
                }

        for output_ in data.get('outputs'):
            tx_hash = output_.get('transaction').get('hash')
            if transactions.get(tx_hash):
                transactions.get(tx_hash).get('outputs').append({
                    'address': output_.get('outputAddress').get('address'),
                    'currency': self.currency,
                    'value': Decimal(str(output_.get('value'))),
                })
            else:
                transactions[tx_hash] = {
                    'txid': tx_hash,
                    'block': output_.get('block').get('height'),
                    'confirmations': data.get('blocks')[0].get('height') - output_.get('block').get('height'),
                    'date': output_.get('block').get('timestamp').get('time'),
                    'outputs': [{
                        'address': output_.get('outputAddress').get('address'),
                        'currency': self.currency,
                        'value': Decimal(str(output_.get('value'))),
                    }],
                    'inputs': [],
                }
        return transactions

    def get_tx_details_batch(self, tx_hashes: list) -> dict:
        data = {
            'query': CardanoBitqueryAPI.queries.get('get_tx_details'),
            'variables': {
                'network': 'cardano',
                'hashes': tx_hashes,
                'limit': 10,
                'offset': 0,
                'from': datetime.datetime.now().strftime('%Y-%m-%d'),
            }
        }
        response = self.request('', headers={'Content-Type': 'application/json', 'X-API-KEY': self.get_api_key()},
                                body=json.dumps(data))
        if (not response) or response.get('errors'):
            raise APIError(f'Cardano BITQUERY failed with getting tx details.\ntxhash:{tx_hashes}')

        txs = response.get('data').get('cardano')
        if not txs:
            raise APIError(f'Cardano BITQUERY failed with getting tx details.\ntxhash:{tx_hashes}')

        transactions = {}
        for tx in txs.get('transactions'):
            parsed_tx = self.parse_tx_details(tx)
            transactions.update(parsed_tx)
        return self.parse_inputs_outputs(txs, transactions)

    def parse_tx_details(self, tx: dict) -> dict:
        return {
            tx.get('hash'): {
                'hash': tx.get('hash'),
                'success': True,  # api does not have status field
                'is_valid': True,
                'inputs': [],
                'outputs': [],
                'transfers': [],
                'block': tx.get('block').get('height'),
                'fees': Decimal(str(tx.get('feeValue'))),
                'date': parse_iso_date(tx.get('block').get('timestamp').get('time')),
                'raw': tx,
            }
        }

    def get_api_key(self) -> str:
        return random.choice(settings.LTC_BITQUERY_API_KEY)
