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


class LiteCoinSpaceResponseValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.0005')
    precision = 8
    valid_script_pub_keys = ['scriptpubkey', 'scriptpubkey_asm', 'scriptpubkey_type', 'scriptpubkey_address']

    @classmethod
    def validate_block_head_response(cls, block_head_response: int) -> bool:
        if not block_head_response:
            return False
        if not isinstance(block_head_response, int):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, Any]) -> bool:
        if not tx_details_response:
            return False
        if not tx_details_response.get('txid'):
            return False
        if tx_details_response.get('fee') is None:
            return False
        if tx_details_response.get('vin') is None:
            return False
        if tx_details_response.get('vout') is None:
            return False
        if not tx_details_response.get('status'):
            return False
        if not tx_details_response.get('status').get('confirmed'):
            return False
        if not tx_details_response.get('status').get('block_height'):
            return False
        if not tx_details_response.get('status').get('block_hash'):
            return False
        if not tx_details_response.get('status').get('block_time'):
            return False
        return True

    @classmethod
    def validate_transfer(cls, transfer: Dict[str, Any]) -> bool:
        if not isinstance(transfer, dict):
            return False
        if not transfer.get('value') or not isinstance(transfer.get('value'), int):
            return False
        if BlockchainUtilsMixin.from_unit(transfer.get('value'), cls.precision) < cls.min_valid_tx_amount:
            return False
        if BlockchainUtilsMixin.from_unit(transfer.get('value'), cls.precision) < cls.min_valid_tx_amount:
            return False
        return all(transfer.get(field) for field in cls.valid_script_pub_keys)


class LiteCoinSpaceResponseParser(ResponseParser):
    validator = LiteCoinSpaceResponseValidator
    symbol = 'LTC'
    currency = Currencies.ltc
    min_valid_tx_amount = Decimal('0.0005')
    precision = 8

    @classmethod
    def parse_block_head_response(cls, block_head_response: int) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return block_head_response

        return None

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, Any], block_head: int) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        input_addresses = []
        if cls.validator.validate_tx_details_response(tx_details_response):
            block_height = tx_details_response.get('status').get('block_height')
            block_hash = tx_details_response.get('status').get('block_hash')
            timestamp = tx_details_response.get('status').get('block_time')
            tx_fee = BlockchainUtilsMixin.from_unit(tx_details_response.get('fee'), cls.precision)
            for vin in tx_details_response.get('vin'):
                prevout = vin.get('prevout')
                if not vin.get('is_coinbase') and prevout and cls.validator.validate_transfer(prevout):
                    from_address = prevout.get('scriptpubkey_address')
                    if from_address in input_addresses:
                        for transfer in transfers:
                            if transfer.from_address == from_address:
                                transfer.value += BlockchainUtilsMixin.from_unit(prevout.get('value'), cls.precision)
                    else:
                        transfer = TransferTx(
                            tx_hash=tx_details_response.get('txid'),
                            success=True,
                            from_address=from_address,
                            to_address='',
                            value=BlockchainUtilsMixin.from_unit(prevout.get('value'), cls.precision),
                            symbol=cls.symbol,
                            confirmations=block_head - block_height,
                            block_hash=block_hash,
                            date=parse_utc_timestamp(timestamp),
                            block_height=block_height,
                            tx_fee=tx_fee
                        )
                        transfers.append(transfer)
                        input_addresses.append(from_address)
            for vout in tx_details_response.get('vout'):
                if cls.validator.validate_transfer(vout):
                    to_address = vout.get('scriptpubkey_address')
                    if to_address in input_addresses:
                        for transfer in transfers:
                            if transfer.from_address == to_address:
                                transfer.value -= BlockchainUtilsMixin.from_unit(vout.get('value'), cls.precision)
                    else:
                        transfer = TransferTx(
                            tx_hash=tx_details_response.get('txid'),
                            success=True,
                            from_address='',
                            to_address=to_address,
                            value=BlockchainUtilsMixin.from_unit(vout.get('value'), cls.precision),
                            symbol=cls.symbol,
                            confirmations=block_head - block_height,
                            block_hash=block_hash,
                            date=parse_utc_timestamp(timestamp),
                            block_height=block_height,
                            tx_fee=tx_fee
                        )
                        transfers.append(transfer)
        return transfers


class LiteCoinSpaceApi(GeneralApi):
    symbol = 'LTC'
    cache_key = 'ltc'
    currency = Currencies.ltc
    parser = LiteCoinSpaceResponseParser
    _base_url = 'https://litecoinspace.org/api/'
    supported_requests = {
        'get_block_head': 'blocks/tip/height',
        'get_tx_details': 'tx/{tx_hash}'
    }
