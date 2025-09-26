import json
import random
from decimal import Decimal
from typing import Any, List

from django.conf import settings

from exchange.blockchain.api.general.dtos import Balance, TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class GetBlockSolValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.001')
    valid_program_id = '11111111111111111111111111111111'
    precision = 9

    @classmethod
    def validate_general_response(cls, response: dict) -> bool:
        if not response:
            return False
        if not response.get('result'):
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response: dict) -> bool:
        if (cls.validate_general_response(balance_response)
                and balance_response.get('result').get('value')):
            return True
        return False

    @classmethod
    def validate_balances_response(cls, balances_response: dict) -> bool:
        if (cls.validate_general_response(balances_response)
                and balances_response.get('result').get('value')):
            return True
        return False

    @classmethod
    def validate_block_head_response(cls, block_head_response: dict) -> bool:
        if (cls.validate_general_response(block_head_response)
                and block_head_response.get('result').get('absoluteSlot')):
            return True
        return False

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: dict) -> bool:
        if (cls.validate_general_response(block_txs_response)
                and block_txs_response.get('result').get('transactions')):
            return True
        return False

    @classmethod
    def validate_transaction(cls, transaction: dict) -> bool:
        if transaction.get('meta').get('err') \
                or transaction.get('meta').get('status').get('Err') \
                or 'Ok' not in transaction.get('meta').get('status') \
                or not transaction.get('transaction').get('signatures'):  # not empty tx_hash
            return False
        return True

    @classmethod
    def validate_transfer(cls, transfer: dict) -> bool:
        if not any(transfer.get(key) for key in ('program', 'parsed', 'programId')):  # not empty main fields
            return False
        # Check the name and address of the transaction's program
        # If the program name is not "system" or the address
        # is not the valid address "11111111111111111111111111111111",
        # consider the transaction invalid.
        if (transfer.get('program') != 'system'
                or transfer.get('programId') != cls.valid_program_id
                or not transfer.get('parsed').get('info')
                or not transfer.get('parsed').get('info').get('source')
                or not transfer.get('parsed').get('info').get('destination')
                or transfer.get('parsed').get('info').get('source').casefold() ==
                transfer.get('parsed').get('info').get('destination').casefold()
                or not transfer.get('parsed').get('type')  # not empty type of tx
                or transfer.get('parsed').get('type') not in ['transfer', 'transferChecked']
                or BlockchainUtilsMixin.from_unit(transfer.get('parsed').get('info').get('lamports'),
                                                  precision=cls.precision) < cls.min_valid_tx_amount):
            return False
        return True


class GetBlockSolParser(ResponseParser):
    validator = GetBlockSolValidator
    symbol = 'SOL'
    currency = Currencies.sol
    precision = 9

    @classmethod
    def parse_balance_response(cls, balance_response: dict) -> Decimal:
        return BlockchainUtilsMixin.from_unit(balance_response.get('result').get('value'), precision=cls.precision) \
            if cls.validator.validate_balance_response(balance_response) else Decimal(0)

    @classmethod
    def parse_balances_response(cls, balances_response: dict) -> List[Balance]:
        if not cls.validator.validate_balances_response(balances_response):
            return []
        balances = []
        for balance in balances_response.get('result').get('value'):
            balances.append(
                Balance(
                    balance=BlockchainUtilsMixin.from_unit(balance.get('lamports'),
                                                           cls.precision) if balance else Decimal('0')
                )
            )
        return balances

    @classmethod
    def parse_block_head_response(cls, block_head_response: dict) -> Any:
        return block_head_response.get('result').get('absoluteSlot') \
            if cls.validator.validate_block_head_response(block_head_response) else None

    @classmethod
    def parse_block_txs_response(cls, block_txs_response: dict) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=None,
                block_hash=None,
                tx_hash=tx.get('transaction').get('signatures')[0],
                date=None,
                success=True,
                confirmations=None,
                from_address=transfer.get('parsed').get('info').get('source'),
                to_address=transfer.get('parsed').get('info').get('destination'),
                value=BlockchainUtilsMixin.from_unit(transfer.get('parsed').get('info').get('lamports'),
                                                     precision=cls.precision),
                symbol=cls.symbol,
                memo=None,
                tx_fee=None,
                token=None,
            )
            for tx in block_txs_response.get('result').get('transactions')
            if cls.validator.validate_transaction(tx)
            for transfer in tx.get('transaction').get('message').get('instructions')
            if cls.validator.validate_transfer(transfer)
        ] if cls.validator.validate_block_txs_response(block_txs_response) else []


class GetBlockSolApi(GeneralApi):
    parser = GetBlockSolParser
    _base_url = 'https://go.getblock.io/'
    symbol = 'SOL'
    cache_key = 'sol'
    rate_limit = 2  # 0.5 request per second
    SUPPORT_GET_BALANCE_BATCH = True
    GET_BALANCES_MAX_ADDRESS_NUM = 1000
    BALANCES_NOT_INCLUDE_ADDRESS = True
    supported_requests = {
        'get_balance': f'{random.choice(settings.SOL_GETBLOCK_APIKEY)}',
        'get_balances': f'{random.choice(settings.SOL_GETBLOCK_APIKEY)}',
        'get_block_head': f'{random.choice(settings.SOL_GETBLOCK_APIKEY)}',
        'get_block_txs': f'{random.choice(settings.SOL_GETBLOCK_APIKEY)}',
    }

    @classmethod
    def get_balance_body(cls, address: str) -> str:
        data = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'getBalance',
            'params': [address]
        }
        return json.dumps(data)

    @classmethod
    def get_balances_body(cls, addresses: List[str]) -> str:
        data = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'getMultipleAccounts',
            'params': [addresses]
        }
        return json.dumps(data)

    @classmethod
    def get_block_head_body(cls) -> str:
        data = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'getEpochInfo',
        }
        return json.dumps(data)

    @classmethod
    def get_block_txs_body(cls, block_height: int) -> str:
        data = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'getBlock',
            'params': [
                block_height,
                {'encoding': 'jsonParsed',
                 'maxSupportedTransactionVersion': 0,
                 'transactionDetails': 'full',
                 'rewards': False}
            ]
        }
        return json.dumps(data)
