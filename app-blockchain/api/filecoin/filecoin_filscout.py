import datetime
import json
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from django.conf import settings

from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_iso_date
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
    from exchange.base.parsers import parse_iso_date

from exchange.blockchain.api.general.dtos.dtos import TransferTx


class FilecoinFilscoutValidator(ResponseValidator):
    CODE_SUCCESSFUL = 200

    @classmethod
    def validate_general_response(cls, response: Dict[str, Any]) -> bool:
        if (not response or not response.get('data') or response.get('code') is None or
                response.get('code') != cls.CODE_SUCCESSFUL):
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(balance_response):
            return False
        if not balance_response.get('data').get('balance') or not isinstance(
                balance_response.get('data').get('balance'), str):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        return cls.validate_transaction(tx_details_response.get('data'))

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if not transaction.get('cid'):
            return False
        if transaction.get('exitCodeName') is None or transaction.get('exitCodeName') != 'OK':
            return False
        if transaction.get('value') is None or 'FIL' not in transaction.get('value'):
            return False
        value = transaction.get('value').replace(' FIL', '').replace(',', '')
        if Decimal(value) <= cls.min_valid_tx_amount:
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
        if not block_txs_response.get('Message') or block_txs_response.get(
                'Message').casefold() != 'success'.casefold():
            return False
        if block_txs_response.get('code') is None or block_txs_response.get('code') != cls.CODE_SUCCESSFUL:
            return False
        return True

    @classmethod
    def validate_tipset_block_hash_response(cls, tipset_block_hash_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(tipset_block_hash_response):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, Any]) -> bool:

        if not cls.validate_general_response(block_head_response):
            return False
        if len(block_head_response.get('data').get('height_blocks')) == 0:
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        if (not address_txs_response.get('Message')
                or address_txs_response.get('Message').casefold() != 'success'.casefold()):
            return False
        return True


class FilecoinFilscoutParser(ResponseParser):
    validator = FilecoinFilscoutValidator
    symbol = 'FIL'
    currency = Currencies.fil
    precision = 18

    @staticmethod
    def parse_amount(value: str) -> Any:
        value = value.replace(',', '')
        amount = re.findall(r'\d*\.?\d+', value)
        return amount[0]

    @classmethod
    def calculate_fee(cls, transaction: Dict[str, Any]) -> Union[int, Decimal]:
        burn_fee = float(cls.parse_amount(transaction.get('burnFee')))
        miner_tip = float(cls.parse_amount(transaction.get('minerTip')))
        fee = burn_fee + miner_tip
        # fee is in NanoFil in here
        return BlockchainUtilsMixin.from_unit(BlockchainUtilsMixin.to_unit(fee, 9), cls.precision)

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, Any]) -> Decimal:
        if cls.validator.validate_balance_response(balance_response):
            value = cls.parse_amount(balance_response.get('data').get('balance'))
            if 'nano' in balance_response.get('data').get('balance'):
                return BlockchainUtilsMixin.from_unit(BlockchainUtilsMixin.to_unit(value, 9), cls.precision)
            return Decimal(value)
        return Decimal(0)

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, Any]) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return block_head_response.get('data').get('height_blocks')[0].get('height')
        return None

    @staticmethod
    def convert_to_iso8601(input_time: str) -> str:
        # Parse the input string assuming it's in the format "YYYY-MM-DD HH:MM:SS"
        dt = datetime.datetime.strptime(input_time, '%Y-%m-%d %H:%M:%S')
        # Format it into the ISO 8601 format with 'Z' to indicate UTC
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, Any], block_head: int) -> List[TransferTx]:
        if cls.validator.validate_tx_details_response(tx_details_response):
            transaction = tx_details_response.get('data')
            fees = cls.calculate_fee(transaction)
            block = transaction.get('height')
            separator = ','
            block_hash = separator.join(tx_details_response.get('data').get('blockCid'))
            confirmations = block_head - transaction.get('height') + 1
            return [TransferTx(
                tx_hash=transaction.get('cid'),
                success=True,
                from_address=transaction.get('from'),
                to_address=transaction.get('to'),
                block_height=block,
                memo=None,
                date=parse_iso_date(cls.convert_to_iso8601(transaction.get('time'))),
                tx_fee=fees,
                confirmations=confirmations,
                value=BlockchainUtilsMixin.from_unit(transaction.get('atto_value'), cls.precision),
                symbol=cls.symbol,
                token=None,
                block_hash=block_hash,
            )]
        return []

    @classmethod
    def parse_address_txs_response(cls,
                                   _: str,
                                   address_txs_response: Dict[str, Any],
                                   block_head: int) -> List[TransferTx]:
        if cls.validator.validate_address_txs_response(address_txs_response):
            transactions = address_txs_response.get('data')
            address_txs: List[TransferTx] = []
            for transaction in transactions:
                if cls.validator.validate_transaction(transaction):
                    block = transaction.get('height')
                    confirmations = block_head - block + 1
                    amount = Decimal(str(cls.parse_amount(transaction.get('value'))))
                    fee = BlockchainUtilsMixin.from_unit(
                        BlockchainUtilsMixin.to_unit(float(cls.parse_amount(transaction.get('fee'))), 9), 18)
                    address_tx = TransferTx(
                        tx_hash=transaction.get('cid'),
                        from_address=transaction.get('from'),
                        to_address=transaction.get('to'),
                        value=amount,
                        block_height=block,
                        date=parse_iso_date(cls.convert_to_iso8601(transaction.get('timeFormat'))),
                        confirmations=confirmations,
                        memo=None,
                        block_hash=None,
                        success=True,
                        symbol=cls.symbol,
                        tx_fee=fee
                    )
                    address_txs.append(address_tx)
            return address_txs
        return []

    @classmethod
    def parse_block_txs_response(cls,
                                 block_txs_response: List[Dict[str, Any]],
                                 _: Optional[int] = None) -> List[TransferTx]:
        txs = []
        for response in block_txs_response:
            if cls.validator.validate_block_txs_response(response):
                txs.append(response.get('data'))
        transactions = [item for sublist in txs for item in sublist]
        block_txs: List[TransferTx] = []
        for tx in transactions:
            if cls.validator.validate_transaction(tx):
                from_address = tx.get('from')
                to_address = tx.get('to')
                tx_hash = tx.get('cid')
                tx_value = Decimal(str(cls.parse_amount(tx.get('value'))))
                fee = BlockchainUtilsMixin.from_unit(
                    BlockchainUtilsMixin.to_unit(float(cls.parse_amount(tx.get('fee'))), 9), 18)
                block_tx = TransferTx(
                    from_address=from_address,
                    to_address=to_address,
                    tx_hash=tx_hash,
                    symbol=cls.symbol,
                    value=tx_value,
                    block_hash=None,
                    block_height=tx.get('height'),
                    confirmations=0,
                    date=parse_iso_date(cls.convert_to_iso8601(tx.get('timeFormat'))),
                    memo=None,
                    success=True,
                    tx_fee=fee
                )
                block_txs.append(block_tx)
        return block_txs

    @classmethod
    def parse_tipset_blocks(cls, tipset_blocks_response: Dict[str, Any]) -> Optional[list]:
        if cls.validator.validate_tipset_block_hash_response(tipset_blocks_response):
            tipset_blocks_with_details = tipset_blocks_response.get('data').get('blocks')
            tipset_blocks = []
            for tipset_block_with_details in tipset_blocks_with_details:
                tipset_blocks.append(tipset_block_with_details.get('cid'))
            return tipset_blocks
        return None


class FilecoinFilscoutApi(GeneralApi):
    """
    coins: Filecoin
    API docs:
    Explorer: https://www.filutils.com/
    """
    PAGINATION_LIMIT = 25
    PAGINATION_OFFSET = 0
    PAGINATION_PAGE = 1
    parser = FilecoinFilscoutParser
    _base_url = 'https://api.filutils.com/api'
    cache_key = 'fil'
    supported_requests = {
        'get_balance': '/v2/actor/{address}',
        'get_block_head': '/v2/block/latest',
        'get_tx_details': '/v2/message/{tx_hash}',
        'get_address_txs': '/v2/message',
        'get_tipset_blocks': '/v2/tipset/{tipset_height}',
        'get_block_txs': '/v2/block/message'
    }

    @classmethod
    def get_address_txs_body(cls, address: str) -> str:
        data = {
            'address': address,
            'method': 'Send',
            'pageSize': cls.PAGINATION_LIMIT,
            'pageIndex': cls.PAGINATION_PAGE
        }
        return json.dumps(data)

    @classmethod
    def get_block_txs(cls, block_height: int) -> list:
        page_index = 1
        responses = []
        while True:
            response = cls.request('get_block_txs', body=cls.get_block_body(block_height, page_index))
            if not response or not response.get('data'):
                break
            responses.append(response)
            page_index = page_index + 1

        return responses

    @staticmethod
    def get_block_body(block_hash: str, page_index: int) -> str:
        data = {
            'blockCid': block_hash,
            'exitCode': 'OK',
            'method': 'Send',
            'pageSize': 25,
            'pageIndex': page_index
        }
        return json.dumps(data)

    @classmethod
    def get_tipset_blocks_hash(cls, tipset_height: int) -> Any:
        return cls.request('get_tipset_blocks', tipset_height=tipset_height)

    @classmethod
    def get_header(cls) -> Dict[str, Any]:
        return {'content-type': 'application/json'}
