import random
from decimal import Decimal
from typing import Dict, List, Optional, Union

from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_iso_date
else:
    from exchange.base.parsers import parse_iso_date

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin


class CovalenthqResponseValidator(ResponseValidator):
    min_valid_tx_amount = Decimal(0)
    precision = 18

    @classmethod
    def validate_general_response(cls, response: Dict[str, any]) -> bool:
        if response.get('data') is None:
            return False
        if response.get('data').get('items') is None:
            return False
        if len(response.get('data').get('items')) == 0:
            return False
        if response.get('error'):
            return False
        if response.get('error_message') is not None:
            return False
        if response.get('error_code') is not None:
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: dict) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        return True

    @classmethod
    def validate_token_transaction_details_response(cls, tx_details_response: Dict[str, any]) -> bool:
        key2check = ['block_signed_at', 'block_height', 'block_hash', 'tx_hash', 'successful', 'from_address',
                     'to_address', 'log_events']
        for key in key2check:
            if not tx_details_response.get(key):
                return False
        if tx_details_response.get('from_address') == tx_details_response.get('to_address'):
            return False
        if tx_details_response.get('from_address') in cls.invalid_from_addresses_for_ETH_like:
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, any]) -> bool:
        if not transaction or not isinstance(transaction, dict):
            return False
        if transaction.get('log_events'):
            return False
        if not transaction.get('block_height') or not isinstance(transaction.get('block_height'), int):
            return False
        if not transaction.get('block_signed_at') or not isinstance(transaction.get('block_signed_at'), str):
            return False
        if not transaction.get('tx_hash') or not isinstance(transaction.get('tx_hash'), str):
            return False
        if not transaction.get('successful') or not isinstance(transaction.get('successful'), bool):
            return False
        if not transaction.get('from_address') or not isinstance(transaction.get('from_address'), str):
            return False
        if not transaction.get('to_address') or not isinstance(transaction.get('to_address'), str):
            return False
        if transaction.get('from_address') == transaction.get('to_address'):
            return False
        if not transaction.get('value') or not isinstance(transaction.get('value'), str):
            return False
        value = BlockchainUtilsMixin.from_unit(int(transaction.get('value')), cls.precision)
        if value <= cls.min_valid_tx_amount:
            return False
        if not transaction.get('fees_paid') or not isinstance(transaction.get('fees_paid'), str):
            return False
        if transaction.get('from_address') in cls.invalid_from_addresses_for_ETH_like:
            return False
        return True

    @classmethod
    def validate_token_transaction(cls, transaction: Dict[str, any], contract_info: Dict[str, Union[str, int]]) -> bool:
        if transaction is None:
            return False
        transfers = transaction.get('transfers')
        if transfers is None or len(transfers) != 1:
            return False
        transfer = transfers[0]
        if transfer is None:
            return False
        if transfer.get('from_address') == transfer.get('to_address'):
            return False
        if transfer.get('from_address') in cls.invalid_from_addresses_for_ETH_like:
            return False
        if transaction.get('to_address') != contract_info.get('address'):
            return False
        if transfer.get('contract_address') != contract_info.get('address'):
            return False
        if not transaction.get('successful'):
            return False
        if Decimal(transfer.get('delta')) == 0:
            return False
        return True

    @classmethod
    def validate_address_tx_transaction(cls, address_txs_response: dict) -> bool:
        return cls.validate_transaction(address_txs_response)

    @classmethod
    def validate_block_txs_raw_response(cls, block_txs_raw_response: Dict[str, any]) -> bool:
        if not block_txs_raw_response or not isinstance(block_txs_raw_response, dict):
            return False
        if not block_txs_raw_response.get('data') or not isinstance(block_txs_raw_response.get('data'), dict):
            return False
        if not block_txs_raw_response.get('data').get('items') or not isinstance(
                block_txs_raw_response.get('data').get('items'), list):
            return False
        return True


class CovalenthqResponseParser(ResponseParser):
    validator = CovalenthqResponseValidator

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, any]) -> Decimal:
        if not cls.validator.validate_general_response(balance_response):
            return Decimal(0)
        items = balance_response.get('data').get('items')
        for item in items:
            if item.get('contract_ticker_symbol') == cls.symbol:
                return BlockchainUtilsMixin.from_unit(int(item.get('balance')), precision=cls.precision)
        return Decimal(0)

    @classmethod
    def parse_token_balance_response(cls, balance_response: Dict[str, any],
                                     contract_info: Dict[str, Union[int, str]]) -> Decimal:
        if not cls.validator.validate_general_response(balance_response):
            return Decimal(0)
        items = balance_response.get('data').get('items')
        for item in items:
            if item.get('contract_address').casefold() == contract_info.get('address').casefold():
                return BlockchainUtilsMixin.from_unit(int(item.get('balance')), contract_info.get('decimals'))
        return Decimal(0)

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, any], block_head: int) -> List[TransferTx]:
        if cls.validator.validate_tx_details_response(tx_details_response):
            transaction = tx_details_response.get('data').get('items')[0]
            if cls.validator.validate_transaction(transaction):
                return [TransferTx(
                    block_height=transaction.get('block_height'),
                    block_hash=transaction.get('block_hash'),
                    tx_hash=transaction.get('tx_hash'),
                    date=parse_iso_date(transaction.get('block_signed_at')),
                    success=True,
                    confirmations=block_head - transaction.get('block_height'),
                    from_address=transaction.get('from_address'),
                    to_address=transaction.get('to_address'),
                    value=BlockchainUtilsMixin.from_unit(int(transaction.get('value')), precision=cls.precision),
                    symbol=cls.symbol,
                    tx_fee=BlockchainUtilsMixin.from_unit(int(transaction.get('fees_paid')), precision=cls.precision),
                )]

            if cls.validator.validate_token_transaction_details_response(transaction):
                token_transfers = []
                log_events = transaction.get('log_events')
                for log_event in log_events:
                    if not log_event.get('decoded') or log_event.get('decoded').get(
                            'name') != 'Transfer':
                        continue
                    params = log_event.get('decoded').get('params')
                    if not params:
                        continue
                    contract_address = log_event.get('sender_address')
                    currency, contract_address = cls.get_currency_by_contract(contract_address)
                    if currency is None:
                        continue

                    contract_info = cls.get_currency_info_by_contract(currency, contract_address)
                    fee = transaction.get('gas_spent') * transaction.get('gas_price')
                    token_transfers.append(TransferTx(
                        block_height=transaction.get('block_height'),
                        block_hash=transaction.get('block_hash'),
                        tx_hash=transaction.get('tx_hash'),
                        date=parse_iso_date(transaction.get('block_signed_at')),
                        success=transaction.get('successful'),
                        confirmations=block_head - transaction.get('block_height'),
                        from_address=params[0].get('value'),
                        to_address=params[1].get('value'),
                        value=BlockchainUtilsMixin.from_unit(int(params[2].get('value')),
                                                             contract_info.get('decimals')),
                        symbol=contract_info.get('symbol'),
                        tx_fee=BlockchainUtilsMixin.from_unit(int(fee), precision=cls.precision),
                        token=contract_address,
                    ))
                return token_transfers
        return []

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, any]) -> Optional[str]:
        if not cls.validator.validate_general_response(block_head_response):
            return None
        return block_head_response.get('data').get('items')[0].get('height')

    @classmethod
    def parse_address_txs_response(cls, _: str, address_txs_response: Dict[str, any], block_head: int) -> List[
        TransferTx]:
        if not cls.validator.validate_general_response(address_txs_response):
            return []
        transactions = address_txs_response.get('data').get('items')
        address_txs: List[TransferTx] = []
        for transaction in transactions:
            if cls.validator.validate_address_tx_transaction(transaction):
                block_height = transaction.get('block_height')
                address_tx = TransferTx(
                    block_height=block_height,
                    block_hash=transaction.get('block_hash'),
                    tx_hash=transaction.get('tx_hash'),
                    date=parse_iso_date(transaction.get('block_signed_at')),
                    success=True,
                    confirmations=block_head - block_height,
                    from_address=transaction.get('from_address'),
                    to_address=transaction.get('to_address'),
                    value=BlockchainUtilsMixin.from_unit(int(transaction.get('value')), precision=cls.precision),
                    symbol=cls.symbol,
                    tx_fee=BlockchainUtilsMixin.from_unit(int(transaction.get('fees_paid')), precision=cls.precision),
                )
                address_txs.append(address_tx)
        return address_txs

    @classmethod
    def parse_token_txs_response(cls,
                                 _: str,
                                 address_txs_response: Dict[str, any],
                                 block_head: int,
                                 contract_info: Dict[str, Union[str, int]],
                                 __: str = '') -> List[TransferTx]:
        if not cls.validator.validate_general_response(address_txs_response):
            return []
        transactions = address_txs_response.get('data').get('items')
        token_transfers: List[TransferTx] = []
        for transaction in transactions:
            if cls.validator.validate_token_transaction(transaction, contract_info):
                transfer = transaction.get('transfers')[0]
                block_height = transaction.get('block_height')
                token_transfer = TransferTx(
                    block_height=block_height,
                    block_hash=transaction.get('block_hash'),
                    tx_hash=transfer.get('tx_hash'),
                    date=parse_iso_date(transfer.get('block_signed_at')),
                    success=True,
                    confirmations=block_head - block_height,
                    from_address=transfer.get('from_address'),
                    to_address=transfer.get('to_address'),
                    value=BlockchainUtilsMixin.from_unit(int(transfer.get('delta')), contract_info.get('decimals')),
                    symbol=contract_info.get('symbol'),
                    tx_fee=BlockchainUtilsMixin.from_unit(
                        int(transaction.get('gas_spent')) * int(transaction.get('gas_price')),
                        precision=cls.precision),
                    token=contract_info.get('address'),
                )
                token_transfers.append(token_transfer)
        return token_transfers

    @classmethod
    def parse_block_txs_response(cls, block_txs_response: Dict[str, any]) -> List[TransferTx]:
        block_txs: List[TransferTx] = []
        if cls.validator.validate_general_response(block_txs_response):
            transactions = block_txs_response.get('data').get('items')
            for tx in transactions:
                if cls.validator.validate_transaction(tx):
                    from_address = tx.get('from_address')
                    to_address = tx.get('to_address')
                    tx_hash = tx.get('tx_hash')
                    tx_value = BlockchainUtilsMixin.from_unit(int(tx.get('value')), precision=cls.precision)
                    block_height = tx.get('block_height')
                    block_hash = tx.get('block_hash')
                    block_tx = TransferTx(
                        block_height=block_height,
                        block_hash=block_hash,
                        tx_hash=tx_hash,
                        date=parse_iso_date(tx.get('block_signed_at')),
                        success=True,
                        from_address=from_address,
                        to_address=to_address,
                        value=tx_value,
                        symbol=cls.symbol,
                        tx_fee=BlockchainUtilsMixin.from_unit(int(tx.get('fees_paid')),
                                                              precision=cls.precision),
                    )
                    block_txs.append(block_tx)
        return block_txs


class CovalenthqApi(GeneralApi):
    parser = CovalenthqResponseParser

    supported_requests = {
        'get_balance': '/address/{address}/balances_v2/?&key={apikey}',
        'get_token_balance': '/address/{address}/balances_v2/?&key={apikey}',
        'get_tx_details': '/transaction_v2/{tx_hash}/?&key={apikey}',
        'get_address_txs': '/address/{address}/transactions_v3/?key={apikey}',
        'get_token_txs': '/address/{address}/transfers_v2/?key={apikey}&contract-address={'
                         'contract_address}&page-number=0&page-size=25',
        'get_block_txs': '/block/{height}/transactions_v3/?&key={apikey}',
        'get_block_head': '/block_v2/latest/?&key={apikey}'
    }

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.COVALENT_API_KEYS)
