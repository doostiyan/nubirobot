from exchange.base.models import Currencies
from exchange.blockchain.contracts_conf import harmony_ERC20_contract_info, harmony_ERC20_contract_currency
from exchange.blockchain.api.common_apis.web3 import Web3API


class OneWeb3API(Web3API):
    """
    Harmony Web3 API.

    supported coins: ONE

    API docs: https://web3py.readthedocs.io/'
    Explorer: https://explorer.harmony.one/

    supported requests:
        get_balance
        check_block_status
        get_latest_block, get_tx_details: wrong from address for this tx:
            https://explorer.harmony.one/tx/0xaa7de7b6d5815b93bc149381f3c139d462f4efecdb7e56735ade303221939879
    """

    symbol = 'ONE'
    currency = Currencies.one
    cache_key = 'one'
    block_height_offset = 12

    _base_url = 'https://harmony.public-rpc.com'
    # _base_url = 'https://1rpc.io/one'

    def __init__(self):
        from web3.middleware import ExtraDataToPOAMiddleware
        super().__init__()
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    @property
    def contract_currency_list(self):
        return harmony_ERC20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return harmony_ERC20_contract_info.get(self.network)
