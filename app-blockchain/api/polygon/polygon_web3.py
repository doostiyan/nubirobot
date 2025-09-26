from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.web3 import Web3API
from exchange.blockchain.contracts_conf import polygon_ERC20_contract_info, polygon_ERC20_contract_currency


class PolygonWeb3API(Web3API):
    """
    MATIC Web3 API.

    supported coins: MATIC

    API docs: https://web3py.readthedocs.io/'

    supported requests:
        get_balance
        check_block_status
        get_latest_block
    """

    symbol = 'MATIC'
    currency = Currencies.pol
    cache_key = 'matic'
    block_height_offset = 25

    # _base_url = 'https://matic-mainnet.chainstacklabs.com'
    # _base_url = 'https://rpc-mainnet.matic.quiknode.pro'
    # _base_url = 'https://polygon-pokt.nodies.app'
    # _base_url = 'https://polygon.meowrpc.com'
    _base_url = 'https://polygon-rpc.com'

    USE_PROXY = False

    def __init__(self):
        from web3.middleware import ExtraDataToPOAMiddleware
        super().__init__()
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    @property
    def contract_currency_list(self):
        return polygon_ERC20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return polygon_ERC20_contract_info.get(self.network)
