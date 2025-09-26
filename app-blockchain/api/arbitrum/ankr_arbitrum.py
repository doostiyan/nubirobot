from exchange.blockchain.api.arbitrum.alchemy_arbitrum import AlchemyArbitrumResponseParser
from exchange.blockchain.api.commons.web3 import Web3Api


class AnkrArbitrumApi(Web3Api):
    parser = AlchemyArbitrumResponseParser
    _base_url = 'https://rpc.ankr.com/arbitrum/2cafb72cbbfe0368d09778b64f3902346c171a723b484bb928cee8402a545939'
    cache_key = 'arb'
    GET_BLOCK_ADDRESSES_MAX_NUM = 300
    max_workers_for_get_block = 3
    instance = None
