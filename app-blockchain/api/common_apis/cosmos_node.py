from abc import ABC
from decimal import Decimal

import coinaddrvalidator

from exchange.base.parsers import parse_iso_date
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError, ParseError, ValidationError
from exchange.blockchain.api.general_api import NobitexBlockchainAPI


class CosmosNode(NobitexBlockchainAPI, BlockchainUtilsMixin, ABC):
    PRECISION = 6
    default_pagination_limit = 30
    default_pagination_offset = 0
    symbol = ''
    main_denom = ''
    currency = None
    cache_key = ''
    _base_url = ''
    chain_id = ''
    blockchain_name = ''
    valid_transfer_types = []
    get_txs_keyword = ''
    supported_requests = {}

    @classmethod
    def unify_amount(cls, num):
        return Decimal(num) / (10 ** cls.PRECISION)

    def get_name(self):
        return 'node_api'

    def validate_address(self, address):
        validate = coinaddrvalidator.validate(self.blockchain_name, address)
        if not validate.valid:
            raise ValidationError('Address not valid')
        return validate.valid

    def get_header(self):
        return None

    def get_tx_direction(self, tx, address):
        msg = self.get_tx_messages(tx)[0]
        to_address = (msg.get('to_address') or msg.get('outputs')[0].get('address')).casefold()
        from_address = (msg.get('from_address') or msg.get('inputs')[0].get('address')).casefold()        # check self transaction
        if to_address == from_address:
            return None
        if address.casefold() == to_address:
            return 'incoming'
        elif address.casefold() == from_address:
            return 'outgoing'
        else:
            return None

    def get_balance(self, address):
        self.validate_address(address)
        denom = self.symbol.lower()
        try:
            response = self.request('get_balance', headers=self.get_header(), address=address, denom='u' + denom)
        except ConnectionError:
            raise APIError(f"Failed to get Balance from {self.symbol} API: connection error")
        if response is None:
            raise APIError(f"Get Balance response of {self.symbol} is None")
        balance_amount = self.parse_balance(response)
        return {
            self.currency: {
                'symbol': denom,
                'amount': balance_amount,
                'unconfirmed_amount': Decimal('0'),
                'address': address
            }
        }

    def parse_balance(self, response):
        denom = self.symbol.lower()
        balances = response.get('balance') or response.get('balances')
        if not isinstance(balances, list):
            balances = [balances]
        if balances == []:
            return Decimal(0)
        for balance in balances:
            if balance.get('denom') == 'u' + denom:
                return self.from_unit(int(balance.get('amount')))
        raise APIError(f'Failed to get {denom} address balance , balance response: {response}')

    def validate_transaction(self, tx, address, tx_direction):
        try:
            tx_status_code = int(tx.get('code'))
            if tx_status_code != 0:  # only zero code means success
                return False
            msgs = self.get_tx_messages(tx)
            msg_type = msgs[0].get('type') or msgs[0].get('@type')
            if msg_type not in self.valid_transfer_types:
                return False
            if len(msgs) != 1:  # to support send and "multisend with just one transfer"
                return False
            tx_amount_list = msgs[0].get('amount') or msgs[0].get('inputs')[0].get('coins')
            if len(tx_amount_list) != 1:
                return False
            tx_denom = tx_amount_list[0].get('denom')
            if tx_denom != 'u' + self.symbol.lower():  # is denom excepted symbol
                return False
            memo = self.get_tx_memo(tx)
            if tx_direction == 'incoming' and ((not memo) or memo.isspace()):  # blank memo is not valid
                return False
            direction = self.get_tx_direction(tx, address)
            if not direction or direction != tx_direction:
                return False
        except AttributeError:
            raise ParseError(f'{self.symbol} parsing error Tx is {tx}.')
        return True

    def validate_transaction_detail(self, details):
        try:
            tx = details.get('tx')
            tx_response = details.get('tx_response')
            tx_status_code = int(tx_response.get('code'))
            if tx_status_code != 0:  # only zero code means success
                return False
            msgs = tx.get('body').get('messages')
            msg_type = msgs[0].get('type') or msgs[0].get('@type')
            if msg_type not in self.valid_transfer_types:
                return False
            if len(msgs) != 1:  # to support send and "multisend with just one transfer"
                return False
            tx_amount_list = msgs[0].get('amount') or msgs[0].get('inputs')[0].get('coins')
            if len(tx_amount_list) != 1:
                return False
            from_address = (msgs[0].get('from_address') or msgs[0].get('inputs')[0].get('address')).casefold()
            to_address = (msgs[0].get('to_address') or msgs[0].get('outputs')[0].get('address')).casefold()
            if from_address == to_address:
                return False
            tx_denom = tx_amount_list[0].get('denom')
            if tx_denom != 'u' + self.symbol.lower():  # is denom excepted symbol
                return False
            memo = tx_response.get('tx').get('body').get('memo')
            if (not memo) or memo.isspace():  # blank memo is not valid
                return False
        except AttributeError:
            raise ParseError(f'{self.symbol} parsing error Tx is {details}.')
        return True

    def get_txs(self, address, pagination_offset=default_pagination_offset, pagination_limit=default_pagination_limit,
                tx_direction_filter='incoming'):
        if tx_direction_filter == 'incoming':
            tx_query_direction = 'recipient'
        elif tx_direction_filter == 'outgoing':
            tx_query_direction = 'sender'
        else:
            raise APIError(f"incorrect arg tx_query_direction = {tx_direction_filter}")
        self.validate_address(address)
        block_head = self.get_block_head()
        try:
            response = self.request('get_transactions',
                                    headers=self.get_header(),
                                    pagination_offset=pagination_offset,
                                    pagination_limit=pagination_limit,
                                    tx_query_direction=tx_query_direction,
                                    address=address)
        except ConnectionError:
            raise APIError(f"Failed to get txs from {self.symbol} API: connection error")
        transactions = []
        txs = response.get(self.get_txs_keyword)
        for tx in txs:
            if self.validate_transaction(tx, address, tx_direction_filter):
                parsed_tx = self.parse_tx(tx, address, block_head)
                transactions.append(parsed_tx)
        return transactions

    def parse_tx(self, tx, address, block_head):
        try:
            msg = self.get_tx_messages(tx)[0]  # just handle first message
            from_address = (msg.get('from_address') or msg.get('inputs')[0].get('address')).casefold()
            to_address = (msg.get('to_address') or msg.get('outputs')[0].get('address')).casefold()
            tx_amount_list = msg.get('amount') or msg.get('inputs')[0].get('coins')
            tx_amount = self.from_unit(int(tx_amount_list[0].get('amount')))
            tx_block_height = int(tx.get('height'))
            direction = self.get_tx_direction(tx, address)
            tx_hash = tx.get('txhash')
            date = parse_iso_date(tx.get('timestamp'))
            raw = tx.get('raw_log')
        except AttributeError:
            raise ParseError(f'{self.symbol} parsing error Tx is {tx}.')
        if direction == 'outgoing':
            tx_amount = -tx_amount
        transaction = {
            self.currency: {
                'address': address,
                'hash': tx_hash,
                'from_address': from_address,
                'to_address': to_address,
                'amount': tx_amount,
                'block': tx_block_height,
                'date': date,
                'confirmations': block_head - tx_block_height,
                'direction': direction,
                'memo': self.get_tx_memo(tx),
                'raw': raw
            }
        }
        return transaction

    def get_block_head(self):
        try:
            response = self.request('get_block_head', headers=self.get_header(),)
        except ConnectionError:
            raise APIError(f"Failed to get Block Head from {self.symbol} API: connection error")
        if not response:
            raise APIError(f'get_block_head of {self.symbol} Response is none')
        try:
            block_height = int(response.get('block').get('header').get('height'))
        except AttributeError:
            raise ParseError(f'{self.symbol} get block head parsing error.')
        return block_height

    def get_tx_details(self, tx_hash):
        try:
            response = self.request('get_transaction', headers=self.get_header(), tx_hash=tx_hash)
        except ConnectionError:
            raise APIError(f"Failed to get_tx_details from {self.symbol} API: connection error")
        if not response:
            raise APIError(f'{self.symbol} get_tx_detail Response is none')
        tx_details = self.parse_tx_details(response)
        return tx_details

    def parse_tx_details(self, response):
        is_valid = self.validate_transaction_detail(response)
        if not is_valid:
         return {
            'success': False,
         }
        try:
            tx = response.get('tx')
            tx_response = response.get('tx_response')
            msg = tx.get('body').get('messages')[0]
            tx_amount_list = msg.get('amount') or msg.get('inputs')[0].get('coins')
            block_head = self.get_block_head()
            tx_block = int(tx_response.get('height'))
            transfer = [{
                'type': msg.get('@type') or msg.get('type'),
                'symbol': tx_amount_list[0].get('denom'),
                'currency': self.currency,
                'from': msg.get('from_address') or msg.get('inputs')[0].get('address'),
                'to': msg.get('to_address') or msg.get('outputs')[0].get('address'),
                'value': self.from_unit(int(tx_amount_list[0].get('amount'))),
                'is_valid': is_valid
            }]
            tx_detail = {
                'hash': tx_response.get('txhash'),
                'success': (int(tx_response.get('code')) == 0),  # only zero code means success
                'inputs': [],
                'outputs': [],
                'transfers': transfer,
                'block': tx_block,
                'confirmations': block_head - tx_block,
                'fees': self.from_unit(int(tx.get('auth_info').get('fee').get('amount')[0].get('amount'))),
                'date': parse_iso_date(tx_response.get('timestamp')),
                'memo': tx_response.get('tx').get('body').get('memo'),
                'raw': tx_response.get('raw_log')
            }
        except AttributeError:
            raise ParseError(f'{self.symbol} parsing error tx_details response is {response}.')
        return tx_detail

    def get_message_attr(self, message, attribute):
        """
        get one attribute from message dictionary in get_txs response
        :param message:  dict to get attribute from
        :param attribute: permitted values: ['from_address', 'to_address', 'amount']
        """
        try:
            msg_attr = message.get(attribute)
        except AttributeError:
            raise ParseError(f'{self.symbol} parsing message attribute error. message is {message}.')
        return msg_attr

    def get_tx_memo(self, tx):
        try:
            memo = tx.get('tx').get('body').get('memo')
        except AttributeError:
            raise ParseError(f'{self.symbol} parsing memo error Tx is {tx}.')
        return memo

    def get_tx_messages(self, tx):
        try:
            messages = tx.get('tx').get('body').get('messages')
        except AttributeError:
            raise ParseError(f'{self.symbol} parsing messages error Tx is {tx}.')
        return messages

    def get_delegated_balance(self, address):
        self.validate_address(address)
        try:
            response = self.request('get_staked_balance', headers=self.get_header(), address=address)
        except ConnectionError:
            raise APIError(f"Failed to  get staked balance from {self.symbol} API: connection error")
        if response is None:
            raise APIError(f"Get staked balance response of {self.symbol} is None")
        try:
            balance_amount = self.parse_delegated_balance(response)
        except AttributeError:
            raise ParseError(f'{self.symbol} parsing balance response error response is {response}.')
        return balance_amount

    def parse_delegated_balance(self, response):
        balance = response.get('delegation_responses')[0].get('balance')
        balance_denom = balance.get('denom')
        balance_amount = balance.get('amount')
        if balance_denom != self.main_denom:
            raise APIError(f"{self.symbol} API: balance denom not matched with main denom")
        return self.unify_amount(balance_amount)

    def get_staking_reward(self, address):
        self.validate_address(address)
        try:
            response = self.request('get_staking_reward', headers=self.get_header(), address=address)
        except ConnectionError:
            raise APIError(f"Failed to  get rewards balance from {self.symbol} API: connection error")
        if response is None:
            raise APIError(f"Get rewards balance response of {self.symbol} is None")
        try:
            reward_amount = self.parse_staking_reward(response)
        except AttributeError:
            raise ParseError(f'{self.symbol} parsing rewards balance response error response is {response}.')
        return reward_amount

    def parse_staking_reward(self, response):
        for reward in response.get('total'):
            reward_denom = reward.get('denom')
            if reward_denom == self.main_denom:
                return self.unify_amount(reward.get('amount'))
        return Decimal('0')
