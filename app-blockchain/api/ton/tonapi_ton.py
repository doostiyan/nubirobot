import datetime
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

import pytz
from django.conf import settings
from django.core.cache import cache

from exchange.base.models import Currencies
from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.api.general.utilities import Utilities
from exchange.blockchain.contracts_conf import ton_contract_currency, ton_contract_info
from exchange.blockchain.logger_util import logger
from exchange.blockchain.utils import BlockchainUtilsMixin

from .utils import TonAddressConvertor, TonHashConvertor, calculate_tx_confirmations


class TonApiValidator(ResponseValidator):
    min_valid_tx_amount = Decimal(0)

    @classmethod
    def validate_general_response(cls, response: Dict[str, Any]) -> bool:
        if response.get('error') is not None:
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(balance_response):
            return False
        if balance_response.get('balance') is None:
            return False
        return True

    @classmethod
    def validate_transfer(cls, transfer: Dict[str, Any]) -> bool:
        if transfer.get('is_scam'):
            return False
        if transfer.get('in_progress'):
            return False
        return True

    @classmethod
    def validate_token_tx_details_response(cls, token_tx_details_response: Dict[str, Any]) -> bool:
        return cls.validate_transfer(token_tx_details_response)

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        if not tx_details_response.get('success'):
            return False
        if tx_details_response and isinstance(tx_details_response, list):
            tx_details_response = tx_details_response[0]

        return cls.validate_transaction(tx_details_response)

    @classmethod
    def validate_token_transfer(cls, transfer: Dict[str, Any], contract_info: Dict[str, Union[str, int]]) -> bool:
        if transfer.get('type') != 'JettonTransfer':
            return False
        if transfer.get('status') != 'ok':
            return False
        if transfer.get('JettonTransfer', {}).get('jetton', {}).get('symbol') != contract_info.get('symbol'):
            return False
        if TonAddressConvertor.convert_hex_to_bounceable(
                transfer.get('JettonTransfer', {}).get('jetton', {}).get('address')[2:]) != contract_info.get(
            'address'):
            return False
        amount = BlockchainUtilsMixin.from_unit(int(transfer.get('JettonTransfer').get('amount')),
                                                contract_info.get('decimals'))
        if amount < Decimal('0.01'):
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if transaction is None:
            return False
        if not transaction.get('account'):
            return False

        compute_phase = transaction.get('compute_phase')
        if not compute_phase or not isinstance(compute_phase, dict):
            return False
        if not compute_phase.get('success') or compute_phase.get('exit_code') != 0:
            return False

        action_phase = transaction.get('action_phase')
        if not action_phase.get('success') or action_phase.get('result_code') != 0:
            return False

        if not transaction.get('in_msg') and not transaction.get('out_msgs'):
            return False
        if transaction.get('in_msg').get('source', {}).get('address') == transaction.get('in_msg').get('destination',
                                                                                                       {}).get(
            'address'):
            return False
        if not transaction.get('out_msgs'):
            if not transaction.get('in_msg').get('source', {}).get('address'):
                return False
            if not transaction.get('in_msg').get('destination', {}).get('address'):
                return False
        elif transaction.get('out_msgs'):
            if transaction.get('in_msg').get('source', {}).get('address'):
                return False
        return True

    @classmethod
    def validate_tx_details_transaction(cls, transaction: Dict[str, Any]) -> bool:
        contract_address = TonAddressConvertor.convert_hex_to_bounceable(
            transaction.get('JettonTransfer', {}).get('jetton', {}).get('address')[2:])
        currency = ton_contract_currency.get('mainnet').get(contract_address)
        if not currency:
            return False
        contract_info = ton_contract_info.get('mainnet').get(currency)
        return cls.validate_token_transfer(transaction, contract_info)

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Dict[str, Any]) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        if not isinstance(address_txs_response, dict):
            return False
        if not address_txs_response.get('transactions') or not isinstance(address_txs_response.get('transactions'),
                                                                          list):
            return False
        return True

    @classmethod
    def validate_address_tx_transaction(cls, transaction: Dict[str, Any]) -> bool:
        if not transaction:
            return False
        key2check = ['hash', 'account', 'success', 'utime', 'compute_phase', 'total_fees', 'in_msg', 'block', 'aborted',
                     'destroyed', 'out_msgs', 'action_phase']
        for key in key2check:
            if transaction.get(key) is None:
                return False
        if not transaction.get('success'):
            return False
        if transaction.get('account').get('is_scam'):
            return False
        if transaction.get('transaction_type') != 'TransOrd':
            return False
        if transaction.get('compute_phase').get('exit_code_description') != 'Ok':
            return False
        if transaction.get('compute_phase').get('exit_code') != 0:
            return False
        if not transaction.get('compute_phase').get('success'):
            return False
        if transaction.get('compute_phase').get('skipped'):
            return False
        if not transaction.get('action_phase').get('success'):
            return False
        if transaction.get('action_phase').get('result_code') != 0:
            return False
        if transaction.get('aborted'):
            return False
        if transaction.get('destroyed'):
            return False
        if not transaction.get('out_msgs'):
            if not transaction.get('in_msg').get('source', {}).get('address'):
                return False
            if not transaction.get('in_msg').get('destination', {}).get('address'):
                return False
            # Checks if the transaction is not related to fee payment
            if transaction.get('in_msg').get('op_code') != '0x00000000':
                return False
        elif transaction.get('out_msgs'):
            if transaction.get('in_msg').get('source', {}).get('address'):
                return False
        return True


class TonApiResponseParser(ResponseParser):
    validator = TonApiValidator
    symbol = 'TON'
    currency = Currencies.ton
    precision = 9
    average_block_time = 5

    @classmethod
    def _get_memo(cls, transaction: Dict[str, Any]) -> Optional[str]:
        try:
            return transaction['in_msg']['decoded_body']['text']
        except Exception:
            return None

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, Any]) -> Decimal:
        if not cls.validator.validate_balance_response(balance_response):
            return Decimal(0)

        return Decimal(BlockchainUtilsMixin.from_unit((int(balance_response.get('balance'))), precision=cls.precision))

    @classmethod
    def get_user_friendly_address(cls, address: Optional[str]) -> str:
        if not address:
            return None
        try:
            converted_address = TonAddressConvertor.convert_hex_to_bounceable(address[2:])
        except Exception:
            return address
        return converted_address

    @classmethod
    def parse_token_txs_response(cls,
                                 address: str,
                                 token_txs_response: Dict[str, Any],
                                 block_head: int,
                                 contract_info: Dict[str, Union[str, int]],
                                 direction: str = '') -> List[TransferTx]:
        if direction == 'outgoing':
            return cls.parse_withdraw_token_txs_response(address, token_txs_response, block_head, contract_info)
        transfers: List[TransferTx] = []
        for event in token_txs_response.get('events', []):
            if not cls.validator.validate_transfer(event):
                continue
            events: List[TransferTx] = []
            for transfer in event.get('actions', []):
                if not cls.validator.validate_token_transfer(transfer, contract_info):
                    continue
                action = TransferTx(
                    block_height=0,
                    block_hash=None,
                    tx_hash=event.get('event_id'),
                    date=parse_utc_timestamp(event.get('timestamp')),
                    success=True,
                    confirmations=calculate_tx_confirmations(cls.average_block_time, event.get('timestamp')),
                    from_address=TonAddressConvertor.convert_hex_to_bounceable(
                        transfer.get('JettonTransfer').get('sender').get('address')[2:]),
                    to_address=TonAddressConvertor.convert_hex_to_bounceable(
                        transfer.get('JettonTransfer').get('recipient').get('address')[2:]),
                    value=BlockchainUtilsMixin.from_unit(int(transfer.get('JettonTransfer').get('amount')),
                                                         contract_info.get('decimals')),
                    symbol=contract_info.get('symbol'),
                    memo=transfer.get('JettonTransfer', {}).get('comment'),
                )
                for tx in events:
                    if tx.memo and tx.memo == action.memo and tx.symbol == action.symbol:
                        tx.value += action.value
                        break
                else:
                    events.append(action)

            transfers.extend(events)
        return transfers

    @classmethod
    def parse_withdraw_token_txs_response(cls,
                                          address: str,
                                          token_txs_response: Dict[str, Any],
                                          _: Optional[int],
                                          contract_info: Dict[str, Union[str, int]]) -> List[TransferTx]:
        transfers = []
        for event in token_txs_response.get('events', []):
            if not cls.validator.validate_transfer(event):
                continue
            withdraws = {}
            for transfer in event.get('actions', []):
                if not cls.validator.validate_token_transfer(transfer, contract_info):
                    continue
                from_address = TonAddressConvertor.convert_hex_to_bounceable(
                    transfer.get('JettonTransfer').get('sender').get('address')[2:])
                amount = BlockchainUtilsMixin.from_unit(int(transfer.get('JettonTransfer').get('amount')),
                                                        contract_info.get('decimals'))
                if from_address != address:
                    continue
                if withdraws.get(from_address):
                    withdraws[from_address] += amount
                else:
                    withdraws[from_address] = amount

            for from_address, amount in withdraws.items():
                transfers.append(
                    TransferTx(
                        block_height=0,
                        block_hash=None,
                        tx_hash=event.get('event_id'),
                        date=parse_utc_timestamp(event.get('timestamp')),
                        success=True,
                        confirmations=calculate_tx_confirmations(cls.average_block_time, event.get('timestamp')),
                        from_address=from_address,
                        to_address='',
                        value=amount,
                        symbol=contract_info.get('symbol'),
                        token=contract_info.get('address')
                    )
                )

        return transfers

    @classmethod
    def parse_token_tx_details_response(cls,
                                        token_tx_details_response: Dict[str, Any],
                                        _: Optional[int]) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        if not cls.validator.validate_token_tx_details_response(token_tx_details_response):
            return []
        for transfer in token_tx_details_response.get('actions', []):
            contract_address = TonAddressConvertor.convert_hex_to_bounceable(
                transfer.get('JettonTransfer', {}).get('jetton', {}).get('address')[2:])
            currency = ton_contract_currency.get('mainnet').get(contract_address)
            if not currency:
                continue
            contract_info = ton_contract_info.get('mainnet').get(currency)
            if not cls.validator.validate_token_transfer(transfer,
                                                         contract_info):
                continue
            event = TransferTx(
                block_height=0,
                block_hash=None,
                tx_hash=token_tx_details_response.get('event_id'),
                date=parse_utc_timestamp(token_tx_details_response.get('timestamp')),
                success=True,
                confirmations=calculate_tx_confirmations(cls.average_block_time,
                                                         token_tx_details_response.get('timestamp')),
                from_address=TonAddressConvertor.convert_hex_to_bounceable(
                    transfer.get('JettonTransfer').get('sender').get('address')[2:]),
                to_address=TonAddressConvertor.convert_hex_to_bounceable(
                    transfer.get('JettonTransfer').get('recipient').get('address')[2:]),
                value=BlockchainUtilsMixin.from_unit(int(transfer.get('JettonTransfer').get('amount')),
                                                     contract_info.get('decimals')),
                symbol=contract_info.get('symbol'),
                memo=transfer.get('JettonTransfer', {}).get('comment'),
            )
            for tx in transfers:
                if tx.memo and tx.memo == event.memo and tx.symbol == event.symbol:
                    tx.value += event.value
                    break
            else:
                transfers.append(event)

        return transfers

    @classmethod
    def parse_tx_details_response(cls,
                                  tx_details_response: Union[List[Dict[str, Any]], Dict[str, Any]],
                                  _: Optional[int]) -> List[TransferTx]:
        if cls.validator.validate_tx_details_response(tx_details_response):
            if isinstance(tx_details_response, list):
                tx_details_response = tx_details_response[0]

            memo = None
            block_height = None
            block_pattern = re.compile(r'\d+')
            if ((block := tx_details_response.get('block', '').split(',')[-1])
                    and (block_height := re.findall(block_pattern, block)[0])):
                block_height = int(block_height)

            if not tx_details_response.get('in_msg').get('source', {}).get('address'):
                from_address = cls.get_user_friendly_address(
                    tx_details_response.get('out_msgs')[0].get('source', {}).get('address'))
                to_address = cls.get_user_friendly_address(
                    tx_details_response.get('out_msgs')[0].get('destination', {}).get('address'))
                amount = BlockchainUtilsMixin.from_unit((int(tx_details_response.get('out_msgs')[0].get('value'))),
                                                        precision=cls.precision)
            else:
                from_address = cls.get_user_friendly_address(
                    tx_details_response.get('in_msg').get('source', {}).get('address'))
                to_address = cls.get_user_friendly_address(
                    tx_details_response.get('in_msg').get('destination', {}).get('address'))
                amount = BlockchainUtilsMixin.from_unit((int(tx_details_response.get('in_msg').get('value'))),
                                                        precision=cls.precision)
                memo = cls._get_memo(tx_details_response)

            confirmations = calculate_tx_confirmations(cls.average_block_time, tx_details_response.get('utime'))
            base64_tx_hash = Utilities.normalize_hash(
                network='TON',
                currency=None,
                tx_hashes=[tx_details_response.get('hash')]
            )
            return [TransferTx(
                block_height=block_height,
                block_hash=None,
                tx_hash=base64_tx_hash[0],
                date=parse_utc_timestamp(tx_details_response.get('utime')),
                success=True,
                confirmations=confirmations,
                from_address=from_address,
                to_address=to_address,
                value=amount,
                symbol=cls.symbol,
                memo=memo,
                tx_fee=None,
            )]
        return []

    @classmethod
    def parse_address_txs_response(cls,
                                   _: str,
                                   address_txs_response: Dict[str, Any],
                                   __: Optional[int]) -> List[TransferTx]:
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return []
        transfers: List[TransferTx] = []
        for tx in address_txs_response.get('transactions'):
            if cls.validator.validate_address_tx_transaction(tx):
                block_height = None
                block_pattern = re.compile(r'\d+')
                if ((block := tx.get('block', '').split(',')[-1])
                        and (block_height := re.findall(block_pattern, block)[0])):
                    block_height = int(block_height)

                if not tx.get('in_msg').get('source', {}).get('address'):
                    from_address = cls.get_user_friendly_address(
                        tx.get('out_msgs')[0].get('source', {}).get('address'))
                    to_address = cls.get_user_friendly_address(
                        tx.get('out_msgs')[0].get('destination', {}).get('address'))
                    amount = BlockchainUtilsMixin.from_unit((int(tx.get('out_msgs')[0].get('value'))),
                                                            precision=cls.precision)
                    tx_hash = tx.get('in_msg').get('hash')
                    try:
                        memo = tx.get('in_msg').get('decoded_body').get('payload')[0].get('message').get(
                            'message_internal').get('body').get('value').get('value').get('text')
                    except Exception:
                        memo = None
                else:
                    from_address = cls.get_user_friendly_address(
                        tx.get('in_msg').get('source', {}).get('address'))
                    to_address = cls.get_user_friendly_address(
                        tx.get('in_msg').get('destination', {}).get('address'))
                    amount = BlockchainUtilsMixin.from_unit((int(tx.get('in_msg').get('value'))), cls.precision)
                    memo = cls._get_memo(tx)
                    tx_hash = TonHashConvertor.ton_convert_hash(tx.get('hash'), output_format='base64')

                confirmations = calculate_tx_confirmations(cls.average_block_time, tx.get('utime'))

                transfers.append(TransferTx(
                    block_height=block_height,
                    tx_hash=tx_hash,
                    date=parse_utc_timestamp(tx.get('utime')),
                    success=True,
                    confirmations=confirmations,
                    from_address=from_address,
                    to_address=to_address,
                    value=amount,
                    symbol=cls.symbol,
                    memo=memo,
                ))
        return transfers

    @classmethod
    def parse_tx_withdraw_hash(cls, response: Dict[str, Any]) -> str:
        return response.get('in_msg', {}).get('hash') or ''


class TonApi(GeneralApi):
    parser = TonApiResponseParser
    _base_url = 'https://tonapi.io/'
    cache_key = 'ton'
    need_block_head_for_confirmation = False
    timeout = 90
    GET_ADDRESS_TXS_HOUR_OFFSET = 5
    request_reliability = 6
    reliability_need_status_codes = [500]
    supported_requests = {
        'get_balance': 'v2/accounts/{address}',
        'get_address_txs': '/v2/blockchain/accounts/{address}/transactions?limit=999',
        'get_address_txs_lt': '/v2/blockchain/accounts/{address}/transactions?limit=999&before_lt={lt}',
        'get_token_txs': 'v2/accounts/{address}/jettons/{contract_address}/history?'
                         'limit=900&end_date={end_date}&start_date={start_date}',
        'get_token_txs_lt': 'v2/accounts/{address}/jettons/{contract_address}/history?limit=999&before_lt={lt}',
        'get_token_tx_details': 'v2/events/{tx_hash}/jettons',
        'get_tx_details': 'v2/blockchain/transactions/{tx_hash}',
    }

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {
            'User-Agent': 'Mozilla/5.0',
            'Authorization': 'Bearer ' + settings.TON_API_APIKEY
        }

    @classmethod
    def get_tx_details(cls, tx_hash: str) -> Any:
        tx_hash = Utilities.normalize_hash(
            network='TON',
            currency=None,
            tx_hashes=[tx_hash],
            output_format='hex'
        )[0]
        return super().get_tx_details(tx_hash)

    @classmethod
    def get_withdraw_hash(cls, tx_hash: str) -> Any:
        return cls.request(request_method='get_tx_details', body=cls.get_tx_details_body(tx_hash),
                           headers=cls.get_headers(), tx_hash=tx_hash)

    def get_token_txs(self, address: str, contract_info: Dict[str, Union[str, int]], direction: str = '',
                      start_date: Optional[int] = None, end_date: Optional[int] = None) -> Dict[str, list]:
        if start_date and end_date:
            return self.get_token_txs_time(address, contract_info, direction, start_date, end_date)
        is_retry = cache.get(f'{settings.BLOCKCHAIN_CACHE_PREFIX}token_txs_retry')
        if is_retry:
            cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}token_txs_retry', value=False)
            start_date = cache.get(f'{settings.BLOCKCHAIN_CACHE_PREFIX}token_txs_start_date')
            end_date = cache.get(f'{settings.BLOCKCHAIN_CACHE_PREFIX}token_txs_end_date')
            return self.get_token_txs_by_time_with_retry(address, contract_info, start_date, end_date)
        return self.get_token_txs_original(address, contract_info, direction)

    @classmethod
    def get_token_txs_original(cls,
                               address: str,
                               contract_info: Dict[str, Union[str, int]],
                               _: str = '') -> Dict[str, list]:
        txs = []
        response = None
        now = pytz.timezone('UTC').localize(datetime.datetime.utcnow())
        end_date = int((now - datetime.timedelta(minutes=1)).timestamp())
        start_date = int((now - datetime.timedelta(hours=cls.GET_ADDRESS_TXS_HOUR_OFFSET)).timestamp())
        while True:
            end_date = response['events'][-1]['timestamp'] if response and response['events'] else end_date
            try:
                response = cls.request(request_method='get_token_txs',
                                       body=cls.get_token_txs_body(address, contract_info),
                                       headers=cls.get_headers(), address=address,
                                       contract_address=contract_info.get('address'),
                                       end_date=end_date,
                                       start_date=start_date,
                                       apikey=cls.get_api_key(), timeout=cls.timeout)
            except Exception:
                break
            txs += response.get('events', [])
            if not response['events'] or response['events'][-1]['timestamp'] < start_date:
                break

        return {'events': txs}

    @classmethod
    def get_token_txs_time(cls,
                           address: str,
                           contract_info: Dict[str, Union[str, int]],
                           _: str = '',
                           start_date: int = 1727343000,
                           end_date: int = 1727364600) -> Dict[str, list]:
        txs = []
        response = None
        while True:
            end_date = response['events'][-1]['timestamp'] if response and response['events'] else end_date
            try:
                for _ in range(10):
                    response = cls.request(request_method='get_token_txs',
                                           body=cls.get_token_txs_body(address, contract_info),
                                           headers=cls.get_headers(), address=address,
                                           contract_address=contract_info.get('address'),
                                           end_date=end_date,
                                           start_date=start_date,
                                           apikey=cls.get_api_key(), timeout=cls.timeout)
                    if response.get('events', []):
                        break
            except Exception:
                break
            txs += response.get('events', [])
            if not response['events'] or response['events'][-1]['timestamp'] < start_date:
                break
        return {'events': txs}

    @classmethod
    def get_token_txs_lt(cls,
                         address: str,
                         contract_info: Dict[str, Union[str, int]],
                         _: str = '',
                         lt: int = 49477351000002,
                         start_date: int = 1727382600) -> Dict[str, list]:
        txs = []
        response = None
        while True:
            events_exists_count = 0
            events_exists_limit = 5
            lt = response['next_from'] + 7000000 if response else lt
            unique_txs = []
            try:
                for _ in range(30):
                    response = cls.request(request_method='get_token_txs_lt',
                                           body=cls.get_token_txs_body(address, contract_info),
                                           headers=cls.get_headers(), address=address,
                                           contract_address=contract_info.get('address'),
                                           lt=lt,
                                           apikey=cls.get_api_key(), timeout=cls.timeout)
                    if response.get('events', []):
                        events_exists_count += 1
                        if not unique_txs:
                            unique_txs += response.get('events', [])
                        else:
                            for event in response.get('events'):
                                if event not in unique_txs:
                                    unique_txs.append(event)
                        if events_exists_count >= events_exists_limit:
                            break
            except Exception:
                break
            txs += unique_txs
            if not unique_txs or unique_txs[-1]['timestamp'] < start_date:
                break

        return {'events': txs}

    @classmethod
    def get_token_txs_by_time_with_retry(cls, address: str,
                                         contract_info: Dict[str, Union[int, str]],
                                         start_date: int,
                                         end_date: int) -> Dict[str, list]:
        start_date_str = datetime.datetime.fromtimestamp(start_date).strftime('%Y-%m-%d %H:%M:%S')
        end_date_str = datetime.datetime.fromtimestamp(end_date).strftime('%Y-%m-%d %H:%M:%S')
        logger.info('Getting txs from %s to %s', end_date_str, start_date_str)
        j = 0
        unique_txs = []
        previous_end_date = None
        while True:
            events_exists_count = 0
            events_exists_limit = 5

            if unique_txs and previous_end_date:
                end_date = int((unique_txs[-1]['timestamp'] + previous_end_date) / 2)

            if end_date == previous_end_date:
                end_date -= 1
            end_date_str = datetime.datetime.fromtimestamp(end_date).strftime('%Y-%m-%d %H:%M:%S')
            previous_end_date = end_date
            logger.info('Round %d, end_date: %s', j + 1, end_date_str)

            events = []
            for _ in range(20):
                number_of_new_items_found = 0
                try:
                    response = cls.request(request_method='get_token_txs',
                                           body=cls.get_token_txs_body(address, contract_info),
                                           headers=cls.get_headers(),
                                           address=address,
                                           contract_address=contract_info.get('address'),
                                           end_date=end_date,
                                           start_date=start_date,
                                           apikey=cls.get_api_key(),
                                           timeout=cls.timeout)
                    events = response.get('events', [])
                    if events:
                        logger.info('Length of events is: %d', len(events))
                        events_exists_count += 1
                        if not unique_txs:
                            unique_txs += events
                        else:
                            for event in response.get('events'):
                                if event not in unique_txs:
                                    number_of_new_items_found += 1
                                    unique_txs.append(event)
                            logger.info('Number of new items found: %d', number_of_new_items_found)
                        logger.info('Length of unique_txs: %d', {len(unique_txs)})
                        if events_exists_count >= events_exists_limit:
                            break
                    else:
                        logger.info('Response is empty')
                except Exception as e:
                    logger.info('Exception handled: %s', e)
            j += 1
            unique_txs = sorted(unique_txs, key=lambda tx: tx['timestamp'], reverse=True)
            if not events or unique_txs[-1]['timestamp'] < start_date:
                break
        return {'events': unique_txs}

    @classmethod
    def get_address_txs(cls, address: str, **kwargs: Any) -> Dict[str, Any]:
        txs = []
        response = None
        after_lt = None

        while True:
            before_lt = response['transactions'][-1]['lt'] if response and response['transactions'] else None
            try:
                if before_lt:
                    response = cls.request(request_method='get_address_txs_lt', body=cls.get_address_txs_body(address),
                                           headers=cls.get_headers(),
                                           apikey=cls.get_api_key(), timeout=cls.timeout, address=address, lt=before_lt)
                else:
                    response = cls.request(request_method='get_address_txs', body=cls.get_address_txs_body(address),
                                           headers=cls.get_headers(),
                                           apikey=cls.get_api_key(), timeout=cls.timeout, address=address)
            except Exception:
                break
            txs += response.get('transactions', [])

            if not after_lt or not response['transactions'] or response['transactions'][-1]['lt'] < after_lt:
                break

        return {'transactions': txs}
