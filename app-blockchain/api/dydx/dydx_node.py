from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.cosmosnode import CosmosNodeApi, CosmosNodeParser, CosmosNodeValidator


class DydxNodeValidator(CosmosNodeValidator):
    symbol = 'DYDX'
    get_txs_keyword = 'tx_responses'
    valid_transfer_types = ['/cosmos.bank.v1beta1.MsgSend']


class DydxNodeParser(CosmosNodeParser):
    validator = DydxNodeValidator
    precision = 18
    symbol = 'DYDX'
    currency = Currencies.dydx
    get_txs_keyword = 'tx_responses'


class DydxNode(CosmosNodeApi):
    """
    restApi Providers: https://www.mintscan.io/cosmos/info
    """
    parser = DydxNodeParser
    symbol = 'DYDX'
    cache_key = 'dydx'
    _base_url = ''
    supported_requests = {
        'get_balance': '/cosmos/bank/v1beta1/balances/{address}/by_denom?denom=uatom',
        'get_block_head': '/cosmos/base/tendermint/v1beta1/blocks/latest',
        'get_address_txs': '/cosmos/tx/v1beta1/txs?pagination.limit=30'
                           '&pagination.offset=0&orderBy=ORDER_BY_DESC&'
                           'query=transfer.{tx_query_direction}%3D%27{address}%27',
        'get_tx_details': '/cosmos/tx/v1beta1/txs/{tx_hash}',
    }
    main_denom = 'adydx'
    blockchain_name = 'dydx'
    chain_id = 'dydx-mainnet-1'


class DydxEcostake(DydxNode):
    _base_url = 'https://rest-dydx.ecostake.com'


class DydxPublicRpc(DydxNode):
    _base_url = 'https://dydx-rest.publicnode.com'


class DydxKingnodes(DydxNode):
    _base_url = 'https://dydx-ops-rest.kingnodes.com'


class DydxEnigma(DydxNode):
    _base_url = 'https://dydx-dao-rpc.enigma-validator.com'


class DydxPolkachu(DydxNode):
    _base_url = 'https://dydx-dao-api.polkachu.com'
