from decimal import Decimal

from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


# This is down
class EtccoopexplorerAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: ETC
    """

    _base_url = 'https://classic.etccoopexplorer.com/api'
    symbol = 'ETC'

    active = True

    rate_limit = 0
    max_items_per_page = 1000
    page_offset_step = None
    confirmed_num = None
    PRECISION = 18
    XPUB_SUPPORT = False

    supported_requests = {
        'get_balances': '?module=account&action=balancemulti&address={addresses}',
    }

    def get_name(self):
        return 'etccoopexplorer_api'

    def get_balances(self, addresses):
        # TODO This function has not been tested as the api does not response
        for address in addresses:
            self.validate_address(address)
        joined_addresses = ','.join(addresses)
        response = self.request('get_balances', addresses=joined_addresses)
        if response is None:
            raise APIError("[EtccoopexplorerAPI][Get Balances] response is None")

        if response.get('status') != '1' or response.get('message') == 'ok':
            raise APIError("[EtccoopexplorerAPI][Get Balances] unsuccessful")
        if response.get('result') is None:
            raise APIError("[EtccoopexplorerAPI][Get Balances] result is None")
        balances = []
        address_index = 0
        if not addresses:
            return None
        for info in addresses.get('result'):
            if info.get('account').lower() != addresses[address_index].lower():
                continue
            balance = info.get('balance')
            if not balance:
                continue
            balance = Decimal(balance) / Decimal(1e18)
            balances.append({
                'address': addresses[address_index],
                'amount': balance,
            })
            address_index += 1
        return balances
