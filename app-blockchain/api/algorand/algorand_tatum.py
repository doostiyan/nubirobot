import random
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.conf import settings

from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
    from exchange.base.parsers import parse_utc_timestamp

from exchange.blockchain.api.general.dtos.dtos import TransferTx


class TatumAlgorandValidator(ResponseValidator):
    valid_operation = 'pay'
    min_valid_tx_amount = Decimal('1')
    genesis_hash = 'wGHE2Pwdvd7S12BL5FaOP20EGYesN73ktiC1qzkkit8='

    @classmethod
    def validate_general_response(cls, response: Any) -> bool:
        if not response:
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response: dict) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        return True

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: dict) -> bool:
        if not cls.validate_general_response(block_txs_response):
            return False
        if not isinstance(block_txs_response, dict):
            return False
        if block_txs_response.get('genesisHash') != cls.genesis_hash:
            return False
        if not isinstance(block_txs_response.get('txns'), list):
            return False
        return True

    @classmethod
    def validate_block_txs_raw_response(cls, block_txs_raw_response: Dict[str, Any]) -> bool:
        if not block_txs_raw_response or not isinstance(block_txs_raw_response, dict):
            return False
        if not block_txs_raw_response.get('txns') or not isinstance(block_txs_raw_response.get('txns'), list):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: dict) -> bool:
        if not cls.validate_general_response(tx_details_response):
            return False
        return cls.validate_transaction(tx_details_response)

    @classmethod
    def validate_transaction(cls, transaction: dict) -> bool:
        if not isinstance(transaction, dict):
            return False
        if transaction.get('txType') != cls.valid_operation:
            return False
        if not isinstance(transaction.get('confirmedRound'), int):
            return False
        if (transaction.get('confirmedRound') < transaction.get('firstValid') or
                transaction.get('confirmedRound') > transaction.get('lastValid')):
            return False
        if transaction.get('genesisHash') != cls.genesis_hash:
            return False
        if not transaction.get('id'):
            return False
        if not isinstance(transaction.get('paymentTransaction'), dict):
            return False
        if not transaction.get('fee'):
            return False
        payment_transaction = transaction.get('paymentTransaction')
        if not payment_transaction.get('amount'):
            return False
        value = Decimal(str(payment_transaction.get('amount')))
        if value < cls.min_valid_tx_amount:
            return False
        if transaction.get('sender') == payment_transaction.get('receiver'):
            return False
        if not transaction.get('signature', {}).get('sig'):
            return False
        return True


class TatumAlgorandResponseParser(ResponseParser):
    validator = TatumAlgorandValidator
    symbol = 'ALGO'
    currency = Currencies.algo

    @classmethod
    def parse_block_head_response(cls, block_head_response: int) -> Optional[int]:
        if cls.validator.validate_block_head_response(block_head_response):
            return block_head_response
        return None

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, Any], block_head: int) -> List[TransferTx]:
        if cls.validator.validate_tx_details_response(tx_details_response):
            tx_hash = tx_details_response.get('id')
            fee = Decimal(str(tx_details_response.get('fee')))
            block_height = tx_details_response.get('confirmedRound')
            confirmations = block_head - block_height + 1
            date = parse_utc_timestamp(tx_details_response.get('roundTime'))
            from_address = tx_details_response.get('sender')
            to_address = tx_details_response.get('paymentTransaction').get('receiver')
            value = Decimal(str(tx_details_response.get('paymentTransaction').get('amount')))
            return [TransferTx(
                tx_hash=tx_hash,
                tx_fee=fee,
                from_address=from_address,
                to_address=to_address,
                value=value,
                date=date,
                confirmations=confirmations,
                block_height=block_height,
                success=True,
                symbol=cls.symbol
            )]
        return []

    @classmethod
    def parse_block_txs_response(cls, block_txs_response: Dict[str, Any]) -> List[TransferTx]:
        block_txs: List[TransferTx] = []
        if cls.validator.validate_block_txs_response(block_txs_response):
            transactions = block_txs_response.get('txns')
            for transaction in transactions:
                if cls.validator.validate_transaction(transaction):
                    tx_hash = transaction.get('id')
                    fee = Decimal(str(transaction.get('fee')))
                    block_height = transaction.get('confirmedRound')
                    date = parse_utc_timestamp(transaction.get('roundTime'))
                    from_address = transaction.get('sender')
                    to_address = transaction.get('paymentTransaction').get('receiver')
                    value = Decimal(str(transaction.get('paymentTransaction').get('amount')))
                    block_tx = TransferTx(
                        tx_hash=tx_hash,
                        tx_fee=fee,
                        from_address=from_address,
                        to_address=to_address,
                        value=value,
                        date=date,
                        block_height=block_height,
                        success=True,
                        symbol=cls.symbol)
                    block_txs.append(block_tx)
        return block_txs


class TatumAlgorandApi(GeneralApi):
    _base_url = 'https://api.tatum.io/v3/algorand/'
    rate_limit = 0.017  # 60 rps
    instance = None
    cache_key = 'algo'
    parser = TatumAlgorandResponseParser

    supported_requests = {
        'get_tx_details': 'transaction/{tx_hash}',
        'get_block_head': 'block/current',
        'get_block_txs': 'block/{height}'
    }

    def get_header(self) -> Dict[str, str]:
        return {
            'x-api-key': self.get_api_key()
        }

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.TATUM_API_KEYS)
