from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.commons.web3 import Web3Api, Web3ResponseParser, Web3ResponseValidator
from exchange.blockchain.contracts_conf import BASE_ERC20_contract_currency, BASE_ERC20_contract_info


class AlchemyBaseResponseValidator(Web3ResponseValidator):
    valid_input_len = [138, 202]

class AlchemyBaseResponseParser(Web3ResponseParser):
    validator = AlchemyBaseResponseValidator

    symbol = 'ETH'
    currency = Currencies.eth
    decimals = 18

    @classmethod
    def contract_currency_list(cls) -> dict:
        return BASE_ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls) -> dict:
        return BASE_ERC20_contract_info.get(cls.network_mode)


class AlchemyBaseApi(Web3Api):
    parser = AlchemyBaseResponseParser
    # _base_url = 'https://base-mainnet.g.alchemy.com/v2/ShgERM-vbHRU2bUEOvy9iLzQHoGmAx1W' # noqa: ERA001
    # _base_url = 'https://base.meowrpc.com' # noqa: ERA001
    _base_url = 'https://base-rpc.publicnode.com'
    # _base_url = 'https://base-pokt.nodies.app' # noqa: ERA001
    cache_key = 'base'
    GET_BLOCK_ADDRESSES_MAX_NUM = 500
    max_workers_for_get_block = 3
    block_height_offset = 10
    instance = None
    USE_PROXY = True
