from typing import List
from decimal import Decimal
from django.conf import settings
from exchange.blockchain.utils import APIError
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseValidator, ResponseParser

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class TzstatsValidatorTezos(ResponseValidator):
    min_valid_tx_amount = Decimal('0.01')

    @classmethod
    def validate_general_response(cls, response):
        if not response:
            return False
        if isinstance(response, dict) and 'errors' in response:
            raise APIError('[TzstatsTezosApi][ValidateGeneralResponse] Error:' + response.get('errors'))
        return True

    @classmethod
    def validate_balance_response(cls, balance_response) -> bool:
        if (cls.validate_general_response(balance_response)
                and len(balance_response[0]) == 2
                and isinstance(balance_response[0][1], float)):
            return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response) -> bool:
        return cls.validate_general_response(tx_details_response)

    @classmethod
    def validate_transaction(cls, transaction) -> bool:
        if (transaction is None
                or any(transaction.get(field) is None for field in
                       ('type', 'hash', 'time', 'status', 'is_success', 'volume', 'sender', 'receiver'))):
            return False
        if (transaction.get('type') != 'transaction'
                or not transaction.get('is_success')
                or transaction.get('sender') == transaction.get('receiver')
                or transaction.get('volume') <= 0
                or transaction.get('status') != 'applied'
                or 'initiator' in transaction
                or ('parameters' in transaction and transaction.get('parameters', ''))
                or ('is_contract' in transaction and transaction.get('is_contract'))
                or ('is_internal' in transaction and transaction.get('is_internal'))):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response) -> bool:
        if cls.validate_general_response(block_head_response) and block_head_response.get('height') is not None:
            return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response) -> bool:
        return cls.validate_general_response(address_txs_response)

    @classmethod
    def validate_block_txs_response(cls, block_txs_response) -> bool:
        return cls.validate_general_response(block_txs_response)

    @classmethod
    def validate_amount(cls, amount):
        if cls.min_valid_tx_amount < Decimal(str(amount)):
            return True
        return False

    @classmethod
    def validate_block_txs_raw_response(cls, block_txs_raw_response) -> bool:
        if not block_txs_raw_response or not isinstance(block_txs_raw_response, list):
            return False
        return True


class TzstatsParserTezos(ResponseParser):
    validator = TzstatsValidatorTezos
    symbol = 'XTZ'
    currency = Currencies.xtz
    precision = 6

    @classmethod
    def parse_balance_response(cls, balance_response) -> Decimal:
        if cls.validator.validate_balance_response(balance_response):
            return Decimal(str(balance_response[0][1]))

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=(tx.get('height')),
                block_hash=tx.get('block'),
                tx_hash=tx.get('hash'),
                date=parse_iso_date(tx.get('time')),
                success=True,
                confirmations=tx.get('confirmations'),
                from_address=tx.get('sender'),
                to_address=tx.get('receiver'),
                value=Decimal(str(tx.get('volume'))),
                symbol=cls.symbol,
                memo=None,
                tx_fee=Decimal(str(tx.get('fee'))),
                token=None,
            )
            for tx in tx_details_response
            if cls.validator.validate_transaction(tx) and cls.validator.validate_amount(tx.get('volume'))
        ] if cls.validator.validate_tx_details_response(tx_details_response) else []

    @classmethod
    def parse_block_head_response(cls, block_head_response):
        if cls.validator.validate_block_head_response(block_head_response):
            return int(block_head_response.get('height'))

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=(tx.get('height')),
                block_hash=tx.get('block'),
                tx_hash=tx.get('hash'),
                date=parse_iso_date(tx.get('time')),
                success=True,
                confirmations=tx.get('confirmations'),
                from_address=tx.get('sender'),
                to_address=tx.get('receiver'),
                value=Decimal(str(tx.get('volume'))),
                symbol=cls.symbol,
                memo=None,
                tx_fee=Decimal(str(tx.get('fee'))),
                token=None,
            )
            for tx in address_txs_response
            if cls.validator.validate_transaction(tx) and cls.validator.validate_amount(tx.get('volume'))
        ] if cls.validator.validate_general_response(address_txs_response) else []

    @classmethod
    def parse_block_txs_response(cls, block_txs_response) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=(tx.get('height')),
                block_hash=tx.get('block'),
                tx_hash=tx.get('hash'),
                date=parse_iso_date(tx.get('time')),
                success=True,
                confirmations=tx.get('confirmations'),
                from_address=tx.get('sender'),
                to_address=tx.get('receiver'),
                value=Decimal(str(tx.get('volume'))),
                symbol=cls.symbol,
                memo=None,
                tx_fee=Decimal(str(tx.get('fee'))),
                token=None,
            )
            for tx in block_txs_response
            if cls.validator.validate_transaction(tx)
        ] if cls.validator.validate_block_txs_response(block_txs_response) else []


class TzstatsTezosAPI(GeneralApi):
    parser = TzstatsParserTezos
    symbol = 'XTZ'
    cache_key = 'xtz'
    _base_url = 'https://api.tzpro.io'
    block_height_offset = 4
    USE_PROXY = True
    supported_requests = {
        'get_balance': '/series/balance?address={address}&limit=1',
        'get_tx_details': '/explorer/op/{tx_hash}',
        'get_block_head': '/explorer/block/head',
        'get_address_txs': '/explorer/account/{address}/operations',
        'get_block_txs': '/explorer/block/{height}/operations'
    }

    @classmethod
    def get_api_key(cls):
        return '9AKZW1IUS0K1R1NTTY3ZAW4JKI604OD'

    @classmethod
    def get_headers(cls):
        return {'X-API-Key': cls.get_api_key()}
