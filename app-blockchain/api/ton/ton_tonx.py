import json
from typing import Any, Dict, List, Optional

from django.conf import settings

from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin

from .utils import calculate_tx_confirmations

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class TonXTonValidator(ResponseValidator):

    @classmethod
    def validate_general_response(cls, response: Dict[str, Any]) -> bool:
        if not response or not isinstance(response, dict):
            return False
        if not response.get('result'):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False

        if not isinstance(tx_details_response.get('result'), list):
            return False

        transaction = tx_details_response.get('result')[0]

        return cls.validate_transaction(transaction)

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if not transaction or not isinstance(transaction, dict):
            return False
        if not transaction.get('hash') or not isinstance(transaction.get('hash'), str):
            return False
        if not transaction.get('orig_status') or transaction.get('orig_status') != 'active':
            return False
        if not transaction.get('end_status') or transaction.get('end_status') != 'active':
            return False
        if not transaction.get('now') or not isinstance(transaction.get('now'), int):
            return False
        if not transaction.get('description') or not isinstance(transaction.get('description'), dict):
            return False
        description = transaction.get('description')
        if not description.get('type') or not isinstance(description.get('type'), str):
            return False
        if description.get('type') != 'ord':
            return False
        if not description.get('compute_ph') or not isinstance(description.get('compute_ph'), dict):
            return False
        if not description.get('compute_ph').get('success'):
            return False
        if description.get('compute_ph').get('exit_code') is None or description.get('compute_ph').get(
                'exit_code') != 0:
            return False
        if not description.get('storage_ph'):
            return False
        if not description.get('action') or not isinstance(description.get('action'), dict):
            return False
        if not description.get('action').get('valid'):
            return False
        if not description.get('action').get('success'):
            return False
        if description.get('action').get('result_code') is None or description.get('action').get('result_code') != 0:
            return False
        if not transaction.get('out_msgs').get('out_msgs'):
            if not transaction.get('in_msg') or not isinstance(transaction.get('in_msg'), dict):
                return False
            if not transaction.get('in_msg').get('source'):
                return False
            if not transaction.get('in_msg').get('destination'):
                return False
            if transaction.get('in_msg').get('source_friendly') == transaction.get('in_msg').get(
                    'destination_friendly'):
                return False
            # Checks if the transaction is not related to fee payment
            if not transaction.get('in_msg').get('opcode') or not isinstance(transaction.get('in_msg').get('opcode'),
                                                                             str):
                return False
            if transaction.get('in_msg').get('opcode') != '0x00000000':
                return False
        elif len(transaction.get('out_msgs').get('out_msgs')) >= 1:
            if transaction.get('in_msg').get('source'):
                return False
        else:
            return False

        return True


class TonXTonResponseParser(ResponseParser):
    validator = TonXTonValidator
    symbol = 'TON'
    currency = Currencies.ton
    precision = 9
    average_block_time = 5

    @classmethod
    def get_user_friendly_address(cls, address: str) -> str:
        return address

    @classmethod
    def _calculate_memo(cls, transaction: Dict[str, Any]) -> str:
        import codecs

        from tvm_valuetypes.cell import deserialize_boc
        if not transaction.get('message_content') or not isinstance(transaction.get('message_content'), dict):
            return ''
        if (not transaction.get('message_content').get('body') or
                not isinstance(transaction.get('message_content').get('body'), str)):
            return ''
        b64_boc = transaction.get('message_content').get('body')
        boc = codecs.decode(codecs.encode(b64_boc, 'utf-8'), 'base64')
        cell = deserialize_boc(boc)
        bytes_memo = cell.data.data.tobytes()[4:]
        memo = int(cell.data.data.tobytes()[4:]) if bytes_memo.isdigit() else ''
        return str(memo)

    @classmethod
    def parse_tx_details_response(cls,
                                  tx_details_response: Dict[str, Any],
                                  _: Optional[int]) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        if cls.validator.validate_tx_details_response(tx_details_response):
            tx_details_response = tx_details_response.get('result')[0]
            if not tx_details_response.get('in_msg').get('source_friendly'):
                out_msg = tx_details_response.get('out_msgs').get('out_msgs')[0]
                from_address = out_msg.get('source_friendly')
                to_address = out_msg.get('destination_friendly')
                amount = BlockchainUtilsMixin.from_unit((int(out_msg.get('value'))),
                                                        precision=cls.precision)
                fee = BlockchainUtilsMixin.from_unit(int(out_msg.get('fwd_fee')), precision=cls.precision)
                memo = cls._calculate_memo(out_msg)
            else:
                in_msg = tx_details_response.get('in_msg')
                from_address = in_msg.get('source_friendly')
                to_address = in_msg.get('destination_friendly')
                amount = BlockchainUtilsMixin.from_unit((int(in_msg.get('value'))),
                                                        precision=cls.precision)
                fee = BlockchainUtilsMixin.from_unit(int(in_msg.get('fwd_fee')), precision=cls.precision)
                memo = cls._calculate_memo(tx_details_response.get('in_msg'))

            timestamp = tx_details_response.get('now')
            confirmations = calculate_tx_confirmations(cls.average_block_time, timestamp)
            transfers.append(TransferTx(
                block_height=tx_details_response.get('block_ref').get('seqno'),
                block_hash=None,
                tx_hash=tx_details_response.get('hash'),
                date=parse_utc_timestamp(timestamp),
                success=True,
                confirmations=confirmations,
                from_address=from_address,
                to_address=to_address,
                value=amount,
                symbol=cls.symbol,
                memo=memo or '',
                tx_fee=fee,
            ))

        return transfers


class TonXTonApi(GeneralApi):
    """
    API DOC: https://docs.tonxapi.com/reference/ton-api-overview
    """

    parser = TonXTonResponseParser
    _base_url = 'https://mainnet-rpc.tonxapi.com/v2/json-rpc/7251ea1f-1a0e-4394-8dc5-97c8613c1ba7'
    cache_key = 'ton'
    symbol = 'TON'
    need_block_head_for_confirmation = False

    supported_requests = {
        'get_tx_details': '',
    }

    @classmethod
    def get_headers(cls) -> Dict[str, Any]:
        return {'content-type': 'application/json', 'accept': 'application/json'}

    @classmethod
    def get_tx_details_body(cls, tx_hash: str) -> str:
        data = {
            'id': 1,
            'jsonrpc': '2.0',
            'method': 'getTransactions',
            'params': {
                'limit': 256,
                'hash': tx_hash
            }
        }
        return json.dumps(data)
