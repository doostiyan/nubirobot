import random
from django.conf import settings
from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.cosmosnode import CosmosNodeApi, CosmosNodeParser, CosmosNodeValidator


class AtomNodeValidator(CosmosNodeValidator):
    symbol = 'ATOM'
    get_txs_keyword = 'tx_responses'
    valid_transfer_types = ['/cosmos.bank.v1beta1.MsgSend', '/cosmos.bank.v1beta1.MsgMultiSend']


class AtomNodeParser(CosmosNodeParser):
    validator = AtomNodeValidator
    precision = 6
    symbol = 'ATOM'
    currency = Currencies.atom
    get_txs_keyword = 'tx_responses'


class AtomNode(CosmosNodeApi):
    """
    restApi Providers: https://www.mintscan.io/cosmos/info
    """
    parser = AtomNodeParser
    symbol = 'ATOM'
    cache_key = 'atom'
    _base_url = ''
    supported_requests = {
        'get_balance': '/cosmos/bank/v1beta1/balances/{address}/by_denom?denom=uatom',
        'get_block_head': '/cosmos/base/tendermint/v1beta1/blocks/latest',
        'get_address_txs': '/cosmos/tx/v1beta1/txs?pagination.limit=30'
                            '&pagination.offset=0&orderBy=ORDER_BY_DESC&'
                            'query=transfer.{tx_query_direction}%3D%27{address}%27',
        'get_tx_details': '/cosmos/tx/v1beta1/txs/{tx_hash}',
    }
    main_denom = 'uatom'
    blockchain_name = 'cosmos'
    chain_id = 'cosmoshub-4'


class AtomscanNode(AtomNode):
    _base_url = 'https://cosmos.lcd.atomscan.com'


class CosmosNetworkNode(AtomNode):
    # not recommended since slow and not reliable response
    _base_url = 'https://cosmos-lcd.easy2stake.com'


class FigmentNode(AtomNode):
    _base_url = 'https://cosmoshub-4--lcd--full.datahub.figment.io'
    rate_limit = 1.15  # 3m request per month, 10 request per second, 10 concurrent request

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.FIGMENT_API_KEY)

    def get_header(self):
        return {
            "Authorization": self.get_api_key()
        }


class AtomAllthatnode(AtomNode):
    _base_url = 'https://cosmos-mainnet-rpc.allthatnode.com:1317'
    supported_requests = {
        'get_balance': '/cosmos/bank/v1beta1/balances/{address}',
        'get_block_head': '/blocks/latest',
        'get_tx_details': '/cosmos/tx/v1beta1/txs/{tx_hash}',
        'get_staked_balance': '/cosmos/staking/v1beta1/delegations/{address}',
        'get_staking_reward': '/cosmos/distribution/v1beta1/delegators/{address}/rewards',
        'get_address_txs': '/cosmos/tx/v1beta1/txs?pagination.limit=30'
                            '&pagination.offset=0&orderBy=ORDER_BY_DESC&'
                            'events=transfer.{tx_query_direction}%3D%27{address}%27',
    }


class AtomGetblockNode(AtomNode):
    """
    API docs: https://getblock.io/nodes/atom/
    """
    _base_url = 'https://atom.getblock.io/mainnet'
    rate_limit = 2.17  # 40000 request per day

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.ATOM_GETBLOCK_APIKEY)

    def get_header(self):
        return {
            'x-api-key': self.get_api_key()
        }


class PupmosNode(AtomNode):
    _base_url = 'https://api-cosmoshub.pupmos.network'


class LavenderFiveNode(AtomNode):
    _base_url = 'https://cosmoshub-api.lavenderfive.com'
