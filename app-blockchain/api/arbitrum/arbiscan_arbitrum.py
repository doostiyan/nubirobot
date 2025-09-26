import random
from decimal import Decimal
from typing import List

from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin


class ArbiscanArbitrumResponseValidator(ResponseValidator):
    min_valid_tx_amount = Decimal(0)
    valid_method_id = '0x'

    @classmethod
    def validate_general_response(cls, response):
        if response.get('status') != '1':
            return False
        if response.get('message') != 'OK':
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        if address_txs_response.get('result') is None or \
                len(address_txs_response.get('result')) == 0:
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction) -> bool:
        if transaction is None:
            return False
        if transaction.get('isError') != '0':
            return False
        if transaction.get('methodId') != cls.valid_method_id:
            return False
        if transaction.get('functionName') != '':
            return False
        if Decimal(transaction.get('value')) <= cls.min_valid_tx_amount:
            return False
        if transaction.get('from') == transaction.get('to'):
            return False
        if transaction.get('from') in cls.invalid_from_addresses_for_ETH_like:
            return False
        if transaction.get('txreceipt_status') != '1':
            return False
        return True

    @classmethod
    def validate_token_transaction(cls, transaction, contract_info) -> bool:
        if transaction is None:
            return False
        if Decimal(transaction.get('value')) == 0:
            return False
        if transaction.get('from') == transaction.get('to'):
            return False
        if transaction.get('from') in cls.invalid_from_addresses_for_ETH_like:
            return False
        if transaction.get('contractAddress') != contract_info.get('address'):
            return False
        return True


class ArbiscanArbitrumResponseParser(ResponseParser):
    validator = ArbiscanArbitrumResponseValidator
    precision = 18
    symbol = 'ETH'
    currency = Currencies.eth

    @classmethod
    def parse_balance_response(cls, balance_response) -> Decimal:
        if not cls.validator.validate_general_response(balance_response):
            return Decimal(0)
        return BlockchainUtilsMixin.from_unit(int(balance_response.get('result')), precision=cls.precision)

    @classmethod
    def parse_token_balance_response(cls, balance_response, contract_info) -> Decimal:
        if not cls.validator.validate_general_response(balance_response):
            return Decimal(0)
        return BlockchainUtilsMixin.from_unit(int(balance_response.get('result')),
                                              precision=contract_info.get('decimals'))

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return []
        transactions = address_txs_response.get('result')
        address_txs: List[TransferTx] = []
        for transaction in transactions:
            if cls.validator.validate_transaction(transaction):
                address_tx = cls.get_address_tx_from_transaction_data(transaction, cls.precision)
                address_txs.append(address_tx)
        return address_txs

    @classmethod
    def parse_token_txs_response(cls, address, token_txs_response, block_head, contract_info, direction='') -> List[TransferTx]:
        if not cls.validator.validate_address_txs_response(token_txs_response):
            return []
        transactions = token_txs_response.get('result')
        token_txs: List[TransferTx] = []
        for transaction in transactions:
            if cls.validator.validate_token_transaction(transaction, contract_info):
                token_tx = cls.get_address_tx_from_transaction_data(transaction,
                                                                    contract_info.get('decimals'),
                                                                    contract_info.get('address'))
                token_txs.append(token_tx)
        return token_txs

    @classmethod
    def get_address_tx_from_transaction_data(cls, tx_data, precision, contract_address=None):
        confirmations = int(tx_data.get('confirmations'))
        return TransferTx(
            block_height=int(tx_data.get('blockNumber')),
            tx_hash=tx_data.get('hash'),
            date=parse_utc_timestamp(int(tx_data.get('timeStamp'))),
            success=True,
            confirmations=confirmations,
            from_address=tx_data.get('from'),
            to_address=tx_data.get('to'),
            value=BlockchainUtilsMixin.from_unit(int(tx_data.get('value')), precision=precision),
            symbol=cls.symbol,
            token=contract_address,
        )


class ArbiscanArbitrumApi(GeneralApi):
    parser = ArbiscanArbitrumResponseParser
    _base_url = 'https://api.arbiscan.io/api'
    cache_key = 'arb'
    symbol = 'ETH'
    need_block_head_for_confirmation = False
    instance = None

    supported_requests = {
        'get_balance': '?module=account&action=balance&address={address}&tag=latest&apikey={apikey}',
        'get_token_balance': '?module=account&action=tokenbalance&contractaddress={contract_address}&address={address}&tag=latest&apikey={apikey}',
        'get_address_txs': '?module=account&action=txlist&address={address}&startblock=100000000&endblock=latest&page=1&offset=25&sort=desc&apikey={apikey}',
        'get_token_txs': '?module=account&action=tokentx&contractaddress={contract_address}&address={address}&startblock=100000000&endblock=latest&page=1&offset=25&sort=desc&apikey={apikey}'
    }

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.ARBITRUM_ARBISCAN_API_KEY)
