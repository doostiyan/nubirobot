import random
from decimal import Decimal
from typing import List, Optional

from django.conf import settings

from exchange.base.parsers import parse_timestamp
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import APIError, BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class SolScanValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.001')
    valid_program_id = '11111111111111111111111111111111'
    precision = 9

    @classmethod
    def validate_general_response(cls, response: dict) -> bool:
        if not response:
            return False
        if isinstance(response, dict) and 'error' in response:
            raise APIError('[SolScanAPI][ValidateGeneralResponse]' + response.get('error').get('message'))
        return True

    @classmethod
    def validate_balance_response(cls, balance_response: dict) -> bool:
        if cls.validate_general_response(balance_response) and balance_response.get('lamports'):
            return True
        return False

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: dict) -> bool:
        if (cls.validate_general_response(tx_details_response)
                and tx_details_response.get('solTransfers')
                and tx_details_response.get('status') == 'Success'
                and tx_details_response.get('txHash')):
            return True
        return False

    @classmethod
    def validate_transaction(cls, transaction: dict) -> bool:
        if 'amount' in transaction:  # check value of tx_details
            if BlockchainUtilsMixin.from_unit(int(transaction.get('amount')), cls.precision) < cls.min_valid_tx_amount:
                return False
        elif 'lamport' in transaction:  # check value of address_txs
            if BlockchainUtilsMixin.from_unit(int(transaction.get('lamport')), cls.precision) < cls.min_valid_tx_amount:
                return False
            if transaction.get('status') != 'Success':  # check status of address_txs
                return False
        else:
            return False

        # check from_address != to_address based on tx_details or address_txs response
        if 'source' in transaction:
            if transaction.get('source') == transaction.get('destination'):
                return False
        elif 'src' in transaction:
            if transaction.get('src') == transaction.get('dst'):
                return False
        else:
            return False

        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: dict) -> bool:
        if cls.validate_general_response(block_head_response) and block_head_response.get('absoluteSlot'):
            return True
        return False

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: dict) -> bool:
        if cls.validate_general_response(address_txs_response) and address_txs_response.get('data'):
            return True
        return False


class SolScanParser(ResponseParser):
    validator = SolScanValidator
    symbol = 'SOL'
    currency = Currencies.sol
    precision = 9

    @classmethod
    def parse_balance_response(cls, balance_response: dict) -> Decimal:
        return BlockchainUtilsMixin.from_unit(int(balance_response.get('lamports')), precision=cls.precision) \
            if cls.validator.validate_balance_response(balance_response) else Decimal(0)

    @classmethod
    def parse_block_head_response(cls, block_head_response: dict) -> Optional[int]:
        return int(block_head_response.get('absoluteSlot')) \
            if cls.validator.validate_block_head_response(block_head_response) else None

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: dict, block_head: int) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=tx_details_response.get('slot'),
                block_hash=None,
                tx_hash=tx_details_response.get('txHash'),
                date=parse_timestamp(tx_details_response.get('blockTime')),
                success=True,
                confirmations=block_head - tx_details_response.get('slot'),
                from_address=transfer.get('source'),
                to_address=transfer.get('destination'),
                value=BlockchainUtilsMixin.from_unit(int(transfer.get('amount')), precision=cls.precision),
                symbol=cls.symbol,
                memo=None,
                tx_fee=None,
                token=None,
            )
            for transfer in tx_details_response.get('solTransfers')
            if cls.validator.validate_transaction(transfer)
        ] if cls.validator.validate_tx_details_response(tx_details_response) else []

    @classmethod
    def parse_address_txs_response(cls, _: str, address_txs_response: dict, block_head: int) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=transfer.get('slot'),
                block_hash=None,
                tx_hash=transfer.get('txHash'),
                date=parse_timestamp(transfer.get('blockTime')),
                success=True,
                confirmations=block_head - transfer.get('slot'),
                from_address=transfer.get('src'),
                to_address=transfer.get('dst'),
                value=BlockchainUtilsMixin.from_unit(int(transfer.get('lamport')), precision=cls.precision),
                symbol=cls.symbol,
                memo=None,
                tx_fee=None,
                token=None,
            )
            for transfer in address_txs_response.get('data')
            if cls.validator.validate_transaction(transfer)
        ] if cls.validator.validate_address_txs_response(address_txs_response) else []


class SolScanSolApi(GeneralApi):
    """
        solscan API explorer.
        supported coins: solana
        API docs: https://public-api.solscan.io/docs/
        Explorer: https://solscan.io/
    """

    parser = SolScanParser
    symbol = 'SOL'
    cache_key = 'sol'
    _base_url = 'https://public-api.solscan.io'
    rate_limit = 0.2  # 5 req/sec
    TRANSACTIONS_LIMIT = 50

    supported_requests = {
        'get_balance': '/account/{address}',
        'get_tx_details': '/transaction/{tx_hash}',
        'get_block_head': '/chaininfo/',
        'get_address_txs': '/account/solTransfers?account={address}&offset=0&limit=50'
    }

    @classmethod
    def get_headers(cls) -> dict:
        return {
            'accept': 'application/json',
            'token': random.choice(settings.SOLSCAN_APIKEY)
        }
