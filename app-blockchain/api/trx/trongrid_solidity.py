import json
from decimal import Decimal
from typing import Dict, List, Optional, Union

import base58
from django.core.cache import cache

from exchange.base.parsers import parse_utc_timestamp_ms
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


class TrongridSolidityAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: tron
    API docs: https://developers.tron.network/reference#solidity-node-api
    Explorer: https://tronscan.org
    """

    active = True

    symbol = 'TRX'
    _base_url = 'https://api.trongrid.io'
    rate_limit = 0
    PRECISION = 6
    max_items_per_page = 50  # 50 for transactions history
    page_offset_step = None
    confirmed_num = None
    min_valid_tx_amount = Decimal('0.001')

    supported_requests = {
        'get_balance': '/walletsolidity/getaccount',
        'get_txs': '/walletextension/gettransactionstothis',
    }

    def get_name(self) -> str:
        return 'trongrid_solidity_api'

    def get_balance(self, address: str) -> Optional[Dict[str, Union[int, Decimal]]]:
        self.validate_address(address)
        data = {
            'address': address,
            'visible': True
        }
        response = self.request('get_balance', json=data, force_post=True)
        if response is None:
            raise APIError('[TrongridSolidityAPI][Get Balance] response is None')
        balance = response.get('balance')
        if balance is None:
            return None
        return {
            'amount': self.from_unit(balance),
        }

    def get_txs(self, address: str) -> List[Dict[str, any]]:
        self.validate_address(address)
        data = {
            'account': {
                'address': base58.b58decode_check(address).hex().upper()
            },
            'limit': 30
        }
        response = self.request('get_txs', address=address, body=json.dumps(data))
        if response is None:
            raise APIError(f'[TrongridSolidityAPI][{self.symbol}][Get Transactions] response is None')

        txs = response.get('transaction')
        if txs is None:
            return []

        transactions = []
        for tx in txs:
            parsed_tx = self.parse_tx(tx, address)
            if parsed_tx is not None:
                transactions.append(parsed_tx)
        return transactions

    def parse_tx(self, tx: dict, address: str) -> Optional[Dict[str, any]]:
        contract_ret = tx.get('ret', [{}])[0].get('contractRet')
        if contract_ret != 'SUCCESS':
            return None
        contract = tx.get('raw_data', {}).get('contract', [{}])[0]
        transaction_type = contract.get('type')
        if transaction_type != 'TransferContract':
            return None
        value = contract.get('parameter', {}).get('value', {}).get('amount')
        if not value:
            return None

        try:
            value = self.from_unit(value)
        except ValueError:
            return None
        if value < self.min_valid_tx_amount:
            return None
        owner_address = contract.get('parameter', {}).get('value', {}).get('owner_address')
        to_address = contract.get('parameter', {}).get('value', {}).get('to_address')
        if base58.b58decode_check(address).hex().upper() != to_address.upper():
            value = -1 * value
        if owner_address in ['TM9RwJndZHmDVLSZcY6J76ci22AzPp2krj', 'TVCAuYMw5afP96y5Wep866AXVWZJRH8fdo']:
            return None
        if base58.b58decode_check('TM9RwJndZHmDVLSZcY6J76ci22AzPp2krj').hex().lower() == owner_address.lower():
            return None

        if base58.b58decode_check('TVCAuYMw5afP96y5Wep866AXVWZJRH8fdo').hex().lower() == owner_address.lower():
            return None

        confirmations = 20
        transaction_block_number = int(tx.get('blockNumber'))
        latest_block = cache.get('trx_latest_block')
        if latest_block and transaction_block_number:
            confirmations = min(confirmations, latest_block - transaction_block_number)

        # Timestamp maybe incorrect in some cases.
        # e.q.: c34cb2268758acdd39922010f0aedc9da8ac821ff287358b057082b835302ede
        timestamp = int(tx.get('raw_data', {}).get('expiration'))
        return {
            'date': parse_utc_timestamp_ms(timestamp),
            'from_address': base58.b58encode_check(bytes.fromhex(owner_address)),
            'amount': value,
            'hash': tx.get('txID'),
            'confirmations': confirmations,
            'raw': tx
        }
