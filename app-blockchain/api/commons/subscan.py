import datetime
import json
import random
from decimal import Decimal
from typing import Dict, List, Optional

import pytz
from django.conf import settings

from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.ss58 import ss58_encode
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin


class SubScanResponseValidator(ResponseValidator):
    symbol = None
    precision = None
    min_event_length = None
    valid_call_module_functions = ['transfer_allow_death', 'transfer_keep_alive', 'batch', 'batch_all', 'transfer_all']
    valid_call_modules = ['balances', 'utility']
    FROM_EVENT_INDEX = 0
    TO_EVENT_INDEX = 1
    AMOUNT_EVENT_INDEX = 2

    @classmethod
    def validate_general_response(cls, response: Dict[str, any]) -> bool:
        if not response:
            return False
        if not response.get('message') or response.get('message').casefold() != 'Success'.casefold():
            raise APIError(f"[SubscanAPI] Unsuccessful:{response.get('message')}")
        if response.get('code') is None or response.get('code') != 0:
            return False
        if not response.get('data') or not isinstance(response.get('data'), dict):
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(balance_response):
            return False
        if not balance_response.get('data').get('account', {}).get('balance'):
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        if not address_txs_response.get('data').get('transfers') or not isinstance(
                address_txs_response.get('data').get('transfers'), list):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        if not any(tx_details_response.get('data').get(field) for field in
                   ['block_num', 'block_timestamp', 'extrinsic_hash', 'block_hash', 'fee']):
            return False
        if not tx_details_response.get('data').get('success'):
            return False
        if tx_details_response.get('data').get('call_module') not in cls.valid_call_modules:
            return False
        if tx_details_response.get('data').get('call_module_function') not in cls.valid_call_module_functions:
            return False
        if tx_details_response.get('data').get('error'):
            return False
        if tx_details_response.get('data').get('pending'):
            return False
        if not tx_details_response.get('data').get('finalized'):
            return False
        if not tx_details_response.get('data').get('event'):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        if not block_head_response.get('data').get('blockNum') or not isinstance(
                block_head_response.get('data').get('blockNum'), str):
            return False
        return True

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(block_txs_response):
            return False
        if not any(block_txs_response.get('data').get(field) for field in
                   ['block_num', 'block_timestamp', 'hash', 'events']):
            return False
        if not block_txs_response.get('data').get('finalized'):
            return False
        if not isinstance(block_txs_response.get('data').get('events'), list):
            return False
        return True

    @classmethod
    def validate_block_txs_raw_response(cls, block_txs_raw_response: Dict[str, any]) -> bool:
        if not block_txs_raw_response or not isinstance(block_txs_raw_response, dict):
            return False
        if not block_txs_raw_response.get('data') or not isinstance(block_txs_raw_response.get('data'), dict):
            return False
        if not block_txs_raw_response.get('data').get('events') or not isinstance(
                block_txs_raw_response.get('data').get('events'), list):
            return False
        return True

    @classmethod
    def validate_transfer(cls, transfer: Dict[str, any]) -> bool:
        if not any(transfer.get(field) for field in ['extrinsic_hash', 'module_id', 'event_id', 'params']):
            return False
        if transfer.get('module_id').casefold() != 'balances'.casefold():
            return False
        if transfer.get('event_id').casefold() != 'Transfer'.casefold():
            return False
        if not transfer.get('finalized'):
            return False
        # info of transfers is in json mode and we should split it for our needs
        event_info = json.loads(transfer.get('params'))
        if len(event_info) < cls.min_event_length:
            return False
        for event in range(cls.min_event_length):
            if event == cls.FROM_EVENT_INDEX and event_info[event].get('name') != 'from':
                return False
            if event == cls.TO_EVENT_INDEX and event_info[event].get('name') != 'to':
                return False
            if event == cls.AMOUNT_EVENT_INDEX and event_info[event].get('name') != 'amount':
                return False
            if not event_info[event].get('value'):
                return False
        transfer_value = BlockchainUtilsMixin.from_unit(int(event_info[2].get('value')), cls.precision)
        if transfer_value <= cls.min_valid_tx_amount:
            return False
        return True

    @classmethod
    def validate_address_tx_transaction(cls, transaction: Dict[str, any]) -> bool:
        if not any(transaction.get(field) for field in
                   ['block_num', 'block_timestamp', 'amount', 'fee', 'hash', 'module', 'asset_symbol', 'from', 'to']):
            return False
        if not transaction.get('success'):
            return False
        if transaction.get('module').casefold() != 'balances'.casefold():
            return False
        # We check that our symbol is equal to asset_symbol field in each transfer for valdiation
        if transaction.get('asset_symbol') != cls.symbol:
            return False
        if transaction.get('asset_unique_id') != cls.symbol:
            return False
        if transaction.get('asset_type') != '':
            return False
        if transaction.get('from').casefold() == transaction.get('to').casefold():
            return False
        if transaction.get('from').casefold() in cls.invalid_from_addresses_for_ETH_like:
            return False
        if Decimal(transaction.get('amount')) != BlockchainUtilsMixin.from_unit(int(transaction.get('amount_v2')),
                                                                                cls.precision):
            return False
        value = Decimal(transaction.get('amount'))
        if value <= cls.min_valid_tx_amount:
            return False
        return True


class SubScanResponseParser(ResponseParser):
    validator = SubScanResponseValidator

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, any]) -> Decimal:
        if cls.validator.validate_balance_response(balance_response):
            return Decimal(balance_response.get('data').get('account').get('balance'))
        return Decimal('0')

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, any]) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return int(block_head_response.get('data').get('blockNum'))
        return None

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, any], block_head: int) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        if cls.validator.validate_tx_details_response(tx_details_response):
            events = tx_details_response.get('data').get('event')
            # In here events are like transfers
            for event in events:
                if cls.validator.validate_transfer(event):
                    tx_hash = tx_details_response.get('data').get('extrinsic_hash')
                    block_height = tx_details_response.get('data').get('block_num')
                    confirmations = block_head - block_height + 1
                    date = datetime.datetime.fromtimestamp(
                        tx_details_response.get('data').get('block_timestamp'), pytz.utc)
                    event_info = json.loads(event.get('params'))
                    from_address = cls.pub_key_to_address(event_info[0].get('value'))
                    if from_address in cls.validator.invalid_from_addresses_for_ETH_like:
                        continue
                    to_address = cls.pub_key_to_address(event_info[1].get('value'))
                    value = BlockchainUtilsMixin.from_unit(int(event_info[2].get('value')), cls.precision)
                    tx_fee = BlockchainUtilsMixin.from_unit(int(tx_details_response.get('data').get('fee')),
                                                            cls.precision)
                    block_hash = tx_details_response.get('data').get('block_hash')
                    transfer = TransferTx(
                        tx_hash=tx_hash,
                        confirmations=confirmations,
                        date=date,
                        from_address=from_address,
                        to_address=to_address,
                        value=value,
                        block_height=block_height,
                        symbol=cls.symbol,
                        success=True,
                        tx_fee=tx_fee,
                        block_hash=block_hash
                    )
                    transfers.append(transfer)
        return transfers

    @classmethod
    def pub_key_to_address(cls, pub_key: str) -> str:
        # We use this function which has come from old structure to find from_address and to_address
        # The default is set to 0 but it varies for each Coin
        address_format = 0
        return ss58_encode(pub_key, ss58_format=address_format)

    @classmethod
    def parse_address_txs_response(cls, _: str, address_txs_response: Dict[str, any], block_head: int) -> \
            List[TransferTx]:
        transfers: List[TransferTx] = []
        if cls.validator.validate_address_txs_response(address_txs_response):
            transactions = address_txs_response.get('data').get('transfers')
            for transaction in transactions:
                if cls.validator.validate_address_tx_transaction(transaction):
                    block_height = transaction.get('block_num')
                    tx_hash = transaction.get('hash')
                    value = Decimal(transaction.get('amount'))
                    confirmations = block_head - block_height + 1
                    date = datetime.datetime.fromtimestamp(transaction.get('block_timestamp'), pytz.utc)
                    from_address = transaction.get('from')
                    to_address = transaction.get('to')
                    tx_fee = BlockchainUtilsMixin.from_unit(int(transaction.get('fee')), cls.precision)
                    transfer = TransferTx(
                        tx_hash=tx_hash,
                        date=date,
                        success=True,
                        symbol=cls.symbol,
                        from_address=from_address,
                        to_address=to_address,
                        value=value,
                        confirmations=confirmations,
                        block_height=block_height,
                        tx_fee=tx_fee
                    )
                    transfers.append(transfer)

        return transfers

    @classmethod
    def parse_block_txs_response(cls, block_txs_response: Dict[str, any]) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        if cls.validator.validate_block_txs_response(block_txs_response):
            events = block_txs_response.get('data').get('events')
            for event in events:
                if cls.validator.validate_transfer(event):
                    block_hash = block_txs_response.get('data').get('hash')
                    tx_hash = event.get('extrinsic_hash')
                    block_height = event.get('block_num')
                    index = event.get('event_idx')
                    event_info = json.loads(event.get('params'))
                    from_address = cls.pub_key_to_address(event_info[0].get('value'))
                    if from_address in cls.validator.invalid_from_addresses_for_ETH_like:
                        continue
                    to_address = cls.pub_key_to_address(event_info[1].get('value'))
                    value = BlockchainUtilsMixin.from_unit(int(event_info[2].get('value')), cls.precision)
                    transfer = TransferTx(
                        tx_hash=tx_hash,
                        block_height=block_height,
                        block_hash=block_hash,
                        from_address=from_address,
                        to_address=to_address,
                        value=value,
                        success=True,
                        symbol=cls.symbol,
                        index=index,
                        date=parse_utc_timestamp(block_txs_response.get('data').get('block_timestamp'))
                    )
                    transfers.append(transfer)
        return transfers


class SubScanApi(GeneralApi):
    parser = SubScanResponseParser
    USE_PROXY = False
    TRANSACTIONS_LIMIT = 100  # maximum is 100
    offset = 0  # offset is for offset of page in address_txs
    supported_requests = {
        'get_balance': '/api/v2/scan/search',
        'get_address_txs': '/api/v2/scan/transfers',
        'get_block_head': '/api/scan/metadata',
        'get_block_txs': '/api/scan/block',
        'get_tx_details': '/api/scan/extrinsic',
    }

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': cls.get_api_key()
        }

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.SUBSCAN_API_KEY)

    @classmethod
    def get_tx_details_body(cls, tx_hash: str) -> str:
        data = {
            'hash': tx_hash,
        }
        return json.dumps(data)

    @classmethod
    def get_balance_body(cls, address: str) -> str:
        data = {
            'key': address,
        }
        return json.dumps(data)

    @classmethod
    def get_address_txs_body(cls, address: str) -> str:
        data = {
            'row': cls.TRANSACTIONS_LIMIT,
            'page': cls.offset,
            'address': address,
        }
        return json.dumps(data)

    @classmethod
    def get_block_txs_body(cls, block_height: int) -> str:
        data = {
            'block_num': block_height
        }
        return json.dumps(data)
