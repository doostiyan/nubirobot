import sys
import traceback
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

import base58
import pytz
from django.core.cache import cache

from exchange.base.models import Currencies
from exchange.base.parsers import parse_utc_timestamp_ms
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.contracts_conf import TRC20_contract_currency, TRC20_contract_info
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


def to_hex(address: str) -> str:
    return base58.b58encode_check(bytes.fromhex(address)).decode('utf-8')


class TrongridAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: tron
    API docs: https://github.com/tronscan/tronscan-frontend/blob/dev2019/document/api.md
    Explorer: https://tronscan.org
    """

    active = True

    symbol = 'TRX'
    currency = Currencies.trx
    _base_url = 'https://api.trongrid.io/v1/'
    testnet_url = 'https://api.shasta.trongrid.io/v1/'
    rate_limit = 0
    PRECISION = 6
    max_items_per_page = 50  # 50 for transactions history
    page_offset_step = None
    confirmed_num = None
    headers: dict = {}
    min_valid_tx_amount = Decimal('0.001')
    USE_PROXY = True

    supported_requests = {
        'get_balance': 'accounts/{address}?only_confirmed=true',
        'get_trc10_tokenlist': 'assets?limit={limit}',
        'get_trc10_token': 'assets/{identifier}',
        'get_txs': 'accounts/{address}/transactions?limit={limit}&only_to=true&only_confirmed=true',
        'get_txs_fingerprint': 'accounts/{address}/transactions?limit={limit}&only_confirmed={'
                               'only_confirmed}&fingerpirnt={offset}',
        'get_trc20_txs': 'accounts/{address}/transactions/trc20?limit={limit}&only_confirmed={only_confirmed}',
        'get_trc20_txs_fingerprint': 'accounts/{address}/transactions/trc20?limit={limit}&only_confirmed={'
                                     'only_confirmed}&fingerpirnt={offset}',
        'get_contract_txs': 'accounts/{address}/transactions/trc20?limit={limit}&only_confirmed={'
                            'only_confirmed}&contract_address={contract_address}',
        'get_contract_txs_fingerprint': 'accounts/{address}/transactions/trc20?limit={limit}&only_confirmed={'
                                        'only_confirmed}&fingerpirnt={offset}&contract_address={contract_address}',
    }

    def get_name(self) -> str:
        return 'trongrid_api'

    def get_balance(self, address: str) -> dict:
        self.validate_address(address)
        response = self.request('get_balance', address=address, headers=self.headers, timeout=25)
        if not response:
            raise APIError(f'[TrongridAPI][{self.symbol}][Get Balance] response is None')

        if not response.get('success', False):
            raise APIError(f'[TrongridAPI][{self.symbol}][Get Balance] unsuccessful')

        try:
            data = response.get('data', [{}])[0]
            balance = data.get('balance', 0)
        except IndexError:
            # Inactive address
            return [{
                'symbol': self.symbol,
                'amount': 0,
                'address': address
            }]

        main_balance = self.from_unit(int(balance))
        # Ignore asset balance and trc20 balance other than USDT
        balances = {
            self.currency: {
                'symbol': self.symbol,
                'amount': main_balance,
                'address': address
            }
        }
        for coin in data.get('trc20'):
            contract = list(coin.keys())[0]
            currency = self.contract_currency(contract)
            contract_info = self.contract_info(currency)
            if currency:
                balances[currency] = {
                    'amount': self.from_unit(int(coin.get(contract)), contract_info.get('decimals')),
                    'address': address
                }
        return balances

    def get_txs(self, address: str, offset: int = 0, limit: int = 30, unconfirmed: bool = False,
                tx_type: str = 'trx') -> List[Dict[str, any]]:
        """ Get account transaction from trongrid.io
        :param address: target address to get txs
        :param offset: Fingerprint in previous transaction result
        :param limit: Limit in the number of transaction in each response
        :param unconfirmed: False|True. True if you want to return unconfirmed transactions too.
        :param tx_type: normal|assets|all. If you set all return both normal and assets transactions.
        :return: List of transactions
        """
        self.validate_address(address)
        txs = self._get_txs(address=address, offset=offset, limit=limit, unconfirmed=unconfirmed)
        trc10_token_info = None
        if tx_type in ['assets', None]:
            trc10_token_info = self._get_token_list(limit)

        result = []
        for tx in txs:
            parsed_tx = self.parse_tx(tx, address, tx_type, trc10_token_info)
            if parsed_tx is not None:
                result.append(parsed_tx)
        return result

    def get_token_txs(self, address: str, contract_info: Optional[dict] = None, offset: Optional[int] = None,
                      limit: Optional[int] = None, unconfirmed: bool = False, contract_address: Optional[str] = None,
                      _: str = '') -> List[Dict[str, any]]:
        if not contract_address:
            contract_address = contract_info.get('address')
        self.validate_address(address)
        txs = self._get_trc20_txs(address=address,
                                  offset=offset,
                                  limit=limit,
                                  unconfirmed=unconfirmed,
                                  contract_address=contract_address)
        result = []
        for tx in txs:
            parsed_tx = self.parse_trc20_tx(tx, address)
            if parsed_tx is not None:
                result.append(parsed_tx)
        return result

    def _get_txs(self, address: str, offset: Optional[int] = None, limit: Optional[int] = None,
                 unconfirmed: bool = False) -> list:
        if not offset or offset == 0:
            response = self.request(
                'get_txs',
                limit=limit,
                address=address,
                only_confirmed=not unconfirmed,
                headers=self.headers,
                timeout=25,
            )
        else:
            response = self.request(
                'get_txs_fingerprint',
                limit=limit,
                offset=offset,
                address=address,
                only_confirmed=not unconfirmed,
                headers=self.headers,
                timeout=25,
            )

        if not response:
            return []
        if not response.get('success'):
            return []
        result = response.get('data', [])
        if result is None:
            result = []
        return result

    def _get_trc20_txs(self, address: str, offset: Optional[int] = None, limit: Optional[int] = None,
                       unconfirmed: bool = False, contract_address: Optional[str] = None) -> list:
        has_fingerprint = False
        if not offset or offset == 0:
            has_fingerprint = True

        has_contract_addr = contract_address is not None
        if not has_fingerprint and not has_contract_addr:
            response = self.request(
                'get_trc20_txs',
                limit=limit,
                address=address,
                only_confirmed=not unconfirmed,
                headers=self.headers,
                timeout=25,
            )
        elif not has_fingerprint and has_contract_addr:
            response = self.request(
                'get_contract_txs',
                limit=limit,
                address=address,
                only_confirmed=not unconfirmed,
                contract_address=contract_address,
                headers=self.headers,
                timeout=25,
            )
        elif has_fingerprint and not has_contract_addr:
            response = self.request(
                'get_trc20_txs_fingerprint',
                limit=limit,
                offset=offset,
                address=address,
                only_confirmed=not unconfirmed,
                headers=self.headers,
                timeout=25,
            )
        else:
            response = self.request(
                'get_contract_txs_fingerprint',
                limit=limit,
                offset=offset,
                address=address,
                only_confirmed=not unconfirmed,
                contract_address=contract_address,
                headers=self.headers,
                timeout=25,
            )

        if not response:
            return []
        if not response.get('success'):
            return []
        result = response.get('data', [])
        if result is None:
            result = []

        return result

    def _get_token_list(self, limit: Optional[int] = None) -> dict:
        response = self.request(
            'get_trc10_tokenlist',
            limit=limit,
            headers=self.headers,
            timeout=25,
        )
        if not response:
            return {}
        if not response.get('success'):
            return {}
        tokens = response.get('data')
        result = {}
        for token in tokens:
            result[token.get('id')] = token
        return result

    def parse_tx(self, tx: dict, address: str, tx_type: str = 'all', trc10_token_list: Optional[dict] = None) -> \
            Optional[Dict[str, any]]:
        contracts = tx.get('raw_data', {}).get('contract', [{}])
        if contracts is None or contracts == []:
            contracts = [{}]
        main_contract_detail = contracts[0]
        main_contract_params = main_contract_detail.get('parameter', {})

        asset_data = None
        contract_address = None
        result_tx = tx.get('ret', [{}])

        if result_tx is None or result_tx == [] or result_tx[0].get('contractRet') != 'SUCCESS':
            return None
        tx_tp = main_contract_detail.get('type')
        # TODO: Support TriggerSmartContract and CreateSmartContract
        if tx_tp == 'TransferAssetContract' and tx_type in ['assets', 'all']:

            token_info = trc10_token_list.get(main_contract_params.get('value', {}).get('asset_name'))
            if not token_info:
                response = self.request(
                    'get_trc10_token',
                    main_contract_params.get('value', {}).get('asset_name'),
                    headers=self.headers,
                    timeout=25,
                )
                if not response:
                    return None
                if not response.get('success'):
                    return None
                data = response.get('data')
                if not data or data == []:
                    return None
                token_info = data[0]
            asset_data = token_info
            symbol = asset_data.get('abbr')
            amount = self.from_unit(int(main_contract_params.get('value', {}).get('amount')),
                                    asset_data.get('precision'))
            contract_address = to_hex(asset_data.get('owner_address'))
        elif tx_tp == 'TransferContract' and tx_type in ['trx', 'all']:
            symbol = self.symbol
            amount = self.from_unit(int(main_contract_params.get('value', {}).get('amount')))
        else:
            return None
        if amount < self.min_valid_tx_amount:
            return None

        to_address = to_hex(main_contract_params.get('value', {}).get('to_address'))
        from_address = to_hex(main_contract_params.get('value', {}).get('owner_address'))
        if from_address in ['TM9RwJndZHmDVLSZcY6J76ci22AzPp2krj', 'TVCAuYMw5afP96y5Wep866AXVWZJRH8fdo']:
            return None
        if address.lower() == from_address.lower():
            amount = -amount
        elif address.lower() != to_address.lower():
            return None
        if from_address.lower() == to_address.lower():
            return None

        # Estimating confirmations
        confirmations = 20
        transaction_block_number = int(tx.get('blockNumber'))
        try:
            latest_block = cache.get('trx_latest_block')
            if latest_block and transaction_block_number:
                confirmations = max(confirmations, latest_block - transaction_block_number)
        except Exception:
            traceback.print_exception(*sys.exc_info())

        return {
            'symbol': symbol,
            'block': transaction_block_number,
            'date': parse_utc_timestamp_ms(tx.get('block_timestamp')),
            'from_address': to_hex(main_contract_params.get('value', {}).get('owner_address')),
            'to_address': to_hex(main_contract_params.get('value', {}).get('to_address')),
            'contract_address': contract_address,
            'amount': amount,
            'hash': tx.get('txID'),
            'confirmations': confirmations,
            'confirmed': None,
            'type': tx_type,
            'kind': 'transaction',
            'asset_data': asset_data,
            'raw': tx,
            'memo': None
        }

    def parse_trc20_tx(self, tx: dict, address: str) -> Optional[Dict[str, any]]:
        if tx.get('from') in ['TM9RwJndZHmDVLSZcY6J76ci22AzPp2krj', 'TVCAuYMw5afP96y5Wep866AXVWZJRH8fdo']:
            return None

        if tx.get('type') != 'Transfer':
            return None
        currency = self.contract_currency(tx.get('token_info', {}).get('address'))
        if currency is None:
            return None
        contract_info = self.contract_info(currency)
        amount = self.from_unit(int(tx.get('value', 0)), contract_info.get('decimals'))
        if address.lower() == tx.get('from', {}).lower():
            amount = -amount
            direction = 'outgoing'
        elif address.lower() == tx.get('to', {}).lower():
            direction = 'incoming'
        else:
            return None
        # TODO: set return format as blockbook.py get_txs
        return {
            'symbol': tx.get('token_info', {}).get('symbol'),
            'date': datetime.fromtimestamp(int(tx.get('block_timestamp') / 1000.0), pytz.utc),
            'from_address': tx.get('from', {}),
            'to_address': tx.get('to', {}),
            'contract_address': tx.get('token_info', {}).get('address'),
            'amount': amount,
            'hash': tx.get('transaction_id'),
            'confirmations': 1,
            'confirmed': None,
            'type': tx.get('type'),
            'kind': 'transaction',
            'direction': direction,
            'token_info': tx.get('token_info'),
            'raw': tx,
            'memo': None
        }

    @property
    def contract_currency_list(self) -> dict:
        return TRC20_contract_currency.get(self.network)

    @property
    def contract_info_list(self) -> dict:
        return TRC20_contract_info.get(self.network)
