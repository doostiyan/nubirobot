import json
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.conf import settings

from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class FilecoinGlifValidator(ResponseValidator):

    @classmethod
    def validate_general_response(cls, response: Dict[str, Any]) -> bool:
        if not response or not isinstance(response, dict):
            return False
        if response.get('error'):
            return False
        if not response.get('result') or not isinstance(response.get('result'), dict):
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, any]) -> bool:
        if not balance_response or balance_response.get('result') is None:
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        if (not block_head_response.get('result').get('Height') or
                not isinstance(block_head_response.get('result').get('Height'), int)):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        return cls.validate_transaction(tx_details_response.get('result'))

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if not transaction.get('CID') or not isinstance(transaction.get('CID'), dict):
            return False
        if not transaction.get('CID').get('/') or not isinstance(transaction.get('CID').get('/'), str):
            return False
        if not transaction.get('From') or not isinstance(transaction.get('From'), str):
            return False
        if not transaction.get('To') or not isinstance(transaction.get('To'), str):
            return False
        if transaction.get('From').casefold() == transaction.get('To').casefold():
            return False

        # Method 0 is equal to transfer method
        if transaction.get('Method') is None or transaction.get('Method') != 0:
            return False
        if not transaction.get('Value') or not isinstance(transaction.get('Value'), str):
            return False
        if transaction.get('Params'):
            return False
        return True


class FilecoinGlifParser(ResponseParser):
    validator = FilecoinGlifValidator
    symbol = 'FIL'
    currency = Currencies.fil
    precision = 18

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, any]) -> Decimal:
        if cls.validator.validate_balance_response(balance_response):
            return BlockchainUtilsMixin.from_unit(int(balance_response.get('result')), cls.precision)
        return Decimal(0)

    @classmethod
    def parse_tx_details_response(cls,
                                  tx_details_response: Dict[str, Any],
                                  _: Optional[int]) -> List[TransferTx]:
        if cls.validator.validate_tx_details_response(tx_details_response):
            result = tx_details_response.get('result')
            tx_hash = result.get('CID').get('/')
            from_address = result.get('From')
            to_address = result.get('To')
            value = BlockchainUtilsMixin.from_unit(int(result.get('Value')), cls.precision)
            transfer = TransferTx(
                tx_hash=tx_hash,
                from_address=from_address,
                to_address=to_address,
                value=value,
                symbol=cls.symbol,
                success=True,
                memo=''
            )
            return [transfer]
        return []

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, Any]) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return block_head_response.get('result').get('Height')
        return None


class FilecoinGlifApi(GeneralApi):
    """
    coins: Filecoin
    API docs: https://api.node.glif.io/
    :exception ValueError, APIError, AddressNotExist, InternalServerError, BadGateway, GatewayTimeOut
    """
    _base_url = 'https://api.node.glif.io/rpc/v0'
    symbol = 'FIL'
    currency = Currencies.fil
    PRECISION = 18
    cache_key = 'fil'
    parser = FilecoinGlifParser

    supported_requests = {
        'get_balance': ''
    }

    rpc_methods = {
        'get_balance': 'Filecoin.WalletBalance'
    }

    @classmethod
    def get_balance_body(cls, address: str) -> str:
        data = {
            'jsonrpc': '2.0',
            'method': cls.rpc_methods.get('get_balance'),
            'id': 1,
            'params': [address],
        }

        return json.dumps(data)


class FilecoinGlifNodeAPI(FilecoinGlifApi):
    _base_url = 'https://api.node.glif.io'
    need_block_head_for_confirmation = False

    supported_requests = {
        'get_tx_details': '',
        'get_block_head': '',
    }
    rpc_methods = {
        'get_tx_details': 'Filecoin.ChainGetMessage',
        'get_block_head': 'Filecoin.ChainHead'
    }

    @classmethod
    def get_tx_details_body(cls, tx_hash: str) -> str:
        data = {
            'jsonrpc': '2.0',
            'method': cls.rpc_methods.get('get_tx_details'),
            'id': 1,
            'params': [{
                '/': tx_hash
            }],
        }
        return json.dumps(data)

    @classmethod
    def get_block_head_body(cls) -> str:
        data = {
            'jsonrpc': '2.0',
            'method': cls.rpc_methods.get('get_block_head'),
            'id': 1,
            'params': [],
        }
        return json.dumps(data)
