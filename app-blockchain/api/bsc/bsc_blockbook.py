from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.blockbook import BlockbookAPI
from exchange.blockchain.contracts_conf import BEP20_contract_currency, BEP20_contract_info
from exchange.blockchain.validators import convert_eth_address_to_checksum


class BscBlockbookAPI(BlockbookAPI):
    """
    Blockbook API explorer.

    supported coins: binance coin, bitcoin, ethereum, tether
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer:
    """
    _base_url = f'{settings.DIRECT_NODES_SERVER}/bsc-blockbook'
    TOKEN_NETWORK = True
    symbol = 'BSC'
    USE_PROXY = False
    PRECISION = 18
    currency = Currencies.bnb
    cache_key = 'bsc'
    last_blocks = 200000

    @property
    def contract_currency_list(self):
        return BEP20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return BEP20_contract_info.get(self.network)

    def to_explorer_address_format(self, address):
        return convert_eth_address_to_checksum(address=address)

    @classmethod
    def convert_address(cls, address):
        return address.lower()


class BscNobitexBlockbookAPI(BscBlockbookAPI):  # Do not use this. This is down.
    """
    Blockbook API explorer.

    supported coins: binance coin, bitcoin, ethereum, tether
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer:
    """
    _base_url = 'https://nodes.nobitex1.ir/bsc-blockbook'
    USE_PROXY = False


class BscKleverBlockbookAPI(BscBlockbookAPI):
    """
    Blockbook API explorer.

    supported coins: binance coin, bitcoin, ethereum, tether
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer:
    """
    _base_url = 'https://bscxplorer.com'
    USE_PROXY = True if not settings.IS_VIP else False
