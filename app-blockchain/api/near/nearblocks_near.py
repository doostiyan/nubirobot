import random
from datetime import timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.conf import settings

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_utc_timestamp_nanosecond
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
    from exchange.base.parsers import parse_utc_timestamp_nanosecond


class NearBlocksValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.05')
    precision = 24

    @classmethod
    def validate_general_response(cls, response: Any) -> bool:
        if not response:
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, Any]) -> bool:
        if (cls.validate_general_response(block_head_response)
                and block_head_response.get('blocks')
                and isinstance(block_head_response.get('blocks'), list)
                and block_head_response.get('blocks')[0].get('block_height')):
            return True
        return False

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, Any]) -> bool:
        if (cls.validate_general_response(balance_response)
                and balance_response.get('account') and balance_response.get('account')[0].get('amount')):
            return True
        return False

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, Any]) -> bool:
        if cls.validate_general_response(tx_details_response) and tx_details_response.get('txns'):
            return True
        return False

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if (any(not transaction.get(field) for field in
                ('transaction_hash', 'block_timestamp', 'block', 'receiver_account_id',
                 'actions', 'actions_agg', 'outcomes', 'outcomes_agg'))):
            return False

        if (not transaction.get('outcomes').get('status')
                or not transaction.get('block').get('block_height')
                or not transaction.get('outcomes_agg').get('transaction_fee')
                or not transaction.get('actions_agg').get('deposit')
                or transaction.get('actions')[0].get('action').casefold() != 'TRANSFER'.casefold()
                or BlockchainUtilsMixin.from_unit(int(Decimal(str(transaction.get('actions_agg').get('deposit')))),
                                                  precision=cls.precision) <= cls.min_valid_tx_amount):
            return False

        if ('signer_account_id' in transaction and
                (transaction.get('signer_account_id').casefold() == transaction.get('receiver_account_id').casefold()
                 or transaction.get('signer_account_id').casefold() == 'system'.casefold())):
            return False
        if ('predecessor_account_id' in transaction and
                (transaction.get('predecessor_account_id').casefold() == transaction.get(
                    'receiver_account_id').casefold()
                 or transaction.get('predecessor_account_id').casefold() == 'system'.casefold())):
            return False

        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Dict[str, Any]) -> bool:
        if cls.validate_general_response(address_txs_response) and address_txs_response.get('txns'):
            return True
        return False


class NearBlocksParser(ResponseParser):
    validator = NearBlocksValidator
    precision = 24
    symbol = 'NEAR'
    currency = Currencies.near

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, Any]) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return int(block_head_response.get('blocks')[0].get('block_height'))
        return None

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, Any]) -> Optional[Decimal]:
        if cls.validator.validate_balance_response(balance_response):
            return BlockchainUtilsMixin.from_unit(int(balance_response.get('account')[0].get('amount')),
                                                  precision=cls.precision)
        return None

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, Any], block_head: int) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=tx.get('block').get('block_height'),
                block_hash=tx.get('included_in_block_hash'),
                tx_hash=tx.get('transaction_hash'),
                date=parse_utc_timestamp_nanosecond(tx.get('block_timestamp')).replace(tzinfo=timezone.utc),
                success=True,
                confirmations=block_head - tx.get('block').get('block_height'),
                from_address=tx.get('signer_account_id'),
                to_address=tx.get('receiver_account_id'),
                value=BlockchainUtilsMixin.from_unit(int(Decimal(str(tx.get('actions_agg').get('deposit')))),
                                                     precision=cls.precision),
                symbol=cls.symbol,
                memo=None,
                tx_fee=BlockchainUtilsMixin.from_unit(tx.get('outcomes_agg').get('transaction_fee'),
                                                      precision=cls.precision),
                token=None,
            )
            for tx in tx_details_response.get('txns')
            if cls.validator.validate_transaction(tx)
        ] if cls.validator.validate_tx_details_response(tx_details_response) else []

    @classmethod
    def parse_address_txs_response(cls,
                                   _: str,
                                   address_txs_response: Dict[str, Any],
                                   block_head: int) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=tx.get('block').get('block_height'),
                block_hash=None,
                tx_hash=tx.get('transaction_hash'),
                date=parse_utc_timestamp_nanosecond(tx.get('block_timestamp')).replace(tzinfo=timezone.utc),
                success=True,
                confirmations=block_head - tx.get('block').get('block_height'),
                from_address=tx.get('predecessor_account_id'),
                to_address=tx.get('receiver_account_id'),
                value=BlockchainUtilsMixin.from_unit(int(Decimal(str(tx.get('actions_agg').get('deposit')))),
                                                     precision=cls.precision),
                symbol=cls.symbol,
                memo=None,
                tx_fee=BlockchainUtilsMixin.from_unit(tx.get('outcomes_agg').get('transaction_fee'),
                                                      precision=cls.precision),
                token=None,
            )
            for tx in address_txs_response.get('txns')
            if cls.validator.validate_transaction(tx)
        ] if cls.validator.validate_address_txs_response(address_txs_response) else []


class NearBlocksApi(GeneralApi):
    """
    API Doc: https://api.nearblocks.io/api-docs/
    """
    parser = NearBlocksParser
    cache_key = 'near'
    symbol = 'NEAR'
    _base_url = 'https://api3.nearblocks.io'
    supported_requests = {
        'get_balance': '/v1/account/{address}',
        'get_block_head': '/v1/blocks/latest?limit=1',
        'get_tx_details': '/v1/txns/{tx_hash}',
        'get_address_txs': '/v1/account/{address}/txns?page=1&per_page=25&order=desc'
    }

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + cls.get_api_key()
        }

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.NEAR_BLOCKS_APIKEY)

    max_workers_for_get_block = 3
