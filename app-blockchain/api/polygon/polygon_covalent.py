from decimal import Decimal

from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.covalenthq import CovalenthqAPI
from exchange.blockchain.contracts_conf import polygon_ERC20_contract_info, polygon_ERC20_contract_currency
from exchange.blockchain.utils import APIError


class PolygonCovalenthqAPI(CovalenthqAPI):

    _base_url = 'https://api.covalenthq.com/v1/137/'
    testnet_url = 'https://api.covalenthq.com/v1/80001/'
    symbol = 'MATIC'
    currency = Currencies.pol
    PRECISION = 18
    cache_key = 'matic'
    USE_PROXY = False

    def get_txs(self, address):
        txs = []
        response = self.request('get_transactions', address=address, api_key=self.get_api_key())
        if not response:
            raise APIError('[GetTransaction] Response is None.')
        if response.get('error'):
            raise APIError('[GetTransaction] Unsuccessful.')

        transactions = response.get('data', {}).get('items', [])
        block_head = self.get_block_head()
        for tx in transactions:
            if self.validate_transaction(tx):
                parsed_tx = self.parse_tx(tx, address, block_head)
                if parsed_tx:
                    txs.append(parsed_tx)
        return txs

    def validate_transaction(self, tx):
        value = int(tx.get('value'))
        log_events = tx.get('log_events')
        if tx.get('successful') and value != Decimal('0') and len(log_events) == 2:
            for log_event in log_events:
                if log_event.get('sender_address') != '0x0000000000000000000000000000000000001010':
                    return False
                if log_event.get('sender_name') != 'Matic Token':
                    return False
                if log_event.get('sender_contract_ticker_symbol') != 'MATIC':
                    return False
                if log_event.get('sender_contract_decimals') != 18:
                    return False
            return True
        return False

    @property
    def contract_currency_list(self):
        return polygon_ERC20_contract_currency.get(self.network)

    @property
    def contract_info_list(self):
        return polygon_ERC20_contract_info.get(self.network)
