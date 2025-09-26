from decimal import Decimal
from typing import Dict, Union

from django.conf import settings

from exchange.blockchain.api.commons.blockbook import BlockBookApi, BlockBookParser, BlockBookValidator
from exchange.blockchain.contracts_conf import ERC20_contract_currency, ERC20_contract_info
from exchange.blockchain.validators import convert_eth_address_to_checksum

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class EthereumBlockBookValidator(BlockBookValidator):
    min_valid_tx_amount = Decimal('0.0')


class EthereumBlockBookParser(BlockBookParser):
    validator = EthereumBlockBookValidator
    precision = 18
    currency = Currencies.eth
    TOKEN_NETWORK = True
    symbol = 'ETH'

    @classmethod
    def contract_currency_list(cls) -> Dict[str, int]:
        return ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls) -> Dict[int, Dict[str, Union[str, int]]]:
        return ERC20_contract_info.get(cls.network_mode)

    @classmethod
    def convert_address(cls, address: str) -> str:
        return address.lower()

    @classmethod
    def to_explorer_address_format(cls, address: str) -> str:
        return convert_eth_address_to_checksum(address=address)


class EthereumBlockBookApi(BlockBookApi):
    parser = EthereumBlockBookParser

    """
    coins: eth
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer: https://blockbook-ethereum.tronwallet.me
    """

    testnet_url = 'https://ac-dev1.net:39136'  # 'https://blockbook-eth.binancechain.io'
    symbol = 'ETH'
    cache_key = 'eth'
    USE_PROXY = True
    SUPPORT_PAGING = True


class EthereumHeatWallet1BlockBookApi(EthereumBlockBookApi):
    """
    coins: eth
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer: https://blockbook-ethereum.tronwallet.me
    """

    _base_url = 'https://eth1.heatwallet.com'


class EthereumHeatWallet2BlockBookApi(EthereumBlockBookApi):
    """
    coins: eth
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer: https://blockbook-ethereum.tronwallet.me
    """

    _base_url = 'https://eth2.heatwallet.com'


class EthereumEthBlockBlockBookApi(EthereumBlockBookApi):
    """
    coins: eth
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer: https://blockbook-ethereum.tronwallet.me
    """

    _base_url = 'https://ethblockexplorer.org'


class EthereumBinanceBlockbookApi(EthereumBlockBookApi):
    """
    coins: eth
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer: https://blockbook-ethereum.tronwallet.me
    """

    _base_url = 'https://ethblockexplorer.org'
