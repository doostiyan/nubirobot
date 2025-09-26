import datetime
import time
from decimal import Decimal

import pytz
from django.conf import settings
from exchange.base.logging import log_event, report_event, report_exception
from exchange.base.models import Currencies
from exchange.base.parsers import parse_iso_date
from exchange.blockchain.bep20 import Bep20BlockchainInspector
from exchange.blockchain.metrics import metric_incr
from exchange.blockchain.models import CurrenciesNetworkName, Transaction


class EOSBlockchainInspector(Bep20BlockchainInspector):
    currency = Currencies.eos
    currency_list = [Currencies.eos]

    get_balance_method = {
        CurrenciesNetworkName.EOS: 'get_wallets_balance_eos',
        CurrenciesNetworkName.BSC: 'get_wallets_balance_bsc',
    }

    get_transactions_method = {
        CurrenciesNetworkName.EOS: 'get_wallet_transactions_eos',
        CurrenciesNetworkName.BSC: 'get_wallet_transactions_bsc',
    }

    get_transaction_details_method = {
        CurrenciesNetworkName.EOS: 'get_transaction_details_eos',
        CurrenciesNetworkName.BSC: 'get_transaction_details_bsc',
    }

    @classmethod
    def parse_quantity(cls, q):
        if not q or not q.endswith(' EOS'):
            return None
        return Decimal(q[:-4])

    @classmethod
    def parse_actions_v2(cls, info, address):
        actions = info.get('actions')
        last_block = int(info.get('lib'))
        transactions = []

        if not actions:
            return []
        for action in actions:
            act = action.get('act') or {}
            if act.get('name') != 'transfer':
                continue
            if act.get('account') != 'eosio.token':
                continue
            act_data = act.get('data') or {}
            if not isinstance(act_data, dict):
                continue

            # checking transaction authorization
            authorizations = act.get('authorization')
            for auth in authorizations:
                account_from = act_data.get('from')
                if account_from == auth.get('actor') and auth.get('permission') in ['active', 'owner']:
                    break
            else:
                continue

            if act_data.get('symbol') != "EOS":
                continue

            raw_value = cls.parse_quantity(act_data.get('quantity'))
            if not raw_value:
                continue
            elif raw_value < Decimal(0.0005):
                continue
            else:
                if act_data.get('from') == address:  # is send.
                    value = -1 * raw_value
                elif act_data.get('to') == address:  # is receive
                    value = raw_value
                else:
                    continue

            # checking transaction memo
            memo = act_data.get('memo')
            if memo is None or memo == '':
                continue

            confirmations = last_block - action.get('block_num')
            is_double_spend = confirmations >= 0 and not action.get('irreversible')
            transactions.append(Transaction(
                address=address,
                from_address=[act_data.get('from')],
                hash=action.get('trx_id'),
                timestamp=parse_iso_date(action.get('@timestamp') + 'Z'),
                value=value,
                confirmations=confirmations,
                is_double_spend=is_double_spend,
                block=action.get('block_num'),
                tag=memo,
                details=action,
            ))
        return transactions

    @classmethod
    def parse_actions(cls, info, address, return_withdraws=False):
        actions = info.get('actions')
        last_block = int(info.get('last_irreversible_block'))
        transactions = []

        if not actions:
            return []
        for action in actions:
            action_trace = action.get('action_trace') or {}
            act = action_trace.get('act') or {}
            if act.get('name') != 'transfer':
                continue
            if act.get('account') != 'eosio.token':
                continue
            act_data = act.get('data') or {}
            if not isinstance(act_data, dict):
                continue
            if action_trace.get('receiver') != act_data.get('to'):
                continue

            # checking transaction authorization
            authorizations = act.get("authorization")
            for auth in authorizations:
                account_from = act_data.get('from')
                if account_from == auth.get('actor') and auth.get('permission') in ['active', 'owner']:
                    break
            else:
                continue

            raw_value = cls.parse_quantity(act_data.get('quantity'))
            if not raw_value:
                continue
            elif raw_value < Decimal(0.0005):
                continue
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
                if not return_withdraws:
                    continue

            confirmations = last_block - action.get('block_num')
            is_double_spend = confirmations >= 0 and not action.get('irreversible')
            transactions.append(Transaction(
                address=address,
                from_address=[act_data.get('from')],
                hash=action_trace.get('trx_id'),
                timestamp=parse_iso_date(action.get('block_time') + 'Z'),
                value=value,
                confirmations=confirmations,
                is_double_spend=is_double_spend,
                block=action.get('block_num'),
                tag=memo,
                details=action,
            ))
        return transactions

    @classmethod
    def get_wallets_balance_eos(cls, address_list, raise_error=False):
        """ Get EOS account balance
        """
        time.sleep(1)
        balances = []
        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            explorer_url = 'https://jungle.eosn.io'
        else:
            explorer_url = 'https://api.eosn.io'
        explorer_url += '/v1/chain/get_account'
        for address in address_list:
            try:
                api_response = cls.get_session().post(explorer_url, json={
                    'account_name': address,
                }, timeout=30)
                api_response.raise_for_status()
                info = api_response.json()
            except Exception as e:
                if raise_error:
                    raise e
                metric_incr('api_errors_count', labels=['eos', 'jungle'])
                print('Failed to get EOS wallet balance from API: {}'.format(str(e)))
                # report_event('EOSN API Error')
                return None
            if info.get('account_name') != address:
                continue
            balance = cls.parse_quantity(info.get('core_liquid_balance'))
            if balance is None:
                continue
            balances.append({
                'address': address,
                'received': balance,
                'sent': Decimal('0'),
                'balance': balance,
                'unconfirmed': Decimal('0'),
            })
        return balances

    @classmethod
    def get_wallet_transactions_greymass(cls, address, return_withdraws=False, raise_error=False):
        time.sleep(1)
        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            explorer_url = 'https://api.jungle.alohaeos.com'
        else:
            explorer_url = 'https://eos.greymass.com'
        explorer_url += '/v1/history/get_actions'
        try:
            api_response = cls.get_session().get(explorer_url, json={
                'account_name': address,
                'offset': -40,
            }, timeout=60)
            api_response.raise_for_status()
            info = api_response.json()
        except Exception as e:
            if raise_error:
                raise e
            metric_incr('api_errors_count', labels=['eos', 'greymass'])
            print('Failed to get EOS wallet transactions from API: {}'.format(str(e)))
            return None
        transactions = cls.parse_actions(info, address, return_withdraws=return_withdraws) or []
        return transactions

    @classmethod
    def get_wallet_transactions_eossweden(cls, address, raise_error=False):
        time.sleep(1)
        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            explorer_url = 'https://jungle.eosn.io'
        else:
            explorer_url = 'https://api.eosrio.io'
        explorer_url += '/v2/history/get_actions?account={}&limit=50'.format(address)
        try:
            api_response = cls.get_session().get(explorer_url, timeout=60)
            api_response.raise_for_status()
            info = api_response.json()
        except Exception as e:
            if raise_error:
                raise e
            metric_incr('api_errors_count', labels=['eos', 'eosrio'])
            print('[EOSSWEDEN] Failed to get EOS wallet transactions from API: {}'.format(str(e)))
            return None
        transactions = cls.parse_actions_v2(info, address) or []
        return transactions

    @classmethod
    def get_wallet_transactions_eos(cls, address, network=None):
        return cls.get_wallet_transactions_greymass(address)

    @classmethod
    def verify_transaction(cls, transaction: Transaction) -> bool:
        tx_hash = transaction.hash

        if cls.TESTNET_ENABLED and settings.USE_TESTNET_BLOCKCHAINS:
            return True
        else:
            explorer_url = 'https://www.api.bloks.io/dfuse?type=fetch_transaction&id={}'
            greymass_url = 'https://eos.greymass.com/v1/history/get_transaction'

        info = None
        get_data_from_bloks_io = False
        try:
            cls.get_session().headers = {'Content-Type': 'application/json'}
            api_response = cls.get_session().get(url=explorer_url.format(tx_hash), timeout=60)
            api_response.raise_for_status()
            info = api_response.json()
            get_data_from_bloks_io = True
        except Exception as e:
            metric_incr('api_errors_count', labels=['eos', 'bloksio'])
            print('Verify Transaction: Failed to get EOS transaction from bloks.io API: {}'.format(str(e)))

        if not get_data_from_bloks_io:
            try:
                json = {"id": tx_hash, "block_num_hint": 0}
                cls.get_session().headers = {'Content-Type': 'application/json'}
                api_response = cls.get_session().post(url=greymass_url, json=json, timeout=60)
                api_response.raise_for_status()
                info = api_response.json()
            except Exception as e:
                metric_incr('api_errors_count', labels=['eos', 'greymass'])
                print('Verify Transaction: Failed to get EOS transaction from greymass API: {}'.format(str(e)))
                return False

        if info is None:
            return False

        # check hash
        if info.get('id') != tx_hash:
            return False

        tx_from = transaction.details.get('action_trace').get('act').get('data').get('from')
        tx_to = transaction.details.get('action_trace').get('act').get('data').get('to')

        if get_data_from_bloks_io:
            actions = info.get('execution_trace').get('action_traces')
            block_num = info.get('execution_trace').get('block_num')
        else:
            actions = info.get('trx').get('trx').get('actions')
            block_num = info.get('block_num')

        error_message = []
        for action in actions:
            if get_data_from_bloks_io:
                data = action.get('act').get('data') or {}
                account = action.get('act').get('account')
                name = action.get('act').get('name')
                auth = action.get('act').get('authorization')
            else:
                data = action.get('data')
                account = action.get('account')
                name = action.get('name')
                auth = action.get('authorization')

            # check address
            if data.get('from') != tx_from:
                error_message.append('different sender addresses')
                continue
            elif data.get('to') != tx_to:
                error_message.append('different receiver addresses')
                continue

            # check tag (memo)
            if data.get('memo') == '' or data.get('memo') is None:
                if transaction.tag is not None:
                    error_message.append('different memo')
                    continue
            elif data.get('memo') != transaction.tag:
                error_message.append('different memo')
                continue

            # check address and value
            tx_value = data.get('quantity')
            tx_value = cls.parse_quantity(tx_value)
            if data.get('to') == transaction.address:
                if tx_value != transaction.value:
                    error_message.append('different receiving value')
                    continue
            elif data.get('from') == transaction.address:
                if -1 * tx_value != transaction.value:
                    error_message.append('different sending value')
                    continue
            else:
                if tx_value != Decimal(0):
                    error_message.append('value is not zero')
                    continue

            # check block number
            if block_num != transaction.block:
                error_message.append('different block number')
                continue

            # check account and action name
            if account != 'eosio.token':
                error_message.append('invalid account (account should be "eosio.token")')
                continue
            elif name != 'transfer':
                error_message.append('invalid action name (action name should be "transfer")')
                continue

            # check authorization
            if auth is None or len(auth) > 1:
                error_message.append('invalid authorization: auth is None or auth length is greater than one')
                continue
            if auth[0].get('actor') != data.get('from') or auth[0].get('permission') != 'active':
                error_message.append('invalid authorization')
                continue

            return True

        print('Verify Transaction: Failed to Verify EOS Transaction: {}'.format(',  '.join(error_message)))
        return False

    @classmethod
    def get_wallet_withdraws(cls, address):
        all_txs = cls.get_wallet_transactions_greymass(address, return_withdraws=True)
        start_time = pytz.timezone('UTC').localize(datetime.datetime.utcnow()) - datetime.timedelta(hours=3)  # now -3 hours , UTC base because api outputs are in UTC
        withdraws = list(filter(lambda tx: tx.value < Decimal('0') and tx.timestamp > start_time, all_txs))
        return withdraws
