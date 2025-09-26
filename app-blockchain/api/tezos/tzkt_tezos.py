import json
from typing import List
from decimal import Decimal
from django.conf import settings
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin
from exchange.blockchain.api.general.general import GeneralApi, ResponseValidator, ResponseParser

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class TzktTezosValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.01')

    @classmethod
    def validate_general_response(cls, response):
        if not response:
            return False
        if isinstance(response, dict):
            if 'errors' in response:
                raise APIError('[TzktTezosApi][ValidateGeneralResponse] Error:' + response.get('errors'))
        return True

    @classmethod
    def validate_balance_response(cls, balance_response) -> bool:
        if cls.validate_general_response(balance_response) and isinstance(balance_response, int):
            return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response) -> bool:
        return cls.validate_general_response(tx_details_response)

    @classmethod
    def validate_transaction(cls, transaction) -> bool:
        if (transaction is None
                or any(transaction.get(field) is None for field in
                       ('type', 'hasInternals', 'timestamp', 'amount', 'status', 'level', 'target', 'sender'))):
            return False
        if ((transaction.get('type') != 'transaction')
                or (transaction.get('sender').get('address') == transaction.get('target').get('address'))
                or (transaction.get('amount') <= 0)
                or (transaction.get('status') != 'applied')
                or (transaction.get('hasInternals'))
                or ('targetCodeHash' in transaction)
                or ('parameter' in transaction and transaction.get('parameter', ''))
                or ('initiator' in transaction)):
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response) -> bool:
        return cls.validate_general_response(address_txs_response)

    @classmethod
    def validate_block_txs_response(cls, block_txs_response) -> bool:
        if cls.validate_general_response(block_txs_response) and block_txs_response.get('transactions') is not None:
            return True

    @classmethod
    def validate_block_txs_raw_response(cls, block_txs_raw_response) -> bool:
        if not block_txs_raw_response or not isinstance(block_txs_raw_response, dict):
            return False
        if not block_txs_raw_response.get('transactions') or not isinstance(block_txs_raw_response.get('transactions'), list):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response) -> bool:
        if cls.validate_general_response(block_head_response) and isinstance(block_head_response, int):
            return True

    @classmethod
    def validate_amount(cls, amount, precision):
        if cls.min_valid_tx_amount < BlockchainUtilsMixin.from_unit(int(amount), precision):
            return True
        return False


class TzktTezosParser(ResponseParser):
    validator = TzktTezosValidator
    symbol = 'XTZ'
    currency = Currencies.xtz
    precision = 6

    @classmethod
    def parse_balance_response(cls, balance_response) -> Decimal:
        if cls.validator.validate_balance_response(balance_response):
            return Decimal(BlockchainUtilsMixin.from_unit((int(balance_response)), precision=cls.precision))

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=(tx.get('level')),
                block_hash=tx.get('block'),
                tx_hash=tx.get('hash'),
                date=parse_iso_date(tx.get('timestamp')),
                success=True,
                confirmations=block_head - int(tx.get('level')),
                from_address=tx.get('sender').get('address'),
                to_address=tx.get('target').get('address'),
                value=BlockchainUtilsMixin.from_unit((int(tx.get('amount'))), precision=cls.precision),
                symbol=cls.symbol,
                memo=None,
                tx_fee=BlockchainUtilsMixin.from_unit(tx.get('bakerFee'), precision=cls.precision),
                token=None,
            )
            for tx in tx_details_response
            if cls.validator.validate_transaction(tx) and cls.validator.validate_amount(tx.get('amount'), cls.precision)
        ] if cls.validator.validate_tx_details_response(tx_details_response) else []

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=tx.get('level'),
                block_hash=tx.get('block'),
                tx_hash=tx.get('hash'),
                date=parse_iso_date(tx.get('timestamp')),
                success=True,
                confirmations=block_head - tx.get('level'),
                from_address=tx.get('sender').get('address'),
                to_address=tx.get('target').get('address'),
                value=BlockchainUtilsMixin.from_unit((int(tx.get('amount'))), precision=cls.precision),
                symbol=cls.symbol,
                memo=None,
                tx_fee=BlockchainUtilsMixin.from_unit(tx.get('bakerFee'), precision=cls.precision),
                token=None,
            )
            for tx in address_txs_response
            if cls.validator.validate_transaction(tx) and cls.validator.validate_amount(tx.get('amount'), cls.precision)
        ] if cls.validator.validate_address_txs_response(address_txs_response) else []

    @classmethod
    def parse_block_txs_response(cls, block_txs_response) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=tx.get('level'),
                block_hash=tx.get('block'),
                tx_hash=tx.get('hash'),
                date=parse_iso_date(tx.get('timestamp')),
                success=True,
                confirmations=None,
                from_address=tx.get('sender').get('address'),
                to_address=tx.get('target').get('address'),
                value=BlockchainUtilsMixin.from_unit((int(tx.get('amount'))), precision=cls.precision),
                symbol=cls.symbol,
                memo=None,
                tx_fee=BlockchainUtilsMixin.from_unit(tx.get('bakerFee'), precision=cls.precision),
                token=None,
            )
            for tx in block_txs_response.get('transactions')
            if cls.validator.validate_transaction(tx)
        ] if cls.validator.validate_block_txs_response(block_txs_response) else []

    @classmethod
    def parse_block_head_response(cls, block_head_response):
        if cls.validator.validate_block_head_response(block_head_response):
            return int(block_head_response)


class TzktTezosAPI(GeneralApi):
    parser = TzktTezosParser
    symbol = 'XTZ'
    cache_key = 'xtz'
    _base_url = 'https://api.tzkt.io/v1'
    block_height_offset = 4
    supported_requests = {
        'get_block_head': '/blocks/count',
        'get_balance': '/accounts/{address}/balance',
        'get_tx_details': '/operations/transactions/{tx_hash}',
        'get_address_txs': '/accounts/{address}/operations',
        'get_block_txs': '/blocks/{height}?operations=true'
    }
