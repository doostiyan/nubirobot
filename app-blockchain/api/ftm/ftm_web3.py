from exchange.base.models import Currencies
from exchange.blockchain.contracts_conf import opera_ftm_contract_currency, opera_ftm_contract_info
from exchange.blockchain.api.common_apis.web3 import Web3API


class FtmWeb3API(Web3API):
    """
    Fantom Web3 API.

    supported coins: FTM

    API docs: https://web3py.readthedocs.io/'
    Explorer: https://explorer.fantom.network/

    supported requests:
        get_balance
        check_block_status
        get_latest_block
    """

    symbol = 'FTM'
    currency = Currencies.ftm
    cache_key = 'ftm'

    # _base_url = 'https://1rpc.io/klay'
    # _base_url = 'https://fantom-mainnet.public.blastapi.io/'
    # _base_url = 'https://fantom.drpc.org'
    _base_url = 'https://fantom-rpc.publicnode.com'
    testnet_url = 'https://rpc.testnet.fantom.network/'
    USE_PROXY = False
    block_height_offset = 12
    @property
    def contract_currency_list(self):
        return opera_ftm_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return opera_ftm_contract_info.get(self.network)



