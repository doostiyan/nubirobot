import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings

from exchange.base.parsers import parse_utc_timestamp_ms
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class NearOfficialValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.05')
    precision = 24

    @classmethod
    def validate_general_response(cls, response: Any) -> bool:
        if not response:
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: List[Dict[str, Any]]) -> bool:
        if (cls.validate_general_response(block_head_response)
                and isinstance(block_head_response, list)
                and block_head_response[0]
                and block_head_response[0].get('result')
                and block_head_response[0].get('result').get('data')
                and isinstance(block_head_response[0].get('result').get('data'), list)
                and block_head_response[0].get('result').get('data')[0].get('height')):
            return True
        return False

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: List[Dict[str, Any]]) -> bool:
        if (cls.validate_general_response(tx_details_response)
                and isinstance(tx_details_response, list)
                and tx_details_response[0]
                and tx_details_response[0].get('result')
                and tx_details_response[0].get('result').get('data')):
            return True
        return False

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if any(not transaction.get(field) for field in
               ('signerId', 'receiverId', 'hash', 'status', 'actions', 'blockHash')):
            return False
        if (transaction.get('signerId').casefold() == transaction.get('receiverId').casefold()
                or transaction.get('status') != 'success'
                or len(transaction.get('actions')) != 1  # as we do not support multiple transfer
                or not transaction.get('actions')[0].get('args').get('deposit')
                or BlockchainUtilsMixin.from_unit(
                    int(Decimal(transaction.get('actions')[0].get('args').get('deposit'))),
                    precision=cls.precision) <= cls.min_valid_tx_amount
                or transaction.get('actions')[0].get('kind') != 'transfer'):
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: List[Dict[str, Any]]) -> bool:
        if (cls.validate_general_response(address_txs_response)
                and isinstance(address_txs_response, list)
                and address_txs_response[0]
                and address_txs_response[0].get('result')
                and address_txs_response[0].get('result').get('data')
                and address_txs_response[0].get('result').get('data').get('items')):
            return True
        return False

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: List[Dict[str, Any]]) -> bool:
        if (cls.validate_general_response(block_txs_response)
                and isinstance(block_txs_response, list)
                and block_txs_response[0]
                and block_txs_response[0].get('result')
                and block_txs_response[0].get('result').get('data')
                and block_txs_response[0].get('result').get('data').get('items')):
            return True
        return False

    @classmethod
    def validate_block_hash_response(cls, block_hash_response: List[Dict[str, Any]]) -> bool:
        if (cls.validate_general_response(block_hash_response)
                and isinstance(block_hash_response, list)
                and block_hash_response[0]
                and block_hash_response[0].get('result')
                and block_hash_response[0].get('result').get('data')
                and block_hash_response[0].get('result').get('data').get('transactionsCount')
                and block_hash_response[0].get('result').get('data').get('hash')):
            return True
        return False


class NearOfficialParser(ResponseParser):
    validator = NearOfficialValidator
    precision = 24
    symbol = 'NEAR'
    currency = Currencies.near

    @classmethod
    def parse_block_head_response(cls, block_head_response: List[Dict[str, Any]]) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return int(block_head_response[0].get('result').get('data')[0].get('height'))
        return None

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: List[Dict[str, Any]], _: int) -> List[TransferTx]:
        if cls.validator.validate_tx_details_response(tx_details_response):
            tx = tx_details_response[0].get('result').get('data')
            date = parse_utc_timestamp_ms(tx.get('blockTimestamp'))
            return [
                TransferTx(
                    block_height=None,
                    block_hash=tx.get('blockHash'),
                    tx_hash=tx.get('hash'),
                    date=date,
                    success=True,
                    confirmations=cls.calculate_tx_confirmations(date),
                    from_address=tx.get('signerId'),
                    to_address=tx.get('receiverId'),
                    value=BlockchainUtilsMixin.from_unit(int(tx.get('actions')[0].get('args').get('deposit')),
                                                         precision=cls.precision),
                    symbol=cls.symbol,
                    memo=None,
                    # According to the response of other apis, we can calculate fee in this way:
                    tx_fee=BlockchainUtilsMixin.from_unit(int(tx.get('outcome').get('tokensBurnt')) * 2,
                                                          precision=cls.precision),
                    token=None,
                )
            ] if cls.validator.validate_transaction(tx) else []
        return []

    @classmethod
    def parse_address_txs_response(cls,
                                   _: str,
                                   address_txs_response: List[Dict[str, Any]],
                                   __: int) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=None,
                block_hash=tx.get('blockHash'),
                tx_hash=tx.get('hash'),
                date=parse_utc_timestamp_ms(tx.get('blockTimestamp')),
                success=True,
                confirmations=cls.calculate_tx_confirmations(parse_utc_timestamp_ms(tx.get('blockTimestamp'))),
                from_address=tx.get('signerId'),
                to_address=tx.get('receiverId'),
                value=BlockchainUtilsMixin.from_unit(int(tx.get('actions')[0].get('args').get('deposit')),
                                                     precision=cls.precision),
                symbol=cls.symbol,
                memo=None,
                tx_fee=None,
                token=None,
            )
            for tx in address_txs_response[0].get('result').get('data').get('items')
            if cls.validator.validate_transaction(tx)
        ] if cls.validator.validate_address_txs_response(address_txs_response) else []

    @classmethod
    def parse_block_txs_response(cls, block_txs_response: List[Dict[str, Any]]) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=None,
                block_hash=tx.get('blockHash'),
                tx_hash=tx.get('hash'),
                date=parse_utc_timestamp_ms(tx.get('blockTimestamp')),
                success=True,
                confirmations=cls.calculate_tx_confirmations(parse_utc_timestamp_ms(tx.get('blockTimestamp'))),
                from_address=tx.get('signerId'),
                to_address=tx.get('receiverId'),
                value=BlockchainUtilsMixin.from_unit(int(tx.get('actions')[0].get('args').get('deposit')),
                                                     precision=cls.precision),
                symbol=cls.symbol,
                memo=None,
                tx_fee=None,
                token=None,
            )
            for tx in block_txs_response[0].get('result').get('data').get('items')
            if cls.validator.validate_transaction(tx)
        ] if cls.validator.validate_block_txs_response(block_txs_response) else []

    @classmethod
    def parse_block_hash_response(cls, block_hash_response: List[Dict[str, Any]]) -> Optional[Tuple[str, int]]:
        if cls.validator.validate_block_hash_response(block_hash_response):
            block_hash = block_hash_response[0].get('result').get('data').get('hash')
            txs_count = block_hash_response[0].get('result').get('data').get('transactionsCount')
            return block_hash, txs_count
        return None

    @classmethod
    def calculate_tx_confirmations(cls, tx_date: datetime) -> int:
        diff = (datetime.datetime.now(datetime.timezone.utc) - tx_date).total_seconds()
        return int(diff / 1.2)  # Near block time is 1 seconds, for more reliability we get it for '1.2'.


class NearOfficialAPI(GeneralApi):
    """
    API Explorer: https://explorer.near.org
    """
    parser = NearOfficialParser
    cache_key = 'near'
    symbol = 'NEAR'
    USE_PROXY = bool(not settings.IS_VIP)
    TRANSACTIONS_LIMIT = 50
    _base_url = 'https://explorer-backend-mainnet-prod-24ktefolwq-uc.a.run.app/'
    supported_requests = {
        'get_address_txs': 'trpc/transaction.listByAccountId?batch=1&input={{"0":{{"accountId":"{address}",'
                           '"limit":10}}}}',
        'get_block_head': 'trpc/block.list?batch=1&input={{"0":{{"limit":1}}}}',
        'get_block_txs': 'trpc/transaction.listByBlockHash?batch=1&input={{"0":{{"blockHash":"{hash}",'
                         '"limit":{limit}}}}}',
        'get_block_hash': 'trpc/block.byId?batch=1&input={{"0":{{"height":{block_height}}}}}',
        'get_tx_details': 'trpc/transaction.byHashOld?batch=1&input={{"0":{{"hash":"{tx_hash}"}}}}',
    }

    # In this API, to get block transactions, we first need to make a request and get the block hash first,
    # and then use the block hash to get the block transactions.
    @classmethod
    def get_block_hash(cls, block_height: int) -> Any:
        return cls.request('get_block_hash', block_height=block_height)

    @classmethod
    def get_block_txs(cls, block_hash: str, txs_count: int) -> Any:
        return cls.request('get_block_txs', hash=block_hash, limit=min(txs_count, cls.TRANSACTIONS_LIMIT))
