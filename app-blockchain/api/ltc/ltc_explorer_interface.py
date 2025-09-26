from decimal import Decimal

from exchange.blockchain.api.general.explorer_interface import ExplorerInterface

from .ltc_bitquery import LtcBitqueryAPI
from .ltc_space import LiteCoinSpaceApi
from .ltc_blockcypher_new import LiteCoinBlockcypherAPI
from .ltc_blockbook_new import LiteCoinBlockBookAPI, LiteCoinBinanceBlockBookAPI, LiteCoinAtomicWalletBlockBookAPI, \
    LiteCoinHeatWalletBlockbookAPI
from .ltc_tatum import LiteCoinTatumApi


# Binance BlockBook not working, returning 443 for each request.
# HeatWallet nor working, returning 502(Bad Gateway) for each request.


class LTCExplorerInterface(ExplorerInterface):
    balance_apis = [LiteCoinBlockBookAPI, LiteCoinAtomicWalletBlockBookAPI, LiteCoinBlockcypherAPI, LtcBitqueryAPI,
                    LiteCoinBinanceBlockBookAPI, LiteCoinHeatWalletBlockbookAPI]
    tx_details_apis = [LiteCoinBlockcypherAPI, LiteCoinBlockBookAPI, LiteCoinAtomicWalletBlockBookAPI, LiteCoinSpaceApi,
                       LiteCoinBinanceBlockBookAPI, LiteCoinHeatWalletBlockbookAPI, LiteCoinTatumApi]
    address_txs_apis = [LiteCoinBlockBookAPI, LiteCoinAtomicWalletBlockBookAPI, LiteCoinBinanceBlockBookAPI,
                        LiteCoinHeatWalletBlockbookAPI]
    block_txs_apis = [LiteCoinBlockBookAPI, LiteCoinAtomicWalletBlockBookAPI, LtcBitqueryAPI,
                      LiteCoinBinanceBlockBookAPI, LiteCoinHeatWalletBlockbookAPI]
    block_head_apis = [LiteCoinBlockBookAPI, LtcBitqueryAPI, LiteCoinHeatWalletBlockbookAPI, LiteCoinTatumApi]
    symbol = 'LTC'
    min_valid_tx_amount = Decimal('0.0005')
