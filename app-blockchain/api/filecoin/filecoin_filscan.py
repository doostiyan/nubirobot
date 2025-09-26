import json
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


class FilecoinFilscanValidator(ResponseValidator):
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
        if not balance_response.get('result').get('account_type'):
            return False
        if not balance_response.get('result').get('account_info'):
            return False
        if not balance_response.get('result').get('account_info').get('account_basic'):
            return False
        if not balance_response.get('result').get('account_info').get('account_basic').get('account_balance'):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        if not tx_details_response.get('result').get('MessageDetails'):
            return False
        if not tx_details_response.get('result').get('MessageDetails').get('message_basic'):
            return False
        return cls.validate_transaction(tx_details_response.get('result').get('MessageDetails').get('message_basic'))

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if not transaction.get('cid'):
            return False
        if transaction.get('exit_code') is None or transaction.get('exit_code') != 'Ok':
            return False
        if transaction.get('value') is None or BlockchainUtilsMixin.from_unit(
                int(transaction.get('value')), cls.precision) <= cls.min_valid_tx_amount:
            return False
        if transaction.get('method_name') is None or transaction.get('method_name').casefold() != 'Send'.casefold():
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
        if not block_txs_response.get('result').get('message_list'):
            return False
        return True

    @classmethod
    def validate_tipset_block_hash_response(cls, tipset_block_hash_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(tipset_block_hash_response):
            return False
        if not tipset_block_hash_response.get('result').get('tipset_list'):
            return False
        if not tipset_block_hash_response.get('result').get('tipset_list')[0]:
            return False
        if not tipset_block_hash_response.get('result').get('tipset_list')[0].get('block_basic'):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        if block_head_response.get('result').get('block_time') is None or block_head_response.get('result').get(
                'block_time') == 0:
            return False
        if block_head_response.get('result').get('height') is None:
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        if not address_txs_response.get('result').get('messages_by_account_id_list'):
            return False
        return True


class FilecoinFilscanParser(ResponseParser):
    validator = FilecoinFilscanValidator
    symbol = 'FIL'
    currency = Currencies.fil
    precision = 18

    @classmethod
    def calculate_fee(cls, transfers: List[Dict[str, Any]]) -> Union[int, Decimal]:
        fee = 0
        for transfer in transfers:
            if transfer.get('consume_type') == 'MinerTip' or transfer.get('consume_type') == 'BaseFeeBurn':
                fee = fee + int(transfer.get('value'))
        return BlockchainUtilsMixin.from_unit(fee, cls.precision)

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, Any]) -> Union[int, Decimal]:
        if cls.validator.validate_balance_response(balance_response):
            return BlockchainUtilsMixin.from_unit(
                int(balance_response.get('result').get('account_info').get('account_basic').get('account_balance')),
                cls.precision
            )
        return Decimal(0)

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, Any]) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return block_head_response.get('result').get('height')
        return None

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, Any], block_head: int) -> List[TransferTx]:
        if not cls.validator.validate_tx_details_response(tx_details_response):
            return []

        transaction = tx_details_response.get('result').get('MessageDetails').get('message_basic')
        consume_list = tx_details_response.get('result').get('MessageDetails').get('consume_list')
        value = BlockchainUtilsMixin.from_unit(int(transaction.get('value')), precision=cls.precision)
        separator = ','
        if tx_details_response.get('result').get('MessageDetails').get('blk_cids'):
            block_hash = separator.join(tx_details_response.get('result').get('MessageDetails').get('blk_cids'))
        else:
            block_hash = None
        block = transaction.get('height')
        confirmations = block_head - block + 1
        return [TransferTx(
            tx_hash=transaction.get('cid'),
            success=True,
            block_height=block,
            date=parse_utc_timestamp(transaction.get('block_time')),
            memo=None,
            tx_fee=cls.calculate_fee(consume_list),
            confirmations=confirmations,
            symbol=cls.symbol,
            from_address=transaction.get('from'),
            to_address=transaction.get('to'),
            value=value,
            token=None,
            block_hash=block_hash
        )]

    @classmethod
    def parse_address_txs_response(
            cls,
            address: str,
            address_txs_response: Dict[str, Any],
            block_head: int
    ) -> List[TransferTx]:
        _ = address
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return []

        transactions = address_txs_response.get('result').get('messages_by_account_id_list')
        address_txs: List[TransferTx] = []
        for transaction in transactions:
            if cls.validator.validate_transaction(transaction):
                block = transaction.get('height')
                confirmations = block_head - block + 1
                from_address = transaction.get('from')
                amount = BlockchainUtilsMixin.from_unit(int(transaction.get('value')), cls.precision)
                address_tx = TransferTx(
                    tx_hash=transaction.get('cid'),
                    from_address=from_address,
                    to_address=transaction.get('to'),
                    value=amount,
                    block_height=block,
                    date=parse_utc_timestamp(transaction.get('block_time')),
                    confirmations=confirmations,
                    memo=None,
                    block_hash=None,
                    success=True,
                    symbol=cls.symbol,
                    tx_fee=None
                )
                address_txs.append(address_tx)
        return address_txs

    @classmethod
    def parse_block_txs_response(
            cls,
            block_txs_response: List[Dict[str, Any]],
            __: Optional[int] = None
    ) -> List[TransferTx]:
        txs = []
        for response in block_txs_response:
            if cls.validator.validate_block_txs_response(response):
                txs.append(response.get('result').get('message_list'))
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
                    block_hash=None,
                    block_height=tx.get('height'),
                    confirmations=None,
                    date=parse_utc_timestamp(tx.get('block_time')),
                    memo=None,
                    success=True,
                    tx_fee=None
                )
                block_txs.append(block_tx)
        return block_txs

    @classmethod
    def parse_tipset_blocks(cls, tipset_blocks_response: Dict[str, Any]) -> List[str]:
        if not cls.validator.validate_tipset_block_hash_response(tipset_blocks_response):
            return []

        tipset_blocks_with_details = tipset_blocks_response.get('result').get('tipset_list')[0].get('block_basic')
        tipset_blocks = []
        for tipset_block_with_details in tipset_blocks_with_details:
            tipset_blocks.append(tipset_block_with_details.get('cid'))
        return tipset_blocks


class FilecoinFilscanApi(GeneralApi):
    """
    coins: Filecoin
    API docs:
    Explorer: https://filscan.io/
    """
    PAGINATION_LIMIT = 25
    PAGINATION_OFFSET = 0
    parser = FilecoinFilscanParser
    _base_url = 'https://api-v2.filscan.io/api/v1/'
    cache_key = 'fil'
    supported_requests = {
        'get_balance': 'AccountInfoByID',
        'get_block_head': 'FinalHeight',
        'get_tx_details': 'MessageDetails',
        'get_address_txs': 'MessagesByAccountID',
        'get_tipset_blocks': 'LatestBlocks',
        'get_block_txs': 'MessagesByBlock'
    }

    @classmethod
    def get_balance_body(cls, address: str) -> str:
        return json.dumps({
            'account_id': address
        })

    @classmethod
    def get_tx_details_body(cls, tx_hash: str) -> str:
        return json.dumps({
            'message_cid': tx_hash
        })

    @classmethod
    def get_block_head_body(cls) -> str:
        return json.dumps({})

    @classmethod
    def get_address_txs_body(cls, address: str) -> str:
        return json.dumps({
            'account_id': address,
            'address': '',
            'filters': {
                'index': 0,
                'page': 0,
                'limit': 20,
                'method_name': 'Send'
            }})

    @classmethod
    def get_block_txs(cls, block_height: int) -> List[Dict[str, Any]]:
        page_index = 0
        responses = []
        while True:
            response = cls.request('get_block_txs', body=cls.get_block_body(block_height, page_index))
            if not response or not response.get('result') or not response.get('result').get('message_list'):
                break
            responses.append(response)
            page_index = page_index + 1
        return responses

    @classmethod
    def get_block_body(cls, block_hash: str, page_index: int) -> str:
        return json.dumps({
            'filters': {
                'index': page_index,
                'limit': 30,
                'method_name': 'Send'
            },
            'block_cid': block_hash
        })

    @classmethod
    def get_tipset_blocks_hash(cls, tipset_height: int) -> Dict[str, Any]:
        body = json.dumps({
            'filters': {
                'start': tipset_height,
                'input_type': 'height'
            }
        })
        return cls.request('get_tipset_blocks', body=body)
