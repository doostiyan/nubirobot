from exchange.blockchain.api.arbitrum.alchemy_arbitrum import AlchemyArbitrumResponseParser
from exchange.blockchain.api.commons.web3 import Web3Api


class Arb1ArbitrumApi(Web3Api):
    parser = AlchemyArbitrumResponseParser
    _base_url = 'https://arb1.arbitrum.io/rpc'
    USE_PROXY = True
    cache_key = 'arb'
    GET_BLOCK_ADDRESSES_MAX_NUM = 300
    max_workers_for_get_block = 3
    instance = None
