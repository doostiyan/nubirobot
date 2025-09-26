from exchange.blockchain.models import Currencies
from exchange.blockchain.api.general.evm_based.routescan_api import (RoutescanApi, RoutescanResponseParser,
                                                                     RoutescanResponseValidator)


class FlareRoutescanResponseParser(RoutescanResponseParser):
    symbol = 'FLR'
    currency = Currencies.flr
    validator = RoutescanResponseValidator


class FlareRoutescanApi(RoutescanApi):
    parser = FlareRoutescanResponseParser
    symbol = 'FLR'
    cache_key = 'flr'
    chain_id = 14
