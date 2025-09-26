from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.web3 import Web3API
from exchange.blockchain.contracts_conf import BEP20_contract_currency, BEP20_contract_info


class BSCRPC(Web3API):
    """
    supported requests:
        check_block_status
        get_latest_block
    """

    currency = Currencies.bnb
    symbol = 'BSC'
    USE_PROXY = False
    PRECISION = 18
    cache_key = 'bsc'
    block_height_offset = 20
    _base_url = 'https://bscrpc.com/'
    # _base_url = 'https://bsc.publicnode.com'
    # _base_url = 'https://nodes3.nobitex1.ir//bsc-fullnode-rpc/'

    def __init__(self):
        from web3.middleware import ExtraDataToPOAMiddleware

        super().__init__()
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    def get_name(self):
        return 'rpc_api'

    @property
    def contract_currency_list(self):
        return BEP20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return BEP20_contract_info.get(self.network)
