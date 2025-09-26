from typing import Dict, List, Optional

from cashaddress import convert
from cashaddress.convert import InvalidAddress
from django.conf import settings

from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_utc_timestamp
else:
    from exchange.base.parsers import parse_utc_timestamp

from exchange.blockchain.api.general.dtos.dtos import TransferTx


class HaskoinValidator(ResponseValidator):

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, any]) -> bool:
        if not tx_details_response or not isinstance(tx_details_response, dict):
            return False
        if not tx_details_response.get('txid') or not isinstance(tx_details_response.get('txid'), str):
            return False
        if tx_details_response.get('fee') is None or not isinstance(tx_details_response.get('fee'), int):
            return False
        if tx_details_response.get('deleted') or not isinstance(tx_details_response.get('deleted'), bool):
            return False
        if tx_details_response.get('rbf') or not isinstance(tx_details_response.get('rbf'), bool):
            return False
        if not tx_details_response.get('inputs') or not isinstance(tx_details_response.get('inputs'), list):
            return False
        if not tx_details_response.get('outputs') or not isinstance(tx_details_response.get('outputs'), list):
            return False
        if not tx_details_response.get('time') or not isinstance(tx_details_response.get('time'), int):
            return False
        if not tx_details_response.get('block') or not isinstance(tx_details_response.get('block'), dict):
            return False
        if (not tx_details_response.get('block').get('height') or
                not isinstance(tx_details_response.get('block').get('height'), int)):
            return False
        return True

    @classmethod
    def validate_transfer(cls, transfer: Dict[str, any]) -> bool:
        if not transfer.get('value') or not isinstance(transfer.get('value'), int):
            return False
        if not transfer.get('address') or not isinstance(transfer.get('address'), str):
            return False
        return True


class HaskoinResponseParser(ResponseParser):
    validator = HaskoinValidator

    @staticmethod
    def convert_address(address: str) -> Optional[str]:
        try:
            return convert.to_legacy_address(address)
        except InvalidAddress:
            return None

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, any], _: int) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        if cls.validator.validate_tx_details_response(tx_details_response):
            tx_hash = tx_details_response.get('txid')
            block_height = tx_details_response.get('block').get('height')
            date = parse_utc_timestamp(tx_details_response.get('time'))
            fee = BlockchainUtilsMixin.from_unit(tx_details_response.get('fee'), precision=cls.precision)
            for inp in tx_details_response.get('inputs'):
                if cls.validator.validate_transfer(inp) and (
                        not inp.get('coinbase') or isinstance(inp.get('coinbase'), bool)):
                    from_address = cls.convert_address(inp.get('address'))
                    value = BlockchainUtilsMixin.from_unit(inp.get('value'), precision=cls.precision)
                    for tx in transfers:
                        if tx.from_address == from_address:
                            tx.value += value
                            break
                    else:
                        transfer = TransferTx(
                            tx_hash=tx_hash,
                            from_address=from_address,
                            to_address='',
                            value=value,
                            block_height=block_height,
                            success=True,
                            symbol=cls.symbol,
                            date=date,
                            tx_fee=fee,
                        )
                        transfers.append(transfer)
            for output in tx_details_response.get('outputs'):
                if cls.validator.validate_transfer(output):
                    to_address = cls.convert_address(output.get('address'))
                    value = BlockchainUtilsMixin.from_unit(output.get('value'), precision=cls.precision)
                    for tx in transfers:
                        if tx.from_address == to_address:
                            tx.value -= value
                            break
                    else:
                        transfer = TransferTx(
                            tx_hash=tx_hash,
                            from_address='',
                            to_address=to_address,
                            value=value,
                            block_height=block_height,
                            success=True,
                            symbol=cls.symbol,
                            date=date,
                            tx_fee=fee,
                        )
                        transfers.append(transfer)

        return transfers


class HaskoinApi(GeneralApi):
    parser = HaskoinResponseParser
    _base_url = 'https://api.haskoin.com'
    need_block_head_for_confirmation = False
    supported_requests = {
        'get_tx_details': '/{network}/transaction/{tx_hash}',
    }

    @classmethod
    def get_tx_details(cls, tx_hash: str) -> Optional[str]:
        return cls.request(request_method='get_tx_details', tx_hash=tx_hash,
                           network=cls.symbol.lower())
