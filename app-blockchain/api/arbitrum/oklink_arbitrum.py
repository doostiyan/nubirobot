from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.commons.oklink import OklinkApi, OklinkResponseParser


class OklinkArbitrumResponseParser(OklinkResponseParser):
    symbol = 'ETH'
    currency = Currencies.eth
    precision = 18


class OkLinkArbitrumApi(OklinkApi):
    parser = OklinkArbitrumResponseParser
    cache_key = 'arb'
    supported_requests = {
        'get_address_txs': '/address/transaction-list?address={address}&chainShortName=arbitrum',
        'get_token_txs': '/address/transaction-list?address={address}&protocolType=token_20&chainShortName=arbitrum',
        'get_block_head': '/block/block-list?limit=1&chainShortName=arbitrum'
    }
    instance = None
