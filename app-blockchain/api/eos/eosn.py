import json
from decimal import Decimal

from exchange.base.models import Currencies
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


def parse_quantity(q):
    if not q or not q.endswith(' EOS'):
        return None
    return Decimal(q[:-4])


class EosrioAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: EOS
    """

    # _base_url = 'https://api.eossweden.org'
    # _base_url = 'https://api.eosn.io'
    _base_url = 'https://eos.eosusa.io'
    testnet_url = 'https://jungle.eosn.io'
    symbol = 'EOS'
    currency = Currencies.eos

    active = True

    rate_limit = 0
    max_items_per_page = 1000
    page_offset_step = None
    confirmed_num = None
    PRECISION = 4
    XPUB_SUPPORT = False
    
    USE_PROXY = False

    supported_requests = {
        'get_balance': '/v1/chain/get_account',
        'get_tx_details': '/v2/history/get_transaction?id={tx_hash}',
    }

    def get_name(self):
        return 'eosrio_api'

    def get_balance(self, address):
        self.validate_address(address)

        response = self.request('get_balance', body=json.dumps({'account_name':address}), force_post=True)
        if response is None:
            raise APIError("[EosnAPI][Get Balance] response is none")
        if response.get('account_name') != address:
            return None
        balance = parse_quantity(response.get('core_liquid_balance'))
        if balance is None:
            return None
        return {
            'amount': balance,
        }
