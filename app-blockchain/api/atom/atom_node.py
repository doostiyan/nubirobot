import random
from abc import ABC

from django.conf import settings

from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.cosmos_node import CosmosNode


class AtomNode(CosmosNode, ABC):
    """
    restApi Providers: https://www.mintscan.io/cosmos/info
    """
    symbol = 'ATOM'
    currency = Currencies.atom
    cache_key = 'atom'
    main_denom = 'uatom'
    blockchain_name = 'cosmos'
    _base_url = ''
    chain_id = 'cosmoshub-4'
    valid_transfer_types = ['/cosmos.bank.v1beta1.MsgSend', '/cosmos.bank.v1beta1.MsgMultiSend']
    get_txs_keyword = 'tx_responses'
    supported_requests = {
        'get_balance': '/cosmos/bank/v1beta1/balances/{address}/by_denom?denom={denom}',
        'get_block_head': '/cosmos/base/tendermint/v1beta1/blocks/latest',
        'get_transactions': '/cosmos/tx/v1beta1/txs?pagination.limit={pagination_limit}'
                            '&pagination.offset={pagination_offset}&orderBy=ORDER_BY_DESC&'
                            'events=transfer.{tx_query_direction}%3D%27{address}%27',
        'get_transaction': '/cosmos/tx/v1beta1/txs/{tx_hash}',
    }


class AtomscanNode(AtomNode):
    # _base_url = 'https://cosmos.lcd.atomscan.com'
    # _base_url = 'https://api-cosmoshub.pupmos.network'
    _base_url = 'https://atom.getblock.io/24e54120-9947-405b-9566-ccf61e0ab760/mainnet/'

    def get_name(self):
        return 'scan_api'


class CosmosNetworkNode(AtomNode):
    # not recommended since slow and not reliable response
    # _base_url = 'https://api.cosmos.network'
    _base_url = 'https://cosmos-lcd.easy2stake.com'
    USE_PROXY = True if not settings.IS_VIP else False

    def get_name(self):
        return 'cosmos_network_api'


class FigmentNode(AtomNode):
    _base_url = 'https://cosmoshub-4--lcd--full.datahub.figment.io'
    rate_limit = 1.15  # 3m request per month, 10 request per second, 10 concurrent request

    def get_name(self):
        return 'figment_api'

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
        'get_transaction': '/cosmos/tx/v1beta1/txs/{tx_hash}',
        'get_staked_balance': '/cosmos/staking/v1beta1/delegations/{address}',
        'get_staking_reward': '/cosmos/distribution/v1beta1/delegators/{address}/rewards',
        'get_transactions': '/cosmos/tx/v1beta1/txs?pagination.limit={pagination_limit}'
                            '&pagination.offset={pagination_offset}&orderBy=ORDER_BY_DESC&'
                            'events=transfer.{tx_query_direction}%3D%27{address}%27',
    }

    def get_name(self):
        return 'allthatnode'


class AtomGetblockNode(AtomNode):
    """
    API docs: https://getblock.io/nodes/atom/
    """
    _base_url = 'https://atom.getblock.io/mainnet'
    rate_limit = 2.17  # 40000 request per day

    def get_name(self):
        return 'atom_getblocks'

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.ATOM_GETBLOCK_APIKEY)

    def get_header(self):
        return {
            'x-api-key': self.get_api_key()
        }


class PupmosNode(AtomNode):
    _base_url = 'https://api-cosmoshub.pupmos.network'

    def get_name(self):
        return 'atom_pupmos'


class LavenderFiveNode(AtomNode):
    _base_url = 'https://cosmoshub-api.lavenderfive.com'

    def get_name(self):
        return 'lavenderfive_node'
