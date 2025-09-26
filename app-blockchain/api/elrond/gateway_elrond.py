import datetime
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


class GatewayElrondValidator(ResponseValidator):
    successful_code = 'successful'
    valid_operation = 'transfer'
    success_status = 'success'
    min_valid_tx_amount = Decimal(0)
    valid_block_status = 'on-chain'
    valid_mini_block_type = 'TxBlock'

    @classmethod
    def validate_general_response(cls, response: Dict[str, Any]) -> bool:
        if response.get('code') != cls.successful_code:
            return False
        if response.get('error') != '':
            return False
        if response.get('data') is None:
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(balance_response):
            return False
        if balance_response.get('data').get('balance') is None:
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        transaction = tx_details_response.get('data').get('transaction')
        return cls.validate_transaction(transaction)

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if transaction is None:
            return False
        if (transaction.get('operation') or transaction.get('function')) != cls.valid_operation:
            return False
        if transaction.get('function') is not None and transaction.get('function') != cls.valid_operation:
            return False
        if transaction.get('receiver') == transaction.get('sender'):
            return False
        if transaction.get('status') != cls.success_status:
            return False
        if Decimal(transaction.get('value')) <= cls.min_valid_tx_amount:
            return False
        return True

    @classmethod
    def validate_mini_block(cls, mini_block: Dict[str, Any]) -> bool:
        if mini_block.get('type') != cls.valid_mini_block_type:
            return False
        return True

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(block_txs_response):
            return False
        if block_txs_response.get('data').get('block') is None:
            return False
        if block_txs_response.get('data').get('block').get('status') != cls.valid_block_status:
            return False
        if not isinstance(block_txs_response.get('data').get('block').get('miniBlocks'), list):
            return False
        return True

    @classmethod
    def validate_block_txs_raw_response(cls, block_txs_raw_response: Dict[str, Any]) -> bool:
        if not block_txs_raw_response or not isinstance(block_txs_raw_response, dict):
            return False
        if not block_txs_raw_response.get('data') or not isinstance(block_txs_raw_response.get('data'), dict):
            return False
        if (not block_txs_raw_response.get('data').get('block') or
                not isinstance(block_txs_raw_response.get('data').get('block'), dict)):
            return False
        if (not block_txs_raw_response.get('data').get('block').get('miniBlocks') or
                not isinstance(block_txs_raw_response.get('data').get('block').get('miniBlocks'), list)):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        if (block_head_response.get('data') is None or
                block_head_response.get('data').get('status') is None or
                block_head_response.get('data').get('status').get('erd_highest_final_nonce') is None):
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: List[Dict[str, Any]]) -> bool:
        if address_txs_response is None or len(address_txs_response) == 0:
            return False
        return True


class ElrondGatewayResponseParser(ResponseParser):
    validator = GatewayElrondValidator

    symbol = 'EGLD'
    currency = Currencies.egld
    precision = 18
    average_block_time = 6

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, Any]) -> Decimal:
        if not cls.validator.validate_balance_response(balance_response):
            return Decimal(0)
        return BlockchainUtilsMixin.from_unit(
            int(balance_response.get('data').get('balance')),
            precision=cls.precision
        )

    @classmethod
    def parse_tx_details_response(
            cls,
            tx_details_response: Dict[str, Any],
            block_head: int
    ) -> Optional[List[TransferTx]]:
        _ = block_head
        if not cls.validator.validate_tx_details_response(tx_details_response):
            return None
        transaction = tx_details_response.get('data').get('transaction')
        # Block height is only for destination shard
        block = transaction.get('blockNonce') if transaction.get('destinationShard') == 1 else 0
        confirmations = cls.calculate_tx_confirmations(transaction.get('timestamp'))
        fee = BlockchainUtilsMixin.from_unit(int(transaction.get('initiallyPaidFee')), cls.precision)
        return [TransferTx(
            tx_hash=transaction.get('hash'),
            success=True,
            block_height=block,
            date=parse_utc_timestamp(transaction.get('timestamp')),
            confirmations=confirmations,
            symbol=cls.symbol,
            from_address=transaction.get('sender'),
            to_address=transaction.get('receiver'),
            value=BlockchainUtilsMixin.from_unit(int(transaction.get('value')), precision=cls.precision),
            block_hash=transaction.get('blockHash'),
            tx_fee=fee,
            memo=None,
            token=None
        )]

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, Any]) -> Optional[int]:
        if not cls.validator.validate_block_head_response(block_head_response):
            return None
        return block_head_response.get('data').get('status').get('erd_highest_final_nonce')

    @classmethod
    def parse_address_txs_response(cls, address: str, address_txs_response: List[Dict[str, Any]],
                                   __: int) -> List[TransferTx]:
        _ = address
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return []
        address_txs: List[TransferTx] = []
        for transaction in address_txs_response:
            confirmations = cls.calculate_tx_confirmations(transaction.get('timestamp'))
            if cls.validator.validate_transaction(transaction):
                fee = BlockchainUtilsMixin.from_unit(int(transaction.get('fee')), cls.precision)
                address_tx = TransferTx(
                    tx_hash=transaction.get('txHash'),
                    from_address=transaction.get('sender'),
                    to_address=transaction.get('receiver'),
                    value=BlockchainUtilsMixin.from_unit(
                        int(transaction.get('value')),
                        precision=cls.precision
                    ),
                    block_height=0,
                    date=parse_utc_timestamp(transaction.get('timestamp')),
                    confirmations=confirmations,
                    tx_fee=fee,
                    success=True,
                    symbol=cls.symbol,
                    memo=None,
                    block_hash=None
                )
                address_txs.append(address_tx)
        return address_txs

    @classmethod
    def calculate_tx_confirmations(cls, tx_date: float) -> int:
        diff = (datetime.datetime.timestamp(datetime.datetime.now(datetime.timezone.utc)) - tx_date)
        return int(diff / cls.average_block_time)

    @classmethod
    def parse_block_txs_response(cls, block_txs_response: Dict[str, Any]) -> Optional[List[TransferTx]]:
        if not cls.validator.validate_block_txs_response(block_txs_response):
            return None
        block_txs: List[TransferTx] = []
        for mini_block in block_txs_response.get('data').get('block').get('miniBlocks'):
            if cls.validator.validate_mini_block(mini_block):
                for tx in mini_block.get('transactions'):
                    if cls.validator.validate_transaction(tx):
                        from_address = tx.get('sender')
                        to_address = tx.get('receiver')
                        tx_hash = tx.get('hash')
                        tx_value = tx.get('value')
                        confirmations = cls.calculate_tx_confirmations(
                            block_txs_response.get('data').get('block').get('timestamp'))
                        block_tx = TransferTx(
                            from_address=from_address,
                            to_address=to_address,
                            tx_hash=tx_hash,
                            symbol=cls.symbol,
                            value=BlockchainUtilsMixin.from_unit(int(tx_value), precision=cls.precision),
                            tx_fee=BlockchainUtilsMixin.from_unit(int(tx.get('initiallyPaidFee')), cls.precision),
                            success=True,
                            block_hash=block_txs_response.get('data').get('block').get('hash'),
                            confirmations=confirmations,
                            block_height=block_txs_response.get('data').get('block').get('nonce'),
                            date=parse_utc_timestamp(block_txs_response.get('data').get('block').get('timestamp')),
                            memo=None,
                        )
                        block_txs.append(block_tx)
        return block_txs


class GatewayElrondApi(GeneralApi):
    parser = ElrondGatewayResponseParser
    _base_url = 'https://gateway.multiversx.com'
    cache_key = 'egld'
    shard_number = 1
    USE_PROXY = False
    instance = None
    supported_requests = {
        'get_balance': '/address/{address}/balance',
        'get_tx_details': '/transaction/{tx_hash}',
        'get_address_txs': '/accounts/{address}/transactions',
        'get_block_txs': f'/block/{shard_number}/by-nonce/{{height}}?withTxs=true',
        'get_block_head': f'/network/status/{shard_number}'
    }
