from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
    from blockchain.parsers import parse_iso_date
else:
    from exchange.base.models import Currencies
    from exchange.base.parsers import parse_iso_date

from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.utils import BlockchainUtilsMixin, ParseError


class BnbMintscan(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: bnb
    API docs:
    Explorer: https://binance.mintscan.io/
    """

    _base_url = 'https://api-binance-mainnet.cosmostation.io/v1'
    symbol = 'BNB'
    currency = Currencies.bnb
    PRECISION = 8
    valid_transfer_types = ['cosmos-sdk/Send']

    supported_requests = {
        'get_tx_details': '/txs/{tx_hash}',
        'get_block_head': '/blocks?limit=1'
    }

    @staticmethod
    def get_header():
        return {'Referer': 'https://binance.mintscan.io/'}

    def parse_tx_details(self, tx, tx_hash=None):
        is_valid = self.validate_transaction_detail(tx)
        if not is_valid:
            return {
                'success': False,
            }
        success = tx.get('result')
        memo = tx.get('memo') or ''
        details = tx.get('messages')[0]
        confirmations = self.get_block_head() - tx.get('height') + 1
        transfers = [{
            'type': 'transfer',
            'symbol': self.symbol,
            'currency': self.currency,
            'from': details.get('value').get('inputs')[0].get('address'),
            'to': details.get('value').get('outputs')[0].get('address'),
            'token': None,
            'value': self.from_unit(int(details.get('value').get('inputs')[0].get('coins')[0].get('amount')),
                                    precision=8),
            'is_valid': is_valid,
        }]
        tx_details = {
            'hash': tx_hash,
            'success': success,
            'inputs': [],
            'outputs': [],
            'transfers': transfers,
            'block': tx.get('height'),
            'memo': memo,
            'confirmations': confirmations,
            'fees': 0,
            'date': parse_iso_date(tx.get('timestamp')),
            'raw': tx
        }
        return tx_details

    def validate_transaction_detail(self, details):
        try:
            success = int(details.get('code')) == 0 and details.get('result')
            if not success:
                return False
            msgs = details.get('messages')
            if len(msgs) != 1:  # as we don't support multi-msg yet
                return False
            msg_type = msgs[0].get('type')
            if msg_type not in self.valid_transfer_types:
                return False
            tx_coins_list = msgs[0].get('value').get('inputs')[0].get('coins')
            if len(tx_coins_list) != 1:  # it must not happen because we already skipped multi-send tx
                return False
            from_address = msgs[0].get('value').get('inputs')[0].get('address').casefold()
            to_address = msgs[0].get('value').get('outputs')[0].get('address').casefold()
            if from_address == to_address:
                return False
            value = self.from_unit(int(msgs[0].get('value').get('inputs')[0].get('coins')[0].get('amount')),
                                   precision=8)
            if not self.validate_tx_amount(value):
                return False
            tx_denom = tx_coins_list[0].get('denom').casefold()
            if tx_denom != self.symbol.casefold():  # is denom excepted symbol
                return False
        except AttributeError:
            raise ParseError(f'{self.symbol} parsing error Tx is {details}.')
        return True

    def parse_block_head(self, response):
        return response.get('data')[0].get('height')
