import random
from decimal import Decimal
from typing import Dict, List, Union

import base58

from exchange import settings
from exchange.base.models import Currencies
from exchange.base.parsers import parse_utc_timestamp, parse_utc_timestamp_ms
from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.contracts_conf import TRC20_contract_currency, TRC20_contract_info
from exchange.blockchain.utils import BlockchainUtilsMixin


class TatumTronValidator(ResponseValidator):
    MIN_VALID_DATA_LENGTH = 72
    min_valid_tx_amount = Decimal('0.001')
    precision = 6

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: dict) -> bool:
        if not tx_details_response:
            return False
        if not tx_details_response.get('blockNumber'):
            return False
        if not tx_details_response.get('txID'):
            return False
        if not tx_details_response.get('ret') or not isinstance(tx_details_response.get('ret'), list):
            return False
        if not tx_details_response.get('ret')[0]:
            return False
        if tx_details_response.get('ret')[0].get('contractRet') != 'SUCCESS':
            return False
        if not tx_details_response.get('rawData') or not isinstance(tx_details_response.get('rawData'), dict):
            return False
        if not tx_details_response.get('rawData').get('timestamp'):
            return False
        if not tx_details_response.get('rawData').get('contract') or not isinstance(
                tx_details_response.get('rawData').get('contract'), list):
            return False
        if not tx_details_response.get('rawData').get('contract')[0]:
            return False
        if not tx_details_response.get('rawData').get('contract')[0].get('type'):
            return False
        if not tx_details_response.get('rawData').get('contract')[0].get('parameter'):
            return False
        if not tx_details_response.get('rawData').get('contract')[0].get('parameter').get('value'):
            return False
        if not tx_details_response.get('rawData').get('contract')[0].get('parameter').get('value').get(
                'ownerAddressBase58'):
            return False

        deposit_black_list_addresses = ['TM9RwJndZHmDVLSZcY6J76ci22AzPp2krj', 'TVCAuYMw5afP96y5Wep866AXVWZJRH8fdo']
        if tx_details_response.get('rawData').get('contract')[0].get('parameter').get('value').get(
                'ownerAddressBase58') in deposit_black_list_addresses:
            return False

        return True

    @classmethod
    def validate_tx_details_transaction(cls, transaction: dict) -> bool:
        if not cls.validate_tx_details_response(transaction):
            return False

        transfer_main_params = transaction.get('rawData').get('contract')[0].get('parameter').get('value')

        if transaction.get('rawData').get('contract')[0].get('type') == 'TransferContract':
            if not transfer_main_params.get('amount') or not transfer_main_params.get('toAddressBase58'):
                return False
            if transfer_main_params.get('fromAddressBase58') == transfer_main_params.get('ownerAddressBase58'):
                return False
            if BlockchainUtilsMixin.from_unit(transfer_main_params.get('amount'),
                                              cls.precision) < cls.min_valid_tx_amount:
                return False
        else:
            return False

        return True

    @classmethod
    def validate_token_tx_details_transaction(cls, transaction: dict) -> bool:
        if not cls.validate_tx_details_response(transaction):
            return False

        transfer_main_params = transaction.get('rawData').get('contract')[0].get('parameter').get('value')

        if transaction.get('rawData').get('contract')[0].get('type') == 'TriggerSmartContract':
            if not transfer_main_params.get('contractAddressBase58'):
                return False
            if transfer_main_params.get('contractAddressBase58') == to_hex(
                    '41' + transfer_main_params.get('data')[32:72]):
                return False
            if (not transfer_main_params.get('data')
                    or len(transfer_main_params.get('data')) < cls.MIN_VALID_DATA_LENGTH):
                return False
        else:
            return False

        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: dict) -> bool:
        if not block_head_response:
            return False
        if not block_head_response.get('blockNumber'):
            return False

        return True


class TatumTronParser(ResponseParser):
    validator = TatumTronValidator
    symbol = 'TRX'
    precision = 6
    currency = Currencies.trx

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: dict, block_head: int) -> List[TransferTx]:
        if not cls.validator.validate_tx_details_transaction(tx_details_response):
            return []

        transfer_main_params = tx_details_response.get('rawData').get('contract')[0].get('parameter').get(
            'value')

        try:
            date = parse_utc_timestamp_ms(tx_details_response.get('rawData').get('timestamp'))
        except Exception:
            try:
                # Convert .NET Ticks to Unix Timestamp with precise offset correction
                utc_time_stamp = (tx_details_response.get('rawData').get('timestamp') // 10_000_000) - 62135611197
                date = parse_utc_timestamp(utc_time_stamp)
            except Exception:
                return None  # Return None if both attempts fail

        return [
            TransferTx(
                block_height=tx_details_response.get('blockNumber'),
                tx_hash=tx_details_response.get('txID'),
                date=date,
                success=True,
                confirmations=block_head - tx_details_response.get('blockNumber'),
                from_address=transfer_main_params.get('ownerAddressBase58'),
                to_address=transfer_main_params.get('toAddressBase58'),
                value=BlockchainUtilsMixin.from_unit(transfer_main_params.get('amount'), precision=cls.precision),
                symbol=cls.symbol,
            )
        ]

    @classmethod
    def parse_token_tx_details_response(cls, token_tx_details_response: dict, block_head: int) -> List[TransferTx]:
        if not cls.validator.validate_token_tx_details_transaction(token_tx_details_response):
            return []

        transfer_main_params = token_tx_details_response.get('rawData').get('contract')[0].get(
            'parameter').get('value')

        contract_address = transfer_main_params.get('contractAddressBase58')
        currency = cls.contract_currency_list().get(contract_address)
        if not currency:
            return []
        contract_info = cls.contract_info_list().get(currency)
        symbol = contract_info.get('symbol')

        try:
            date = parse_utc_timestamp(token_tx_details_response.get('rawData').get('timestamp'))

        except Exception:
            # Sometimes the timestamp is with miliseconds
            try:
                date = parse_utc_timestamp_ms(token_tx_details_response.get('rawData').get('timestamp'))
            except Exception:
                return None

        return [
            TransferTx(
                block_height=token_tx_details_response.get('blockNumber'),
                tx_hash=token_tx_details_response.get('txID'),
                date=date,
                success=True,
                confirmations=block_head - token_tx_details_response.get('blockNumber'),
                from_address=transfer_main_params.get('ownerAddressBase58'),
                to_address=to_hex('41' + transfer_main_params.get('data')[32:72]),
                value=BlockchainUtilsMixin.from_unit(int(transfer_main_params.get('data')[-64:], 16),
                                                     precision=contract_info.get('decimals')),
                symbol=symbol,
                token=transfer_main_params.get('contractAddressBase58')
            )
        ]

    @classmethod
    def parse_block_head_response(cls, block_head_response: dict) -> any:
        if not cls.validator.validate_block_head_response(block_head_response):
            return None

        return block_head_response.get('blockNumber')

    @classmethod
    def contract_currency_list(cls) -> Dict[str, int]:
        return TRC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls) -> Dict[int, Dict[str, Union[str, int]]]:
        return TRC20_contract_info.get(cls.network_mode)


class TatumTronApi(GeneralApi):
    parser = TatumTronParser
    _base_url = 'https://api.tatum.io/v3/tron/'
    cache_key = 'trx'
    symbol = 'TRX'
    USE_PROXY = True
    supported_requests = {
        'get_tx_details': 'transaction/{tx_hash}',
        'get_token_tx_details': 'transaction/{tx_hash}',
        'get_block_head': 'info'
    }

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.TATUM_API_KEYS)

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {
            'x-api-key': cls.get_api_key()
        }


def to_hex(address: str) -> str:
    return base58.b58encode_check(bytes.fromhex(address)).decode('utf-8')
