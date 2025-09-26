from exchange.base.models import Currencies
from exchange.blockchain.api.common_apis.cosmos_node import CosmosNode
from exchange.blockchain.utils import ParseError


class TerraNode(CosmosNode):
    symbol = 'LUNA'
    currency = Currencies.luna
    cache_key = 'terra'
    blockchain_name = 'terramoney'
    _base_url = 'https://fcd.terra.dev'
    chain_id = 'columbus-5'
    valid_transfer_types = ['bank/MsgSend', '/cosmos.bank.v1beta1.MsgSend']
    get_txs_keyword = 'txs'
    supported_requests = {
        'get_balance': '/cosmos/bank/v1beta1/balances/{address}/by_denom?denom={denom}',
        'get_block_head': '/cosmos/base/tendermint/v1beta1/blocks/latest',
        'get_transactions': '/v1/txs?offset={pagination_offset}&limit={pagination_limit}&account={address}',
        'get_transaction': '/cosmos/tx/v1beta1/txs/{tx_hash}'
    }

    def get_message_attr(self, message, attribute):
        """
        :param message: messages dict (extract from get_txs response) to get attribute from
        :param attribute: permitted values: [from_address, to_address, amount]
        """
        try:
            msg_attr = message.get('value').get(attribute)
        except AttributeError:
            raise ParseError(f'{self.symbol} parsing message attribute error. message is {message}.')
        return msg_attr

    def get_tx_memo(self, tx):
        try:
            memo = tx.get('tx').get('value').get('memo')
        except AttributeError:
            raise ParseError(f'{self.symbol}  parsing memo error Tx is {tx}.')
        return memo

    def get_tx_messages(self, tx):
        try:
            messages = tx.get('tx').get('value').get('msg')
        except AttributeError:
            raise ParseError(f'{self.symbol} parsing messages error Tx is {tx}.')
        return messages
