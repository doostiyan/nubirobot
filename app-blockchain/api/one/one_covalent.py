from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.covalenthq import CovalenthqAPI
from exchange.blockchain.api.one.one_rpc import HarmonyRPC
from exchange.blockchain.contracts_conf import harmony_ERC20_contract_info, harmony_ERC20_contract_currency
from exchange.blockchain.utils import APIError


class ONECovalenthqAPI(CovalenthqAPI):
    """
    tx_details: only support One Tx_hash (instead of ETH Tx_hash)
    """

    _base_url = 'https://api.covalenthq.com/v1/1666600000/'
    testnet_url = 'https://api.covalenthq.com/v1/1666700000/'
    rpc_url_mainnet = 'https://api.s0.t.hmny.io'
    symbol = 'ONE'
    currency = Currencies.one
    PRECISION = 18
    cache_key = 'one'
    rpc = HarmonyRPC()

    USE_PROXY = False

    def get_txs(self, address):
        txs = []
        hashes = []
        response = self.request('get_transactions', address=address, api_key=self.get_api_key())
        if not response:
            raise APIError('[GetTransaction] Response is None.')
        if response.get('error'):
            raise APIError('[GetTransaction] Unsuccessful.')

        transactions = response.get('data', {}).get('items', [])
        block_head = self.get_block_head()
        for tx in transactions:
            if tx.get('successful'):
                parsed_tx = self.parse_tx(tx, address, block_head)
                if parsed_tx:
                    hashes.append(tx.get('tx_hash'))
                    txs.append(parsed_tx)

        hashes = self.rpc.get_txs_hashes(hashes)
        if not hashes:
            return []
        for eth_hash, tx in zip(hashes, txs):
            tx[self.currency]['hash'] = eth_hash
        return txs

    @property
    def contract_currency_list(self):
        return harmony_ERC20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return harmony_ERC20_contract_info.get(self.network)
