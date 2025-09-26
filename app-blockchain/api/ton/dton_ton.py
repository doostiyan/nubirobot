import base64
import json
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin

from .utils import TonAddressConvertor, calculate_tx_confirmations


class DtonTonValidator(ResponseValidator):
    success_status = 0
    precision = 9

    @classmethod
    def validate_general_response(cls, response: Dict[str, Any]) -> bool:
        if response.get('data') is None or response.get('errors'):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        blocks = block_head_response.get('data').get('blocks')[0]
        if blocks is None or len(blocks) != 1 or blocks.get('seqno') is None:
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False

        transactions = tx_details_response.get('data').get('raw_transactions')
        if transactions is None or len(transactions) != 1:
            return False

        return cls.validate_transaction(transactions[0])

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if transaction is None:
            return False
        if transaction.get('in_msg_src_addr_address_hex') is None:
            if len(transaction.get('out_msg_value_grams')) == 0 or len(
                    transaction.get('out_msg_dest_addr_address_hex')) > 1:
                return False
        else:
            if transaction.get('in_msg_value_grams') is None:
                return False
            if len(transaction.get('out_msg_value_grams')) != 0:
                return False

        if transaction.get('in_msg_src_addr_address_hex') == transaction.get('in_msg_dest_addr_address_hex'):
            return False
        if transaction.get('aborted') != cls.success_status:
            return False
        if transaction.get('action_ph_result_code') != 0.0:
            return False

        return True

    @classmethod
    def validate_memo(cls, transaction: Dict[str, Any]) -> bool:
        if transaction.get('in_msg_comment') is None:
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(balance_response):
            return False
        if len(balance_response.get('data').get('transactions')) == 0:
            return False
        if balance_response.get('data').get('transactions')[0].get('account_storage_balance_grams') is None:
            return False

        return True

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(block_txs_response):
            return False

        transactions = block_txs_response.get('data').get('transactions')
        if transactions is None or len(transactions) == 0:
            return False

        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Dict[str, Any]) -> bool:
        return cls.validate_general_response(address_txs_response)


class DtonTonParser(ResponseParser):
    validator = DtonTonValidator
    symbol = 'TON'
    currency = Currencies.ton
    precision = 9
    average_block_time = 5

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, Any]) -> Optional[int]:
        if not cls.validator.validate_block_head_response(block_head_response):
            return None

        return int(block_head_response.get('data').get('blocks')[0].get('seqno'))

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, Any]) -> Decimal:
        if not cls.validator.validate_balance_response(balance_response):
            return Decimal(0)

        return BlockchainUtilsMixin.from_unit(int(
            balance_response.get('data').get('transactions')[0].get('account_storage_balance_grams')),
            precision=cls.precision)

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, Any], _: Optional[int]) -> List[TransferTx]:
        if cls.validator.validate_tx_details_response(tx_details_response):
            transaction = tx_details_response.get('data').get('raw_transactions')[0]

            if transaction.get('in_msg_src_addr_address_hex') is None:
                from_address = TonAddressConvertor.convert_hex_to_bounceable(
                    transaction.get('in_msg_dest_addr_address_hex'))
                to_address = TonAddressConvertor.convert_hex_to_bounceable(
                    transaction.get('out_msg_dest_addr_address_hex')[0])
                tx_value = BlockchainUtilsMixin.from_unit(int(transaction.get('out_msg_value_grams')[0]),
                                                          precision=cls.precision)
            else:
                from_address = TonAddressConvertor.convert_hex_to_bounceable(
                    transaction.get('in_msg_src_addr_address_hex'))
                to_address = TonAddressConvertor.convert_hex_to_bounceable(
                    transaction.get('in_msg_dest_addr_address_hex'))
                tx_value = BlockchainUtilsMixin.from_unit(int(transaction.get('in_msg_value_grams')),
                                                          precision=cls.precision)

            block = int(transaction.get('seqno'))
            tx_date = (parse_iso_date(transaction.get('gen_utime') + 'Z'))
            return [TransferTx(block_height=block,
                               block_hash=None,
                               tx_hash=convert_hex_to_base64(transaction.get('hash')),
                               date=tx_date,
                               success=True,
                               confirmations=calculate_tx_confirmations(cls.average_block_time, tx_date.timestamp()),
                               from_address=from_address,
                               to_address=to_address,
                               value=tx_value,
                               symbol=cls.symbol,
                               memo=transaction.get('in_msg_comment') or '',
                               tx_fee=None,
                               token=None)]
        return []

    @classmethod
    def parse_block_txs_response(cls, block_txs_response: Dict[str, Any]) -> List[TransferTx]:
        if cls.validator.validate_block_txs_response(block_txs_response):
            block_txs = []
            for tx in block_txs_response.get('data').get('transactions'):
                if cls.validator.validate_transaction(tx) and cls.validator.validate_memo(tx):
                    from_address = TonAddressConvertor.convert_hex_to_bounceable(tx.get('in_msg_src_addr_address_hex'))
                    to_address = TonAddressConvertor.convert_hex_to_bounceable(tx.get('in_msg_dest_addr_address_hex'))
                    tx_hash = convert_hex_to_base64(tx.get('hash'))
                    tx_value = BlockchainUtilsMixin.from_unit(int(tx.get('in_msg_value_grams')),
                                                              precision=cls.precision)
                    block_tx = TransferTx(
                        block_height=None,
                        block_hash=None,
                        tx_hash=tx_hash,
                        date=None,
                        success=True,
                        confirmations=0,
                        from_address=from_address,
                        to_address=to_address,
                        value=tx_value,
                        symbol=cls.symbol,
                        memo=None,
                        tx_fee=None,
                    )
                    block_txs.append(block_tx)

            return block_txs
        return []

    @classmethod
    def parse_address_txs_response(cls, _: str, address_txs_response: Dict[str, Union[str, int]],
                                   __: Optional[int]) -> List[TransferTx]:
        if cls.validator.validate_address_txs_response(address_txs_response):
            address_txs = []
            for tx in address_txs_response.get('data').get('raw_transactions'):
                if cls.validator.validate_transaction(tx) and cls.validator.validate_memo(tx):
                    block = int(tx.get('seqno'))
                    if tx.get('in_msg_src_addr_address_hex') is None:
                        from_address = TonAddressConvertor.convert_hex_to_bounceable(
                            tx.get('in_msg_dest_addr_address_hex'))
                        to_address = TonAddressConvertor.convert_hex_to_bounceable(
                            tx.get('out_msg_dest_addr_address_hex')[0])
                        tx_value = BlockchainUtilsMixin.from_unit(int(tx.get('out_msg_value_grams')[0]),
                                                                  precision=cls.precision)
                    else:
                        from_address = TonAddressConvertor.convert_hex_to_bounceable(
                            tx.get('in_msg_src_addr_address_hex'))
                        to_address = TonAddressConvertor.convert_hex_to_bounceable(
                            tx.get('in_msg_dest_addr_address_hex'))
                        tx_value = BlockchainUtilsMixin.from_unit(int(tx.get('in_msg_value_grams')),
                                                                  precision=cls.precision)

                    tx_hash = convert_hex_to_base64(tx.get('hash'))
                    tx_date = (parse_iso_date(tx.get('gen_utime') + 'Z'))
                    address_tx = TransferTx(
                        block_height=block,
                        block_hash=None,
                        tx_hash=tx_hash,
                        date=tx_date,
                        success=True,
                        confirmations=calculate_tx_confirmations(cls.average_block_time, tx_date.timestamp()),
                        from_address=from_address,
                        to_address=to_address,
                        value=tx_value,
                        symbol=cls.symbol,
                        memo=tx.get('in_msg_comment'),
                        tx_fee=None,
                        token=None,
                    )

                    address_txs.append(address_tx)

            return address_txs
        return []


class DtonTonApi(GeneralApi):
    parser = DtonTonParser
    need_block_head_for_confirmation = False
    cache_key = 'ton'
    _base_url = 'https://dton.io/graphql/'
    TRANSACTIONS_LIMIT = 100
    supported_requests = {'get_address_txs': '',
                          'get_block_txs': '',
                          'get_block_head': '',
                          'get_tx_details': '',
                          'get_balance': ''}
    # If you are testing locally, comment this line
    USE_PROXY = bool(not settings.IS_VIP)
    queries = {'get_address_txs': """
                    query address_txs($limit: Int!, $address: String) {
                        raw_transactions(
                            workchain: 0
                            aborted: 0
                            page_size: $limit
                            address: $address
                            in_msg_dest_addr_address_hex: $address
                        ) {
                            seqno
                            action_ph_result_code
                            aborted
                            in_msg_src_addr_address_hex
                            in_msg_dest_addr_address_hex
                            hash
                            in_msg_value_grams
                            gen_utime
                            in_msg_comment
                            out_msg_value_grams
                            out_msg_dest_addr_address_hex
                        }
                    } """,
               'get_tx_details': """
                    query tx_details($tx_hash: String) {
                        raw_transactions(
                            workchain: 0
                            aborted: 0
                            hash: $tx_hash
                        ) {
                            seqno
                            action_ph_result_code
                            aborted
                            in_msg_src_addr_address_hex
                            in_msg_dest_addr_address_hex
                            hash
                            in_msg_value_grams
                            gen_utime
                            in_msg_comment
                            out_msg_value_grams
                            out_msg_dest_addr_address_hex
                        }
                    } """,
               'get_block_txs': """
                    query block_txs($height: Float!, $limit: Int!) {
                        transactions(
                            workchain: 0
                            aborted: 0
                            page_size: $limit
                            seqno: $height
                        ) {
                            seqno
                            action_ph_result_code
                            aborted
                            in_msg_src_addr_address_hex
                            in_msg_dest_addr_address_hex
                            hash
                            outmsg_cnt
                            in_msg_value_grams
                            gen_utime
                        }
                    } """,
               'get_block_head': """
                    {
                        blocks(
                            workchain: 0,
                            page_size: 1,
                        ) {
                            seqno
                          }
                    } """,
               'get_balance': """
                    query address_balance($limit: Int!, $address: String) {
                        transactions(
                            workchain: 0
                            aborted: 0
                            page_size: $limit
                            address: $address
                        ) {
                            account_storage_balance_grams
                        }
                    } """
               }

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {'Content-Type': 'application/json'}

    @classmethod
    def get_block_head_body(cls) -> str:
        data = {'query': cls.queries.get('get_block_head')}
        return json.dumps(data)

    @classmethod
    def get_tx_details_body(cls, tx_hash: str) -> str:
        data = {'query': cls.queries.get('get_tx_details'),
                'variables': {'tx_hash': convert_base64_to_hex(tx_hash)}}
        return json.dumps(data)

    @classmethod
    def get_address_txs_body(cls, address: str) -> str:
        data = {'query': cls.queries.get('get_address_txs'),
                'variables': {'limit': cls.TRANSACTIONS_LIMIT,
                              'address': TonAddressConvertor.convert_bounceable_to_hex(address)}}
        return json.dumps(data)

    @classmethod
    def get_block_txs_body(cls, block_height: int) -> str:
        data = {'query': cls.queries.get('get_block_txs'),
                'variables': {'height': block_height,
                              'limit': cls.TRANSACTIONS_LIMIT}}
        return json.dumps(data)

    @classmethod
    def get_balance_body(cls, address: str) -> str:
        data = {'query': cls.queries.get('get_balance'),
                'variables': {'limit': 1,
                              'address': TonAddressConvertor.convert_bounceable_to_hex(address)}}
        return json.dumps(data)


def convert_hex_to_base64(hex_form: str) -> str:
    return base64.b64encode(bytes.fromhex(hex_form)).decode()


def convert_base64_to_hex(base64_form: str) -> str:
    return base64.b64decode(base64_form.encode()).hex()
