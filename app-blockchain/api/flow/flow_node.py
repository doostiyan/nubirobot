import base64
import json
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.conf import settings

from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_iso_date
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
    from exchange.base.parsers import parse_iso_date

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI
from exchange.blockchain.utils import BlockchainUtilsMixin


class FlowNodeFlowValidator(ResponseValidator):
    FEE_ADDRESS = '0xf919ee77447b7497'
    FLOW_TOKEN_CONTRACT = '1654653399040a61'  # noqa: S105
    DEPOSIT_EVENT_CONTRACT = f'A.{FLOW_TOKEN_CONTRACT}.FlowToken.TokensDeposited'
    WITHDRAW_EVENT_CONTRACT = f'A.{FLOW_TOKEN_CONTRACT}.FlowToken.TokensWithdrawn'
    valid_transfer_types = [DEPOSIT_EVENT_CONTRACT, WITHDRAW_EVENT_CONTRACT]
    excluded_addresses = ['0x1bf2b9d59ad1ba04']

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, Any]) -> bool:
        if not balance_response.get('address'):
            return False
        if not balance_response.get('balance'):
            return False
        if not isinstance(balance_response.get('balance'), str):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: List[Dict[str, Any]]) -> bool:
        if not block_head_response[0]:
            return False
        if not block_head_response[0].get('block_status'):
            return False
        if not block_head_response[0].get('header'):
            return False
        if not block_head_response[0].get('header').get('height') or not isinstance(
                block_head_response[0].get('header').get('height'), str):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, Any]) -> bool:
        if not tx_details_response.get('block_id'):
            return False
        if not tx_details_response.get('execution') or tx_details_response.get('execution') != 'Success':
            return False
        if not tx_details_response.get('status') or tx_details_response.get('status') != 'Sealed':
            return False
        if tx_details_response.get('status_code') != 0:
            return False
        if tx_details_response.get('error_message') != '':
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        event_type = transaction.get('type')
        if event_type in [cls.DEPOSIT_EVENT_CONTRACT, cls.WITHDRAW_EVENT_CONTRACT]:
            transaction['decoded_payload'] = json.loads(
                base64.b64decode(transaction.get('payload')).decode('utf-8')).get(
                'value').get('fields')
            if not transaction.get('decoded_payload')[1].get('value').get('value'):
                return False
            tx_value = Decimal(str(transaction.get('decoded_payload')[0].get('value').get('value')))
            if tx_value <= cls.min_valid_tx_amount:
                return False
            return True
        return False

    @classmethod
    def validate_block_tx_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if transaction.get('type') not in cls.valid_transfer_types:
            return False
        if not transaction.get('transaction_id'):
            return False
        payload = transaction.get('payload')
        decoded_payload = json.loads(base64.b64decode(payload).decode('utf-8'))
        address_info = decoded_payload.get('value').get('fields')[1].get('value').get('value')
        if not address_info:
            return False
        address = address_info.get('value')
        if address in cls.excluded_addresses:
            return False
        decoded_payload_fields = decoded_payload.get('value').get('fields')
        tx_value = Decimal(decoded_payload_fields[0].get('value').get('value'))
        if tx_value <= cls.min_valid_tx_amount:
            return False
        if decoded_payload_fields[1].get('value').get('value') is None:  # check address field is not None
            return False
        if decoded_payload_fields[1].get('value').get('value').get('value') == cls.FEE_ADDRESS:
            return False
        return True

    @classmethod
    def validate_batch_block_txs_response(cls, batch_block_txs_response: Any) -> bool:
        if not batch_block_txs_response:
            return False
        return True


class FlowNodeResponseParser(ResponseParser):
    """
        coins: Flow
        API docs: https://developers.flow.com/http-api
        rate limit: https://developers.flow.com/nodes/access-api-rate-limits
        get latest block rate limit : 100 request per second per client IP
        other request rate limit: 2000 rps

        """
    symbol = 'FLOW'
    precision = 8
    min_valid_tx_amount = Decimal('0.0')
    currency = Currencies.flow
    validator = FlowNodeFlowValidator

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, Any]) -> Decimal:
        if cls.validator.validate_balance_response(balance_response):
            return BlockchainUtilsMixin.from_unit(int(balance_response.get('balance')), cls.precision)
        return Decimal(0)

    @classmethod
    def parse_block_head_response(cls, block_head_response: List[Dict[str, Any]]) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return int(block_head_response[0].get('header').get('height'))
        return None

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, Any], _: Optional[int]) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        if cls.validator.validate_tx_details_response(tx_details_response):
            events = tx_details_response.get('events')
            tx_hash = tx_details_response.get('events')[0].get('transaction_id')
            tx_fee = None
            valid_events = []  # It's going to be a list of dicts
            # In each transaction we have some events which are like transfers.
            # So we should validate them first, then create transfer objects with
            # from_address or to_address
            for event in events:
                from_address = ''
                to_address = ''
                if cls.validator.validate_transaction(event):
                    tx_value = Decimal(event.get('decoded_payload')[0].get('value').get('value'))
                    address = event.get('decoded_payload')[1].get('value').get('value').get('value')
                    if address == cls.validator.FEE_ADDRESS:
                        tx_fee = tx_value
                        continue
                    if event.get('type') == cls.validator.WITHDRAW_EVENT_CONTRACT:
                        from_address = address
                    elif event.get('type') == cls.validator.DEPOSIT_EVENT_CONTRACT:
                        to_address = address
                    valid_events.append({'tx_value': tx_value, 'from_address': from_address, 'to_address': to_address})
            for event in valid_events:
                if (event.get('from_address') != '' or event.get('to_address') != '') and \
                        event.get('tx_value') != tx_fee:  # This condition is for ignoring fee-transfer
                    transfer = TransferTx(
                        tx_hash=tx_hash,
                        success=True,
                        symbol=cls.symbol,
                        from_address=event.get('from_address'),
                        to_address=event.get('to_address'),
                        block_hash=tx_details_response.get('block_id'),
                        value=event.get('tx_value'),
                        tx_fee=tx_fee,
                    )
                    transfers.append(transfer)
        return transfers

    @classmethod
    def parse_batch_block_txs_response(cls, batch_block_txs_response: List[Dict[str, Any]]) -> List[TransferTx]:
        if cls.validator.validate_batch_block_txs_response(batch_block_txs_response):
            blocks_txs: List[TransferTx] = []
            for block_height in batch_block_txs_response:
                if block_height.get('events'):
                    events = block_height.get('events')
                    for event in events:
                        if cls.validator.validate_block_tx_transaction(event):
                            payload = event.get('payload')
                            decoded_payload = json.loads(base64.b64decode(payload).decode('utf-8'))
                            address_info = decoded_payload.get('value').get('fields')[1].get('value').get('value')
                            tx_value = Decimal(decoded_payload.get('value').get('fields')[0].get('value').get('value'))
                            address = address_info.get('value')
                            is_incoming = 'Deposited' in event.get('type')
                            date = parse_iso_date(block_height.get('block_timestamp'))
                            block_tx = TransferTx(
                                tx_hash=event.get('transaction_id'),
                                from_address=address if not is_incoming else '',
                                to_address=address if is_incoming else '',
                                value=tx_value,
                                success=True,
                                symbol=cls.symbol,
                                block_hash=block_height.get('block_id'),
                                block_height=int(block_height.get('block_height')),
                                date=date
                            )
                            blocks_txs.append(block_tx)

            return blocks_txs
        return []


class FlowNodeApi(GeneralApi, NobitexBlockchainBlockAPI):
    PRECISION = 8
    symbol = 'FLOW'
    cache_key = 'flow'
    currency = Currencies.flow
    SUPPORT_BATCH_GET_BLOCKS = True
    _base_url = 'https://rest-mainnet.onflow.org/v1/'
    rate_limit = 0.01  # minimum rps
    GET_BLOCK_ADDRESSES_MAX_NUM = 249
    parser = FlowNodeResponseParser
    supported_requests = {
        'get_balance': 'accounts/{address}',
        'get_block_head': 'blocks?height=sealed',
        'get_tx_details': 'transaction_results/{tx_hash}',
        'get_blocks_txs_deposit':
            'events?end_height={to_block}&start_height={from_block}&type='
            f'{FlowNodeResponseParser.validator.DEPOSIT_EVENT_CONTRACT}',
        'get_blocks_txs_withdraw':
            'events?end_height={to_block}&start_height={from_block}&type='
            f'{FlowNodeResponseParser.validator.WITHDRAW_EVENT_CONTRACT}',

    }
    USE_PROXY = True

    @classmethod
    def get_batch_block_txs(cls, from_block: int, to_block: int) -> Any:
        deposit_response = cls.request(request_method='get_blocks_txs_deposit',
                                       body=cls.get_blocks_txs_body(from_block, to_block),
                                       headers=cls.get_headers(),
                                       from_block=from_block,
                                       to_block=to_block)
        withdraw_response = cls.request(request_method='get_blocks_txs_withdraw',
                                        body=cls.get_blocks_txs_body(from_block, to_block),
                                        headers=cls.get_headers(),
                                        from_block=from_block,
                                        to_block=to_block)
        return deposit_response + withdraw_response
