from decimal import Decimal
from typing import List

from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general.dtos import TransferTx

from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin


class StellarBlockchairValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.00')

    @classmethod
    def validate_general_response(cls, response):
        if not response:
            return False
        if not response.get('data'):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        if not block_head_response.get('data').get('best_ledger_height'):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        for key, value in tx_details_response.get('data').items():
            if 'transaction' in value and 'operations' in value:
                if not tx_details_response.get('data').get(key):
                    return False
                if not tx_details_response.get('data').get(key).get('transaction'):
                    return False
                key2check_transaction = ['successful', 'ledger', 'max_fee', 'created_at']
                for check in key2check_transaction:
                    if not tx_details_response.get('data').get(key).get('transaction').get(check):
                        return False
                return True
        return False

    @classmethod
    def validate_transaction(cls, transaction) -> bool:
        key2check = ['type', 'asset_type', 'type_i', 'source_account', 'from', 'to',
                     'amount', 'transaction_successful']
        for key in key2check:
            if not transaction.get(key):
                return False
        if all([transaction.get('type') == 'payment',
                transaction.get('asset_type') == 'native',
                transaction.get('type_i') == 1,
                transaction.get('source_account') == transaction.get('from'),
                not (transaction.get('asset_issuer') or transaction.get('asset_code'))]):
            return True
        return False


class StellarBlockchairParser(ResponseParser):
    validator = StellarBlockchairValidator
    precision = 7
    symbol = 'XLM'
    currency = Currencies.xlm

    @classmethod
    def parse_block_head_response(cls, block_head_response):
        if cls.validator.validate_block_head_response(block_head_response):
            return block_head_response.get('data').get('best_ledger_height')
        return 0

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        if not cls.validator.validate_tx_details_response(tx_details_response):
            return []
        operations = {}
        tx_hash = None
        for key, value in tx_details_response.get('data').items():
            if 'transaction' in value and 'operations' in value:
                tx_hash = key
                operations = tx_details_response.get('data').get(tx_hash).get('operations')
                break
        transfers: List[TransferTx] = []
        for operation in operations:
            if not cls.validator.validate_transaction(operation):
                continue
            transfers.append(TransferTx(
                tx_hash=tx_hash,
                success=True,
                from_address=operation.get('from'),
                to_address=operation.get('to'),
                value=Decimal(operation.get('amount')),
                symbol=cls.symbol,
                confirmations=block_head - tx_details_response.get('data').get(tx_hash).get('transaction').get('ledger'),
                block_height=tx_details_response.get('data').get(tx_hash).get('transaction').get('ledger'),
                block_hash=None,
                date=parse_iso_date(tx_details_response.get('data').get(tx_hash).get('transaction').get('created_at')),
                memo=tx_details_response.get('data').get(tx_hash).get('transaction').get('memo') or '',
                tx_fee=BlockchainUtilsMixin.from_unit(int(tx_details_response.get('data').get(tx_hash).
                                                          get('transaction').get('max_fee')), cls.precision),
                token=None,
            )
            )
        return transfers


class StellarBlockchairAPI(GeneralApi):
    _base_url = 'https://api.blockchair.com'
    parser = StellarBlockchairParser
    symbol = 'XLM'
    cache_key = 'xlm'
    currency = Currencies.xlm

    supported_requests = {
        'get_tx_details': '/stellar/raw/transaction/{tx_hash}?operations=true',
        'get_block_head': '/stellar/stats',
    }
