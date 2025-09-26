import json
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.conf import settings

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_utc_timestamp
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
    from exchange.base.parsers import parse_utc_timestamp


class FilecoinFilscanRpcValidator(ResponseValidator):
    precision = 18

    @classmethod
    def validate_general_response(cls, response: Dict[str, Any]) -> bool:
        if not response:
            return False
        if not response.get('result'):
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(balance_response):
            return False
        if not balance_response.get('result').get('basic'):
            return False
        if balance_response.get('result').get('basic').get('balance') is None:
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        return cls.validate_transaction(tx_details_response.get('result'))

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if not transaction.get('cid'):
            return False
        if transaction.get('exit_code') != 0:
            return False
        if transaction.get('value') is None or BlockchainUtilsMixin.from_unit(
                int(transaction.get('value')), cls.precision) <= cls.min_valid_tx_amount:
            return False
        if transaction.get('method_name') is None or transaction.get('method_name').casefold() != 'transfer'.casefold():
            return False
        if transaction.get('from') is None or transaction.get('to') is None or transaction.get(
                'from') == transaction.get('to'):
            return False
        return True

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: Dict[str, Any]) -> bool:
        if not block_txs_response:
            return False
        if not block_txs_response.get('result'):
            return False
        if not block_txs_response.get('result').get('data'):
            return False
        return True

    @classmethod
    def validate_tipset_block_hash_response(cls, tipset_block_hash_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(tipset_block_hash_response):
            return False
        if not tipset_block_hash_response.get('result')[0]:
            return False
        if not tipset_block_hash_response.get('result')[0].get('blocks'):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        if block_head_response.get('result').get('data').get('latest_height') is None:
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        return True


class FilecoinFilscanRpcParser(ResponseParser):
    validator = FilecoinFilscanRpcValidator
    symbol = 'FIL'
    currency = Currencies.fil
    precision = 18

    @classmethod
    def calculate_fee(cls, transfers: List[Optional[int]]) -> Decimal:
        fee = 0
        for transfer in transfers:
            if transfer is not None:
                fee = fee + int(transfer)
        return BlockchainUtilsMixin.from_unit(fee, cls.precision)

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, Any]) -> Decimal:
        if cls.validator.validate_balance_response(balance_response):
            return Decimal(balance_response.get('result').get('basic').get('balance'))
        return Decimal(0)

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, Any]) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return block_head_response.get('result').get('data').get('latest_height')
        return None

    @classmethod
    def parse_tx_details_response(
        cls,
        tx_details_response: Dict[str, Any],
        block_head: int
    ) -> List[TransferTx]:
        if cls.validator.validate_tx_details_response(tx_details_response):
            transaction = tx_details_response.get('result')
            block = transaction.get('height')
            separator = ','
            block_hash = separator.join(transaction.get('blk_cids'))
            confirmations = block_head - transaction.get('height') + 1
            return [TransferTx(
                tx_hash=transaction.get('cid'),
                success=True,
                block_height=block,
                date=parse_utc_timestamp(transaction.get('block_time')),
                memo=None,
                from_address=transaction.get('from'),
                to_address=transaction.get('to'),
                value=BlockchainUtilsMixin.from_unit(int(transaction.get('value')), precision=cls.precision),
                symbol=cls.symbol,
                tx_fee=cls.calculate_fee([transaction.get('base_fee_burn'), transaction.get('miner_tip')]),
                confirmations=confirmations,
                token=None,
                block_hash=block_hash,
            )]
        return []

    @classmethod
    def parse_address_txs_response(
        cls,
        address: str,
        address_txs_response: Dict[str, Any],
        block_head: int,
    ) -> List[TransferTx]:
        _ = address
        if cls.validator.validate_address_txs_response(address_txs_response):
            transactions = address_txs_response.get('result').get('data')
            address_txs: List[TransferTx] = []
            for transaction in transactions:
                if cls.validator.validate_transaction(transaction):
                    block = transaction.get('height')
                    confirmation = block_head - block + 1
                    separator = ','
                    block_hash = separator.join(transaction.get('blk_cids'))
                    amount = BlockchainUtilsMixin.from_unit(int(transaction.get('value')), precision=cls.precision)
                    address_tx = TransferTx(
                        tx_hash=transaction.get('cid'),
                        from_address=transaction.get('from'),
                        to_address=transaction.get('to'),
                        value=amount,
                        block_height=block,
                        date=parse_utc_timestamp(transaction.get('block_time')),
                        confirmations=confirmation,
                        memo=None,
                        block_hash=block_hash,
                        success=True,
                        symbol=cls.symbol,
                        tx_fee=cls.calculate_fee([transaction.get('base_fee_burn'), transaction.get('miner_tip')])
                    )
                    address_txs.append(address_tx)
            return address_txs
        return []

    @classmethod
    def parse_block_txs_response(cls, block_txs_response: List[Dict[str, Any]]) -> List[TransferTx]:
        txs = []
        for response in block_txs_response:
            if cls.validator.validate_block_txs_response(response):
                txs.append(response.get('result').get('data'))
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
                    block_height=None,
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
            tipset_blocks_with_details = tipset_blocks_response.get('result')[0].get('blocks')
            tipset_blocks = []
            for tipset_block_with_details in tipset_blocks_with_details:
                tipset_blocks.append(tipset_block_with_details.get('cid'))
            return tipset_blocks
        return None


class FilecoinFilscanRpcApi(GeneralApi):
    """
    coins: Filecoin
    API docs:
    Explorer: https://filscan.io/
    """
    PAGINATION_LIMIT = 25
    PAGINATION_OFFSET = 0
    parser = FilecoinFilscanRpcParser
    _base_url = 'https://api.filscan.io:8700/rpc/v1'
    cache_key = 'fil'
    supported_requests = {
        'get_balance': '',
        'get_block_head': '',
        'get_tx_details': '',
        'get_address_txs': '',
        'get_tipset_blocks': '',
        'get_block_txs': ''
    }
    rpc_methods = {
        'get_balance': 'filscan.FilscanActorById',
        'get_block_head': 'filscan.StatChainInfo',
        'get_tx_details': 'filscan.MessageDetails',
        'get_address_txs': 'filscan.MessageByAddress',
        'get_tipset_blocks': 'filscan.TipSetTree',
        'get_block_txs': 'filscan.GetMessages'
    }

    @classmethod
    def get_balance_body(cls, address: str) -> str:
        return cls.create_rpc_body('get_balance', [address])

    @classmethod
    def create_rpc_body(cls, method: str, params: Optional[List[Any]] = None) -> str:
        return json.dumps({
            'jsonrpc': '2.0',
            'method': cls.rpc_methods.get(method),
            'id': 1,
            'params': params if params else []
        })

    @classmethod
    def get_tx_details_body(cls, tx_hash: str) -> str:
        return cls.create_rpc_body('get_tx_details', [tx_hash])

    @classmethod
    def get_block_head_body(cls) -> str:
        return cls.create_rpc_body('get_block_head')

    @classmethod
    def get_address_txs_body(cls, address: str) -> str:
        return cls.create_rpc_body('get_address_txs', [
            {'address': address, 'offset_range': {'start': cls.PAGINATION_OFFSET, 'count': cls.PAGINATION_LIMIT}}])

    @classmethod
    def get_block_txs(cls, block_height: int) -> List[Dict[str, Any]]:
        page_index = 0
        responses = []
        while True:
            response = cls.request('get_block_txs', body=cls.get_block_body(block_height, page_index))
            if not response or not response.get('result') or not response.get('result').get('data'):
                break
            responses.append(response)
            page_index = page_index + len(response.get('result').get('data'))
        return responses

    @classmethod
    def get_block_body(cls, block_hash: str, page_index: int) -> str:
        return cls.create_rpc_body('get_block_txs', [
            {'blk_cid': block_hash, 'offset_range': {'start': page_index, 'count': 30}}])

    @classmethod
    def get_tipset_blocks_hash(cls, tipset_height: int) -> Optional[str]:
        return cls.request('get_tipset_blocks', body=cls.create_rpc_body('get_tipset_blocks',
                                                                         [1, tipset_height]))
