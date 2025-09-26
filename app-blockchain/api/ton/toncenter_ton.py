import base64
import datetime
import random
import sys
import traceback
import urllib.parse
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

import pytz
from django.conf import settings

from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.general.dtos.dtos import TransferTx

from .utils import calculate_tx_confirmations


class ToncenterTonValidator(ResponseValidator):
    precision = 9

    @classmethod
    def validate_general_response(cls, response: Any) -> bool:
        if len(response) == 0:
            return False

        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Union[List[Dict[str, Any]], Dict[str, Any]]) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False

        transaction = tx_details_response[0] if isinstance(tx_details_response, list) else tx_details_response

        return cls.validate_transaction(transaction)

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if transaction is None:
            raise APIError('[ToncenterTonApi][validateTransaction] Response is None.')
        if transaction.get('account') is None:
            raise APIError('[ToncenterTonApi][validateGeneralResponse] account is None.')
        if transaction.get('compute_skip_reason') is not None:
            return False
        if transaction.get('action_result_code') != 0:
            return False
        if transaction.get('compute_exit_code') is not None and transaction.get('compute_exit_code') != 0:
            return False
        if transaction.get('in_msg').get('source') == transaction.get('in_msg').get('destination'):
            return False
        if len(transaction.get('out_msgs')) == 0:
            if not transaction.get('in_msg').get('source'):
                return False
            if not transaction.get('in_msg').get('destination'):
                return False
        elif len(transaction.get('out_msgs')) >= 1:
            if transaction.get('in_msg').get('source'):
                return False
        else:
            return False

        return True

    @classmethod
    def validate_memo(cls, transaction: Dict[str, Any]) -> bool:
        # Check Toncenter memo
        if len(transaction.get('out_msgs')) == 0 and transaction.get('in_msg').get('comment') is None:
            # Check Ton indexer memo:
            try:
                if transaction.get('in_msg').get('body').get('comment') is None:
                    return False
            except AttributeError:
                return False
        return True

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: Any) -> bool:
        if not cls.validate_general_response(block_txs_response):
            return False

        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: List[Dict[str, Any]]) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        if block_head_response[0].get('seqno') is None:
            raise APIError('The API did not return the block height')

        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Any) -> bool:
        return cls.validate_general_response(address_txs_response)


class ToncenterTonResponseParser(ResponseParser):
    validator = ToncenterTonValidator
    symbol = 'TON'
    currency = Currencies.ton
    precision = 9
    average_block_time = 5

    FEE_TRANSFER_OP_NUMBER = 260734629

    @classmethod
    def get_memo(cls, transaction: Dict[str, Any]) -> str:
        return transaction.get('in_msg').get('comment')

    @classmethod
    def get_user_friendly_address(cls, address: str) -> str:
        return address

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Union[List[Dict[str, Any]], Dict[str, Any]],
                                  _: Optional[int]) -> List[TransferTx]:
        if not cls.validator.validate_tx_details_response(tx_details_response):
            return []

        tx_details_response = tx_details_response[0] if isinstance(tx_details_response, list) else tx_details_response

        if not tx_details_response.get('in_msg').get('source'):
            from_address = cls.get_user_friendly_address(tx_details_response.get('out_msgs')[0].get('source'))
            to_address = cls.get_user_friendly_address(tx_details_response.get('out_msgs')[0].get('destination'))
            amount = BlockchainUtilsMixin.from_unit((int(tx_details_response.get('out_msgs')[0].get('value'))),
                                                    precision=cls.precision)
            memo = ''
        else:
            from_address = cls.get_user_friendly_address(tx_details_response.get('in_msg').get('source'))
            to_address = cls.get_user_friendly_address(tx_details_response.get('in_msg').get('destination'))
            amount = BlockchainUtilsMixin.from_unit((int(tx_details_response.get('in_msg').get('value'))),
                                                    precision=cls.precision)
            memo = cls.get_memo(tx_details_response)

        confirmations = calculate_tx_confirmations(cls.average_block_time, tx_details_response.get('utime'))

        return [TransferTx(
            block_height=0,
            block_hash=None,
            tx_hash=tx_details_response.get('hash'),
            date=parse_utc_timestamp(tx_details_response.get('utime')),
            success=True,
            confirmations=confirmations,
            from_address=from_address,
            to_address=to_address,
            value=amount,
            symbol=cls.symbol,
            memo=memo or '',
            tx_fee=None,
        )]

    @classmethod
    def parse_block_head_response(cls, block_head_response: List[Dict[str, Any]]) -> Optional[int]:
        if not cls.validator.validate_block_head_response(block_head_response):
            return None

        return block_head_response[0].get('seqno')

    @classmethod
    def parse_address_txs_response(cls, _: str, address_txs_response: List[Dict[str, Any]], __: Optional[int]) -> List[
        TransferTx]:
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return []

        address_txs = []
        for transaction in address_txs_response:
            if cls.validator.validate_transaction(transaction) and cls.validator.validate_memo(transaction):

                tx_hash = transaction.get('hash')
                if not transaction.get('in_msg').get('source'):
                    if transaction.get('out_msgs')[0].get('op') == cls.FEE_TRANSFER_OP_NUMBER:  # Filter fee transfers
                        continue
                    from_address = cls.get_user_friendly_address(transaction.get('out_msgs')[0].get('source'))
                    to_address = cls.get_user_friendly_address(transaction.get('out_msgs')[0].get('destination'))
                    amount = Decimal('0')
                    for out in transaction.get('out_msgs'):
                        amount += BlockchainUtilsMixin.from_unit((int(out.get('value'))), precision=cls.precision)
                    hot_tx_hash = transaction.get('in_msg').get('hash')
                    tx_hash = base64.b64decode(hot_tx_hash.encode()).hex()
                    memo = None
                else:
                    from_address = cls.get_user_friendly_address(transaction.get('in_msg').get('source'))
                    to_address = cls.get_user_friendly_address(transaction.get('in_msg').get('destination'))
                    amount = BlockchainUtilsMixin.from_unit((int(transaction.get('in_msg').get('value'))),
                                                            precision=cls.precision)
                    memo = cls.get_memo(transaction)

                confirmations = calculate_tx_confirmations(cls.average_block_time, transaction.get('utime'))
                address_tx = TransferTx(
                    block_height=0,
                    block_hash=None,
                    tx_hash=tx_hash,
                    date=parse_utc_timestamp(transaction.get('utime')),
                    success=True,
                    confirmations=confirmations,
                    from_address=from_address,
                    to_address=to_address,
                    value=amount,
                    symbol=cls.symbol,
                    memo=memo,
                    tx_fee=BlockchainUtilsMixin.from_unit(int(transaction.get('fee')),
                                                          precision=cls.precision),
                )
                address_txs.append(address_tx)

        return address_txs

    @classmethod
    def parse_block_txs_response(cls, block_txs_response: List[Dict[str, Any]]) -> List[TransferTx]:
        if not cls.validator.validate_block_txs_response(block_txs_response):
            return []

        block_txs = []
        for tx in block_txs_response:
            if cls.validator.validate_transaction(tx) and cls.validator.validate_memo(tx):
                from_address = tx.get('in_msg').get('source')
                to_address = tx.get('in_msg').get('destination')
                tx_hash = tx.get('hash')
                tx_value = tx.get('in_msg').get('value')
                block_tx = TransferTx(
                    block_height=0,
                    block_hash=None,
                    tx_hash=tx_hash,
                    date=parse_utc_timestamp(tx.get('utime')),
                    confirmations=calculate_tx_confirmations(cls.average_block_time, tx.get('utime')),
                    success=True,
                    from_address=from_address,
                    to_address=to_address,
                    value=BlockchainUtilsMixin.from_unit((int(tx_value)), precision=cls.precision),
                    symbol=cls.symbol,
                    token=None,
                    tx_fee=BlockchainUtilsMixin.from_unit(int(tx.get('fee')),
                                                          precision=cls.precision),
                    memo=cls.get_memo(tx) if tx.get('in_msg').get('source') else None
                )
                block_txs.append(block_tx)

        return block_txs

    @classmethod
    def parse_tx_withdraw_hash(cls, response: Dict[str, Any]) -> str:
        in_msg_hash = response.get('in_msg', {}).get('hash')
        return base64.b64decode(in_msg_hash.encode()).hex() or ''


class ToncenterTonApi(GeneralApi):
    parser = ToncenterTonResponseParser
    _base_url = 'https://toncenter.com/api/index/'
    cache_key = 'ton'
    shard = '-9223372036854775808'
    workchain = 0
    TRANSACTIONS_LIMIT = 900
    GET_ADDRESS_TXS_HOUR_OFFSET = 4
    request_reliability = 3
    reliability_need_status_codes = [500, 502]
    timeout = 60
    need_block_head_for_confirmation = False

    supported_requests = {
        'get_block_txs': 'getTransactionsInBlock?workchain=' + str(workchain) + '&shard=' + str(
            shard) + '&seqno={height}',
        'get_block_head': 'getBlocksByUnixTime?workchain=' + str(workchain) + '&limit=1',
        'get_address_txs':
            'getTransactionsByAddress?address={address}&start_utime={start_utime}&end_utime={end_utime}&offset={offset}'
            '&limit=' + str(TRANSACTIONS_LIMIT),
        'get_tx_details': 'getTransactionByHash?tx_hash={tx_hash}',
        'get_withdraw_hash': 'v1/getTransactionByHash?tx_hash={tx_hash}',
    }

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {'x-api-key': random.choice(settings.TON_TONCENTER_APIKEY)}

    @classmethod
    def get_tx_details(cls, tx_hash: str) -> Any:
        tx_hash_url_encoded = urllib.parse.quote_plus(tx_hash)
        return cls.request(request_method='get_tx_details', body=cls.get_tx_details_body(tx_hash),
                           headers=cls.get_headers(), tx_hash=tx_hash_url_encoded)

    @classmethod
    def get_withdraw_hash(cls, tx_hash: str) -> Any:
        return cls.request(request_method='get_withdraw_hash', body=cls.get_tx_details_body(tx_hash),
                           headers=cls.get_headers(), tx_hash=tx_hash)

    @classmethod
    def get_address_txs(cls, address: str, **kwargs: Any) -> list:
        responses = []
        i = 0
        now = pytz.timezone('UTC').localize(datetime.datetime.utcnow())
        end_timestamp = int(now.timestamp())
        from_timestamp = int((now - datetime.timedelta(hours=cls.GET_ADDRESS_TXS_HOUR_OFFSET)).timestamp())
        while True:
            offset = i * cls.TRANSACTIONS_LIMIT
            try:
                response = cls.request(request_method='get_address_txs', body=cls.get_address_txs_body(address),
                                       headers=cls.get_headers(), address=address, offset=offset,
                                       apikey=cls.get_api_key(), timeout=cls.timeout, start_utime=from_timestamp,
                                       end_utime=end_timestamp)
            except Exception:
                traceback.print_exception(*sys.exc_info())
                break

            responses.extend(response)
            i += 1
            if not response or response[-1].get('utime') < from_timestamp:
                break
        return responses
