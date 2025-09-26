from exchange.blockchain.api.ada.cardano_bitquery_new import BitQueryCardanoApi
from exchange.blockchain.api.ada.cardano_blockfrost_new import CardanoBlockFrostApi
from exchange.blockchain.api.ada.cardano_polaris import CardanoPolarisGraphqlApi
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface

from .cardano_graphql_new import CardanoGraphqlApi


class CardanoExplorerInterface(ExplorerInterface):
    balance_apis = [CardanoGraphqlApi, CardanoBlockFrostApi, BitQueryCardanoApi]
    tx_details_apis = [CardanoPolarisGraphqlApi, BitQueryCardanoApi, CardanoBlockFrostApi, CardanoGraphqlApi]
    address_txs_apis = [CardanoBlockFrostApi, CardanoGraphqlApi]
    block_txs_apis = [CardanoPolarisGraphqlApi, CardanoGraphqlApi, CardanoBlockFrostApi]
    block_head_apis = [CardanoGraphqlApi, BitQueryCardanoApi, CardanoBlockFrostApi]
    symbol = 'ADA'
