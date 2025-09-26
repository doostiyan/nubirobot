from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.commons.oklink import OklinkApi, OklinkResponseParser


class OkLinkBscResponseParser(OklinkResponseParser):
    symbol = 'BSC'
    currency = Currencies.bnb
    precision = 18


class OkLinkBscApi(OklinkApi):
    parser = OkLinkBscResponseParser
    cache_key = 'bsc'
    supported_requests = {
        'get_address_txs': '/address/transaction-list?address={address}&chainShortName=bsc',
        'get_token_txs': '/address/transaction-list?address={address}&protocolType=token_20&chainShortName=bsc',
        'get_block_head': '/block/block-list?limit=1&chainShortName=bsc'
    }
