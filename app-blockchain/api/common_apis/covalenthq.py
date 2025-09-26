import random
from decimal import Decimal

from django.conf import settings

from exchange.base.parsers import parse_iso_date
from exchange.blockchain.api.common_apis.blockscan import are_addresses_equal
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class CovalenthqAPI(NobitexBlockchainAPI, BlockchainUtilsMixin):
    """
    Covalent indexing and querying API.

    supported coins: FTM, Polygon

    API docs: https://www.covalenthq.com/docs/api
    """

    # There is a limit of 20 concurrent requests per seconds. But no limits on the volume of the API calls.
    rate_limit = 0
    currency: int

    supported_requests = {
        'get_balance': 'address/{address}/balances_v2/?&key={api_key}',
        'get_transactions': 'address/{address}/transactions_v3/?key={api_key}',
        'get_token_txs': 'address/{address}/transfers_v2/?&key={api_key}&contract-address={'
                         'contract_address}&page-number=0&page-size=25',
        'get_block_head': 'block_v2/latest/?&key={api_key}',
        'get_transaction': 'transaction_v2/{tx_hash}/?key={api_key}'
    }

    def get_name(self):
        return '{}_covalent'.format(self.symbol.lower())

    @property
    def contract_currency_list(self):
        return {}

    @property
    def contract_info_list(self):
        return {}

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.COVALENT_API_KEYS)

    def get_block_head(self):
        response = self.request('get_block_head', api_key=self.get_api_key())
        blocks = response.get('data').get('items')[-1]
        if not blocks or len(blocks) == 0:
            raise APIError('Invalid info(empty blockbook)')

        return blocks.get('height')

    def get_balance(self, address):

        response = self.request('get_balance', address=address, api_key=self.get_api_key())

        if not response:
            raise APIError('[GetBalance] Response is None.')
        if response.get('error'):
            raise APIError('[GetBalance] Unsuccessful.')

        return self.parse_balance(response, address)

    def get_token_balance(self, address, contracts_info):

        return self.get_balance(address)

    def parse_balance(self, data, address):
        balances = {}

        items = data.get('data').get('items')
        for item in items:
            if item.get('contract_ticker_symbol') == self.symbol:
                balances[self.currency] = {
                    'symbol': self.symbol,
                    'address': address,
                    'amount': self.from_unit(int(item.get('balance'))),
                }
            else:
                balance = item.get('balance')
                contract_address = item.get('contract_address')
                currency, contract_address = self.contract_currency(contract_address)
                if currency is None:
                    continue
                contract_info = self.contract_info(currency, contract_address)

                balances[currency] = {
                    'symbol': contract_info.get('symbol'),
                    'balance': self.from_unit(int(balance), contract_info.get('decimals')),
                    'address': address
                }
        return balances

    def contract_currency(self, token_address):
        currency_with_default_contract = self.contract_currency_list.get(token_address)
        if currency_with_default_contract:
            return currency_with_default_contract, None
        if token_address in CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.keys():
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(token_address, {}).get(
                'destination_currency'), token_address
        return None, None

    def contract_info(self, currency, contract_address=None):
        if contract_address and contract_address in CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.keys():
            return CurrenciesNetworkName.PSEUDO_NETWORKS_CONTRACTS.get(contract_address, {}).get('info')
        return self.contract_info_list.get(currency)

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
            if tx.get('successful') and not tx.get('log_events'):
                parsed_tx = self.parse_tx(tx, address, block_head)
                if parsed_tx:
                    txs.append(parsed_tx)
        return txs

    def parse_tx(self, tx, address, block_head):
        direction = 'incoming'

        value = self.from_unit(int(tx.get('value')))
        if value == 0:
            return

        from_address = tx.get('from_address')
        to_address = tx.get('to_address')
        if are_addresses_equal(from_address, address):
            # Transaction is from this address, so it is a withdraw
            value = -value
            direction = 'outgoing'
        elif not are_addresses_equal(to_address, address):
            # Transaction is not to this address, and is not a withdraw, so no deposit should be made
            #  this is a special case and should not happen, so we ignore such special transaction
            return

        elif are_addresses_equal(
            from_address, '0x70Fd2842096f451150c5748a30e39b64e35A3CdF') or are_addresses_equal(
            from_address, '0x491fe5F4724e642C90372B0B95b60c4aC8d13F1c') or are_addresses_equal(
            from_address, '0xB256caa23992e461E277CfA44a2FD72E2d6d2344') or are_addresses_equal(
            from_address, '0x06cC26db08674CbD9FF4d52444712E23cA3d046d') or are_addresses_equal(
            from_address, '0x4752B9bD4E73E2f52323E18137F0E66CDDF3f6C9'
        ):
            value = Decimal(0)

        return {
            self.currency: {
                'address': address,
                'hash': tx.get('tx_hash'),
                'from_address': [from_address],
                'to_address': to_address,
                'amount': value,
                'block': tx.get('block_height'),
                'date': parse_iso_date(tx.get('block_signed_at')),
                'confirmations': block_head - tx.get('block_height'),
                'direction': direction,
                'raw': tx,
                'memo': None
            }
        }

    def get_token_txs(self, address, contract_info, direction=''):
        response = self.request('get_token_txs', address=address, api_key=self.get_api_key(),
                                contract_address=contract_info.get('address'))
        if not response:
            raise APIError('[GetTokenTransaction] Response is None.')
        if response.get('error'):
            raise APIError('[GetTokenTransaction] Unsuccessful.')

        transactions = []
        txs = response.get('data', {}).get('items')
        if not txs:
            return []
        block_head = self.get_block_head()
        for tx in txs:
            if tx.get('successful') and len(tx.get('transfers')) == 1:
                parsed_tx = self.parse_token_tx(tx, address, block_head)
                if parsed_tx:
                    transactions.append(parsed_tx)
        return transactions

    def parse_token_tx(self, tx, address, block_head):
        direction = 'incoming'

        if not tx.get('transfers'):
            return

        for info in tx.get('transfers'):
            contract_address = info.get('contract_address')
            if info.get('method_calls'):
                return None
            if not info.get('transfer_type') or info.get('transfer_type') not in ['IN', 'OUT']:
                return None
            currency, _ = self.contract_currency(contract_address)
            if currency is None:
                return None

            contract_info = self.contract_info(currency, contract_address)

            value = self.from_unit(int(info.get('delta')), contract_info.get('decimals'))
            from_address = info.get('from_address')
            to_address = info.get('to_address')
            if are_addresses_equal(from_address, address):
                # Transaction is from this address, so it is a withdraw
                value = -value
                direction = 'outgoing'
            elif not are_addresses_equal(to_address, address):
                # Transaction is not to this address, and is not a withdraw, so no deposit should be made
                #  this is a special case and should not happen, so we ignore such special transaction.
                return

            elif are_addresses_equal(
                from_address, '0x70Fd2842096f451150c5748a30e39b64e35A3CdF') or are_addresses_equal(
                from_address, '0x491fe5F4724e642C90372B0B95b60c4aC8d13F1c') or are_addresses_equal(
                from_address, '0xB256caa23992e461E277CfA44a2FD72E2d6d2344') or are_addresses_equal(
                from_address, '0x06cC26db08674CbD9FF4d52444712E23cA3d046d') or are_addresses_equal(
                from_address, '0x4752B9bD4E73E2f52323E18137F0E66CDDF3f6C9'
            ):
                value = Decimal(0)

            if value != 0:
                return {
                    currency: {
                        'address': address,
                        'hash': tx.get('tx_hash'),
                        'from_address': [from_address],
                        'to_address': to_address,
                        'amount': value,
                        'block': tx.get('block_height'),
                        'date': parse_iso_date(tx.get('block_signed_at')),
                        'confirmations': block_head - tx.get('block_height'),
                        'direction': direction,
                        'raw': tx,
                        'memo': None
                    }
                }

    def get_tx_details(self, tx_hash):
        tx_hash = tx_hash if tx_hash.startswith('0x') else '0x' + tx_hash
        response = self.request('get_transaction', tx_hash=tx_hash, api_key=self.get_api_key())

        if not response:
            raise APIError('[GetTransactionDetails] Response is None.')
        if response.get('error'):
            raise APIError('[GetTransactionDetails] Unsuccessful.')

        tx_details = self.parse_tx_details(response.get('data').get('items')[0])
        return tx_details

    def parse_tx_details(self, tx):
        transfers = []
        fee = tx.get('gas_spent') * tx.get('gas_price')
        log_events = tx.get('log_events')
        if self.from_unit(int(tx.get('value'))) != Decimal('0') and not log_events:
            transfers.append({
                'type': 'MainCoin',
                'symbol': self.symbol,
                'currency': self.currency,
                'from': tx.get('from_address'),
                'to': tx.get('to_address'),
                'value': self.from_unit(int(tx.get('value'))),
                'is_valid': True,
                'token': None
            })
        response = {
            'hash': tx.get('tx_hash'),
            'success': tx.get('successful'),
            'transfers': transfers,
            'inputs': [],
            'outputs': [],
            'block': tx.get('block_height'),
            'confirmations': 0,
            'fees': self.from_unit(fee),
            'date': parse_iso_date(tx.get('block_signed_at')),
            'raw': tx,
            'memo': None,
        }

        if not log_events:
            return response
        for index, log_event in enumerate(log_events):
            if not log_events[index].get('decoded') or log_events[index].get('decoded').get('name') != 'Transfer':
                continue
            params = log_events[index].get('decoded').get('params')
            if not params:
                continue
            contract_address = log_events[index].get('sender_address')
            currency, _ = self.contract_currency(contract_address)
            if currency is None:
                continue

            contract_info = self.contract_info(currency, contract_address)
            transfers.append({
                'type': log_events[index].get('decoded').get('name'),
                'symbol': log_events[index].get('sender_contract_ticker_symbol'),
                'currency': currency,
                'from': params[0].get('value'),
                'to': params[1].get('value'),
                'value': self.from_unit(int(params[2].get('value')), contract_info.get('decimals')),
                'is_valid': True,
                'token': None
            })

        return {
            'hash': tx.get('tx_hash'),
            'success': tx.get('successful'),
            'transfers': transfers,
            'inputs': [],
            'outputs': [],
            'block': tx.get('block_height'),
            'confirmations': 0,
            'fees': self.from_unit(fee),
            'date': parse_iso_date(tx.get('block_signed_at')),
            'raw': tx,
            'memo': None,
        }
