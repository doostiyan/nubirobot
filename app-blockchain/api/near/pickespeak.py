import random
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List

from django.conf import settings

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_utc_timestamp_nanosecond
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies
    from exchange.base.parsers import parse_utc_timestamp_nanosecond


class NearPikeValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.05')
    precision = 24

    @classmethod
    def validate_general_response(cls, response:Any) -> bool:
        if not response:
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, _:Any) -> bool:
        return False

    @classmethod
    def validate_transaction(cls, transaction: Dict[str,Any]) -> bool:

        if Decimal(str(transaction.get('amount'))) < cls.min_valid_tx_amount:
            return False
        if transaction.get('sender').casefold() == transaction.get('receiver').casefold():
            return False
        if not transaction.get('status'):
            return False

        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Any) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        return True


class NearPikeParser(ResponseParser):
    validator = NearPikeValidator
    precision = 24
    symbol = 'NEAR'
    currency = Currencies.near

    @classmethod
    def parse_block_head_response(cls, _: Any) -> None:
        return

    @classmethod
    def parse_address_txs_response(cls, _: str, address_txs_response: List[Dict[str, Any]], __: int) -> \
            List[TransferTx]:
        transfers = []
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return transfers
        for tx in address_txs_response:
            tx_date_time = parse_utc_timestamp_nanosecond(tx.get('timestamp')).replace(tzinfo=timezone.utc)
            if cls.validator.validate_transaction(tx):
                transfers.append(TransferTx(
                    block_height=tx.get('block_height'),
                    block_hash=None,
                    tx_hash=tx.get('transaction_id'),
                    date=tx_date_time,
                    success=True,
                    confirmations=cls.calculate_tx_confirmations(tx_date_time),
                    from_address=tx.get('sender'),
                    to_address=tx.get('receiver'),
                    value=Decimal(str(tx.get('amount'))),
                    symbol=cls.symbol,
                    memo=None,
                    token=None,
                ))
        return transfers

    @classmethod
    def calculate_tx_confirmations(cls, tx_date: datetime) -> int:
        diff = (datetime.now(timezone.utc) - tx_date).total_seconds()
        return int(diff / 1.2)


class NearPikeApi(GeneralApi):
    need_block_head_for_confirmation = False
    parser = NearPikeParser
    cache_key = 'near'
    symbol = 'NEAR'
    _base_url = 'https://api.pikespeak.ai'
    supported_requests = {
        'get_address_txs': '/account/near-transfer/{address}',
    }
    rate_limit = 6  # 10 requests per min

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice([
            '97bed520-ffe5-4920-b0b5-d41a51bd7e7f',
            '2725d341-3e2d-46f0-90da-be0dd2fb2e28',
            'e0e48869-c6a3-472c-8051-9d647ff2390b',
            'cb1122cb-eda9-41ce-ae08-d81acbaa6363',
        ])

    def get_header(self) -> Dict[str, str]:
        return {
            'x-api-key': self.get_api_key(),
            'accept': 'application/json'
        }
