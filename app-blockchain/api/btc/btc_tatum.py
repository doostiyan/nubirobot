from decimal import Decimal
from typing import List

from django.conf import settings
from exchange.blockchain.api.commons.btc_like_tatum import BtcLikeTatumApi, TatumResponseParser, TatumResponseValidator
from exchange.blockchain.api.general.dtos import TransferTx
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class BitcoinTatumResponseValidator(TatumResponseValidator):
    min_valid_tx_amount = Decimal('0.0005')


class BitcoinTatumResponseParser(TatumResponseParser):
    validator = BitcoinTatumResponseValidator
    symbol = 'BTC'
    currency = Currencies.btc

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        transfers = super().parse_tx_details_response(tx_details_response, block_head)
        for transfer in transfers:
            transfer.value = BlockchainUtilsMixin.from_unit(int(transfer.value), cls.precision)
            transfer.tx_fee = BlockchainUtilsMixin.from_unit(int(transfer.tx_fee), cls.precision)
        return transfers


class BitcoinTatumApi(BtcLikeTatumApi):
    symbol = 'BTC'
    cache_key = 'btc'
    currency = Currencies.btc
    parser = BitcoinTatumResponseParser
    _base_url = 'https://api.tatum.io/v3/bitcoin/'
    instance = None