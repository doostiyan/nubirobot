from collections import defaultdict
from decimal import Decimal

from django.core.cache import cache

from django.conf import settings
from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.models import get_token_code, CurrenciesNetworkName
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.metrics import metric_set


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


class BlockScanAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: Ethereum
    API docs: https://etherscan.io/apis
    :exception ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut
    """

    active = True
    rate_limit = 0.2
    PRECISION = 18
    max_items_per_page = 20  # 20 for get_txs
    page_offset_step = None
    confirmed_num = None

    supported_requests = {
        'get_transactions': '/api?module=account&action=txlist&address={address}&page=1&offset=50&sort=desc&apikey={'
                            'api_key}',
        'get_transaction': '/api?module=proxy&action=eth_getTransactionByHash&txhash={hash}&apikey={api_key}',
        'get_balance': '/api?module=account&action=balance&address={address}&tag=latest&apikey={api_key}',
        'get_balances': '/api?module=account&action=balancemulti&address={address}&tag=latest&apikey={api_key}',
        'get_block_info': '/api?module=proxy&action=eth_blockNumber&apikey={api_key}',
        'get_block': '/api?module=proxy&action=eth_getBlockByNumber&tag={block}&boolean=true&apikey={api_key}',
        'get_token_balance': '/api?module=account&action=tokenbalance&contractaddress={contract_address}&address={'
                             'address}&tag=latest&apikey={api_key}',
        'get_token_txs': '/api?module=account&action=tokentx&contractaddress={contract_address}&address={'
                         'address}&page=1&offset=50&sort=desc&apikey={api_key}',
    }

    def get_name(self):
        return 'scan_api'

    @property
    def contract_currency_list(self):
        return

    @property
    def contract_info_list(self):
        return

    @property
    def headers(self):
        return {
            'User-Agent': 'Mozilla/5.0' if not settings.IS_VIP else
            'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0'
        }

    def get_api_key(self):
        pass

    def get_balances(self, addresses):
        for address in addresses:
            self.validate_address(address)
        addresses = ','.join(addresses)
        api_key = self.get_api_key()
        response = self.request('get_balances', address=addresses, headers=self.headers, api_key=api_key)
        if response is None:
            raise APIError(f'[{self.__class__.__name__}][Get Balances] response is None')
        response_info = response.get('result')
        balances = []
        for addr_info in response_info:
            addr = addr_info['account']
            balances.append({
                'address': addr,
                'balance': self.from_unit(int(addr_info['balance'])),
            })
        return balances

    def get_balance(self, address):
        self.validate_address(address)
        api_key = self.get_api_key()
        response = self.request('get_balance', address=address, headers=self.headers, api_key=api_key)
        if response is None:
            raise APIError(f'[{self.__class__.__name__}][Get Balance] response is None')
        if response.get('status') == '0':
            raise APIError(f"[{self.__class__.__name__}][Get Balance] {response.get('result')}")
        balance = self.from_unit(int(response.get('result', 0)))
        return {
            'address': address,
            'amount': balance,
        }

    def get_token_balance(self, address, contracts_info):
        if type(list(contracts_info.values())[0]) is dict:
            contract_info = list(contracts_info.values())[0]
        else:
            contract_info = contracts_info
        self.validate_address(address)
        api_key = self.get_api_key()
        response = self.request('get_token_balance',
                                address=address,
                                api_key=api_key,
                                contract_address=contract_info.get('address'),
                                headers=self.headers)
        if response is None:
            raise APIError(f'[{self.__class__.__name__}][Get Balance] response is None')
        if response.get('status') == '0':
            raise APIError(f"[{self.__class__.__name__}][Get Balance] {response.get('result')}")
        balance = self.from_unit(int(response.get('result', 0)), contract_info.get('decimals'))
        return {
            'address': address,
            'amount': balance,
        }

    def get_tx_details(self, tx_hash, offset=None, limit=None, unconfirmed=False):
        api_key = self.get_api_key()
        response = self.request('get_transaction', hash=tx_hash, api_key=api_key, headers=self.headers)
        tx = self.parse_tx_details(response.get('result'))
        return tx

    def parse_tx_details(self, tx):
        inputs = []
        outputs = []
        transfers = {}
        tx_info = self.get_transaction_data(tx, tx.get('input'))
        if tx_info:
            transfers.update({tx_info.get('currency'): {
                'type': 'BEP20',
                'symbol': tx_info.get('symbol'),
                'from': tx_info.get('from'),
                'to': tx_info.get('to'),
                'token': tx_info.get('token'),
                'name': '',
                'value': tx_info.get('amount'),
            }})
        return {
            'hash': tx.get('hash'),
            'success': True,
            'inputs': inputs,
            'outputs': outputs,
            'transfers': transfers,
            'block': int(tx.get('blockNumber'), 16),
            'confirmations': int(self.check_block_status().get('result'), 16) - int(tx.get('blockNumber'), 16),
        }

    def get_txs(self, address, offset=None, limit=None, unconfirmed=False):
        self.validate_address(address)
        api_key = self.get_api_key()
        response = self.request('get_transactions', address=address, api_key=api_key, headers=self.headers)
        if not response:
            raise APIError(f'[{self.__class__.__name__}][Get Transactions] response is None')
        if response.get('message') != 'OK' or response.get('message') == 'No transactions found':
            return []
        info = response.get('result')

        # Parse transactions
        transactions = []
        for tx in info:
            if tx.get('txreceipt_status') == '1' and tx.get('isError') == '0':
                if self.validate_transaction(tx.get('input')):
                    parsed_tx = self.parse_tx(tx, address)
                    if parsed_tx is not None:
                        transactions.append(parsed_tx)
        return transactions

    def get_token_txs(self, address, contract_info, direction=''):
        self.validate_address(address)
        api_key = self.get_api_key()
        response = self.request('get_token_txs', address=address, api_key=api_key, contract_address=contract_info.get('address'))
        if not response:
            raise APIError(f'[{self.__class__.__name__}][Get Transactions] response is None')
        if response.get('message') != 'OK' or response.get('message') == 'No transactions found':
            return []
        info = response.get('result')

        transactions = []
        for tx in info:
            parsed_tx = self.parse_tx(tx, address, contract_info.get('address'))
            if parsed_tx is not None:
                transactions.append(parsed_tx)
        return transactions

    def parse_tx(self, tx, address, contract_address=None):
        if tx.get('contractAddress'):
            if tx.get('contractAddress') != contract_address:
                return
            currency, _ = self.contract_currency(tx.get('contractAddress'))
            if currency is None:
                return
            contract_info = self.contract_info(currency, contract_address)
            value = self.from_unit(int(tx.get('value')), contract_info.get('decimals'))
        else:
            currency = self.currency
            value = self.from_unit(int(tx.get('value', 0)))
            if value == 0:
                return

        # Process transaction types
        if are_addresses_equal(tx.get('from'), address):
            # Transaction is from this address, so it is a withdraw
            value = -value
        elif not are_addresses_equal(tx.get('to'), address):
            # Transaction is not to this address, and is not a withdraw, so no deposit should be made
            #  this is a special case and should not happen, so we ignore such special transaction (value will be zero)
            value = Decimal('0')

        elif are_addresses_equal(tx.get('from'),
                                 '0x70Fd2842096f451150c5748a30e39b64e35A3CdF') or are_addresses_equal(
            tx.get('from'), '0x491fe5F4724e642C90372B0B95b60c4aC8d13F1c') or are_addresses_equal(
            tx.get('from'), '0xB256caa23992e461E277CfA44a2FD72E2d6d2344') or are_addresses_equal(
            tx.get('from'), '0x06cC26db08674CbD9FF4d52444712E23cA3d046d') or are_addresses_equal(
            tx.get('from'), '0x4752B9bD4E73E2f52323E18137F0E66CDDF3f6C9'
        ):
            value = Decimal('0')
        return {
            currency: {
                'address': address,
                'from_address': [tx.get('from')],
                'block': int(tx.get('blockNumber')),
                'hash': tx.get('hash'),
                'date': parse_utc_timestamp(tx.get('timeStamp')),
                'amount': value,
                'confirmations': int(tx.get('confirmations', 0)),
                'raw': tx,
                'memo': None
            }
        }

    def contract_currency(self, token_address):
        currency_with_default_contract = self.contract_currency_list.get(token_address)
        if currency_with_default_contract:
            return currency_with_default_contract, None
        if token_address in CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.keys():
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(token_address, {}).get(
                'destination_currency'), token_address
        return None, None

    def contract_info(self, currency, contract_address=None):
        if contract_address in CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.keys():
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(contract_address, {}).get('info')
        return self.contract_info_list.get(currency)

    @classmethod
    def decode_tx_input_data(cls, input_data):
        return {
            'value': int(input_data[74:138], 16),
            'to': '0x' + input_data[34:74]
        }

    def get_transaction_data(self, tx_info, input_data):
        token = ''
        if input_data == '0x' or input_data == '0x0000000000000000000000000000000000000000':
            value = self.from_unit(int(tx_info.get('value'), 16))
            to_address = tx_info.get('to')
            from_address = tx_info.get('from')
            currency = self.currency
            symbol = self.symbol
        else:
            currency, contract_address = self.contract_currency(tx_info.get('to'))
            if currency is None:
                return
            decoded_input_data = self.decode_tx_input_data(input_data)
            to_address = decoded_input_data.get('to')
            from_address = tx_info.get('from')
            contract_info = self.contract_info(currency, contract_address)
            value = decoded_input_data.get('value')
            if currency == get_token_code('1b_babydoge', 'bep20'):
                value -= value * 0.1
            value = self.from_unit(value, contract_info.get('decimals'))
            symbol = contract_info.get('symbol')
            token = tx_info.get('to')
        return {
            'from': from_address,
            'to': to_address,
            'amount': value,
            'currency': currency,
            'symbol': symbol,
            'token': token,
        }

    def check_block_status(self):
        api_key = self.get_api_key()
        info = self.request('get_block_info', api_key=api_key)
        if not info:
            raise APIError('Empty info')
        if not info.get('result'):
            raise APIError('Invalid info')
        return info

    def get_block_head(self):
        return self.check_block_status()

    # Note: in this method we could not recognize if a detected transaction was successfully done or not (to skip it in
    # block processing if it was not successful)
    def get_latest_block(self, after_block_number=None, to_block_number=None, include_inputs=False, include_info=False):
        info = self.check_block_status()
        if not to_block_number:
            latest_block_height_mined = int(info.get('result'), 16)
            if not latest_block_height_mined:
                raise APIError('API Not Return block height')
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
        if max_height - min_height > 100:
            max_height = min_height + 100

        # input_addresses ~ outgoing_txs and output_addresses ~ incoming_txs
        transactions_addresses = {'input_addresses': set(), 'output_addresses': set()}
        transactions_info = {'outgoing_txs': defaultdict(lambda: defaultdict(list)),
                             'incoming_txs': defaultdict(lambda: defaultdict(list))}
        print('Cache latest block height: {}'.format(latest_block_height_processed))
        for block_height in range(min_height, max_height):
            api_key = self.get_api_key()
            response = self.request('get_block', block=hex(block_height), api_key=api_key)
            if not response:
                raise APIError('Get block API returns empty response')
            if response.get('status') == '0':
                raise APIError(f'Get block API error: {info.get("result")}')

            transactions = response.get('result').get('transactions')
            if transactions is None:
                continue
            for tx_info in transactions:
                tx_hash = tx_info.get('hash')
                if not tx_hash:
                    continue
                if not self.validate_transaction(tx_info.get('input')):
                    continue
                tx_data = self.get_transaction_data(tx_info, tx_info.get('input'))
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
        cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}', max_height - 1,
                  86400)
        return transactions_addresses, transactions_info, max_height - 1

    @classmethod
    def validate_transaction(cls, input_data):
        if input_data == '0x' or input_data == '0x0000000000000000000000000000000000000000':
            return True
        if input_data[0:10] == '0xa9059cbb' and len(input_data) == 138:
            return True
        return False


