import json
import random
import datetime
from typing import List
from decimal import Decimal
from django.conf import settings

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseValidator, ResponseParser

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
    from blockchain.parsers import parse_iso_date
else:
    from exchange.base.models import Currencies
    from exchange.base.parsers import parse_iso_date


class EosBitqueryResponseValidator(ResponseValidator):
    symbol = 'EOS'
    min_valid_tx_amount = Decimal('0.0005')
    precision = 4

    @classmethod
    def validate_general_response(cls, response):
        if not response or not isinstance(response, dict):
            return False
        if not response.get('data') or not isinstance(response.get('data'), dict):
            return False
        if not response.get('data').get('eos') or not isinstance(response.get('data').get('eos'), dict):
            return False
        return True

    @classmethod
    def validate_batch_tx_details_response(cls, batch_tx_details_response) -> bool:
        if not cls.validate_general_response(batch_tx_details_response):
            return False
        response = batch_tx_details_response.get('data').get('eos')
        if not response.get('blocks') or not isinstance(response.get('blocks'), list):
            return False
        if not response.get('blocks')[0] or not isinstance(response.get('blocks')[0], dict):
            return False
        if not response.get('blocks')[0].get('height') or not isinstance(response.get('blocks')[0].get('height'), int):
            return False
        if not response.get('transactions') or not isinstance(response.get('transactions'), list):
            return False
        if not response.get('transfers') or not isinstance(response.get('transfers'), list):
            return False
        return True

    @classmethod
    def validate_tx_details_transaction(cls, transaction) -> bool:
        if not transaction or not isinstance(transaction, dict):
            return False
        if not transaction.get('hash') or not isinstance(transaction.get('hash'), str):
            return False
        if not transaction.get('success') or not isinstance(transaction.get('success'), bool):
            return False
        if not transaction.get('block') or not isinstance(transaction.get('block'), dict):
            return False
        if not transaction.get('block').get('height') or not isinstance(transaction.get('block').get('height'), int):
            return False
        if (not transaction.get('block').get('timestamp') or
                not isinstance(transaction.get('block').get('timestamp'), dict)):
            return False
        if (not transaction.get('block').get('timestamp').get('time') or
                not isinstance(transaction.get('block').get('timestamp').get('time'), str)):
            return False
        return True

    @classmethod
    def validate_transfer(cls, transfer) -> bool:
        if not transfer or not isinstance(transfer, dict):
            return False
        if not transfer.get('txHash') or not isinstance(transfer.get('txHash'), str):
            return False
        if not transfer.get('sender') or not isinstance(transfer.get('sender'), dict):
            return False
        if not transfer.get('sender').get('address') or not isinstance(transfer.get('sender').get('address'), str):
            return False
        if not transfer.get('receiver') or not isinstance(transfer.get('receiver'), dict):
            return False
        if not transfer.get('receiver').get('address') or not isinstance(transfer.get('receiver').get('address'), str):
            return False
        if transfer.get('amount') is None:
            return False
        amount = Decimal(str(transfer.get('amount')))
        if amount < cls.min_valid_tx_amount:
            return False
        if not transfer.get('currency') or not isinstance(transfer.get('currency'), dict):
            return False
        if not transfer.get('currency').get('symbol') or not isinstance(transfer.get('currency').get('symbol'), str):
            return False
        if not transfer.get('currency').get('symbol') == cls.symbol:
            return False
        if not transfer.get('currency').get('address') or not isinstance(transfer.get('currency').get('address'), str):
            return False
        if not transfer.get('currency').get('address') == 'eosio.token':
            return False
        if not transfer.get('success') or not isinstance(transfer.get('success'), bool):
            return False
        return True


class EosBitqueryResponseParser(ResponseParser):
    validator = EosBitqueryResponseValidator
    symbol = 'EOS'
    currency = Currencies.eos
    precision = 4

    @classmethod
    def parse_batch_tx_details_response(cls, batch_tx_details_response, block_head) -> List[TransferTx]:
        transfers_txs: List[TransferTx] = []
        if cls.validator.validate_batch_tx_details_response(batch_tx_details_response):
            block_head = batch_tx_details_response.get('data').get('eos').get('blocks')[0].get('height')
            transactions = batch_tx_details_response.get('data').get('eos').get('transactions')
            transfers = batch_tx_details_response.get('data').get('eos').get('transfers')
            txs = {}
            for transaction in transactions:
                if cls.validator.validate_tx_details_transaction(transaction):
                    tx_hash = transaction.get('hash')
                    block_height = transaction.get('block').get('height')
                    confirmations = block_head - block_height
                    date = parse_iso_date(transaction.get('block').get('timestamp').get('time'))
                    # We have transactions and transfers in two different lists, to map them
                    # we use dict with main key of tx_hash.
                    txs[tx_hash] = {'block_height': block_height, 'date': date, 'confirmations': confirmations}
            for transfer in transfers:
                if cls.validator.validate_transfer(transfer):
                    if txs[transfer.get('txHash')]:
                        from_address = transfer.get('sender').get('address')
                        to_address = transfer.get('receiver').get('address')
                        tx_hash = transfer.get('txHash')
                        value = Decimal(str(transfer.get('amount')))
                        memo = transfer.get('memo') or ''
                        block_height = txs.get(tx_hash).get('block_height')
                        date = txs.get(tx_hash).get('date')
                        confirmations = txs.get(tx_hash).get('confirmations')
                        tx = TransferTx(
                            symbol=cls.symbol,
                            success=True,
                            from_address=from_address,
                            to_address=to_address,
                            tx_hash=tx_hash,
                            value=value,
                            memo=memo,
                            block_height=block_height,
                            date=date,
                            confirmations=confirmations
                        )
                        transfers_txs.append(tx)
        return transfers_txs


class EosBitqueryApi(GeneralApi):
    parser = EosBitqueryResponseParser
    # Api does not return memo, so currently we don't use it.
    _base_url = 'https://graphql.bitquery.io/'
    testnet_url = 'https://graphql.bitquery.io/'
    TRANSACTION_DETAILS_BATCH = True
    cache_key = 'eos'
    symbol = 'EOS'
    need_block_head_for_confirmation = False
    supported_requests = {
        'get_tx_details': '',
    }

    queries = {
        'get_tx_details': '''
            query ($hashes: [String!], $from: ISO8601DateTime!) {
                eos {
                    blocks(options: {desc: "height", limit: 1}, date: {since: $from}) {
                        height
                    }
                    transactions(txHash: {in: $hashes}) {
                    hash
                    block {
                        height
                        timestamp {
                        time(format: "%Y-%m-%dT%H:%M:%SZ")
                        }
                    }
                    success
                    }
                    transfers(txHash: {in: $hashes}) {
                    txHash
                    sender {
                        address
                    }
                    receiver {
                        address
                    }
                    amount
                    memo
                    currency {
                        symbol
                        address
                    }
                    success
                    }
                }
            }
        '''
    }

    @classmethod
    def get_headers(cls):
        header = {
            'Content-Type': 'application/json',
            'X-API-KEY': cls.get_api_key()
        }
        return header

    @classmethod
    def get_api_key(cls):
        return random.choice(settings.BITQUERY_API_KEY)

    @classmethod
    def get_tx_details_batch_body(cls, tx_hashes):
        data = {
            'query': cls.queries.get('get_tx_details'),
            'variables': {
                'hashes': tx_hashes,
                'from': datetime.datetime.now().strftime("%Y-%m-%d"),
            }
        }
        return json.dumps(data)
