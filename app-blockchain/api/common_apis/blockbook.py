from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

import pytz
import time
from django.core.cache import cache
from django.utils.timezone import now

from exchange.blockchain.models import CurrenciesNetworkName
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI
from exchange.blockchain.metrics import metric_set

from exchange.blockchain.utils import get_currency_symbol_from_currency_code


class BlockbookAPI(NobitexBlockchainBlockAPI, BlockchainUtilsMixin):
    """
    Blockbook API explorer.

    supported coins: bitcoin, litecoin, and 30 other coins
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer:
    """

    active = True

    rate_limit = 0

    max_items_per_page = None
    max_blocks = 300
    page_offset_step = None
    confirmed_num = 1
    last_blocks = 0
    last_sync_datetime = None
    ignore_warning = False
    ignore_not_sync = True
    PRECISION = 8
    XPUB_SUPPORT = True
    TOKEN_NETWORK = False
    cache_key = 'eth'
    valid_token_transfer_methods = ['0xa9059cbb', '0xe6930a22']

    currency: int

    supported_requests = {
        'get_balance': '/api/v2/address/{address}?details={details}&from={from_block}&pageSize=50',
        'get_balance_xpub': '/api/v2/xpub/{address}?details={details}',
        'get_utxo': '/api/v2/utxo/{address}?confirmed={confirmed}',
        'get_tx': '/api/v2/tx/{tx_hash}',
        'get_block': '/api/v2/block/{block}?page={page}',
        'get_info': '/api/',
    }

    def get_name(self):
        return '{}_blockbook'.format(self.symbol.lower())

    @property
    def contract_currency_list(self):
        return {}

    @property
    def contract_info_list(self):
        return {}

    def check_status_blockbook(self, only_check_status=False):
        """ Check status of blockbook API. Maybe it has warning, maybe it is not sync.
        :param only_check_status: If set true, only check info every one hours.
        :return: Blockbook API info
        """
        if only_check_status:
            if self.last_sync_datetime and self.last_sync_datetime >= now() - timedelta(hours=1):
                return
            self.last_sync_datetime = now()
        start_time = time.monotonic()
        info = self.request(
            'get_info',
        )
        end_time = time.monotonic()
        interval_time = end_time - start_time
        print(f"Elapsed time: {interval_time:.6f} seconds")
        if not info:
            raise APIError('Empty info')

        if not info.get('blockbook'):
            raise APIError('Invalid info(empty blockbook)')

        if not self.ignore_not_sync and not info.get('blockbook', {}).get('inSync', False):
            raise APIError('Not sync API')

        if not info.get('backend'):
            raise APIError('Invalid info(empty backend)')
        if info.get('backend').get('warnings'):
            if not self.ignore_warning:
                raise APIError(f'Warnings: {info.get("backend").get("warnings")}')

        return info

    def get_block_head(self):
        info = self.check_status_blockbook()
        return info.get('blockbook', {}).get('bestHeight')

    def get_tx_details(self, tx_hash):
        response = self.request('get_tx', tx_hash=tx_hash)
        if not response:
            raise APIError('Response is none')
        tx = self.parse_tx_details(response)
        return tx

    def parse_tx_details(self, tx_info):
        inputs = []
        outputs = []
        transfers = []
        vins = tx_info.get('vin')
        vouts = tx_info.get('vout')

        # if not vins[0].get('value') then transaction is account based transaction otherwise it's UTXO's type.
        if not vins[0].get('value'):
            if vins[0].get('isAddress') and vouts[0].get('isAddress'):
                transfers.append({
                    'type': 'MainCoin',
                    'currency': self.currency,
                    'symbol': self.symbol,
                    'from': vins[0].get('addresses')[0],
                    'to': vouts[0].get('addresses')[0],
                    'value': self.from_unit(int(tx_info.get('value')), self.PRECISION),
                    'token': None,
                    'is_valid': True
                })
        else:
            for vin in tx_info.get('vin'):
                if not vin.get('isAddress'):
                    continue
                inputs.append({
                    'currency': self.currency,
                    'address': self.convert_address(vin.get('addresses')[0]),
                    'value': self.from_unit(int(vin.get('value'))),
                    'is_valid': True
                })
            for vout in tx_info.get('vout'):
                if not vout.get('isAddress'):
                    continue
                outputs.append({
                    'currency': self.currency,
                    'address': self.convert_address(vout.get('addresses')[0]),
                    'value': self.from_unit(int(vout.get('value'))),
                    'is_valid': True
                })
        token_transfers = tx_info.get('tokenTransfers') or []
        for transfer in token_transfers:
            contract_address = transfer.get('contract')
            currency, _ = self.contract_currency(contract_address.lower())
            if currency is None:
                continue
            contract_info = self.contract_info(currency)
            transfers.append({
                'type': transfer.get('type'),
                'currency': currency,
                'symbol': transfer.get('symbol'),
                'from': transfer.get('from'),
                'to': transfer.get('to'),
                'token': transfer.get('token'),
                'value': self.from_unit(int(transfer.get('value')), contract_info.get('decimals')),
                'is_valid': True
            })
        if not tx_info.get('ethereumSpecific'):
            success = True
        else:
            success = tx_info.get('ethereumSpecific').get('status') == 1
        return {
            'hash': tx_info.get('txid'),
            'success': success,
            'inputs': inputs,
            'outputs': outputs,
            'transfers': transfers,
            'block': tx_info.get('blockHeight'),
            'confirmations': tx_info.get('confirmations'),
            'fees': self.from_unit(int(tx_info.get('fees'))),
            'date': datetime.fromtimestamp(tx_info.get('blockTime'), pytz.utc),
            'memo': None
        }

    def get_balance(self, address):
        """ Get balance for an address.

        :param address:
        :return:
        """
        self.validate_address(address=address)
        self.check_status_blockbook(only_check_status=True)
        details = 'txslight'
        if len(address) == 111:
            response = self.request('get_balance_xpub',
                                    address=address, details=details, from_block=None)
        else:
            response = self.request('get_balance',
                                    address=address, details=details, from_block=None)

        if not response:
            return None

        balance = self.from_unit(int(response.get('balance')))
        unconfirmed_balance = self.from_unit(int(response.get('unconfirmedBalance')), negative_value=True)
        balances = {
            self.currency: {
                'symbol': self.symbol,
                'amount': balance,
                'unconfirmed_amount': unconfirmed_balance,
                'address': address
            }
        }
        for token in response.get('tokens', [])[:1000]:
            balance = token.get("balance")
            contract_address = token.get('contract')
            contract_currency, _ = self.contract_currency(contract_address.lower())
            if contract_currency is None:
                continue
            contract_info = self.contract_info(contract_currency)
            if not contract_info:
                continue
            decimal = contract_info.get('decimals')
            symbol = contract_info.get('symbol')

            if decimal is None or balance is None or symbol is None or contract_address is None:
                continue
            balances[contract_currency] = {
                'symbol': symbol,
                'amount': self.from_unit(int(balance), decimal),
                'unconfirmed_amount': Decimal('0'),
                'address': address
            }
        return balances

    def get_txs(self, address, offset=None, limit=None, unconfirmed=False, exclude_tokens=True):
        self.validate_address(address=address)
        info = self.check_status_blockbook()
        from_block = None
        if self.last_blocks:
            from_block = info['blockbook'].get('bestHeight') - self.last_blocks
        response = self.request('get_balance',
                                address=address,
                                details='txs',
                                from_block=from_block)
        transactions = response.get('transactions') or []
        txs = []
        for tx_info in transactions[:limit]:
            parsed_txs = self.parse_tx(tx_info, address)
            if not parsed_txs:
                continue
            for i in range(len(parsed_txs)):
                if isinstance(list(parsed_txs.values())[i].get('amount', {}), dict):
                    if exclude_tokens:
                        if list(parsed_txs.values())[i].get('amount', {}).get('contract_address') is not None:
                            continue
            if isinstance(parsed_txs, dict) and len(parsed_txs) > 1:
                txs.extend([{key: value} for key, value in parsed_txs.items()])
            else:
                txs.append(parsed_txs)
        return txs

    def get_token_txs(self, address, contract_info, direction=''):
        if contract_info.get('address') in CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.keys():
            contract_address = contract_info.get('address')
            destination_currency = CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(contract_address).get('destination_currency')
            txs = self.get_txs(address, exclude_tokens=False)
            txs = list(filter(lambda tx: tx.get(destination_currency, {}).get('amount', {}).get('contract_address') == contract_address, txs))
            return txs
        txs = self.get_txs(address, exclude_tokens=False)

        txs = list(filter(lambda tx:
                          isinstance(list(tx.values())[0].get('amount', {}), dict) and
                          list(tx.values())[0].get('amount', {}).get('contract_address') not in CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.keys(), txs))
        return txs

    def parse_tx(self, tx_info, address):
        direction = 'outgoing'
        tx_hash = tx_info.get('txid')
        input_output_info = self.get_input_output_tx(tx_info, include_info=True)
        if input_output_info is None:
            return None
        input_addresses, inputs_info, output_addresses, outputs_info = input_output_info

        addresses = set(output_addresses).difference(input_addresses)

        address = self.to_explorer_address_format(address)
        if address.lower() in map(str.lower, addresses):
            direction = 'incoming'

        tx_output_info = outputs_info.get(self.convert_address(address))
        tx_input_info = inputs_info.get(self.convert_address(address))
        transactions_info = defaultdict(lambda: Decimal('0'))
        if tx_input_info:
            for currency, value in tx_input_info.items():
                if isinstance(value, dict):
                    transactions_info[currency] = value.get('value')
                else:
                    transactions_info[currency] = value
        if tx_output_info:
            for currency, value in tx_output_info.items():
                if direction == 'outgoing':
                    if isinstance(value, dict):
                        transactions_info[currency] -= value.get('value')
                    else:
                        transactions_info[currency] -= value
                else:
                    transactions_info[currency] = value

        return {currency: {
            'date': datetime.fromtimestamp(tx_info['blockTime'], pytz.utc),
            'from_address': list(input_addresses),
            'to_address': addresses,
            'amount': transactions_info.get(currency),
            'block': int(tx_info.get('blockHeight')),
            'fee': self.from_unit(int(tx_info['fees'])),
            'hash': tx_hash,
            'confirmations': int(tx_info['confirmations']),
            'is_error': False,
            'type': 'normal',
            'kind': 'transaction',
            'direction': direction,
            'status': 'confirmed' if tx_info['confirmations'] > self.confirmed_num else 'unconfirmed',
            'raw': tx_info,
            'memo': None
        } for currency in transactions_info.keys()}

    @classmethod
    def validate_transaction(cls, tx_info):
        if cls.TOKEN_NETWORK:
            if tx_info.get('ethereumSpecific').get('status') != 1:
                return False
            if tx_info.get('tokenTransfers'):
                if tx_info.get('ethereumSpecific').get('data')[0:10] not in cls.valid_token_transfer_methods:
                    return False
            else:
                if tx_info.get('ethereumSpecific').get('data') != '0x':
                    return False
        return True

    def contract_currency(self, token_address):
        currency_with_default_contract = self.contract_currency_list.get(token_address)
        if currency_with_default_contract:
            return currency_with_default_contract, None
        if token_address in CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.keys():
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(token_address, {}).get("destination_currency"), token_address
        return None, None

    def contract_info(self, currency, contract_address=None):
        if contract_address in CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.keys():
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(contract_address, {}).get('info')
        return self.contract_info_list.get(currency)

    @classmethod
    def convert_address(cls, address):
        return address

    def get_input_tx(self, tx_info, include_info=False, is_account_format=False):
        input_addresses = set()
        inputs = tx_info.get('vin') or []
        inputs_details = defaultdict(lambda: defaultdict(dict))
        for input_tx in inputs:
            if not input_tx.get('isAddress'):
                continue
            in_address = input_tx.get('addresses') or []
            if len(in_address) != 1:
                continue
            address = self.convert_address(in_address[0])
            if not address:
                continue

            input_addresses.add(address)
            if include_info:
                target_info = tx_info if is_account_format else input_tx
                # if is_account_format:
                #     inputs_details[address][self.currency] += self.from_unit(int(tx_info['value']))
                #     continue
                # inputs_details[address][self.currency] += self.from_unit(int(input_tx['value']))
                try:
                    inputs_details[address][self.currency]['value'] += self.from_unit(int(target_info.get('value')))
                except:
                    inputs_details[address][self.currency] = {'value': self.from_unit(int(target_info.get('value')))}

        return input_addresses, inputs_details

    def get_output_tx(self, tx_info, include_info=False):
        output_addresses = set()
        outputs = tx_info.get('vout') or []
        outputs_details = defaultdict(lambda: defaultdict(dict))
        for output_tx in outputs:
            if not output_tx.get('isAddress'):
                continue
            out_address = output_tx.get('addresses') or []
            if len(out_address) != 1:
                continue
            address = self.convert_address(out_address[0])
            if not address:
                continue

            output_addresses.add(address)
            if include_info:
                # outputs_details[address][self.currency]['value'] += self.from_unit(int(output_tx['value']))
                try:
                    outputs_details[address][self.currency]['value'] += self.from_unit(int(output_tx.get('value')))
                except:
                    outputs_details[address][self.currency] = {'value': self.from_unit(int(output_tx.get('value')))}

        return output_addresses, outputs_details

    def get_input_tx_token(self, token_transfers, include_info=False):
        input_addresses = set()
        inputs_details = defaultdict(lambda: defaultdict(dict))
        for token_transfer in token_transfers:
            from_address = self.convert_address(token_transfer.get('from'))
            if not from_address:
                continue
            input_addresses.add(from_address)
            if include_info:
                token_address = (token_transfer.get('token') or token_transfer.get('contract')).lower()
                currency, contract_address = self.contract_currency(token_address)
                contract_info = self.contract_info(currency, contract_address)
                if not contract_info:
                    continue
                try:
                    inputs_details[from_address][currency]['value'] += self.from_unit(int(token_transfer.get('value')), contract_info.get('decimals'))
                except:
                    inputs_details[from_address][currency] = {'value': self.from_unit(int(token_transfer.get('value')), contract_info.get('decimals')),
                                                              'contract_address': contract_address}

        return input_addresses, inputs_details

    def get_output_tx_token(self, token_transfers, include_info=False):
        output_addresses = set()
        outputs_details = defaultdict(lambda: defaultdict(dict))
        for token_transfer in token_transfers:
            to_address = self.convert_address(token_transfer.get('to'))
            if not to_address:
                continue
            output_addresses.add(to_address)
            if include_info:
                token_address = (token_transfer.get('token') or token_transfer.get('contract')).lower()
                currency, contract_address = self.contract_currency(token_address)
                contract_info = self.contract_info(currency, contract_address)
                if not contract_info:
                    continue
                try:
                    outputs_details[to_address][currency]['value'] += self.from_unit(int(token_transfer.get('value')), contract_info.get('decimals'))
                except:
                    outputs_details[to_address][currency] = {'value': self.from_unit(int(token_transfer.get('value')), contract_info.get('decimals')),
                                                             'contract_address': contract_address}

        return output_addresses, outputs_details

    def get_input_output_tx(self, tx_info, include_info=False):
        is_token_tx = False

        # Get input and output addresses in transaction
        input_addresses = set()
        output_addresses = set()
        inputs_info = {}
        outputs_info = {}
        if self.TOKEN_NETWORK:
            if not self.validate_transaction(tx_info):
                return None
            token_transfers = tx_info.get('tokenTransfers')
            if token_transfers:
                is_token_tx = True
                input_addresses, inputs_info = self.get_input_tx_token(token_transfers, include_info=include_info)
                output_addresses, outputs_info = self.get_output_tx_token(token_transfers, include_info=include_info)

        if not is_token_tx:
            input_addresses, inputs_info = self.get_input_tx(tx_info, include_info=include_info,
                                                             is_account_format=self.TOKEN_NETWORK)
            output_addresses, outputs_info = self.get_output_tx(tx_info, include_info=include_info)
        return input_addresses, inputs_info, output_addresses, outputs_info

    def get_latest_block(self, after_block_number=None, to_block_number=None, include_inputs=False, include_info=False):
        """
            This is a huge function only used for block processing which is a process we make for most of the coins.
            It includes getting all transactions (of at most 100 blocks) and format them in a proper way to use the
            output for updating withdraws and deposits of each coin in database.
        """
        info = self.check_status_blockbook()
        if not to_block_number:
            latest_block_height_mined = info.get('blockbook', {}).get('bestHeight')
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
        max_height = min(max_height, min_height + self.max_blocks)

        # input_addresses ~ outgoing_txs and output_addresses ~ incoming_txs
        transactions_addresses = {'input_addresses': set(), 'output_addresses': set()}
        transactions_info = {'outgoing_txs': defaultdict(lambda: defaultdict(list)),
                             'incoming_txs': defaultdict(lambda: defaultdict(list))}
        print('Cache latest block height: {}'.format(latest_block_height_processed))
        print(f'Get block in range [{min_height, max_height}]')
        for block_height in range(min_height, max_height):
            page = 1
            total_pages = 1
            while page <= total_pages:
                print(f'Getting block: {block_height}, page: {page}')
                response = self.request(
                    'get_block',
                    block=block_height,
                    page=page
                )
                print(f'Block: {block_height}, page: {page}')
                if not response:
                    raise APIError('Get block API returns empty response')
                if response.get('error'):
                    raise APIError(f'Get block API error: {info.get("error")}')

                total_pages = response.get('totalPages') or 1

                transactions = response.get('txs') or []
                for tx_info in transactions:
                    input_output_info = self.get_input_output_tx(tx_info, include_info=include_info)
                    if input_output_info is None:
                        continue
                    input_addresses, inputs_info, output_addresses, outputs_info = input_output_info
                    tx_hash = tx_info.get('txid')
                    if not tx_hash:
                        continue
                    addresses = set(output_addresses).difference(input_addresses)
                    transactions_addresses['output_addresses'].update(addresses)

                    if include_inputs:
                        transactions_addresses['input_addresses'].update(input_addresses)

                    if include_info:
                        for address in transactions_addresses['output_addresses']:
                            tx_output_info = outputs_info[address]
                            if not tx_output_info:
                                continue
                            for token, details in tx_output_info.items():
                                transactions_info['incoming_txs'][address][token].append({
                                    'tx_hash': tx_hash,
                                    'value': details['value'],
                                    'contract_address': details.get('contract'),
                                    'block_height': block_height,
                                    'symbol': get_currency_symbol_from_currency_code(token)
                                })
                        if include_inputs:
                            for address in transactions_addresses['input_addresses']:
                                tx_output_info = outputs_info[address]
                                tx_input_info = inputs_info[address]
                                if not tx_input_info:
                                    continue
                                for coin, details in tx_input_info.items():
                                    output_value = details['value'] - tx_output_info.get(coin, {}).get('value', Decimal('0'))
                                    if coin == self.currency and not self.TOKEN_NETWORK:
                                        output_value -= self.from_unit(int(tx_info.get('fees', 0)))
                                    transactions_info['outgoing_txs'][address][coin].append({
                                        'tx_hash': tx_hash,
                                        'value': output_value,
                                        'contract_address': details.get('contract_address'),
                                        'block_height': block_height,
                                        'symbol': get_currency_symbol_from_currency_code(coin)
                                    })
                page += 1

        last_cache_value = cache.get(f'latest_block_height_processed_{self.cache_key}') or 0
        if max_height - 1 > last_cache_value:
            metric_set(name='latest_block_processed', labels=[self.symbol.lower()], amount=max_height - 1)
            cache.set(f'latest_block_height_processed_{self.cache_key}', max_height - 1, 24 * 60 * 60)
        return transactions_addresses, transactions_info, max_height - 1

    def to_explorer_address_format(self, address):
        return address


