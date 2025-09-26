import random
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.conf import settings

from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class SolanaBeachSolValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.001')
    valid_program_id = '11111111111111111111111111111111'
    precision = 9

    @classmethod
    def validate_general_response(cls, response: Any) -> bool:
        if response:
            return True
        return False

    @classmethod
    def validate_balance_response(cls, balance_response: dict) -> bool:
        if (cls.validate_general_response(balance_response)
                and balance_response.get('value')
                and balance_response.get('value').get('base')
                and balance_response.get('value').get('base').get('balance')):
            return True
        return False

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: dict) -> bool:
        if (cls.validate_general_response(tx_details_response)
                and not tx_details_response.get('meta').get('err')
                and tx_details_response.get('valid')
                and tx_details_response.get('instructions')  # not empty transfers
                and tx_details_response.get('transactionHash')):
            return True
        return False

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, any]) -> bool:
        if not transaction:
            return False

        transfer_sol = transaction.get('parsed', {}).get('TransferSol', {})
        # The transaction must have at least one transfer.
        if not transfer_sol:
            return False

        amount = transfer_sol.get('amount')
        if not amount or BlockchainUtilsMixin.from_unit(int(amount), precision=cls.precision) < cls.min_valid_tx_amount:
            return False

        source_address = transfer_sol.get('source', {}).get('address', '').casefold()
        destination_address = transfer_sol.get('destination', {}).get('address', '').casefold()
        if source_address == destination_address:
            return False

        # Check the name and address of the transaction's program
        # If the program name is not "System Program" or the address
        # is not the valid address "11111111111111111111111111111111",
        # consider the transaction invalid.
        program_id = transaction.get('programId', {})
        program_name = program_id.get('name')
        program_address = program_id.get('address')
        if program_name != 'System Program' or program_address != cls.valid_program_id:
            return False

        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: dict) -> bool:
        if cls.validate_general_response(block_head_response) and block_head_response.get('currentSlot'):
            return True
        return False

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: list) -> bool:
        return cls.validate_general_response(address_txs_response)


class SolanaBeachSolParser(ResponseParser):
    validator = SolanaBeachSolValidator
    symbol = 'SOL'
    currency = Currencies.sol
    precision = 9
    block_number_check = 143835685

    @classmethod
    def parse_balance_response(cls, balance_response: dict) -> Decimal:
        return BlockchainUtilsMixin.from_unit(
            int(balance_response.get('value').get('base').get('balance')), precision=cls.precision) \
            if cls.validator.validate_balance_response(balance_response) else Decimal(0)

    @classmethod
    def parse_block_head_response(cls, block_head_response: dict) -> Optional[str]:
        return block_head_response.get('currentSlot') \
            if cls.validator.validate_block_head_response(block_head_response) else None

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: dict, block_head: int) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=int(tx_details_response.get('blockNumber')),
                block_hash=None,
                tx_hash=tx_details_response.get('transactionHash'),
                date=parse_utc_timestamp(tx_details_response.get('blocktime').get('absolute')),
                success=True,
                confirmations=block_head - int(tx_details_response.get('blockNumber')),
                from_address=transaction.get('parsed').get('TransferSol').get('source').get('address'),
                to_address=transaction.get('parsed').get('TransferSol').get('destination').get('address'),
                value=BlockchainUtilsMixin.from_unit(
                    int(transaction.get('parsed').get('TransferSol').get('amount')),
                    precision=cls.precision),
                symbol=cls.symbol,
                memo=None,
                tx_fee=None,
                token=None,
            )
            for transaction in tx_details_response.get('instructions')
            if cls.validator.validate_transaction(transaction)
        ] if cls.validator.validate_tx_details_response(tx_details_response) else []

    @classmethod
    def parse_address_txs_response(cls, _: str, address_txs_response: list, block_head: int) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=transaction.get('blockNumber'),
                block_hash=None,
                tx_hash=transaction.get('transactionHash').strip()
                if transaction.get('blockNumber') > cls.block_number_check
                else transaction.get('transactionHash'),
                date=parse_utc_timestamp(transaction.get('blocktime').get('absolute')),
                success=True,
                confirmations=block_head - transaction.get('blockNumber'),
                from_address=tx.get('parsed').get('TransferSol').get('source').get('address'),
                to_address=tx.get('parsed').get('TransferSol').get('destination').get('address'),
                value=BlockchainUtilsMixin.from_unit(int(tx.get('parsed').get('TransferSol').get('amount')),
                                                     precision=cls.precision),
                symbol=cls.symbol,
                memo=None,
                tx_fee=None,
                token=None,
            )
            for transaction in address_txs_response
            for tx in transaction.get('instructions')
            if cls.validator.validate_transaction(tx)
        ] if cls.validator.validate_address_txs_response(address_txs_response) else []


class SolanaBeachSolApi(GeneralApi):
    """
       solanaBeach API explorer.
       supported coins: solana
       API docs: https://app.swaggerhub.com/apis-docs/V2261/solanabeach-backend_api/0.0.1
       Explorer:
    """
    parser = SolanaBeachSolParser
    _base_url = 'https://api.solanabeach.io/v1'
    cache_key = 'sol'
    symbol = 'SOL'
    rate_limit = 0.1  # (100 req/10 sec)
    USE_PROXY = True
    supported_requests = {
        'get_balance': '/account/{address}',
        'get_tx_details': '/transaction/{tx_hash}',
        'get_block_head': '/health',
        'get_address_txs': '/account/{address}/transactions?limit=25'
    }

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.SOLANABEACH_API_KEY)

    @classmethod
    def get_headers(cls) -> dict:
        return {
            'accept': 'application/json',
            'Authorization': 'Bearer ' + cls.get_api_key(),
        }
