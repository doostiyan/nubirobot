from decimal import Decimal

from exchange.base.connections import MoneroExplorerClient
from exchange.base.models import Currencies
from exchange.base.parsers import parse_timestamp
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general_block_api import NobitexBlockchainBlockAPI


class MoneroAPI(NobitexBlockchainBlockAPI, BlockchainUtilsMixin):
    """
    As Monero uses private keys to view blockchain data, we get data from our hot wallet that is connected to our
    monero node
    """

    SUPPORT_BATCH_BLOCK_PROCESSING = True
    currency = Currencies.xmr
    symbol = 'XMR'
    USE_PROXY = False
    PRECISION = 12
    cache_key = 'xmr'

    def get_name(self):
        return 'monero_api'

    def get_block_head(self):
        hot_wallet = MoneroExplorerClient.get_client()
        response = hot_wallet.request(
            method='get_block_head',
            params={
                'password': hot_wallet.password,
            },
            rpc_id='curltext',
        )
        if response.get('status') == 'failed':
            raise APIError(f'Monero API error: {response.get("message")}.')
        return response.get('block_head')

    def get_balance(self, address):
        hot_wallet = MoneroExplorerClient.get_client()
        response = hot_wallet.request(
            method='get_balance',
            params={
                'address': address,
                'password': hot_wallet.password,
            },
            rpc_id='curltext',
        )
        if response.get('status') == 'failed':
            raise APIError(f'Monero API error: {response.get("message")}.')
        return {
            self.currency: {
                'symbol': self.symbol,
                'amount': Decimal(response.get('confirmed_balance')),
                'unconfirmed_amount': Decimal(response.get('unconfirmed_balance')),
                'address': address
            }
        }

    def get_txs(self, address):
        txs = []
        hot_wallet = MoneroExplorerClient.get_client()
        response = hot_wallet.request(
            method='get_txs',
            params={
                'address': address,
                'password': hot_wallet.password,
            },
            rpc_id='curltext',
        )
        if response.get('status') == 'failed':
            raise APIError(f'Monero API error: {response.get("message")}.')

        for tx in response.get('transfers'):
            parsed_tx = self.parse_tx(tx)
            if parsed_tx:
                txs.append(parsed_tx)
        return txs

    def parse_tx(self, tx):
        if Decimal(tx.get('amount')) < Decimal('0.001'):
            return
        return {
            self.currency: {
                'block': tx.get('height'),
                'direction': 'incoming',
                'date': parse_timestamp(tx.get('timestamp')),
                'to_address': tx.get('destination'),
                'amount': Decimal(tx.get('amount')),
                'fee': Decimal(tx.get('fee')),
                'hash': tx.get('tx_hash'),
                'confirmations': tx.get('confirmation'),
                'raw': tx,
            }
        }

    def get_tx_details(self, tx_hash):
        hot_wallet = MoneroExplorerClient.get_client()
        response = hot_wallet.request(
            method='get_tx_details',
            params={
                'tx_hash': tx_hash,
                'password': hot_wallet.password,
            },
            rpc_id='curltext',
        )
        if response.get('status') == 'failed':
            raise APIError(f'Monero API error: {response.get("message")}.')

        return self.parse_tx_details(response.get('transfers'))

    def parse_tx_details(self, tx):
        transfers = []
        for transfer in tx:
            if self.from_unit(transfer.get('amount')) < Decimal('0.001'):
                continue
            transfers.append({
                'currency': self.currency,
                'value': self.from_unit(transfer.get('amount')),
                'to': transfer.get('destination'),
                'is_valid': transfer.get('status'),
            })
        return {
            'success': tx[0].get('status'),
            'date': parse_timestamp(tx[0].get('timestamp')),
            'transfers': transfers,
            'fee': self.from_unit(tx[0].get('fee')),
            'hash': tx[0].get('tx_hash'),
            'confirmations': tx[0].get('confirmation'),
            'block': tx[0].get('height')
        }

    def get_blocks(self, min_height, max_height, tx_filter_query=''):
        hot_wallet = MoneroExplorerClient.get_client()
        incoming = hot_wallet.request(
            method='get_blocks_txs',
            params={
                'min_height': min_height,
                'max_height': max_height - 1,
                'password': hot_wallet.password,
            },
            rpc_id='curltext',
        )
        outgoing = hot_wallet.request(
            method='get_outgoing_txs',
            params={
                'min_height': min_height,
                'max_height': max_height - 1,
                'password': hot_wallet.password,
            },
            rpc_id='curltext',
        )
        if incoming.get('status') == 'failed':
            raise APIError(f'Monero API error: {incoming.get("message")}.')
        if outgoing.get('status') == 'failed':
            raise APIError(f'Monero API error: {outgoing.get("message")}.')

        return [incoming, outgoing]

    def parse_block(self, blocks):
        return blocks.get('transfers')

    def parse_transaction_data(self, tx):
        if Decimal(tx.get('amount')) < Decimal('0.001'):
            return
        return {
            'hash': tx.get('tx_hash'),
            'from': tx.get('sender'),
            'to': tx.get('destination'),
            'amount': Decimal(tx.get('amount')),
            'currency': self.currency,
        }

    def validate_transaction(self, tx, address=None):
        return True
