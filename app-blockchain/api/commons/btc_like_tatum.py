import random
from decimal import Decimal
from typing import List, Optional

from django.conf import settings

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_timestamp
else:
    from exchange.base.parsers import parse_timestamp



class TatumResponseValidator(ResponseValidator):

    @classmethod
    def validate_block_head_response(cls, block_head_response: dict) -> bool:
        if not block_head_response or not isinstance(block_head_response, dict):
            return False
        if not block_head_response.get('headers') or not isinstance(block_head_response.get('headers'), int):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: dict) -> bool:
        if not tx_details_response or not isinstance(tx_details_response, dict):
            return False
        if not tx_details_response.get('blockNumber') or not isinstance(tx_details_response.get('blockNumber'), int):
            return False
        if tx_details_response.get('fee') is None:
            return False
        if not tx_details_response.get('hash') or not isinstance(tx_details_response.get('hash'), str):
            return False
        if not tx_details_response.get('inputs') or not isinstance(tx_details_response.get('inputs'), list):
            return False
        if not tx_details_response.get('outputs') or not isinstance(tx_details_response.get('outputs'), list):
            return False
        if not tx_details_response.get('time') or not isinstance(tx_details_response.get('time'), int):
            return False
        return True

    @classmethod
    def validate_transfer(cls, transfer: dict) -> bool:
        if transfer.get('input'):
            input_tx = transfer.get('input')
            if not input_tx or not isinstance(input_tx, dict):
                return False
            if not input_tx.get('coin') or not isinstance(input_tx.get('coin'), dict):
                return False
            if not input_tx.get('coin').get('value'):
                return False
            if not input_tx.get('coin').get('address') or not isinstance(input_tx.get('coin').get('address'), str):
                return False
            if input_tx.get('coin').get('coinbase'):
                return False
            return True
        if transfer.get('output'):
            output_tx = transfer.get('output')
            if not output_tx or not isinstance(output_tx, dict):
                return False
            if not output_tx.get('value'):
                return False
            if not output_tx.get('address') or not isinstance(output_tx.get('address'), str):
                return False
            return True
        return False


class TatumResponseParser(ResponseParser):
    validator = TatumResponseValidator
    symbol = ''
    currency = None
    precision = 8

    @classmethod
    def parse_block_head_response(cls, block_head_response: any) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return block_head_response.get('headers')
        return None

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: any, block_head: int) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        input_addresses = []
        output_addresses = []
        if cls.validator.validate_tx_details_response(tx_details_response):
            block_height = tx_details_response.get('blockNumber')
            timestamp = tx_details_response.get('time')
            date = parse_timestamp(timestamp)
            tx_fee = Decimal(tx_details_response.get('fee'))
            tx_hash = tx_details_response.get('hash')
            for vin in tx_details_response.get('inputs'):
                input_tx = {'input': vin}
                if cls.validator.validate_transfer(input_tx):
                    from_address = vin.get('coin').get('address')
                    if from_address in input_addresses:
                        for transfer in transfers:
                            if transfer.from_address == from_address:
                                transfer.value += Decimal(vin.get('coin').get('value'))
                    else:
                        transfer = TransferTx(
                            tx_hash=tx_hash,
                            success=True,
                            from_address=from_address,
                            to_address='',
                            value=Decimal(vin.get('coin').get('value')),
                            symbol=cls.symbol,
                            confirmations=block_head - block_height,
                            date=date,
                            block_height=block_height,
                            tx_fee=tx_fee,
                            memo=''
                        )
                        transfers.append(transfer)
                        input_addresses.append(from_address)
            for vout in tx_details_response.get('outputs'):
                output_tx = {'output': vout}
                if cls.validator.validate_transfer(output_tx):
                    to_address = vout.get('address')
                    if to_address in input_addresses:
                        for transfer in transfers:
                            if transfer.from_address == to_address:
                                transfer.value -= Decimal(vout.get('value'))
                    elif (to_address in output_addresses) and (to_address not in input_addresses):
                        for transfer in transfers:
                            if transfer.to_address == to_address:
                                transfer.value += Decimal(vout.get('value'))
                    else:
                        transfer = TransferTx(
                            tx_hash=tx_hash,
                            success=True,
                            from_address='',
                            to_address=to_address,
                            value=Decimal(vout.get('value')),
                            symbol=cls.symbol,
                            confirmations=block_head - block_height,
                            date=date,
                            block_height=block_height,
                            tx_fee=tx_fee,
                            memo=''
                        )
                        transfers.append(transfer)
                        output_addresses.append(to_address)
        return transfers


class BtcLikeTatumApi(GeneralApi):
    symbol = ''
    cache_key = ''
    currency = None
    parser = TatumResponseParser
    _base_url = ''
    supported_requests = {
        'get_block_head': 'info',
        'get_tx_details': 'transaction/{tx_hash}'
    }

    @classmethod
    def get_headers(cls) -> Optional[dict]:
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': cls.get_api_key()
        }

    @classmethod
    def get_api_key(cls) -> Optional[str]:
        return random.choice(settings.DOGE_TATUM_API_KEYS)
