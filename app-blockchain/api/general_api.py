from abc import ABC
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any

from django.conf import settings

from exchange.blockchain.utils import Service, APIError, get_address_info, ValidationError, RateLimitError, ParseError


class NobitexBlockchainAPI(Service, ABC):
    symbol: str
    currency: int
    start_offset = 0
    max_items_per_page = None
    page_offset_step = 1
    confirmed_num = 0
    testnet_url = None
    network = 'mainnet'
    XPUB_SUPPORT = False
    # USE_PROXY = True if settings.IS_PROD and settings.NO_INTERNET and not settings.IS_VIP else False
    USE_PROXY = False
    blockchain_api = None
    headers: dict = dict()
    PRECISION = 0
    PAGINATION_LIMIT = 25
    PAGINATION_OFFSET = 0
    PAGINATION_PAGE = 1
    valid_transfer_types = ['']
    get_txs_keyword = ''
    get_incoming_txs_keyword = ''
    get_outgoing_txs_keyword = ''
    min_valid_tx_amount = Decimal('0.0')
    tries = 5  # in case of API connection error
    backoff_delay = 0.5  # second
    BLOCK_TIME = None  # second
    TRANSACTION_DETAILS_BATCH = False
    SUPPORT_GET_BALANCE_BATCH = False
    SUPPORT_BLOCK_HEAD = False
    GET_BALANCES_MAX_ADDRESS_NUM = 0

    def __init__(self, network='mainnet', api_key=None):
        Service.__init__(self, api_key)
        self.network = network
        self.update_network()

    @classmethod
    def get_api(cls, *args, **kwargs):
        kwargs.pop('is_provider_check', None)
        # this is required to prevent unexpected argument exception for old structures
        if cls.blockchain_api is None:
            cls.blockchain_api = cls(*args, **kwargs)
        return cls.blockchain_api

    @staticmethod
    def get_header():
        return None

    def get_balance(self, address):
        self.validate_address(address)
        try:
            response = self.request('get_balance', address=address, headers=self.get_header(),
                                    body=self.get_balance_body(address))
        except ConnectionError:
            raise APIError(f'{self.symbol} API: Failed to get Balance, connection error')
        if response is None:
            raise APIError(f'{self.symbol} API: Get Balance response is None')
        try:
            balance_amount = self.parse_balance(response)
        except TypeError:
            raise APIError(f'{self.symbol} API: Failed to parse balance response: {response}')
        return {
            self.currency: {
                'symbol': self.symbol,
                'amount': balance_amount,
                'address': address
            }
        }

    def get_balances(self, addresses):
        chunk_addresses, balances = [], []
        for i in range(0, len(addresses), self.GET_BALANCES_MAX_ADDRESS_NUM):
            chunk_addresses.append(addresses[i:i + self.GET_BALANCES_MAX_ADDRESS_NUM])
        for address in addresses:
            self.validate_address(address)
        for chunk_list in chunk_addresses:
            formatted_addresses = self.format_batch_addresses(chunk_list)
            try:
                response = self.request('get_balances',
                                        addresses=formatted_addresses,
                                        headers=self.get_header(),
                                        body=self.get_balances_body(chunk_addresses))
            except ConnectionError:
                raise APIError(f'{self.symbol} API: Failed to get Balances, connection error')
            if response is None:
                raise APIError(f'{self.symbol} API: Get Balances response is None')
            try:
                balances.extend(self.parse_balances(response))
            except TypeError:
                raise APIError(f'{self.symbol} API: Failed to parse balance response: {response}')
        return balances

    def get_block_head(self):
        try:
            response = self.request('get_block_head', headers=self.get_header(), api_key=self.get_api_key(), body=self.get_block_head_body())
        except ConnectionError:
            raise APIError(f'{self.symbol} API:Failed to get Block Head, connection error')
        if not response:
            raise APIError(f'{self.symbol} API: get_block_head: Response is none')
        try:
            block_height = self.parse_block_head(response)
        except AttributeError:
            raise APIError(f'{self.symbol} API: Failed to parse block_head. response:{response}')
        return block_height

    def get_txs(self, address, tx_direction_filter='incoming', limit=25):
        if tx_direction_filter == 'incoming':
            tx_query_direction = self.get_incoming_txs_keyword
        elif tx_direction_filter == 'outgoing':
            tx_query_direction = self.get_outgoing_txs_keyword
        else:
            raise APIError(f'incorrect arg tx_query_direction = {tx_direction_filter}')

        self.validate_address(address)
        address = self.to_api_valid_address(address)
        try:
            response = self.request('get_txs',
                                    headers=self.get_header(),
                                    pagination_offset=self.PAGINATION_OFFSET,
                                    pagination_limit=self.PAGINATION_LIMIT,
                                    pagination_page=self.PAGINATION_PAGE,
                                    tx_query_direction=tx_query_direction,
                                    api_key=self.get_api_key(),
                                    address=address,
                                    body=self.get_txs_body(address))
        except ConnectionError:
            raise APIError(f'{self.symbol} API: Failed to get txs, connection error')
        if not response:
            raise APIError(f'{self.symbol} API: Get Txs response is None')

        transactions = []
        try:
            txs = self.parse_get_txs_response(response)
        except AttributeError:
            raise APIError(f'{self.symbol} API: Failed to parse get_txs. response:{response}')
        if not self.SUPPORT_BLOCK_HEAD:
            block_head = self.get_block_head()
        else:
            block_head = None
        for tx in txs:
            if self.validate_transaction(tx, address):
                parsed_tx = self.parse_tx(tx, address, block_head)
                if parsed_tx:
                    transactions.append(parsed_tx)
        return transactions

    def parse_get_txs_response(self, response):
        if self.get_txs_keyword:
            return response.get(self.get_txs_keyword)
        return response

    def get_token_txs(self, address, currency=0, contract_info=None, contract_address=None, direction=''):
        if not currency and not contract_address:
            contract_address = contract_info.get('address')
        self.validate_address(address)
        response = self.request('get_token_txs', address=address, token='')
        if response is None:
            raise APIError(f'[{self.symbol}][Get Token Transactions] response is None')
        txs = self.parse_token_txs(response)
        if txs is None:
            return []

        if not currency:
            currency = self.contract_currency(contract_address)
        transactions = []
        for tx in txs:
            if self.validate_token_transaction(tx, currency):
                parsed_tx = self.parse_token_tx(tx, address)
                if parsed_tx is not None:
                    transactions.append(parsed_tx)
        return transactions

    def get_tx_details(self, tx_hash):
        try:
            response = self.request('get_tx_details', headers=self.get_header(), api_key=self.get_api_key(),
                                    tx_hash=tx_hash, body=self.get_details_body(tx_hash))
        except ConnectionError:
            raise APIError(f'{self.symbol} API: Failed to get_tx_details, connection error')
        if not response:
            raise APIError(f'{self.symbol}: get_tx_detail Response is none')
        try:
            tx_details = self.parse_tx_details(response, tx_hash=tx_hash)
        except AttributeError:
            raise ParseError(f'{self.symbol} parsing error Tx is {response}.')
        return tx_details

    def to_api_valid_address(self, address):
        return address

    def get_txs_body(self, address):
        return None

    def get_details_body(self, tx_hash):
        return None

    def get_balance_body(self, address):
        return None

    def get_balances_body(self, addresses):
        return None

    def get_block_head_body(self):
        return None

    def get_api_key(self):
        return None

    def validate_address(self, address):
        address_info = get_address_info(self.symbol, address)
        if not bool(address_info):
            raise ValidationError('Address not valid')
        if address_info.network == 'test' and self.network == 'mainnet':
            raise ValidationError('Testnet address send to mainnet setup')

    def update_network(self):
        if self.network == 'testnet':
            if self.testnet_url:
                self.base_url = self.testnet_url
            else:
                raise ValueError("API doesn't support testnet.")

    def _load(self, data):
        from decimal import Decimal

        if isinstance(data, dict):
            for key in data:
                data[key] = self._load(data[key])
            return data
        elif isinstance(data, list):
            for i, elem in enumerate(data):
                data[i] = self._load(elem)
            return data
        elif isinstance(data, str):
            new = None
            try:
                new = Decimal(data)
            except ValueError:
                new = data
            finally:
                return new
        else:
            return data

    def request(self, request_method: str, with_rate_limit: bool = True,
                body: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None,
                timeout: int = 30, proxies: Optional[Dict[str, str]] = None,
                force_post: bool = False, **params: Any) -> Dict[str, Any]:
        if headers is None:
            headers = dict()
        headers = {**headers, **self.headers}  # Merge two dicts (function parameter and class property)
        if proxies is None:
            if self.USE_PROXY:
                proxies = settings.DEFAULT_PROXY
        if self.backoff > datetime.now():
            diff = (self.backoff - datetime.now()).total_seconds()
            raise RateLimitError(f'Remaining {diff} seconds of backoff')
        return super(NobitexBlockchainAPI, self).request(
            request_method=request_method, with_rate_limit=with_rate_limit,
            body=body, headers=headers, timeout=timeout, proxies=proxies,
            force_post=force_post, **params)

    def get_contract_info(self, contract_address):
        currency = self.contract_currency(contract_address)
        if not currency:
            return (None, ) * 3

        contract_info = self.contract_info(currency)

        return currency, contract_info.get('symbol'), contract_info.get('decimals')

    def contract_currency(self, token_address):
        return self.contract_currency_list.get(token_address)

    def contract_info(self, currency):
        return self.contract_info_list.get(currency)

    def get_tx_direction(self, tx, address):
        to_address = self.parse_tx_receiver(tx).casefold()
        from_address = self.parse_tx_sender(tx).casefold()
        # check self transaction
        if to_address == from_address:
            return None
        if address.casefold() == to_address:
            return 'incoming'
        elif address.casefold() == from_address:
            return 'outgoing'
        else:
            return None

    @property
    def contract_currency_list(self):
        return {}

    @property
    def contract_info_list(self):
        return {}

    def validate_tx_amount(self, value):
        return value > self.min_valid_tx_amount

    def parse_balance(self, response):
        return 0

    def parse_balances(self, response):
        return []

    def validate_transaction(self, tx, address=None):
        return {}

    def validate_token_transaction(self, tx, currency, direction=''):
        return {}

    def parse_block_head(self, response):
        return 0

    def parse_tx(self, tx, address, block_head=None):
        return {}

    def parse_tx_details(self, tx, tx_hash=None):
        return {}

    def parse_token_txs(self, data):
        return {}

    def parse_token_tx(self, tx, address):
        return {}

    def validate_transaction_detail(self, details):
        return

    def parse_tx_receiver(self, tx):
        return

    def parse_tx_sender(self, tx):
        return

    @classmethod
    def estimate_confirmation_by_date(cls, tx_date: datetime):
        """
        Estimate tx confirmation as a time duration from now divided by network average block time
        """
        diff = (datetime.now(timezone.utc) - tx_date).total_seconds()
        return int(diff / cls.BLOCK_TIME)

    def format_batch_addresses(self, addresses):
        separator = ','
        return separator.join(addresses)
