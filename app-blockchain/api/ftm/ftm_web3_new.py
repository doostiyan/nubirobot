from django.conf import settings

from exchange.blockchain.api.commons.web3 import Web3Api, Web3ResponseParser
from exchange.blockchain.contracts_conf import opera_ftm_contract_currency, opera_ftm_contract_info

if settings.BLOCKCHAIN_CACHE_PREFIX == "cold_":
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class FTMWeb3ResponseParser(Web3ResponseParser):
    symbol = "FTM"
    currency = Currencies.ftm
    precision = 18

    @classmethod
    def contract_currency_list(cls):
        return opera_ftm_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return opera_ftm_contract_info.get(cls.network_mode)


class FtmWeb3Api(Web3Api):
    parser = FTMWeb3ResponseParser
    symbol = 'FTM'
    cache_key = 'ftm'
    #_base_url = 'https://fantom-mainnet.public.blastapi.io/'
    _base_url = 'https://fantom-rpc.publicnode.com'
    # _base_url = 'https://fantom.drpc.org'
    testnet_url = 'https://rpc.testnet.fantom.network/'
    USE_PROXY = False
    block_height_offset = 12
    GET_BLOCK_ADDRESSES_MAX_NUM = 300
