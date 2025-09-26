from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

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


class FilecoinFilfoxValidator(ResponseValidator):
    precision = 18

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, Any]) -> bool:
        if not balance_response:
            return False
        if not balance_response.get('balance'):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: dict) -> bool:
        return cls.validate_transaction(tx_details_response)

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if not transaction.get('cid'):
            return False
        if transaction.get('receipt') is None or transaction.get('receipt').get('exitCode') != 0:
            return False
        if transaction.get('value') is None or BlockchainUtilsMixin.from_unit(
                int(transaction.get('value')), cls.precision) <= cls.min_valid_tx_amount:
            return False
        if transaction.get('method') is None or transaction.get('method').casefold() != 'Send'.casefold():
            return False
        if transaction.get('from') is None or transaction.get('to') is None or transaction.get(
                'from') == transaction.get('to'):
            return False
        return True

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: Dict[str, Any]) -> bool:
        if not block_txs_response:
            return False
        if not block_txs_response.get('messages'):
            return False
        return True

    @classmethod
    def validate_tipset_block_hash_response(cls, tipset_block_hash_response: Dict[str, Any]) -> bool:
        if not tipset_block_hash_response:
            return False
        if not tipset_block_hash_response.get('blocks'):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: List[Dict[str, int]]) -> bool:
        if len(block_head_response[0]) == 0:
            return False
        if block_head_response[0].get('height') is None:
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Dict[str, Any]) -> bool:
        if not address_txs_response.get('messages'):
            return False
        return True


class FilecoinFilfoxParser(ResponseParser):
    validator = FilecoinFilfoxValidator
    symbol = 'FIL'
    currency = Currencies.fil
    precision = 18

    @classmethod
    def calculate_fee(cls, transfers: List[Dict[str, Any]]) -> Decimal:
        fee = 0
        for transfer in transfers:
            if transfer.get('type') == 'miner-fee' or transfer.get('type') == 'burn-fee':
                fee = fee + int(transfer.get('value'))
        return BlockchainUtilsMixin.from_unit(fee, cls.precision)

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, Any]) -> Union[int, Decimal]:
        if cls.validator.validate_balance_response(balance_response):
            return BlockchainUtilsMixin.from_unit(int(balance_response.get('balance')), precision=cls.precision)
        return Decimal(0)

    @classmethod
    def parse_block_head_response(cls, block_head_response: List[Dict[str, Any]]) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return block_head_response[0].get('height')
        return None

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, Any], _: int) -> List[TransferTx]:
        if cls.validator.validate_tx_details_response(tx_details_response):
            transaction = tx_details_response
            block = transaction.get('height')
            confirmations = transaction.get('confirmations')
            separator = ','
            block_hash = separator.join(transaction.get('blocks'))
            return [TransferTx(
                tx_hash=transaction.get('cid'),
                from_address=transaction.get('from'),
                to_address=transaction.get('to'),
                success=True,
                block_height=block,
                date=parse_utc_timestamp(transaction.get('timestamp')),
                tx_fee=cls.calculate_fee(transaction.get('transfers')),
                memo=None,
                confirmations=confirmations,
                value=BlockchainUtilsMixin.from_unit(int(transaction.get('value')), precision=cls.precision),
                symbol=cls.symbol,
                token=None,
                block_hash=block_hash
            )]
        return []

    @classmethod
    def parse_address_txs_response(cls, address: str, address_txs_response: Dict[str, Any], block_head: int) -> List[
        TransferTx]:
        _ = address
        if cls.validator.validate_address_txs_response(address_txs_response):
            transactions = address_txs_response.get('messages')
            address_txs: List[TransferTx] = []
            for transaction in transactions:
                if cls.validator.validate_transaction(transaction):
                    block = transaction.get('height')
                    confirmations = block_head - block + 1
                    amount = BlockchainUtilsMixin.from_unit(int(transaction.get('value')), precision=cls.precision)
                    address_tx = TransferTx(
                        tx_hash=transaction.get('cid'),
                        from_address=transaction.get('from'),
                        to_address=transaction.get('to'),
                        value=amount,
                        block_height=block,
                        date=parse_utc_timestamp(transaction.get('timestamp')),
                        confirmations=confirmations,
                        memo=None,
                        block_hash=None,
                        success=True,
                        symbol=cls.symbol,
                        tx_fee=None
                    )
                    address_txs.append(address_tx)
            return address_txs
        return []

    @classmethod
    def parse_block_txs_response(cls,
                                 block_txs_response: List[Dict[str, Any]],
                                 block_height: Optional[int] = None) -> List[TransferTx]:
        txs = []
        for response in block_txs_response:
            if cls.validator.validate_block_txs_response(response):
                txs.append(response.get('messages'))
        transactions = [item for sublist in txs for item in sublist]
        block_txs: List[TransferTx] = []
        for tx in transactions:
            if cls.validator.validate_transaction(tx):
                from_address = tx.get('from')
                to_address = tx.get('to')
                tx_hash = tx.get('cid')
                tx_value = tx.get('value')
                block_tx = TransferTx(
                    from_address=from_address,
                    to_address=to_address,
                    tx_hash=tx_hash,
                    symbol=cls.symbol,
                    value=BlockchainUtilsMixin.from_unit(int(tx_value), precision=cls.precision),
                    success=True,
                    block_hash=None,
                    block_height=block_height,
                    confirmations=None,
                    date=None,
                    memo=None,
                    tx_fee=None
                )
                block_txs.append(block_tx)
        return block_txs

    @classmethod
    def parse_tipset_blocks(cls, tipset_blocks_response: Dict[str, Any]) -> Optional[List[str]]:
        if cls.validator.validate_tipset_block_hash_response(tipset_blocks_response):
            tipset_blocks_with_details = tipset_blocks_response.get('blocks')
            tipset_blocks = []
            for tipset_block_with_details in tipset_blocks_with_details:
                tipset_blocks.append(tipset_block_with_details.get('cid'))
            return tipset_blocks
        return None


class FilecoinFilfoxApi(GeneralApi):
    """
     coins: Filecoin
     API docs:
     Explorer: https://filfox.info
    """
    parser = FilecoinFilfoxParser
    _base_url = 'https://filfox.info/api/v1'  # 'http://8.218.132.229/api/v1'
    cache_key = 'fil'
    symbol = 'FIL'
    supported_requests = {
        'get_balance': '/address/{address}',
        'get_block_head': '/stats/base-fee?samples=1',
        'get_tx_details': '/message/{tx_hash}',
        'get_address_txs': '/address/{address}/messages?pageSize=100&page=0&method=Send',
        'get_tipset_blocks': '/tipset/{tipset_height}',
        'get_block_txs': '/block/{block_hash}/messages?pageSize=100&page={page_index}&method=Send'
    }

    GET_BLOCK_ADDRESSES_MAX_NUM = 5

    @classmethod
    def get_block_txs(cls, block_height: int) -> List[dict]:
        responses = []
        page_index = 0
        while True:
            response = cls.request('get_block_txs', block_hash=block_height, page_index=page_index)
            if len(response.get('messages')) != 0:
                responses.append(response)
                page_index = page_index + 1
            else:
                break
        return responses

    @classmethod
    def get_tipset_blocks_hash(cls, tipset_height: int) -> Optional[dict]:
        return cls.request('get_tipset_blocks', tipset_height=tipset_height)
