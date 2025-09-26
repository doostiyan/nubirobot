from exchange.blockchain.api.arbitrum.alchemy_arbitrum import AlchemyArbitrumApi
from exchange.blockchain.api.arbitrum.ankr_arbitrum import AnkrArbitrumApi
from exchange.blockchain.api.arbitrum.arb1_arbitrum import Arb1ArbitrumApi
from exchange.blockchain.api.arbitrum.arb_contract_balance_checker import ARBContractBalanceCheckerV2Api
from exchange.blockchain.api.arbitrum.arbiscan_arbitrum import ArbiscanArbitrumApi
from exchange.blockchain.api.arbitrum.covalenthq_arbitrum import CovalenthqArbitrumApi
from exchange.blockchain.api.arbitrum.oklink_arbitrum import OkLinkArbitrumApi
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface


class ArbitrumExplorerInterface(ExplorerInterface):
    balance_apis = [ARBContractBalanceCheckerV2Api, AnkrArbitrumApi, Arb1ArbitrumApi, AlchemyArbitrumApi, CovalenthqArbitrumApi, ArbiscanArbitrumApi]
    token_balance_apis = [ArbiscanArbitrumApi, CovalenthqArbitrumApi]
    tx_details_apis = [AnkrArbitrumApi, Arb1ArbitrumApi, AlchemyArbitrumApi]
    address_txs_apis = [OkLinkArbitrumApi, ArbiscanArbitrumApi, CovalenthqArbitrumApi]
    token_txs_apis = [OkLinkArbitrumApi, ArbiscanArbitrumApi, CovalenthqArbitrumApi]
    block_txs_apis = [AlchemyArbitrumApi, AnkrArbitrumApi, Arb1ArbitrumApi, AlchemyArbitrumApi]
    block_head_apis = [AnkrArbitrumApi, Arb1ArbitrumApi, OkLinkArbitrumApi, AlchemyArbitrumApi]
    symbol = 'ETH'
    network = 'ARB'

    max_block_per_time = 300
