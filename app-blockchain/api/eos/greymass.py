import json
from decimal import Decimal

from exchange.base.parsers import parse_iso_date
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


def parse_quantity(q):
    if not q or not q.endswith(' EOS'):
        return None
    return Decimal(q[:-4])


class GreymassAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: EOS
    """

    _base_url = 'https://eos.greymass.com'
    testnet_url = 'https://api.jungle.alohaeos.com'
    symbol = 'EOS'

    active = True

    rate_limit = 0
    max_items_per_page = 1000
    page_offset_step = None
    confirmed_num = None
    PRECISION = 4
    XPUB_SUPPORT = False

    supported_requests = {
        'get_transactions': '/v1/history/get_actions',
    }

    def get_name(self):
        return 'greymass_api'

    def get_txs(self, address, tx_direction_filter=''):
        self.validate_address(address)

        response = self.request('get_transactions', body=json.dumps({'account_name': address, 'offset': -40}))
        if response is None:
            raise APIError("[GreymassAPI][Get Transactions] response is none")
        txs = response.get('actions')
        last_block = int(response.get('last_irreversible_block'))
        transactions = []
        if not txs:
            return []
        for tx in txs:
            parsed_tx = self.parse_tx(tx, address, last_block, tx_direction_filter)
            if parsed_tx is not None:
                transactions.append(parsed_tx)
        return transactions

    def parse_tx(self, tx, address, last_block, tx_direction_filter=''):

        action_trace = tx.get('action_trace') or {}
        act = action_trace.get('act') or {}
        if act.get('name') != 'transfer':
            return
        if act.get('account') != 'eosio.token':
            return
        act_data = act.get('data') or {}
        if not isinstance(act_data, dict):
            return
        if action_trace.get('receiver') != act_data.get('to'):
            return

        # checking transaction authorization
        authorizations = act.get("authorization")
        for auth in authorizations:
            account_from = act_data.get('from')
            if account_from == auth.get('actor') and auth.get('permission') in ['active', 'owner']:
                break
        else:
            return

        raw_value = parse_quantity(act_data.get('quantity'))
        if not raw_value:
            return
        elif raw_value < Decimal(0.0005):
            return
        else:
            if act_data.get('from') == address:  # is send.
                value = -1 * raw_value
            elif act_data.get('to') == address:  # is receive
                value = raw_value
            else:
                value = Decimal(0)

        # checking transaction memo
        memo = act_data.get('memo')
        if memo is None or memo == '':
            if not tx_direction_filter:
                return

        confirmations = last_block - tx.get('block_num')
        is_double_spend = confirmations >= 0 and not tx.get('irreversible')
        return {
            'hash': action_trace.get('trx_id'),
            'date': parse_iso_date(tx.get('block_time') + 'Z'),
            'amount': value,
            'confirmations': confirmations,
            'is_double_spend': is_double_spend,
            'block': tx.get('block_num'),
            'memo': memo,
            'raw': tx,
        }
