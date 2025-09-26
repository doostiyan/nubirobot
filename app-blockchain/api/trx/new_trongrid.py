import random
from decimal import Decimal
from typing import Dict, List, Optional, Union

import base58
from django.conf import settings

from exchange.base.models import Currencies
from exchange.base.parsers import parse_utc_timestamp_ms
from exchange.blockchain.api.general.dtos import Balance, TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.contracts_conf import TRC20_contract_currency
from exchange.blockchain.utils import BlockchainUtilsMixin


class TrongridTronValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.001')
    precision = 6

    @classmethod
    def validate_general_response(cls, response: Dict[str, any]) -> bool:
        if not response:
            return False
        if not response.get('success'):
            return False
        if response.get('error'):
            return False
        if not response.get('data'):
            return False

        return True

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(balance_response):
            return False
        if not balance_response.get('data') or not isinstance(balance_response.get('data'), list):
            return False
        if not balance_response.get('data')[0].get('balance'):
            return False

        return True

    @classmethod
    def validate_token_balance_response(cls, token_balance_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(token_balance_response):
            return False
        if not token_balance_response.get('data') or not isinstance(token_balance_response.get('data'), list):
            return False
        if not token_balance_response.get('data')[0].get('trc20') or not isinstance(
                token_balance_response.get('data')[0].get('trc20'), list):
            return False

        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False

        return True

    @classmethod
    def validate_address_tx_transaction(cls, transaction: Dict[str, any]) -> bool:
        if not transaction.get('ret'):
            return False
        if transaction.get('ret')[0].get('contractRet') != 'SUCCESS':
            return False
        transfer_main_params = transaction.get('raw_data', {}).get('contract', [{}])[0]
        if not transfer_main_params:
            return False
        if not transfer_main_params.get('type'):
            return False
        if transfer_main_params.get('type') != 'TransferContract':
            return False
        if BlockchainUtilsMixin.from_unit(transfer_main_params.get('parameter').get('value').get('amount'),
                                          precision=cls.precision) <= cls.min_valid_tx_amount:
            return False
        if to_hex(transfer_main_params.get('parameter').get('value').get('owner_address')) in [
            'TM9RwJndZHmDVLSZcY6J76ci22AzPp2krj',
            'TVCAuYMw5afP96y5Wep866AXVWZJRH8fdo']:
            return False

        return True

    @classmethod
    def validate_token_transaction(cls,
                                   transaction: Dict[str, any],
                                   contract_info: Dict[str, Union[int, str]],
                                   _: str = '') -> bool:
        if transaction.get('type') != 'Transfer':
            return False
        if not transaction.get('token_info') or not isinstance(transaction.get('token_info'), dict):
            return False
        if not transaction.get('token_info').get('address'):
            return False
        if contract_info.get('address') != transaction.get('token_info').get('address'):
            return False
        if transaction.get('from') in ['TM9RwJndZHmDVLSZcY6J76ci22AzPp2krj', 'TVCAuYMw5afP96y5Wep866AXVWZJRH8fdo']:
            return False

        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: Dict[str, any]) -> bool:
        if not block_head_response:
            return False
        if not block_head_response.get('block_header'):
            return False
        if not block_head_response.get('block_header').get('raw_data'):
            return False
        if not block_head_response.get('block_header').get('raw_data').get('number'):
            return False

        return True


class TrongridTronParser(ResponseParser):
    validator = TrongridTronValidator
    symbol = 'TRX'
    precision = 6
    currency = Currencies.trx

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, any]) -> Balance:
        if not cls.validator.validate_balance_response(balance_response):
            return Balance(
                balance=Decimal('0'),
            )
        return Balance(
            balance=Decimal(
                BlockchainUtilsMixin.from_unit(balance_response.get('data')[0].get('balance'),
                                               precision=cls.precision)),
            address=to_hex(balance_response.get('data')[0].get('address')),
            symbol=cls.symbol
        )

    @classmethod
    def parse_token_balance_response(cls,
                                     balance_response: Dict[str, any],
                                     contract_info: Dict[str, Union[str, int]]) -> Balance:
        if cls.validator.validate_token_balance_response(balance_response):
            for coin in balance_response.get('data')[0].get('trc20'):
                contract = list(coin.keys())[0]
                if contract == contract_info.get('address'):
                    return Balance(
                        balance=Decimal(
                            BlockchainUtilsMixin.from_unit(int(coin.get(contract)), precision=cls.precision)),
                        address=to_hex(balance_response.get('data')[0].get('address')),
                        symbol=contract_info.get('symbol'),
                        token=contract_info.get('address')
                    )

        return Balance(
            balance=Decimal('0'),
            symbol=contract_info.get('symbol')
        )

    @classmethod
    def parse_address_txs_response(cls,
                                   _: str,
                                   address_txs_response: Dict[str, any],
                                   block_head: int) -> List[TransferTx]:
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return []

        address_txs: List[TransferTx] = []
        for tx in address_txs_response.get('data'):
            if cls.validator.validate_address_tx_transaction(tx):
                transfer_main_params = tx.get('raw_data', {}).get('contract', [{}])[0]

                address_tx = TransferTx(
                    block_height=tx.get('blockNumber'),
                    block_hash=None,
                    tx_hash=tx.get('txID'),
                    date=parse_utc_timestamp_ms(tx.get('block_timestamp')),
                    success=True,
                    confirmations=block_head - tx.get('blockNumber'),
                    from_address=to_hex(transfer_main_params.get('parameter').get('value', {}).get('owner_address')),
                    to_address=to_hex(transfer_main_params.get('parameter').get('value', {}).get('to_address')),
                    value=BlockchainUtilsMixin.from_unit(
                        transfer_main_params.get('parameter').get('value').get('amount'), precision=cls.precision),
                    symbol=cls.symbol
                )
                address_txs.append(address_tx)

        return address_txs

    @classmethod
    def parse_token_txs_response(cls,
                                 _: str,
                                 token_txs_response: Dict[str, any],
                                 __: int,
                                 contract_info: Dict[str, Union[str, int]],
                                 ___: str = '') -> List[TransferTx]:
        if not cls.validator.validate_address_txs_response(token_txs_response):
            return []
        address_txs: List[TransferTx] = []
        for tx in token_txs_response.get('data'):
            if not cls.validator.validate_token_transaction(tx, contract_info):
                continue
            currency = cls.contract_currency_list().get(tx.get('token_info', {}).get('address'))
            if not currency:
                continue

            address_tx = TransferTx(
                block_hash=None,
                tx_hash=tx.get('transaction_id'),
                date=parse_utc_timestamp_ms(tx.get('block_timestamp')),
                success=True,
                confirmations=1,
                from_address=tx.get('from'),
                to_address=tx.get('to'),
                value=BlockchainUtilsMixin.from_unit(
                    int(tx.get('value')), precision=contract_info.get('decimals')),
                symbol=contract_info.get('symbol'),
                token=tx.get('token_info').get('address')
            )
            address_txs.append(address_tx)

        return address_txs

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, any]) -> Optional[int]:
        if not cls.validator.validate_block_head_response(block_head_response):
            return None

        return block_head_response.get('block_header').get('raw_data').get('number')

    @classmethod
    def contract_currency_list(cls) -> Dict[str, int]:
        return TRC20_contract_currency.get(cls.network_mode)


class TrongridTronApi(GeneralApi):
    parser = TrongridTronParser
    _base_url = 'https://api.trongrid.io/'
    cache_key = 'trx'
    TRANSACTIONS_LIMIT = 30
    testnet_url = 'https://api.shasta.trongrid.io/'
    symbol = 'TRX'

    supported_requests = {
        'get_balance': 'v1/accounts/{address}?only_confirmed=true',
        'get_token_balance': 'v1/accounts/{address}?only_confirmed=true',
        'get_address_txs': 'v1/accounts/{address}/transactions?limit=' + str(
            TRANSACTIONS_LIMIT) + '&only_to=true&only_confirmed=true',
        'get_token_txs': 'v1/accounts/{address}/transactions/trc20?limit=' + str(
            TRANSACTIONS_LIMIT) + '&only_confirmed=true&contract_address={contract_address}',
        'get_block_head': 'walletsolidity/getblock'
    }

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.TRONGRID_APIKEYS)

    @classmethod
    def get_headers(cls) -> Dict[str, any]:
        return {
            'TRON-PRO-API-KEY': cls.get_api_key(),
        }


def to_hex(address: str) -> str:
    return base58.b58encode_check(bytes.fromhex(address)).decode('utf-8')
