import datetime
import random
from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.core.cache import cache

from exchange.base.models import Currencies
from exchange.blockchain.api.bsc.bscscan import BscScanAPI
from exchange.blockchain.contracts_conf import BEP20_contract_currency, BEP20_contract_info
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


def are_addresses_equal(addr1, addr2):
    if not addr1 or not addr2:
        return False
    addr1 = addr1.lower()
    if not addr1.startswith('0x'):
        addr1 = '0x' + addr1
    addr2 = addr2.lower()
    if not addr2.startswith('0x'):
        addr2 = '0x' + addr2
    return addr1 == addr2


# So unreliable, that we gave it up (do not give token transfers, do not give value in get_block etc.)
class MoralisAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    Moralis
    API docs: https://deep-index.moralis.io/api-docs/
    Explorer: https://moralis.io
    """

    currency = Currencies.bnb
    symbol = 'ETH'
    PRECISION = 18
    cache_key = 'bsc'

    _base_url = 'https://deep-index.moralis.io'
    # testnet_url = 'https://api-testnet.bscscan.com'
    rate_limit = 0.034  # (30 req/sec)

    def get_name(self):
        return 'moralis_api'

    supported_requests = {
        'get_block': '/api/v2/block/{block_no}?chain=bsc',
        'get_txs': '/api/v2/{address}?chain=bsc&offset={offset}',
        'get_txs_from_block': '/api/v2/{address}?chain=bsc&from_block={from_block}',
        'get_token_txs': '/api/v2/{address}/erc20/transfers?chain=bsc&limit={limit}',
        'get_balance': '/api/v2/{address}/balance?chain=bsc',
        'get_token_balance': '/api/v2/{address}/erc20?chain=bsc',
        'get_tx_details': '/api/v2/transaction/{tx_hash}?chain=bsc',
    }

    @property
    def contract_currency_list(self):
        return BEP20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return BEP20_contract_info.get(self.network)

    def get_balance(self, address):
        self.validate_address(address)
        self.api_key_header = {'X-API-Key': f'{random.choice(settings.MORALIS_API_KEY)}'}
        response = self.request('get_balance', address=address, headers={'Content-Type': 'application/json'})

        try:
            balance = self.from_unit(int(response.get('balance')))
        except (ValueError, Exception) as error:
            raise APIError(f'Moralis bad value: {response.get("balance")}. Raise: {error}')
        return {
            self.currency: {
                'address': address,
                'amount': balance,
            }
        }

    def get_token_balance(self, address, contracts_info=None):
        self.validate_address(address)
        self.api_key_header = {'X-API-Key': f'{random.choice(settings.MORALIS_API_KEY)}'}
        response = self.request('get_token_balance', address=address)
        balances = defaultdict()
        for token_info in response:
            contract_currency = self.contract_currency_list.get(token_info.get("token_address").lower())
            if contract_currency is None:
                continue
            contract_info = self.contract_info_list.get(contract_currency)
            try:
                balance = self.from_unit(int(token_info.get('balance')), contract_info.get('decimals'))
                balances[contract_currency] = {
                    'amount': balance,
                    'address': address,
                }
            except (ValueError, Exception) as error:
                raise APIError(f'Moralis bad value: {token_info.get("balance")}. Raise: {error}')
        return balances

    def get_txs(self, address, limit=25):
        transactions = []
        self.api_key_header = {'X-API-Key': f'{random.choice(settings.MORALIS_API_KEY)}'}
        response = self.request(
            'get_txs',
            address=address,
            offset=0,
            headers={'Content-Type': 'application/json'}
        )
        txs = response.get('result', [])[:limit]
        for tx in txs:
            if tx.get('receipt_status') != '1':
                continue
            if tx.get('input') != '0x':
                continue
            value = self.from_unit(int(tx.get('value')))
            if are_addresses_equal(tx.get('from_address'), address):
                value = -value
            elif not are_addresses_equal(tx.get('to_address'), address):
                value = Decimal('0')
            elif are_addresses_equal(tx.get('from_address'),
                                     '0x70Fd2842096f451150c5748a30e39b64e35A3CdF') or are_addresses_equal(
                tx.get('from'), '0x491fe5F4724e642C90372B0B95b60c4aC8d13F1c') or are_addresses_equal(
                tx.get('from'), '0xB256caa23992e461E277CfA44a2FD72E2d6d2344') or are_addresses_equal(
                tx.get('from'), '0x06cC26db08674CbD9FF4d52444712E23cA3d046d'):
                value = Decimal('0')
            tx_date = parse_iso_date(tx.get('block_timestamp'))
            transactions.append({
                self.currency: {
                    'address': address,
                    'from_address': [tx.get('from_address')],
                    'block': tx.get('block_number'),
                    'hash': tx.get('hash'),
                    'date': tx_date,
                    'confirmations': self.calculate_tx_confirmations(tx_date),
                    'amount': value,
                    'raw': tx,
                    'memo': None
                }
            })
        return transactions

    def get_token_txs(self, address, contract_info=None, limit=25):
        transactions = []
        self.api_key_header = {'X-API-Key': f'{random.choice(settings.MORALIS_API_KEY)}'}
        response = self.request(
            'get_token_txs',
            address=address,
            limit=limit,
            headers={'Content-Type': 'application/json'}
        )
        txs = response.get('result', [])
        for tx in txs:
            currency = self.contract_currency_list.get(tx.get('address'))
            if currency is None:
                continue
            value = self.from_unit(int(tx.get('value')), self.contract_info_list.get(currency).get('decimals'))
            if are_addresses_equal(tx.get('from_address'), address):
                value = -value
            elif not are_addresses_equal(tx.get('to_address'), address):
                value = Decimal('0')
            elif are_addresses_equal(tx.get('from_address'),
                                     '0x70Fd2842096f451150c5748a30e39b64e35A3CdF') or are_addresses_equal(
                tx.get('from'), '0x491fe5F4724e642C90372B0B95b60c4aC8d13F1c') or are_addresses_equal(
                tx.get('from'), '0xB256caa23992e461E277CfA44a2FD72E2d6d2344') or are_addresses_equal(
                tx.get('from'), '0x06cC26db08674CbD9FF4d52444712E23cA3d046d'):
                value = Decimal('0')

            tx_date = parse_iso_date(tx.get('block_timestamp'))
            transactions.append({
                currency: {
                    'address': address,
                    'from_address': [tx.get('from_address')],
                    'block': tx.get('block_number'),
                    'hash': tx.get('transaction_hash'),
                    'date': tx_date,
                    'confirmations': self.calculate_tx_confirmations(tx_date),
                    'amount': value,
                    'raw': tx,
                    'memo': None
                }
            })
        return transactions

    def get_latest_block(self, after_block_number=None, to_block_number=None, include_inputs=False, include_info=True):
        if not to_block_number:
            block_head = BscScanAPI.get_api().check_block_status()
            latest_block_height_mined = int(block_head.get('result'), 16)
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

        transactions_addresses = set()
        transactions_info = defaultdict(lambda: defaultdict(list))
        print('Cache latest block height: {}'.format(latest_block_height_processed))
        for block_height in range(min_height, max_height):
            self.api_key_header = {'X-API-Key': f'{random.choice(settings.MORALIS_API_KEY)}'}
            response = self.request('get_block', block_no=block_height)
            transactions = response.get('transactions') or []
            for tx_info in transactions:
                if tx_info.get('receipt_status') != '1':
                    continue
                tx_hash = tx_info.get('hash')
                if not tx_hash:
                    continue
                if not (tx_info.get('input') == '0x' or tx_info.get('input')[0:10] == '0xa9059cbb'):
                    continue
                tx_data = self.get_transaction_data(tx_info)
                if tx_data is None:
                    continue
                from_address = tx_data.get('from')
                to_address = tx_data.get('to')
                value = tx_data.get('value')
                currency = tx_data.get('currency')

                transactions_addresses.update([to_address])
                if include_inputs:
                    transactions_addresses.update([from_address])

                if include_info:
                    if include_inputs:
                        transactions_info[from_address][currency].append({
                            'tx_hash': tx_hash,
                            'value': value,
                            'direction': 'outgoing',
                        })
                    transactions_info[to_address][currency].append({
                        'tx_hash': tx_hash,
                        'value': value,
                        'direction': 'incoming',
                    })
        cache.set(f'latest_block_height_processed_{self.cache_key}', max_height - 1, 86400)
        return set(transactions_addresses), transactions_info, max_height - 1

    def get_transaction_data(self, tx_info):
        input_ = tx_info.get('input')
        if input_ == '0x' or input_ == '0x0000000000000000000000000000000000000000':
            value = self.from_unit(int(tx_info.get('value', 0)))
            to_address = tx_info.get('to_address')
            from_address = tx_info.get('from_address')
            currency = self.currency
        else:
            to_address = '0x' + tx_info.get('input')[34:74]
            from_address = tx_info.get('from_address')
            currency = self.contract_currency_list.get(tx_info.get('to'))
            if currency is None:
                return
            contract_info = self.contract_info_list.get(currency)
            value = self.from_unit(int(tx_info.get('input')[74:138], 16), contract_info.get('decimals'))
        return {
            'from': from_address,
            'to': to_address,
            'value': value,
            'currency': currency,
        }

    @classmethod
    def calculate_tx_confirmations(cls, tx_date):
        diff = (datetime.datetime.now(datetime.timezone.utc) - tx_date).total_seconds()
        return int(diff / 3.2)  # BSC block time is 3 seconds, for more reliability we get it for '3.2'.

    def get_tx_details(self, tx_hash):
        headers = {'X-API-Key': f'{random.choice(settings.MORALIS_API_KEY)}'}

        try:
            response = self.request('get_tx_details', headers=headers, tx_hash=tx_hash)
        except Exception as e:
            raise APIError("[ETH ethplorer API][Get Transaction details] unsuccessful\nError:{}".format(e))

        tx = self.parse_tx_details(response)
        return tx

    def parse_tx_details(self, tx_info):
        tx_time = parse_iso_date(tx_info.get('block_timestamp'))
        tx_conf = self.calculate_tx_confirmations(tx_time)
        return {
            'from': tx_info.get('from_address'),
            'to': tx_info.get('to_address'),
            'block': tx_info.get('block_number'),
            'timestamp': tx_time,
            'value': self.from_unit(int(tx_info.get('value'))),
            'confirmations': tx_conf,
            'raw': tx_info,
        }
