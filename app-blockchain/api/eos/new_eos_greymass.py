import json
from typing import List
from decimal import Decimal

from django.conf import settings

from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseValidator, ResponseParser

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


def parse_quantity(q):
    if not q or not q.endswith(' EOS'):
        return None
    return Decimal(q[:-4])


class EosGreymassResponseValidator(ResponseValidator):
    symbol = 'EOS'
    min_valid_tx_amount = Decimal('0.0005')
    precision = 4

    @classmethod
    def validate_address_txs_response(cls, address_txs_response) -> bool:
        if not address_txs_response or not isinstance(address_txs_response, dict):
            return False
        if (not address_txs_response.get('last_irreversible_block') or
                not isinstance(address_txs_response.get('last_irreversible_block'), int)):
            return False
        if not address_txs_response.get('actions') or not isinstance(address_txs_response.get('actions'), list):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response) -> bool:
        if not tx_details_response or not isinstance(tx_details_response, dict):
            return False
        if not tx_details_response.get('block_num') or not isinstance(tx_details_response.get('block_num'), int):
            return False
        if (not tx_details_response.get('last_irreversible_block') or
                not isinstance(tx_details_response.get('last_irreversible_block'), int)):
            return False
        if not tx_details_response.get('id') or not isinstance(tx_details_response.get('id'), str):
            return False
        if not tx_details_response.get('block_time') or not isinstance(tx_details_response.get('block_time'), str):
            return False
        if (tx_details_response.get('irreversible') is None or
                not isinstance(tx_details_response.get('irreversible'), bool)):
            return False
        if not tx_details_response.get('trx') or not isinstance(tx_details_response.get('trx'), dict):
            return False
        if (not tx_details_response.get('trx').get('trx') or
                not isinstance(tx_details_response.get('trx').get('trx'), dict)):
            return False
        if (not tx_details_response.get('trx').get('trx').get('actions') or
                not isinstance(tx_details_response.get('trx').get('trx').get('actions'), list)):
            return False
        return True

    @classmethod
    def validate_transfer(cls, transfer) -> bool:
        if not transfer.get('account') or not isinstance(transfer.get('account'), str):
            return False
        if not transfer.get('account') == 'eosio.token':
            return False
        if not transfer.get('name') or not isinstance(transfer.get('name'), str):
            return False
        if not transfer.get('name') == 'transfer':
            return False
        if not transfer.get('data') or not isinstance(transfer.get('data'), dict):
            return False
        data = transfer.get('data')
        if not data.get('from') or not isinstance(data.get('from'), str):
            return False
        if not data.get('to') or not isinstance(data.get('to'), str):
            return False
        if not data.get('quantity') or not isinstance(data.get('quantity'), str):
            return False
        value = parse_quantity(data.get('quantity'))
        if value < cls.min_valid_tx_amount:
            return False
        from_address = data.get('from')
        if not transfer.get('authorization') or not isinstance(transfer.get('authorization'), list):
            return False
        for auth in transfer.get('authorization'):
            if not auth.get('actor') or not isinstance(auth.get('actor'), str):
                continue
            if not auth.get('permission') or not isinstance(auth.get('permission'), str):
                continue
            if auth.get('actor') == from_address and auth.get('permission') in ['active', 'owner']:
                break
        else:
            return False
        return True

    @classmethod
    def validate_address_tx_transaction(cls, transaction) -> bool:
        if not transaction or not isinstance(transaction, dict):
            return False
        if not transaction.get('block_num') or not isinstance(transaction.get('block_num'), int):
            return False
        if not transaction.get('block_time') or not isinstance(transaction.get('block_time'), str):
            return False
        if transaction.get('irreversible') is None or not isinstance(transaction.get('irreversible'), bool):
            return False
        if not transaction.get('action_trace') or not isinstance(transaction.get('action_trace'), dict):
            return False
        if (not transaction.get('action_trace').get('producer_block_id') or
                not isinstance(transaction.get('action_trace').get('producer_block_id'), str)):
            return False
        if (not transaction.get('action_trace').get('receiver') or
                not isinstance(transaction.get('action_trace').get('receiver'), str)):
            return False
        if (not transaction.get('action_trace').get('trx_id') or
                not isinstance(transaction.get('action_trace').get('trx_id'), str)):
            return False
        if (not transaction.get('action_trace').get('act') or
                not isinstance(transaction.get('action_trace').get('act'), dict)):
            return False
        if not cls.validate_transfer(transaction.get('action_trace').get('act')):
            return False
        if transaction.get('action_trace').get('receiver') != transaction.get('action_trace').get('act').get(
                'data').get('to'):
            return False
        return True


class EosGreymassResponseParser(ResponseParser):
    validator = EosGreymassResponseValidator
    symbol = 'EOS'
    currency = Currencies.eos
    precision = 4

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        transfer_txs: List[TransferTx] = []
        if cls.validator.validate_tx_details_response(tx_details_response):
            block_head = tx_details_response.get('last_irreversible_block')
            block_height = tx_details_response.get('block_num')
            confirmations = block_head - block_height
            date = parse_iso_date(tx_details_response.get('block_time') + 'Z')
            tx_hash = tx_details_response.get('id')
            transfers = tx_details_response.get('trx').get('trx').get('actions')
            for transfer in transfers:
                if cls.validator.validate_transfer(transfer):
                    from_address = transfer.get('data').get('from')
                    to_address = transfer.get('data').get('to')
                    value = parse_quantity(transfer.get('data').get('quantity'))
                    memo = transfer.get('data').get('memo') or ''
                    tx = TransferTx(
                        from_address=from_address,
                        to_address=to_address,
                        tx_hash=tx_hash,
                        value=value,
                        date=date,
                        block_height=block_height,
                        memo=memo,
                        confirmations=confirmations,
                        success=True,
                        symbol=cls.symbol

                    )
                    transfer_txs.append(tx)
        return transfer_txs

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        address_txs: List[TransferTx] = []
        if cls.validator.validate_address_txs_response(address_txs_response):
            block_head = address_txs_response.get('last_irreversible_block')
            transactions = address_txs_response.get('actions')
            for transaction in transactions:
                if cls.validator.validate_address_tx_transaction(transaction):
                    block_height = transaction.get('block_num')
                    date = parse_iso_date(transaction.get('block_time') + 'Z')
                    action_trace = transaction.get('action_trace')
                    tx_hash = action_trace.get('trx_id')
                    block_hash = action_trace.get('producer_block_id')
                    confirmations = block_head - block_height
                    data = action_trace.get('act').get('data')
                    from_address = data.get('from')
                    to_address = data.get('to')
                    value = parse_quantity(data.get('quantity'))
                    memo = data.get('memo') or ''
                    tx = TransferTx(
                        from_address=from_address,
                        to_address=to_address,
                        tx_hash=tx_hash,
                        value=value,
                        date=date,
                        block_height=block_height,
                        memo=memo,
                        confirmations=confirmations,
                        success=True,
                        symbol=cls.symbol,
                        block_hash=block_hash
                    )
                    address_txs.append(tx)

        return address_txs


class EosGreymassApi(GeneralApi):
    parser = EosGreymassResponseParser
    _base_url = 'https://eos.greymass.com'
    testnet_url = 'https://api.jungle.alohaeos.com'
    cache_key = 'eos'
    need_block_head_for_confirmation = False
    supported_requests = {
        'get_tx_details': '/v1/history/get_transaction?id={tx_hash}',
        'get_address_txs': '/v1/history/get_actions'
    }

    @classmethod
    def get_address_txs_body(cls, address):
        data = {
            'account_name': address,
            'offset': -40
        }
        return json.dumps(data)
