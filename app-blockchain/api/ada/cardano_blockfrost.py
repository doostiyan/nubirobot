import datetime
import random
from collections import defaultdict
from decimal import Decimal
from typing import Any, Optional

from django.conf import settings
from django.core.cache import cache

from exchange.base.models import Currencies
from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI
from exchange.blockchain.metrics import metric_set
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


class BlockfrostAPI(NobitexBlockchainBlockAPI, BlockchainUtilsMixin):
    """
    Cardano API explorer.

    supported coins: ada
    API docs: https://docs.blockfrost.io/
    Explorer: https://cardano-mainnet.blockfrost.io/api/v0/
    """

    _base_url = 'https://cardano-mainnet.blockfrost.io/api/v0'
    testnet_url = 'https://cardano-testnet.blockfrost.io/api/v0'

    symbol = 'ADA'
    currency = Currencies.ada
    active = True

    PRECISION = 6
    cache_key = 'ada'
    ratelimit = 0.1
    SUPPORT_GET_BALANCE_BATCH = True

    def get_name(self) -> str:
        return f'{self.symbol.lower()}_blockfrost'

    @property
    def api_key_header(self) -> dict:
        return {'project_id': random.choice(settings.BLOCKFROST_API_KEY)}

    supported_requests = {
        'get_balance': '/addresses/{address}',
        'get_txs': '/addresses/{address}/transactions?order=desc',
        'get_tx': '/txs/{hash}',
        'get_utxos': '/txs/{hash}/utxos',
        'get_block': '/blocks/{number}',
        'get_latest_block': '/blocks/latest',
        'get_block_txs': '/blocks/{number}/txs',
        'get_tx_details': '/txs/{tx_hash}'
    }

    def get_api_key(self) -> str:
        return random.choice(settings.BLOCKFROST_API_KEY)

    def get_balances(self, addresses: list) -> Optional[list]:
        balances = []
        for address in addresses:
            response = self.request('get_balance', address=address, headers={'project_id': self.get_api_key()})
            if not response:
                raise APIError('[CardanoBlockfrostAPI][GetBalance] Response is None.')

            if address != response.get('address'):
                return None
            balances.append({
                self.currency: {
                    'address': response.get('address'),
                    'balance': self.from_unit(int(response.get('amount')[0].get('quantity')))
                }
            })
        return balances

    def get_txs(self, address: str, limit: int = 25, _: int = 0) -> list:
        response = self.request('get_txs', address=address, headers={'project_id': self.get_api_key()})
        if not response:
            raise APIError('[CardanoBlockfrostAPI][GetBalance] Response is None.')
        txs = []
        for tx in response[:limit]:
            tx_hash = tx.get('tx_hash')
            tx_info = self.request('get_tx', hash=tx_hash)
            tx_utxos = self.request('get_utxos', hash=tx_hash)
            parsed_tx = self.parse_tx(tx_info, tx_utxos, address)
            if not parsed_tx:
                continue
            block_info = self.request('get_block', number=parsed_tx.get(self.currency).get('block'))
            parsed_tx[self.currency]['date'] = parse_utc_timestamp(block_info.get('time'))
            parsed_tx[self.currency]['confirmations'] = block_info.get('confirmations')
            txs.append(parsed_tx)
        return txs

    def parse_tx(self, tx_info: dict, tx_utxos: dict, address: str) -> Optional[dict]:
        direction = 'outgoing'
        tx_hash = tx_info.get('hash')
        input_output_info = self.get_input_output_tx(tx_utxos, include_info=True)
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
        amount = transactions_info.get(self.currency)
        if amount == Decimal('0'):
            return None
        return {currency: {
            'block': tx_info.get('block_height'),
            'from_address': list(input_addresses),
            'to_address': addresses,
            'amount': amount,
            'fee': self.from_unit(int(tx_info['fees'])),
            'hash': tx_hash,
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
                inputs_details[address][self.currency] += self.from_unit(int(input_tx['amount'][0]['quantity']))

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
                outputs_details[address][self.currency] += self.from_unit(int(output_tx['amount'][0]['quantity']))

        return output_addresses, outputs_details

    def get_input_output_tx(self, tx_info: dict, include_info: bool = False) -> tuple:
        input_addresses, inputs_info = self.get_input_tx(tx_info, include_info=include_info)
        output_addresses, outputs_info = self.get_output_tx(tx_info, include_info=include_info)
        return input_addresses, inputs_info, output_addresses, outputs_info

    def check_block_status(self) -> dict:
        response = self.request('get_latest_block', headers={'project_id': self.get_api_key()})
        if not response:
            raise APIError('[CardanoAPI][CheckStatus] Response is None.')
        return {'blockNum': response.get('height')}

    def get_block_head(self) -> Any:
        block = self.check_block_status()
        return block.get('blockNum')

    def get_latest_block(self,
                         after_block_number: Optional[int] = None,
                         to_block_number: Optional[int] = None,
                         include_inputs: bool = False,
                         include_info: bool = False) -> tuple:
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
        max_height = min(max_height, min_height + 100)

        transactions_addresses = {'input_addresses': set(), 'output_addresses': set()}
        transactions_info = {'outgoing_txs': defaultdict(lambda: defaultdict(list)),
                             'incoming_txs': defaultdict(lambda: defaultdict(list))}

        for block_num in range(min_height, max_height):
            response = self.request('get_block_txs', number=block_num, headers={'project_id': self.get_api_key()})

            txs_hash = response or []
            for tx_hash in txs_hash:
                tx_info = self.request('get_utxos', hash=tx_hash, headers={'project_id': self.get_api_key()})
                input_output_info = self.get_input_output_tx(tx_info, include_info=include_info)
                if input_output_info is None:
                    continue
                input_addresses, inputs_info, output_addresses, outputs_info = input_output_info
                transaction_hash = tx_info.get('hash')
                if not transaction_hash:
                    continue
                addresses = set(output_addresses).difference(input_addresses)
                transactions_addresses['output_addresses'].update(addresses)

                if include_inputs:
                    transactions_addresses['input_addresses'].update(input_addresses)

                if include_info:
                    for address in transactions_addresses['output_addresses']:
                        tx_output_info = outputs_info[address]
                        for token, value in tx_output_info.items():
                            transactions_info['incoming_txs'][address][token].append({
                                'tx_hash': transaction_hash,
                                'value': value,
                            })
                    if include_inputs:
                        for address in transactions_addresses['input_addresses']:
                            tx_output_info = outputs_info[address]
                            tx_input_info = inputs_info[address]
                            for token, value in tx_input_info.items():
                                transactions_info['outgoing_txs'][address][token].append({
                                    'tx_hash': transaction_hash,
                                    'value': value - tx_output_info[token],
                                })
        metric_set(name='latest_block_processed', labels=[self.symbol.lower()], amount=max_height - 1)
        cache.set(cache_key, max_height - 1, 86400)
        return transactions_addresses, transactions_info, max_height - 1

    def get_tx_details(self, tx_hash: str) -> dict:

        tx_info = self.request('get_tx_details', tx_hash=tx_hash)
        tx_utxos = self.request('get_utxos', hash=tx_hash)
        if not tx_info or not tx_utxos:
            raise APIError('[Cardano BlockFrost API][Get Transaction details] unsuccessful')

        return self.parse_tx_details(tx_info, tx_utxos)

    def parse_tx_details(self, tx_info: dict, tx_utxos: dict) -> dict:
        outputs = []
        input_addresses = []
        for input_ in tx_utxos.get('inputs'):
            input_addresses.append(input_.get('address'))
        for output in tx_utxos.get('outputs'):
            if output.get('address') in input_addresses:
                continue
            for amount in output.get('amount'):
                if amount.get('unit') == 'lovelace':
                    outputs.append({
                        'currency': self.currency,
                        'address': output.get('address'),
                        'value': self.from_unit(int(amount.get('quantity')))
                    })
        return {
            'hash': tx_info.get('hash'),
            'outputs': outputs,
            'success': True,
            'block': tx_info.get('block_height'),
            'date': datetime.datetime.fromtimestamp(tx_info.get('block_time')),
            'fees': self.from_unit(int(tx_info.get('fees'))),
            'raw': tx_utxos,
        }
