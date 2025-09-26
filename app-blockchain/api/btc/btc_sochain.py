from exchange.blockchain.api.common_apis.sochain import SochainAPI


class BitcoinSochainAPI(SochainAPI):

    symbol = 'BTC'
    PRECISION = 8
