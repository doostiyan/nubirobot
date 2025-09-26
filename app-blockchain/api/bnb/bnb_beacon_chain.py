from typing import List

from django.conf import settings

from exchange.blockchain.api.general.general import GeneralApi, ResponseValidator, ResponseParser
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.general.dtos.dtos import TransferTx


class BeaconChainResponseValidator(ResponseValidator):
    precision = 8

    @classmethod
    def validate_tx_details_response(cls, tx_details_response) -> bool:
        if not tx_details_response:
            return False
        return cls.validate_transaction(tx_details_response)

    @classmethod
    def validate_transaction(cls, transaction) -> bool:
        if not transaction.get('hash'):
            return False
        if transaction.get('type').casefold() != 'TRANSFER'.casefold():
            return False
        if transaction.get('code') != 0:
            return False
        if not transaction.get('asset') or transaction.get('asset') != 'BNB':
            return False
        if transaction.get('log') != 'Msg 0: ':
            return False
        value = BlockchainUtilsMixin.from_unit(transaction.get('amount'), cls.precision)
        if value <= cls.min_valid_tx_amount:
            return False
        if not transaction.get('fromAddr') or not transaction.get('toAddr'):
            return False
        if transaction.get('fromAddr') == transaction.get('toAddr'):
            return False
        return True


class BeaconChainResponseParser(ResponseParser):
    validator = BeaconChainResponseValidator
    symbol = 'BNB'
    currency = Currencies.bnb
    precision = 8

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        if cls.validator.validate_tx_details_response(tx_details_response):
            return [TransferTx(
                symbol=cls.symbol,
                success=True,
                tx_hash=tx_details_response.get('hash'),
                block_height=tx_details_response.get('blockHeight'),
                value=BlockchainUtilsMixin.from_unit(tx_details_response.get('amount'), cls.precision),
                from_address=tx_details_response.get('fromAddr'),
                to_address=tx_details_response.get('toAddr'),
                memo=tx_details_response.get('memo'),
                tx_fee=BlockchainUtilsMixin.from_unit(tx_details_response.get('fee'), cls.precision)
            )]


class BeaconChainApi(GeneralApi):
    parser = BeaconChainResponseParser
    cache_key = 'bnb'
    _base_url = 'https://api.binance.org/bc/'  # mainnet
    testnet_url = 'https://testnet-api.binance.org/bc/'
    need_block_head_for_confirmation = False
    supported_requests = {
        'get_tx_details': 'api/v1/txs/{tx_hash}'
    }
