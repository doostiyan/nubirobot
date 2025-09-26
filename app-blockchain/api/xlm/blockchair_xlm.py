from decimal import Decimal

from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class XLMBlockchairAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: XLM(stellar)
    API Docs(not only stellar): https://blockchair.com/api/docs#link_M2
    """
    _base_url = 'https://api.blockchair.com'
    symbol = 'XLM'
    currency = Currencies.xlm
    active = True
    PRECISION = 7
    USE_PROXY = False

    supported_requests = {
        'get_tx_details': '/stellar/raw/transaction/{tx_hash}?operations=true',
        'block_head': '/stellar/stats',
    }

    def get_name(self):
        return 'blockchair_api'

    def get_block_head(self):
        response = self.request('block_head')
        if response is None:
            raise APIError('Response is None')
        return response.get('data').get('best_ledger_height')

    def get_tx_details(self, tx_hash):
        try:
            response = self.request('get_tx_details', tx_hash=tx_hash)
        except APIError:
            raise APIError('XLM blockchair API [Get Transaction details] unsuccessful')

        tx = self.parse_tx_details(response, tx_hash)
        tx['confirmations'] = self.get_block_head() - tx.get('block')
        return tx

    def parse_tx_details(self, data, tx_hash):
        success = data.get('data').get(tx_hash).get('transaction').get('successful')
        ledger = data.get('data').get(tx_hash).get('transaction').get('ledger')
        transaction = data.get('data').get(tx_hash).get('transaction')
        transfers = []
        for operation in data.get('data').get(tx_hash).get('operations'):
            if all([operation.get('type') == 'payment',
                    operation.get('asset_type') == 'native',
                    operation.get('type_i') == 1,
                    operation.get('source_account') == operation.get('from'),
                    not (operation.get('asset_issuer') or operation.get('asset_code'))]):
                transfers.append({
                    'type': 'MainCoin',
                    'success': operation.get('transaction_successful'),
                    'is_valid': True,
                    'from': operation.get('from'),
                    'to': operation.get('to'),
                    'currency': self.currency,
                    'value': Decimal(operation.get('amount')),
                })
        return {
            'hash': tx_hash,
            'success': success,
            'is_valid': True if transfers else False,
            'transfers': transfers,
            'memo': transaction.get('memo') or '',
            'block': ledger,
            'fees': self.from_unit(int(transaction.get('max_fee'))),
            'date': parse_iso_date(data.get('data').get(tx_hash).get('transaction').get('created_at')),
            'raw': data,
        }
