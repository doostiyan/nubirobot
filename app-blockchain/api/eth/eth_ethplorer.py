import random
from decimal import Decimal
import datetime

from django.conf import settings
from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.contracts_conf import ERC20_contract_info, ERC20_contract_currency
from exchange.blockchain.api.common_apis.blockscan import are_addresses_equal
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class EthplorerAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: Ethereum
    API docs: https://github.com/EverexIO/Ethplorer/wiki/Ethplorer-API
    :exception ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut
    """

    active = True
    _base_url = 'https://api.ethplorer.io/'
    testnet_url = 'https://kovan-api.ethplorer.io'
    symbol = 'ETH'
    rate_limit = 0.5
    PRECISION = 18
    max_items_per_page = 20  # 20 for get_txs
    page_offset_step = None
    confirmed_num = None

    supported_requests = {
        'get_transactions': 'getAddressTransactions/{address}?apiKey={api_key}',
        'get_tx_details': 'getTxInfo/{tx_hash}?apiKey={api_key}'
    }

    def get_name(self):
        return 'ethplorer_api'

    def get_txs(self, address, offset=None, limit=None, unconfirmed=False):
        self.validate_address(address)
        api_key = random.choice(settings.ETHPLORER_API_KEYS)
        response = self.request('get_transactions', address=address, api_key=api_key)
        if not response:
            raise APIError("[EthplorerAPI][Get Transactions] response is None")

        # Parse transactions
        transactions = []
        for tx in response:
            if tx.get('success'):
                parsed_tx = self.parse_tx(tx, address)
                if parsed_tx is not None:
                    transactions.append(parsed_tx)
        return transactions

    def parse_tx(self, tx, address):
        value = self.from_unit(int(tx.get('value', 0)))

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
            tx.get('from'), '0x06cC26db08674CbD9FF4d52444712E23cA3d046d'):
            value = Decimal('0')

        return {
            'address': address,
            'hash': tx.get('hash'),
            'date': parse_utc_timestamp(tx.get('timestamp')),
            'amount': value,
            'confirmations': 13 if tx.get('success') else 0,
            'raw': tx,
        }

    def get_tx_details(self, tx_hash):
        try:
            api_key = random.choice(settings.ETHPLORER_API_KEYS)
            response = self.request('get_tx_details', tx_hash=tx_hash, api_key=api_key)
        except Exception as e:
            raise APIError(f"[ETH ethplorer API][Get Transaction details] unsuccessful:{e}")

        tx = self.parse_tx_details(response)
        return tx

    def parse_tx_details(self, tx_info):
        tx_time = datetime.datetime.fromtimestamp(tx_info.get('timestamp'))
        tx_block = tx_info.get('blockNumber')
        tx_sender = tx_info.get('from')
        tx_receiver = tx_info.get('to')
        tx_conf = tx_info.get('confirmations')
        operations = None
        if tx_info.get('operations'):
            operations = []  # token transfers mostly
            for tr in tx_info.get('operations'):
                currency = self.contract_currency(tr.get('tokenInfo').get('address'))
                if currency is None:
                    continue
                contract_info = self.contract_info(currency)
                operations.append(
                    {
                        'type': tr.get('type'),
                        'from': tr.get('from'),
                        'to': tr.get('to'),
                        'isEth': tr.get('isEth'),
                        'toke_symbol': tr.get('tokenInfo').get('symbol'),
                        'value': self.from_unit(int(tr.get('value')), contract_info.get('decimals')),
                    }
                )

        return {
            'hash': tx_info.get('hash'),
            'success': tx_info.get('success'),
            'from': tx_sender,
            'to': tx_receiver,
            'operations': operations,
            'block': tx_block,
            'confirmations': tx_conf,
            'fees': None,  # api do not return fees value
            'date': tx_time,
            'raw': tx_info,
        }

    def contract_currency(self, token_address):
        return self.contract_currency_list.get(token_address)

    def contract_info(self, currency):
        return self.contract_info_list.get(currency)

    @property
    def contract_currency_list(self):
        return ERC20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return ERC20_contract_info.get(self.network)
