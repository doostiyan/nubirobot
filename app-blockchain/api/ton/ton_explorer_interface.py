from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.api.ton.dton_ton import DtonTonApi
from exchange.blockchain.api.ton.polaris_ton import PolarisTonApi
from exchange.blockchain.api.ton.ton_tonx import TonXTonApi
from exchange.blockchain.api.ton.tonapi_ton import TonApi
from exchange.blockchain.api.ton.toncenter_ton import ToncenterTonApi

"""
https://bitex-doc.nobitex.ir/doc/the-open-network-z8OhQfFjA6
"""


class TonExplorerInterface(ExplorerInterface):
    balance_apis = [TonApi, DtonTonApi]
    tx_details_apis = [TonApi, ToncenterTonApi, DtonTonApi, TonXTonApi]
    withdraw_hashes_api = [TonApi, ToncenterTonApi]
    token_tx_details_apis = [TonApi, PolarisTonApi]
    address_txs_apis = [TonApi, ToncenterTonApi, DtonTonApi]
    block_txs_apis = [DtonTonApi, ToncenterTonApi]
    block_head_apis = [ToncenterTonApi, DtonTonApi]
    token_txs_apis = [TonApi, PolarisTonApi]
    symbol = 'TON'

    @classmethod
    def get_withdraw_hash(cls, tx_hash: str) -> str:
        api = cls.withdraw_hashes_api[0].get_instance()
        response = api.get_withdraw_hash(tx_hash)
        return api.parser.parse_tx_withdraw_hash(response) or ''
