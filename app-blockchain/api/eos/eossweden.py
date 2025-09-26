import json
from decimal import Decimal

from django.conf import settings

from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


def parse_quantity(q):
    if not q or not q.endswith(' EOS'):
        return None
    return Decimal(q[:-4])


class EosswedenAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    coins: EOS
    """

    # _base_url = 'https://api.eossweden.org'
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

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0'
    } if not settings.IS_VIP else {
        'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/109.0'
    }

    supported_requests = {
        'get_transactions': '/v2/history/get_actions?account={address}&limit=50',
        'get_balance': '/v1/chain/get_account',
        'get_tx_details': '/v2/history/get_transaction?id={tx_hash}',
    }

    def get_name(self):
        return 'eossweden_api'

    def get_txs(self, address, tx_direction_filter=''):
        self.validate_address(address)

        response = self.request('get_transactions', address=address, headers=self.headers)
        if response is None:
            raise APIError("[EosswedenAPI][Get Transactions] response is none")

        txs = response.get('actions')
        last_block = int(response.get('lib'))
        transactions = []
        if not txs:
            return []
        for tx in txs:
            parsed_tx = self.parse_tx(tx, address, last_block, tx_direction_filter)
            if parsed_tx is not None:
                transactions.append(parsed_tx)
        return transactions

    def parse_tx(self, tx, address, last_block, tx_direction_filter=''):

        act = tx.get('act') or {}
        if act.get('name') != 'transfer':
            return
        if act.get('account') != 'eosio.token':
            return
        act_data = act.get('data') or {}
        if not isinstance(act_data, dict):
            return

        # checking transaction authorization
        authorizations = act.get('authorization')
        for auth in authorizations:
            account_from = act_data.get('from')
            if account_from == auth.get('actor') and auth.get('permission') in ['active', 'owner']:
                break
        else:
            return

        if act_data.get('symbol') != "EOS":
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
                return

        # checking transaction memo
        memo = act_data.get('memo')
        if memo is None or memo == '':
            if not tx_direction_filter:
                return

        confirmations = last_block - tx.get('block_num')
        is_double_spend = confirmations >= 0 and not tx.get('irreversible')
        return {
            'hash': tx.get('trx_id'),
            'date': parse_iso_date(tx.get('@timestamp') + 'Z'),
            'amount': value,
            'confirmations': confirmations,
            'is_double_spend': is_double_spend,
            'block': tx.get('block_num'),
            'memo': memo,
            'raw': tx,
        }

    def get_balance(self, address):
        self.validate_address(address)

        response = self.request('get_balance', body=json.dumps({'account_name':address}), force_post=True, headers=self.headers)
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

    def get_tx_details(self, tx_hash):
        response = self.request('get_tx_details', tx_hash=tx_hash, headers=self.headers)
        if response is None:
            raise APIError("[EosnAPI][Get Tx Details] response is none")
        return self.parse_tx_details(response)

    def parse_tx_details(self, info):
        actions = info.get('actions')
        transfers = []
        is_valid = False
        action = None
        memo = ''
        success = True
        if not actions:
            return {
                'hash': info.get('trx_id'),
                'success': info.get('executed'),
                'is_valid': False,
                'inputs': [],
                'outputs': [],
                'transfers': transfers,
                'raw': info
            }
        for action in actions:
            is_valid = False
            act = action.get('act') or {}
            if act.get('name') == 'onerror':
                success = False
                continue
            if act.get('name') != 'transfer' or act.get('account') != 'eosio.token':
                continue
            act_data = act.get('data')
            if act_data is None or not isinstance(act_data, dict):
                continue

            # checking transaction authorization
            authorizations = act.get('authorization')
            for auth in authorizations:
                account_from = act_data.get('from')
                if account_from == auth.get('actor') and auth.get('permission') in ['active', 'owner']:
                    break
            else:
                continue

            if act_data.get('symbol') != 'EOS':
                continue
            quantity = act_data.get('quantity')
            if not quantity or not quantity.endswith(' EOS'):
                continue
            value = Decimal(quantity[:-4])
            if value > Decimal(0.0005):
                is_valid = True

            # checking transaction memo
            memo = act_data.get('memo') or ''

            if is_valid:
                transfers.append({
                    'from': act_data.get('from'),
                    'to': act_data.get('to'),
                    'currency': self.currency,
                    'value': value,
                    'is_valid': is_valid,
                })
        block_num = action.get('block_num')
        # ** request does not contain block head so confirmations and is_double_spend fields is not available # TODO
        # confirmations = last_block - block_num
        # is_double_spend = confirmations >= 0 and not action.get('irreversible')
        date = parse_iso_date(action.get('@timestamp') + 'Z')
        if not transfers:
            is_valid = False
        return {
            'hash': info.get('trx_id'),
            'success': info.get('executed') and success,
            'is_valid': is_valid,
            'inputs': [],
            'outputs': [],
            'transfers': transfers,
            'block': block_num,
            'date': date,
            'memo': memo,
            'raw': info
        }
