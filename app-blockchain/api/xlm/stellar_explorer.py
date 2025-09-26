from decimal import Decimal
from typing import List

from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi


class StellarExplorerValidator:

    @classmethod
    def validate_general_response(cls, response):
        return response is not None

    @classmethod
    def validate_tx_details_response(cls, tx_details_response) -> bool:
        if len(tx_details_response) != 3:
            return False
        if len(tx_details_response[1]) != 1:
            return False
        return True

    @classmethod
    def validate_transaction(cls, tx_details_response) -> bool:
        transaction = tx_details_response[0]
        transaction.update(tx_details_response[1][0])
        if not transaction.get('hash'):
            return False
        if transaction.get('type') != 'payment' or transaction.get('typeI') != 1:
            return False
        if not transaction.get('transactionSuccessful'):
            return False
        if transaction.get('assetType') != 'native':
            return False
        return True


class StellarExplorerParser:
    validator = StellarExplorerValidator
    symbol = 'xlm'
    currency = Currencies.xlm
    precision = 7
    network_mode = 'mainnet'

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        if not cls.validator.validate_tx_details_response(tx_details_response):
            return None
        if not cls.validator.validate_transaction(tx_details_response):
            return None

        transaction = tx_details_response[1][0]
        transaction.update(tx_details_response[0])

        return [TransferTx(
            block_height=transaction.get('ledger'),
            tx_hash=transaction.get('transactionHash'),
            date=parse_iso_date(transaction.get('createdAt')),
            success=True,
            confirmations=0,
            from_address=transaction.get('from'),
            to_address=transaction.get('to'),
            value=Decimal(transaction.get('amount')),
            symbol=cls.symbol,
            tx_fee=Decimal(transaction.get('fee')),
            memo=str(transaction.get('memo'))
        )]


class StellarExplorerApi(GeneralApi):
    parser = StellarExplorerParser
    _base_url = 'https://steexp.com/'
    cache_key = 'xlm'
    need_block_head_for_confirmation = False

    supported_requests = {
        'get_tx_details': 'tx/{tx_hash}?_data=routes/tx.$txHash',
    }

