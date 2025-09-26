from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import List, Union

import pytz
from exchange.base.models import Currencies

from .logging import logger


def convert_tx_details_to_dict(tx_details: dict, result) -> dict:
    if not tx_details:
        return {'success': False}

    value = tx_details.get('value')
    transfer = {
        'symbol': tx_details.get('symbol'),
        'currency': _symbol_to_currency(tx_details.get('symbol')),
        'from': tx_details.get('from_address'),
        'to': tx_details.get('to_address'),
        'value': _decimal(value),
        'is_valid': True,
        'token': tx_details['token'],
        'memo': tx_details['memo']
    }

    if result is not None:
        result.get('transfers').append(transfer)
        return result

    return {
        'transfers': [transfer],
        'inputs': [],
        'outputs': [],
        'hash': tx_details['tx_hash'],
        'success': tx_details['success'],
        'block': tx_details['block_height'],
        'memo': tx_details['memo'],
        'fees': _decimal(tx_details['tx_fee']),
        'date': _utc_datetime(tx_details['date']),
        'confirmations': tx_details['confirmations']
    }


def convert_utxo_based_tx_details_to_dict(tx_details: dict, result) -> dict:
    if not tx_details:
        return {'success': False}
    inputs = None
    outputs = None
    data = {
        'currency': _symbol_to_currency(tx_details.get('symbol')),
        'value': _decimal(tx_details.get('value')),
        'is_valid': tx_details.get('success')
    }
    if tx_details.get('from_address'):
        inputs = {**data, 'address': tx_details.get('from_address')}
    elif tx_details.get('to_address'):
        outputs = {**data, 'address': tx_details.get('to_address')}

    if result is not None:
        if inputs:
            result.get('inputs').append(inputs)
        elif outputs:
            result.get('outputs').append(outputs)
        return result

    date = datetime.strptime(tx_details['date'], "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)

    return {
        'hash': tx_details['tx_hash'],
        'success': tx_details['success'],
        'inputs': [inputs] if inputs else [],
        'outputs': [outputs] if outputs else [],
        'transfers': [],
        'block': tx_details['block_height'],
        'memo': tx_details['memo'],
        'fees': _decimal(tx_details['tx_fee']),
        'date': date,
        'confirmations': tx_details['confirmations']
    }


def convert_block_tx_info(blocks_txs, include_inputs=False, include_info=False):
    transactions_info = {'outgoing_txs': defaultdict(lambda: defaultdict(list)),
                         'incoming_txs': defaultdict(lambda: defaultdict(list))}
    if include_info:
        for block_tx in blocks_txs:
            currency = _symbol_to_currency(block_tx.get('symbol'))
            if include_inputs and block_tx.get('from_address'):
                transactions_info['outgoing_txs'][block_tx.get('from_address')][currency].append({
                    'tx_hash': block_tx.get('tx_hash'),
                    'value': _decimal(block_tx.get('value')),
                    'contract_address': block_tx.get('token'),
                    'block_height': block_tx.get('block_height'),
                    'symbol': block_tx.get('symbol')
                })
            if block_tx.get('to_address'):
                transactions_info['incoming_txs'][block_tx.get('to_address')][currency].append({
                    'tx_hash': block_tx.get('tx_hash'),
                    'value': _decimal(block_tx.get('value')),
                    'contract_address': block_tx.get('token'),
                    'block_height': block_tx.get('block_height'),
                    'symbol': block_tx.get('symbol')
                })
    return transactions_info


def convert_block_addresses(blocks_txs, include_inputs=False):
    transactions_addresses = {'input_addresses': set(), 'output_addresses': set()}
    for block_tx in blocks_txs:
        if include_inputs and block_tx.get('from_address'):
            transactions_addresses['input_addresses'].add(block_tx.get('from_address'))
        if block_tx.get('to_address'):
            transactions_addresses['output_addresses'].add(block_tx.get('to_address'))
    return transactions_addresses


def convert_transfer_tx_to_transaction(transfer_tx: dict):
    from_address = [transfer_tx.get('from_address')] if transfer_tx.get('from_address') else []
    return {
        'contract_address': transfer_tx.get('token'),
        'from_address': from_address,
        'hash': transfer_tx.get('tx_hash'),
        'block': transfer_tx.get('block_height'),
        'timestamp': _utc_datetime(transfer_tx.get('date')),
        'value': _decimal(transfer_tx.get('value')),
        'confirmations': transfer_tx.get('confirmations'),
        'tag': transfer_tx.get('memo'),
    }


def get_symbol_from_currency_code(currency_code):
    for k, v in Currencies._identifier_map.items():
        if v == currency_code:
            return k.lower()
    return None


def _symbol_to_currency(symbol):
    for k, v in Currencies._identifier_map.items():
        if k.lower() == symbol.lower():
            return v
    return None


def convert_all_wallet_balances_to_decimal(wallet_balances: List[dict]) -> List[dict]:
    for wb in wallet_balances:
        for key, value in wb.items():
            if key == 'balance':
                wb[key] = _decimal(value)
    return wallet_balances


def are_transaction_objects_equal(obj_list_f: list, obj_list_s: list) -> bool:
    attributes_to_compare = ['block', 'from_address', 'tag', 'contract_address', 'value', 'timestamp']
    obj_list_f = sorted(obj_list_f, key=lambda be: be.hash)
    obj_list_s = sorted(obj_list_s, key=lambda be: be.hash)
    try:
        is_length_equal = len(obj_list_s) == len(obj_list_f)
    except:
        is_length_equal = False

    for obj_f in obj_list_f:
        for obj_s in obj_list_s:
            if obj_f.hash != obj_s.hash:
                continue
            # Sort the from_address lists before comparison
            obj_f.from_address.sort()
            obj_s.from_address.sort()

            for attr in attributes_to_compare:
                if getattr(obj_f, attr) != getattr(obj_s, attr):
                    logger.warning(
                        f"'{attr}' of transactions are not equal: {getattr(obj_f, attr)} != {getattr(obj_s, attr)} for tx {obj_f.hash}")
                    return False
            break

    obj_list_f_hashes = set([obj.hash for obj in obj_list_f])
    obj_list_s_hashes = set([obj.hash for obj in obj_list_s])
    diff_f_s = obj_list_f_hashes - obj_list_s_hashes
    diff_s_f = obj_list_s_hashes - obj_list_f_hashes
    if not is_length_equal:
        logger.warning(
            f"The length of submodule and standalone are not equal, {len(obj_list_f_hashes)} != {len(obj_list_s_hashes)}, diff_f_s: {diff_f_s}, diff_s_f={diff_s_f}")
        return False
    return True


def _decimal(value: str) -> Union[Decimal, None]:
    if not value:
        return None
    return Decimal('0') if float(value) == 0 else Decimal(value)


def _utc_datetime(datetime_str: str) -> Union[datetime, None]:
    if not datetime_str:
        return None

    datetime_str = datetime_str.replace('Z', '+00:00')  # Convert 'Z' to '+00:00'
    return datetime.fromisoformat(datetime_str).astimezone(pytz.utc)
