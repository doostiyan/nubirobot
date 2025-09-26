import sys
import traceback
from abc import ABC
from collections import defaultdict

from django.conf import settings
from django.core.cache import cache

from exchange.blockchain.metrics import metric_set

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from coldwalletui.logging import report_exception
else:
    from exchange.base.logging import report_exception
from exchange.blockchain.api.general_api import NobitexBlockchainAPI
from exchange.blockchain.utils import APIError, ParseError


class NobitexBlockchainBlockAPI(NobitexBlockchainAPI, ABC):

    SUPPORT_BATCH_BLOCK_PROCESSING = False
    TX_FILTER_QUERY = ''
    cache_key = ''
    GET_BLOCK_ADDRESSES_MAX_NUM = 100
    block_height_offset = 0

    def get_latest_block(self, after_block_number=None, to_block_number=None, include_inputs=False, include_info=False):
        """
        calculate unprocessed block-height range and list all addresses in all transaction in all blocks in that range
        """
        max_height, min_height = self.calculate_unprocessed_block_range(after_block_number, to_block_number)

        blocks = []
        if self.SUPPORT_BATCH_BLOCK_PROCESSING:
            blocks = self.get_blocks(min_height=min_height, max_height=max_height, tx_filter_query=self.TX_FILTER_QUERY)
            block_height = max_height
        else:
            block_height = min_height
            for block_height in range(min_height, max_height):
                try:
                    blocks.append(self.get_block(block_height))
                except Exception as error:
                    traceback.print_exception(*sys.exc_info())
                    break
        transactions_addresses, transactions_info = self.get_block_addresses(blocks, include_inputs=include_inputs,
                                                                             include_info=include_info)

        metric_set(name='latest_block_processed', labels=[self.symbol.lower()], amount=block_height - 1)
        cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}',
                  block_height - 1, 86400)
        return transactions_addresses, transactions_info, block_height - 1

    def calculate_unprocessed_block_range(self, after_block_number, to_block_number):
        if not to_block_number:
            latest_block_height_mined = self.get_block_head()
            if not latest_block_height_mined:
                raise APIError(f'{self.symbol}: API Not Return block height')
        else:
            latest_block_height_mined = to_block_number
        if not after_block_number:
            latest_block_height_processed = cache.\
                get(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{self.cache_key}')
            if latest_block_height_processed is None:
                latest_block_height_processed = latest_block_height_mined - 5
        else:
            latest_block_height_processed = after_block_number
        print('Cache latest block height: {}'.format(latest_block_height_processed))

        if latest_block_height_mined > latest_block_height_processed:
            min_height = latest_block_height_processed + 1
        else:
            min_height = latest_block_height_mined + 1
        max_height = min(latest_block_height_mined + 1, min_height + self.GET_BLOCK_ADDRESSES_MAX_NUM)
        return max_height, min_height

    def get_block_addresses(self, blocks, include_inputs=False, include_info=False):
        """
            get all transaction of a block and get addresses in each of them
            input_addresses <~> outgoing_txs, output_addresses <~> incoming_txs
        """
        transactions_addresses = {'input_addresses': set(), 'output_addresses': set()}
        transactions_info = {'outgoing_txs': defaultdict(lambda: defaultdict(list)),
                             'incoming_txs': defaultdict(lambda: defaultdict(list))}
        for block in blocks:
            try:
                txs = self.parse_block(block)
                if not txs:
                    continue
            except AttributeError:
                raise ParseError(f'{self.symbol} parsing error! block: {block}.')
            for tx in txs:
                if not self.validate_transaction(tx):
                    continue
                try:
                    tx_data = self.parse_transaction_data(tx)
                except AttributeError:
                    raise ParseError(f'{self.symbol} parsing tx error! tx: {tx}.')
                if tx_data is None:
                    continue
                from_address = tx_data.get('from')
                to_address = tx_data.get('to')
                value = tx_data.get('amount')
                currency = tx_data.get('currency')

                if to_address:
                    transactions_addresses['output_addresses'].add(to_address)
                if include_inputs and from_address:
                    transactions_addresses['input_addresses'].add(from_address)

                if include_info:
                    tx_hash = tx_data.get('hash')
                    if include_inputs and from_address:
                        check_for_duplication = [tx for tx in transactions_info['outgoing_txs'][from_address][self.currency] if tx['tx_hash'] == tx_hash]
                        if check_for_duplication:
                            index = transactions_info['outgoing_txs'][from_address][self.currency].\
                                index(check_for_duplication[0])
                            transactions_info['outgoing_txs'][from_address][self.currency][index]['value'] += value
                        else:
                            transactions_info['outgoing_txs'][from_address][self.currency].append({
                                'tx_hash': tx_hash,
                                'value': value,
                            })
                    if to_address:
                        transactions_info['incoming_txs'][to_address][currency].append({
                            'tx_hash': tx_hash,
                            'value': value,
                        })
        return transactions_addresses, transactions_info

    def get_blocks(self, min_height, max_height, tx_filter_query=''):
        """
            get info of range of blocks
        """
        try:
            response = self.request('get_blocks_txs', min_height=min_height, max_height=max_height,
                                    tx_filter_query=tx_filter_query)
        except ConnectionError:
            raise APIError(f'{self.symbol} API: Failed to get txs of block_range={min_height}-{max_height} '
                           f'and query phrase: {tx_filter_query}, connection error')
        return response

    def get_block(self, block_height):
        """
            get block info from blockchain
        """
        try:
            response = self.request('get_block_txs', block_height=block_height)
        except ConnectionError:
            raise APIError(f'{self.symbol} API: Failed to get txs of block_height={block_height}, connection error')
        return response

    def parse_block(self, response):
        """
            parse txs in block info
        """
        return []

    def parse_transaction_data(self, tx):
        return {}
