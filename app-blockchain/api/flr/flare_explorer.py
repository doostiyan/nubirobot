from typing import List, Optional

from exchange.blockchain.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin


class FlareExplorerResponseValidator(ResponseValidator):
    precision = 18

    @classmethod
    def validate_general_response(cls, response):
        if not response:
            return False
        if not isinstance(response, dict):
            return False
        if not isinstance(response.get('items'), list):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: dict) -> bool:
        if cls.validate_general_response(block_head_response):
            if (
                    block_head_response.get('items') and
                    isinstance(block_head_response.get('items')[0], dict) and
                    block_head_response.get('items')[0].get('height')
            ):
                return True

        return False

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: dict) -> bool:
        return cls.validate_general_response(block_txs_response)

    @classmethod
    def _validate_input_data(cls, input_data: str) -> bool:
        # Currently we just support native currency
        return input_data in ['0x', '0x0000000000000000000000000000000000000000']

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: dict) -> bool:
        if cls.validate_general_response(address_txs_response):
            return True

        return False

    @classmethod
    def validate_address_tx_transaction(cls, transaction: dict) -> bool:
        if not cls.validate_transaction(transaction):
            return False

        if BlockchainUtilsMixin.from_unit(int(transaction.get('value')), cls.precision) <= cls.min_valid_tx_amount:
            return False

        return True

    @classmethod
    def validate_transaction(cls, transaction: dict) -> bool:
        from_address: str = transaction['from']['hash']
        to_address: str = transaction['to']['hash']

        if not from_address or not to_address:
            return False

        if from_address == to_address:
            return False

        if from_address in cls.invalid_from_addresses_for_ETH_like:
            return False

        if not transaction.get('hash'):
            return False

        if transaction.get('status') != 'ok' or transaction.get('result') != 'success':
            return False

        if 'coin_transfer' not in transaction.get('transaction_types'):
            return False

        if not cls._validate_input_data(transaction.get('raw_input')):
            return False

        if any(not transaction.get(key) for key in ["block_number", "hash", "timestamp", "value", "fee"]):
            if not transaction["fee"].get("value"):
                return False

        return True


class FlareExplorerResponseParser(ResponseParser):
    validator = FlareExplorerResponseValidator
    precision = 18
    symbol = 'FLR'
    currency = Currencies.flr

    @classmethod
    def parse_block_head_response(cls, block_head_response: dict) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response=block_head_response):
            return block_head_response['items'][0].get('height')

    @classmethod
    def parse_block_txs_response(cls, block_txs_response) -> List[TransferTx]:
        if not cls.validator.validate_block_txs_response(block_txs_response):
            return []

        filtered_txs = list(
            filter(lambda trx: cls.validator.validate_transaction(trx), block_txs_response['items']))

        block_txs_list: List[TransferTx] = []
        for tx in filtered_txs:
            if block_txs := cls._parse_block_and_detail_tx(tx=tx):
                block_txs_list.extend(block_txs)
        return block_txs_list

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return []

        # Parse transactions
        transfers = []
        for tx in address_txs_response.get('items'):
            if cls.validator.validate_address_tx_transaction(tx):
                transfers.append(
                    TransferTx(
                        block_height=int(tx.get('block_number')),
                        tx_hash=tx.get('hash'),
                        success=True,
                        confirmations=int(tx.get('confirmations', 0)),
                        from_address=tx['from']['hash'],
                        to_address=tx['to']['hash'],
                        date=parse_iso_date(s=tx.get('timestamp')),
                        value=BlockchainUtilsMixin.from_unit(number=int(tx.get('value')), precision=cls.precision),
                        symbol=tx.get('symbol'),
                        tx_fee=BlockchainUtilsMixin.from_unit(int(tx['fee']['value']), precision=cls.precision),
                    ))

        return transfers

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: dict, block_head: int) -> List[TransferTx]:
        if cls.validator.validate_transaction(tx_details_response):
            return cls._parse_block_and_detail_tx(tx_details_response)

    @classmethod
    def _parse_block_and_detail_tx(cls, tx: dict) -> List[TransferTx]:
        return [
                TransferTx(
                    block_height=tx.get('block_number'),
                    tx_hash=tx.get('hash'),
                    success=True,
                    confirmations=tx.get('confirmations'),
                    from_address=tx['from']['hash'],
                    to_address=tx['to']['hash'],
                    date=parse_iso_date(s=tx.get('timestamp')),
                    value=BlockchainUtilsMixin.from_unit(int(tx.get('value')), precision=cls.precision),
                    symbol=cls.symbol,
                    token=None,
                    tx_fee=BlockchainUtilsMixin.from_unit(int(tx['fee']['value']), precision=cls.precision),
                ),
            ]


class FlareExplorerApi(GeneralApi):
    parser = FlareExplorerResponseParser
    _base_url: str = 'https://flare-explorer.flare.network'
    supported_requests: dict = {
        'get_block_head': '/api/v2/blocks?type=block',
        'get_block_txs': '/api/v2/blocks/{height}/transactions',
        'get_tx_details': '/api/v2/transactions/{tx_hash}',
        'get_address_txs': '/api/v2/addresses/{address}/transactions',
    }
    need_block_head_for_confirmation = False
    cache_key = "flr"
    symbol = 'FLR'
