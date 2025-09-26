import datetime
import json
import random
from collections import defaultdict
from decimal import Decimal
from typing import Any, Optional, Tuple

from django.conf import settings
from django.core.cache import cache

from exchange.base.models import Currencies
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.metrics import metric_set
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


class SolanaBitqueryAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: SOL
    API docs: https://graphql.bitquery.io/ide
    :exception ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut
    """

    active = True
    _base_url = 'https://graphql.bitquery.io/'
    testnet_url = 'https://graphql.bitquery.io/'
    symbol = 'SOL'
    rate_limit = 6
    PRECISION = 9
    cache_key = 'sol'
    currency = Currencies.sol

    OFFSET_OF_GETTING_BLOCKS = 100
    END_BLOCK_RANGE_WITH_PROBLEM = 0

    queries = {
        'get_block_head': """
            query ($network: SolanaNetwork!, $limit: Int!, $offset: Int!, $from: ISO8601DateTime) {
                solana(network: $network) {
                    blocks(
                        options: {desc: "height", limit: $limit, offset: $offset}
                        date: {since: $from}
                    ) {
                    height
                }
              }
            }
        """,
        'get_blocks': """
            query ($from: Int!, $to: Int!) {
                solana(network: solana) {
                    transfers(
                        success: {is: true}
                        transferType: {is: transfer}
                        currency: {is: "SOL"}
                        height: {between: [$from, $to]}
                        programId: {is: "11111111111111111111111111111111"}
                        externalProgramId: {is: "11111111111111111111111111111111"}
                    ) {
                        transaction {
                            signature
                            success
                            error
                        }
                        sender {
                            address
                        }
                        receiver {
                            address
                        }
                        currency {
                            symbol
                        }
                        amount
                        instruction {
                            externalProgram {
                                id
                                parsed
                                name
                            }
                            action {
                                name
                            }
                            program {
                                id
                                parsed
                                name
                            }
                            externalAction {
                                name
                            }
                        }
                    }
                }
            }
        """,
    }

    def get_name(self) -> str:
        return 'bitquery_api'

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.BITQUERY_API_KEY)

    def get_header(self) -> dict:
        api_key = self.get_api_key()
        return {'Content-Type': 'application/json', 'X-API-KEY': api_key,
                'accept-encoding': 'gzip'}

    def check_block_status(self) -> Any:
        since = datetime.datetime.now().isoformat()
        data = {
            'query': self.queries.get('get_block_head'),
            'variables': {'from': since, 'limit': 1, 'offset': 0, 'network': 'solana'}
        }
        headers = self.get_header()
        response = self.request(request_method='get_info', body=json.dumps(data),
                                headers=headers)
        if not response:
            raise APIError('Empty info')
        if response.get('errors'):
            raise APIError(f'Error:{response.get("errors")[0].get("message")}')
        if not response.get('data').get('solana').get('blocks'):
            raise APIError('Invalid info(empty blocks)')
        return response.get('data').get('solana').get('blocks')[0]

    def get_block_head(self) -> Any:
        return self.check_block_status()

    def validate_transaction(self, tx: dict) -> bool:
        symbol = tx.get('currency').get('symbol')
        program = tx.get('instruction').get('program')
        external_program = tx.get('instruction').get('externalProgram')
        if symbol != 'SOL':
            return False
        tx_hash = tx.get('transaction').get('signature')
        if not tx_hash:
            return False
        value = Decimal(str(tx.get('amount')))
        if value < 0.000000001: # noqa: PLR2004
            return False
        if not tx.get('transaction').get('success'):
            return False
        if tx.get('transaction').get('error') != '':
            return False
        if (program.get('id') != '11111111111111111111111111111111' or not program.get('parsed') or
                program.get('name') != 'system'):
            return False
        if (external_program.get('id') != '11111111111111111111111111111111' or not external_program.get('parsed') or
                external_program.get('name') != 'system'):
            return False
        if tx.get('instruction').get('action').get('name') != 'transfer':
            return False
        if tx.get('instruction').get('externalAction').get('name') != 'transfer':
            return False
        return True

    def get_latest_block(self, after_block_number: Optional[int] = None, to_block_number: Optional[int] = None,
                         include_inputs: bool = False, include_info: bool = False) -> Tuple[dict, dict, int]:
        if not to_block_number:
            info = self.check_block_status()
            latest_block_height_mined = int(info.get('height')) - 1500
            if not latest_block_height_mined:
                raise APIError('API Not Return block height')
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
        max_height = min(max_height, min_height + self.OFFSET_OF_GETTING_BLOCKS)

        # input_addresses ~ outgoing_txs and output_addresses ~ incoming_txs
        transactions_addresses = {'input_addresses': set(), 'output_addresses': set()}
        transactions_info = {'outgoing_txs': defaultdict(lambda: defaultdict(list)),
                             'incoming_txs': defaultdict(lambda: defaultdict(list))}

        data = {
            'query': self.queries.get('get_blocks'),
            'variables': {'network': 'solana', 'from': min_height, 'to': max_height - 1}
        }
        response = self.request(request_method='', body=json.dumps(data),
                                headers=self.get_header())
        if not response:
            raise APIError('Get block API returns empty response')
        if response.get('errors'):
            if 'Limit for result exceeded' in response.get('errors')[0].get('message'):
                self.OFFSET_OF_GETTING_BLOCKS = int((max_height - min_height) / 2)
                if not self.END_BLOCK_RANGE_WITH_PROBLEM:
                    self.END_BLOCK_RANGE_WITH_PROBLEM = max_height - 1
                return transactions_addresses, transactions_info, 0
            raise APIError(f'Get block API returns error:{response.get("errors")[0].get("message")}')
        transfers = response.get('data').get('solana').get('transfers') or []
        for transfer in transfers:
            if not self.validate_transaction(transfer):
                continue
            tx_hash = transfer.get('transaction').get('signature')
            value = Decimal(str(transfer.get('amount')))
            from_address = transfer.get('sender').get('address')
            to_address = transfer.get('receiver').get('address')

            transactions_addresses['output_addresses'].add(to_address)
            if include_inputs:
                transactions_addresses['input_addresses'].add(from_address)

            if include_info:
                transactions_info['incoming_txs'][to_address][self.currency].append({
                    'tx_hash': tx_hash,
                    'value': value,
                })
                if include_inputs:
                    check_for_duplication = [tx for tx in transactions_info['outgoing_txs'][from_address][self.currency]
                                             if tx['tx_hash'] == tx_hash]
                    if check_for_duplication:
                        index = transactions_info['outgoing_txs'][from_address][self.currency].index(
                            check_for_duplication[0])
                        transactions_info['outgoing_txs'][from_address][self.currency][index]['value'] += value
                    else:
                        transactions_info['outgoing_txs'][from_address][self.currency].append({
                            'tx_hash': tx_hash,
                            'value': value,
                        })

        if self.END_BLOCK_RANGE_WITH_PROBLEM and min_height > self.END_BLOCK_RANGE_WITH_PROBLEM:
            self.END_BLOCK_RANGE_WITH_PROBLEM = 0
            self.OFFSET_OF_GETTING_BLOCKS = 5000
        metric_set(name='latest_block_processed', labels=[self.symbol.lower()], amount=max_height - 1)
        cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}', max_height - 1,
                  86400)
        return transactions_addresses, transactions_info, max_height - 1
