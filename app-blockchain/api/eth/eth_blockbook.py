from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.blockbook import BlockbookAPI
from exchange.blockchain.contracts_conf import ERC20_contract_info, ERC20_contract_currency
from exchange.blockchain.validators import convert_eth_address_to_checksum


class EthereumBlockbookAPI(BlockbookAPI):
    """
    coins: eth
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer: https://blockbook-ethereum.tronwallet.me
    """

    # _base_url = 'https://blockbook-eth.binancechain.io'
    _base_url = 'https://eth1.heatwallet.com'
    testnet_url = 'https://ac-dev1.net:39136'
    TOKEN_NETWORK = True
    symbol = 'ETH'
    PRECISION = 18
    currency = Currencies.eth
    cache_key = 'eth'
    USE_PROXY = True if settings.IS_PROD and settings.NO_INTERNET and not settings.IS_VIP else False

    @property
    def contract_currency_list(self):
        return ERC20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return ERC20_contract_info.get(self.network)

    def to_explorer_address_format(self, address):
        return convert_eth_address_to_checksum(address=address)

    @classmethod
    def convert_address(cls, address):
        return address.lower()


class EthereumHeatWallet1BlockbookAPI(EthereumBlockbookAPI):
    """
    coins: eth
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer: https://blockbook-ethereum.tronwallet.me
    """

    _base_url = 'https://eth1.heatwallet.com'


class EthereumHeatWallet2BlockbookAPI(EthereumBlockbookAPI):
    """
    coins: eth
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer: https://blockbook-ethereum.tronwallet.me
    """

    _base_url = 'https://eth2.heatwallet.com'


class EthereumEthBlockBlockbookAPI(EthereumBlockbookAPI):
    """
    coins: eth
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer: https://blockbook-ethereum.tronwallet.me
    """

    _base_url = 'https://ethblockexplorer.org'


class EthereumEthMetaWireBlockBookAPI(EthereumBlockbookAPI):
    """
    coins: eth
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer: https://blockbook-ethereum.tronwallet.me
    """

    _base_url = 'https://bb.metawire.cloud/mainnet/eth'
    supported_requests = {
        'get_balance': '/v2/address/{address}?details={details}&from={from_block}&pageSize=50',
        'get_balance_xpub': '/v2/xpub/{address}?details={details}',
        'get_utxo': '/v2/utxo/{address}?confirmed={confirmed}',
        'get_tx': '/v2/tx/{tx_hash}',
        'get_block': '/v2/block/{block}?page={page}',
        'get_info': '/',
    }
    USE_PROXY = True



class EthereumBinanceChainBlockbookAPI(EthereumBlockbookAPI):
    """
    coins: eth
    API docs: https://github.com/trezor/blockbook/blob/master/docs/api.md
    Explorer: https://blockbook-ethereum.tronwallet.me
    """

    _base_url = 'https://blockbook-eth.binancechain.io'
    USE_PROXY = True if not settings.IS_VIP else False
