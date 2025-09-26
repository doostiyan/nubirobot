from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.conf import settings

from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_utc_timestamp
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
    from exchange.base.parsers import parse_utc_timestamp

from exchange.blockchain.api.general.dtos.dtos import TransferTx


class AlgoExplorerAlgorandValidator(ResponseValidator):
    valid_operation = 'pay'
    min_valid_tx_amount = Decimal('1')
    precision = 6

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, Any]) -> bool:
        if not balance_response.get('account'):
            return False
        if not balance_response.get('account').get('address'):
            return False
        if balance_response.get('account').get('amount') is None or not isinstance(
                balance_response.get('account').get('amount'), int):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, Any]) -> bool:
        if not tx_details_response.get('current-round'):
            return False
        if not tx_details_response.get('transaction'):
            return False
        transaction = tx_details_response.get('transaction')
        return cls.validate_transaction(transaction)

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if transaction.get('tx-type') != cls.valid_operation:
            return False
        if not isinstance(transaction.get('confirmed-round'), int):
            return False
        if transaction.get('confirmed-round') < transaction.get('first-valid') or transaction.get(
                'confirmed-round') > transaction.get('last-valid'):
            return False
        if not transaction.get('payment-transaction'):
            return False
        if transaction.get('payment-transaction').get('receiver') == transaction.get('sender'):
            return False
        value = BlockchainUtilsMixin.from_unit(transaction.get('payment-transaction').get('amount'),
                                               precision=cls.precision)
        if value < cls.min_valid_tx_amount:
            return False
        if not transaction.get('signature').get('sig'):
            return False
        return True

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: Dict[str, Any]) -> bool:
        if not block_txs_response:
            return False
        if not block_txs_response.get('transactions'):
            return False
        if (not block_txs_response.get('genesis-hash')
                or block_txs_response.get('genesis-hash') != 'wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8='):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, Any]) -> bool:
        if not block_head_response:
            return False
        if block_head_response.get('current-round') is None or not isinstance(block_head_response.get('current-round'),
                                                                              int):
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Dict[str, Any]) -> bool:
        if not address_txs_response.get('transactions'):
            return False
        if not address_txs_response.get('current-round'):
            return False
        return True

    @classmethod
    def validate_batch_block_txs_response(cls, batch_block_txs_response: Dict[str, Any]) -> bool:
        if not batch_block_txs_response:
            return False
        if batch_block_txs_response.get('current-round') is None:
            return False
        if not batch_block_txs_response.get('transactions'):
            return False
        return True

    @classmethod
    def validate_block_tx_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if transaction.get('genesis-hash') != 'wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8=':
            return False
        return cls.validate_transaction(transaction)

    @classmethod
    def validate_block_txs_raw_response(cls, block_txs_raw_response: Dict[str, Any]) -> bool:
        if not block_txs_raw_response or not isinstance(block_txs_raw_response, dict):
            return False
        if (not block_txs_raw_response.get('transactions')
                or not isinstance(block_txs_raw_response.get('transactions'), list)):
            return False
        return True


class AlgoExplorerAlgorandResponseParser(ResponseParser):
    validator = AlgoExplorerAlgorandValidator
    symbol = 'ALGO'
    currency = Currencies.algo
    precision = 6

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, Any]) -> Decimal:
        if cls.validator.validate_balance_response(balance_response):
            return BlockchainUtilsMixin.from_unit(balance_response.get('account').get('amount'),
                                                  precision=cls.precision)
        return Decimal(0)

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, Any], __: int) -> List[TransferTx]:
        if cls.validator.validate_tx_details_response(tx_details_response):
            transaction = tx_details_response.get('transaction')
            block_height = transaction.get('confirmed-round')
            confirmations = tx_details_response.get('current-round') - block_height + 1
            date = parse_utc_timestamp(transaction.get('round-time'))
            from_address = transaction.get('sender')
            to_address = transaction.get('payment-transaction').get('receiver')
            value = BlockchainUtilsMixin.from_unit(transaction.get('payment-transaction').get('amount'),
                                                   precision=cls.precision)
            tx_fee = BlockchainUtilsMixin.from_unit(transaction.get('fee'), precision=cls.precision)
            return [TransferTx(
                tx_hash=transaction.get('id'),
                from_address=from_address,
                to_address=to_address,
                success=True,
                block_height=block_height,
                date=date,
                tx_fee=tx_fee,
                memo=None,
                confirmations=confirmations,
                value=value,
                symbol=cls.symbol,
                token=None,
                block_hash=None
            )]
        return []

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, Any]) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return block_head_response.get('current-round')
        return None

    @classmethod
    def parse_address_txs_response(cls, address: str, address_txs_response: Dict[str, Any],
                                   __: int) -> List[TransferTx]:
        _ = address
        address_txs: List[TransferTx] = []
        if cls.validator.validate_address_txs_response(address_txs_response):
            transactions = address_txs_response.get('transactions')
            for transaction in transactions:
                if cls.validator.validate_transaction(transaction):
                    block_height = transaction.get('confirmed-round')
                    confirmations = address_txs_response.get('current-round') - block_height + 1
                    date = parse_utc_timestamp(transaction.get('round-time'))
                    from_address = transaction.get('sender')
                    to_address = transaction.get('payment-transaction').get('receiver')
                    value = BlockchainUtilsMixin.from_unit(transaction.get('payment-transaction').get('amount'),
                                                           precision=cls.precision)
                    tx_fee = BlockchainUtilsMixin.from_unit(transaction.get('fee'), precision=cls.precision)
                    address_tx = TransferTx(
                        tx_hash=transaction.get('id'),
                        from_address=from_address,
                        to_address=to_address,
                        value=value,
                        block_height=block_height,
                        date=date,
                        confirmations=confirmations,
                        memo=None,
                        block_hash=None,
                        success=True,
                        symbol=cls.symbol,
                        tx_fee=tx_fee
                    )
                    address_txs.append(address_tx)
        return address_txs

    @classmethod
    def parse_block_txs_response(cls, block_txs_response: Dict[str, Any]) -> List[TransferTx]:
        block_txs: List[TransferTx] = []
        if cls.validator.validate_block_txs_response(block_txs_response):
            block_hash = block_txs_response.get('hash')
            for transaction in block_txs_response.get('transactions'):
                if cls.validator.validate_transaction(transaction):
                    block_height = transaction.get('confirmed-round')
                    date = parse_utc_timestamp(transaction.get('round-time'))
                    from_address = transaction.get('sender')
                    to_address = transaction.get('payment-transaction').get('receiver')
                    value = BlockchainUtilsMixin.from_unit(transaction.get('payment-transaction').get('amount'),
                                                           precision=cls.precision)
                    tx_fee = BlockchainUtilsMixin.from_unit(transaction.get('fee'), precision=cls.precision)
                    block_tx = TransferTx(
                        from_address=from_address,
                        to_address=to_address,
                        tx_hash=transaction.get('id'),
                        symbol=cls.symbol,
                        value=value,
                        success=True,
                        block_hash=block_hash,
                        block_height=block_height,
                        confirmations=None,
                        date=date,
                        memo=None,
                        tx_fee=tx_fee
                    )
                    block_txs.append(block_tx)
        return block_txs

    @classmethod
    def parse_batch_block_txs_response(cls, batch_block_txs_response: Dict[str, Any]) -> List[TransferTx]:
        block_txs: List[TransferTx] = []
        if cls.validator.validate_batch_block_txs_response(batch_block_txs_response):
            block_head = batch_block_txs_response.get('current-round')
            transactions = batch_block_txs_response.get('transactions')
            for transaction in transactions:
                if cls.validator.validate_block_tx_transaction(transaction):
                    block_height = transaction.get('confirmed-round')
                    confirmations = block_head - block_height + 1
                    date = parse_utc_timestamp(transaction.get('round-time'))
                    from_address = transaction.get('sender')
                    to_address = transaction.get('payment-transaction').get('receiver')
                    value = BlockchainUtilsMixin.from_unit(transaction.get('payment-transaction').get('amount'),
                                                           precision=cls.precision)
                    tx_fee = BlockchainUtilsMixin.from_unit(transaction.get('fee'), precision=cls.precision)
                    block_tx = TransferTx(
                        tx_hash=transaction.get('id'),
                        from_address=from_address,
                        to_address=to_address,
                        value=value,
                        block_height=block_height,
                        date=date,
                        confirmations=confirmations,
                        memo=None,
                        block_hash=None,
                        success=True,
                        symbol=cls.symbol,
                        tx_fee=tx_fee
                    )
                    block_txs.append(block_tx)
        return block_txs


class AlgoExplorerAlgorandApi(GeneralApi):
    parser = AlgoExplorerAlgorandResponseParser
    _base_url = 'https://indexer.algoexplorerapi.io/'
    cache_key = 'algo'
    rate_limit = 0  # couldn't find any information over its rate limit
    headers = {'content-type': 'application/json'}
    need_block_head_for_confirmation = False
    api_key = None
    block_tx_limit = 1000
    transactions_limit = 25
    supported_requests = {
        'get_balance': 'v2/accounts/{address}',
        'get_tx_details': 'v2/transactions/{tx_hash}',
        'get_address_txs': 'v2/accounts/{address}/transactions',
        'get_block_txs': 'v2/blocks/{height}',
        'get_block_head': 'v2/transactions?limit=1',
        'get_blocks_txs': 'v2/transactions?limit=0&currency-greater-than=0&tx-type=pay&min-round={from_block}&max-round'
                          '={to_block}&sig-type=sig'
    }
