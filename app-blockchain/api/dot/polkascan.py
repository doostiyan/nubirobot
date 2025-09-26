from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache

from exchange.base.models import Currencies
from exchange.blockchain.metrics import metric_set
from exchange.blockchain.ss58 import is_valid_ss58_address, ss58_encode
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError, ValidationError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


# So out of date, consider it
class PolkascanAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    Polkascan API explorer.

    supported coins: dot
    Explorer: https://explorer-32.polkascan.io
    """

    _base_url = 'https://explorer-32.polkascan.io'
    symbol = 'DOT'
    cache_key = 'dot'
    active = True
    currency = Currencies.dot
    rate_limit = 0
    PRECISION = 10

    def get_name(self):
        return 'polkascan_api'

    supported_requests = {
        'get_balance': '/api/v1/polkadot/account/{address}',
        'get_transfers': '/api/v1/polkadot/event?filter[address]={address}&filter[search_index]=2&page[size]={limit}',
        'get_tx': '/api/v1/polkadot/extrinsic/{tx_id}',
        'get_txs': '/api/v1/polkadot/extrinsic?filter[address]={address}&filter[signed]=1&filter[search_index]=2&page[size]={limit}',
        'get_block': '/api/v1/polkadot/block/{num}?include=transactions',
        'get_status': '/api/v1/polkadot/networkstats/latest',
    }

    def validate_address(self, address):
        address_format = 0 if self.network == 'mainnet' else 42
        if not is_valid_ss58_address(address, valid_ss58_format=address_format):
            raise ValidationError('Address not valid')

    def pub_key_to_address(self, pub_key):
        address_format = 0 if self.network == 'mainnet' else 42
        return ss58_encode(pub_key, ss58_format=address_format)

    def get_balance(self, address):
        self.validate_address(address)
        response = self.request('get_balance', address=address)
        if not response:
            raise APIError('[SubscanAPI][GetBalance] Response is None.')
        if response.get('meta').get('errors'):
            raise APIError('[PolkascanAPI][GetBalance] Unsuccessful.')

        return {
            self.currency: {
                'symbol': self.symbol,
                'balance': self.from_unit(response.get('data').get('attributes').get('balance_free')),
                'unconfirmed_balance': Decimal('0'),
                'address': address,
                'reserved': self.from_unit(response.get('data').get('attributes').get('balance_reserved')),
            }
        }

    def get_txs(self, address, limit=25):
        self.validate_address(address)
        transactions = []
        response = self.request('get_transfers', address=address, limit=limit)
        events_info = response.get('data')
        block_head = int(self.check_block_status().get('best_block'))

        # Check last 25 transactions
        for event in events_info:
            event = self.parse_event(event, address)
            if event:
                tx_info = self.request('get_tx', tx_id=event.get('tx_id'))
                event['hash'] = '0x' + tx_info.get('data').get('attributes').get('extrinsic_hash')
                event['date'] = datetime.strptime(tx_info.get('data').get('attributes').get('datetime'),
                                                  '%Y-%m-%dT%H:%M:%S%z')
                event['confirmations'] = block_head - tx_info.get('data').get('attributes').get('block_id')
                transactions.append(event)
        return transactions

    def parse_event(self, event, address):
        event_info = event.get('attributes')
        block = event_info.get('block_id')
        if event_info.get('module_id') == 'balances' and event_info.get('event_id') == 'Transfer':
            from_address = event_info.get('attributes')[0].get('value')
            value = self.from_unit(int(event_info.get('attributes')[2].get('value')))
            if from_address == address:
                value = - value
            elif event_info.get('attributes')[1].get('value') != address:
                return

            return {
                'block': block,
                'from_address': from_address,
                'tx_id': str(block) + f'-{event_info.get("extrinsic_idx")}',
                'event': event.get('id'),
                'value': value,
                'raw': event_info,
            }

    def get_extrinsic(self, address, limit=25):
        """
            Alternative function to get txs, we don't use it now.
        """
        self.validate_address(address)
        transactions = []
        response = self.request('get_txs', address=address, limit=limit)
        if not response:
            raise APIError('[PolkascanAPI][GetTxs] Response is None.')
        txs = response.get('data')
        if txs is None:
            raise APIError('[PolkascanAPI][GetTxs] Txs is None.')
        for tx in txs:
            parsed_tx = self.parse_tx(tx, address)
            if parsed_tx:
                tx_info = self.request('get_tx', tx_id=parsed_tx.get('tx_id'))
                parsed_tx['date'] = datetime.strptime(tx_info.get('data').get('attributes').get('datetime'),
                                                      '%Y-%m-%dT%H:%M:%S%z')
                transactions.append(parsed_tx)
        return transactions

    def parse_tx(self, tx, address=None):
        value = Decimal(0)
        transfers = []
        tx = tx.get('attributes')
        if tx.get('success') == 0 or tx.get('error') != 0:
            return

        from_address = tx.get('address')
        to_address = ''
        tx_hash = '0x' + tx.get('extrinsic_hash')
        if tx.get('module_id') == 'balances' and (
            tx.get('call_id') == 'transfer_keep_alive' or tx.get('call_id') == 'transfer'):
            to_address = tx.get('params')[0].get('value')
            value = self.from_unit(tx.get('params')[1].get('value'))
            is_valid = True

            # if address, then consider related transfers to address otherwise add all transfers.
            if address:
                if from_address == address:
                    value = - value
                elif to_address != address:
                    return
            else:
                transfers.append({
                    'hash': tx_hash,
                    'from': from_address,
                    'currency': self.currency,
                    'is_valid': is_valid,
                    'to': to_address,
                    'value': value,
                })
        elif tx.get('module_id') == 'utility' and tx.get('call_id') == 'batch':
            for transfer in tx.get('params')[0].get('value'):
                if transfer.get('call_module') != 'Balances' or transfer.get('call_function') != 'transfer':
                    continue
                to_address = self.pub_key_to_address(transfer.get('call_args')[0].get('value'))
                value = self.from_unit(transfer.get('call_args')[1].get('value'))
                is_valid = True

                # if address then consider related transfers to address, otherwise add all transfers.
                if address:
                    if from_address == address:
                        value = - value
                    elif to_address != address:
                        continue
                    break
                else:
                    transfers.append({
                        'hash': tx_hash,
                        'is_valid': is_valid,
                        'currency': self.currency,
                        'from': from_address,
                        'to': to_address,
                        'value': value,
                    })
        if address:
            return {
                'to_address': to_address,
                'from_address': from_address,
                'block': tx.get('block_id'),
                'hash': tx_hash,
                'tx_id': str(tx.get('block_id')) + f'-{tx.get("extrinsic_idx")}',
                'date': None,
                'value': value,
                'raw': tx,
            }
        else:
            return transfers

    def check_block_status(self):
        info = self.request('get_status')
        if not info:
            raise APIError('Empty info')
        if info.get('meta').get('errors'):
            raise APIError('Unsuccessful')
        return info.get('data').get('attributes')

    def get_block_head(self):
        return self.check_block_status()

    def get_latest_block(self, after_block_number=None, to_block_number=None, include_inputs=False, include_info=False):
        info = self.check_block_status()
        if not to_block_number:
            latest_block_height_mined = int(info.get('best_block'))
            if not latest_block_height_mined:
                raise APIError('API Not Return block height')
        else:
            latest_block_height_mined = to_block_number

        if not after_block_number:
            latest_block_height_processed = cache.get(f'latest_block_height_processed_{self.cache_key}')
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
        print('Cache latest block height: {}'.format(latest_block_height_processed))
        for block_height in range(min_height, max_height):
            response = self.request('get_block', num=block_height)
            if not response:
                raise APIError('Get block API returns empty response')
            if response.get('meta').get('errors'):
                raise APIError(f'Get block API: Error')

            txs = response.get('included')
            if not txs:
                continue
            for tx in txs:
                parsed_transfers = self.parse_tx(tx)
                if not parsed_transfers:
                    continue
                for transfer in parsed_transfers:
                    tx_hash = transfer.get('hash')
                    from_address = transfer.get('from')
                    to_address = transfer.get('to')
                    value = transfer.get('value')

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
            metric_set(name='latest_block_processed', labels=[self.symbol.lower()], amount=max_height - 1)
            cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}',
                      max_height - 1,
                      86400)
            return transactions_addresses, transactions_info, max_height - 1

    def get_tx_details(self, tx_hash):
        response = self.request('get_tx', tx_id=tx_hash)
        if response.get('meta').get('errors'):
            return {
                'hash': tx_hash,
                'success': False
            }

        parsed_tx = self.parse_tx_details(response.get('data'))
        return parsed_tx

    def parse_tx_details(self, tx):
        transfers = self.parse_tx(tx) or []
        success = tx.get('attributes').get('success') and not tx.get('attributes').get('error')
        is_valid = True
        if not transfers:
            is_valid = False
        for transfer in transfers:
            if not transfer.get('is_valid'):
                is_valid = False
        return {
            'hash': '0x' + tx.get('attributes').get('extrinsic_hash'),
            'id': tx.get('id'),
            'success': success,
            'is_valid': is_valid and success,
            'inputs': [],
            'outputs': [],
            'transfers': transfers,
            'block': tx.get('attributes').get('block_id'),
            'date': datetime.strptime(tx.get('attributes').get('datetime'), '%Y-%m-%dT%H:%M:%S 00:00'),
        }
