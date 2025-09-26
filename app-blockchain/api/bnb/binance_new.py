from decimal import Decimal
from typing import List

from django.conf import settings

from exchange.blockchain.api.general.general import GeneralApi, ResponseValidator, ResponseParser
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
    from blockchain.parsers import parse_iso_date
else:
    from exchange.base.models import Currencies
    from exchange.base.parsers import parse_iso_date

from exchange.blockchain.api.general.dtos.dtos import TransferTx


class BnbBinanceResponseValidator(ResponseValidator):

    @classmethod
    def validate_general_response(cls, response):
        if not response:
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response) -> bool:
        if not address_txs_response or not isinstance(address_txs_response, dict):
            return False
        if not address_txs_response.get('tx') or not isinstance(address_txs_response.get('tx'), list):
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction) -> bool:
        if not transaction.get('txHash') or not isinstance(transaction.get('txHash'), str):
            return False
        if not transaction.get('blockHeight') or not isinstance(transaction.get('blockHeight'), int):
            return False
        if not transaction.get('txType') or not isinstance(transaction.get('txType'), str) or not transaction.get(
                'txType').casefold() == 'TRANSFER'.casefold():
            return False
        if not transaction.get('timeStamp') or not isinstance(transaction.get('timeStamp'), str):
            return False
        if not transaction.get('fromAddr') or not isinstance(transaction.get('fromAddr'), str):
            return False
        if not transaction.get('toAddr') or not isinstance(transaction.get('toAddr'), str):
            return False
        if transaction.get('toAddr') == transaction.get('fromAddr'):
            return False
        if not transaction.get('value') or not isinstance(transaction.get('value'), str):
            return False
        value = Decimal(transaction.get('value'))
        if value <= cls.min_valid_tx_amount:
            return False
        if not transaction.get('txAsset') or not isinstance(transaction.get('txAsset'), str):
            return False
        if not transaction.get('txAsset') == 'BNB':
            return False
        if not transaction.get('txFee') or not isinstance(transaction.get('txFee'), str):
            return False
        if transaction.get('code') is None or transaction.get('code') != 0:
            return False
        if transaction.get('confirmBlocks') is None or not isinstance(transaction.get('confirmBlocks'), int):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response) -> bool:
        if not cls.validate_general_response(response=tx_details_response):
            return False
        if not tx_details_response.get('tx', {}).get('value', {}).get('msg'):
            return False
        if not isinstance(tx_details_response.get('tx', {}).get('value', {}).get('msg'), list):
            return False
        if not tx_details_response.get('tx', {}).get('value', {}).get('msg')[0].get('type') == 'cosmos-sdk/Send':
            return False
        if not tx_details_response.get('tx', {}).get('value', {}).get('msg')[0].get('value', {}):
            return False
        outputs = tx_details_response.get('tx', {}).get('value', {}).get('msg')[0].get('value', {}).get('outputs')
        if not isinstance(outputs, list):
            return False
        if len(outputs) != 1:
            return False
        inputs = tx_details_response.get('tx', {}).get('value', {}).get('msg')[0].get('value', {}).get('inputs')
        if not isinstance(inputs, list):
            return False
        if len(inputs) != 1:
            return False
        if len(inputs[0]['coins']) != 1:
            return False
        if len(outputs[0]['coins']) != 1:
            return False
        if inputs[0]['coins'][0]['amount'] != outputs[0]['coins'][0]['amount']:
            return False

        if not tx_details_response.get('ok') and tx_details_response.get('code') == 0:
            return False
        if not tx_details_response.get('tx').get('value'):
            return False
        if not (tx_details_response.get('height')):
            return False

        return True

    @classmethod
    def validate_input_output(cls, input_output):
        if not input_output.get('coins'):
            return False
        if not isinstance(input_output.get('coins'), list):
            return False
        if not input_output.get('coins')[0].get('denom') == 'BNB':
            return False
        if not input_output.get('coins')[0].get('amount'):
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response) -> bool:
        bnb_items = list(filter(lambda item: item.get('symbol') == 'BNB', balance_response.get('balances', [])))
        if not bnb_items:
            return False
        if not bnb_items[0].get('free'):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response) -> bool:
        if not cls.validate_general_response(response=block_head_response):
            return False
        if not block_head_response.get('sync_info', {}).get('latest_block_height'):
            return False
        return True


class BnbBinanceResponseParser(ResponseParser):
    validator = BnbBinanceResponseValidator
    symbol = 'BNB'
    currency = Currencies.bnb
    precision = 8

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        transfers: List[TransferTx] = []
        if cls.validator.validate_address_txs_response(address_txs_response):
            transactions = address_txs_response.get('tx')
            for transaction in transactions:
                if cls.validator.validate_transaction(transaction) and (
                        transaction.get('fromAddr') == address or transaction.get('toAddr') == address):
                    tx_hash = transaction.get('txHash')
                    block_height = transaction.get('blockHeight')
                    confirmations = transaction.get('confirmBlocks')
                    memo = transaction.get('memo') or ''
                    from_address = transaction.get('fromAddr')
                    to_address = transaction.get('toAddr')
                    value = Decimal(transaction.get('value'))
                    fee = Decimal(transaction.get('txFee'))
                    date = parse_iso_date(transaction.get('timeStamp'))
                    transfer = TransferTx(
                        symbol=cls.symbol,
                        success=True,
                        tx_hash=tx_hash,
                        block_height=block_height,
                        value=value,
                        from_address=from_address,
                        to_address=to_address,
                        memo=memo,
                        tx_fee=fee,
                        date=date,
                        confirmations=confirmations,
                    )
                    transfers.append(transfer)
        return transfers

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        if not cls.validator.validate_tx_details_response(tx_details_response):
            return []

        tx_info = tx_details_response.get('tx', {}).get('value', {}).get('msg')[0]
        transfers = []
        tx_hash = tx_details_response.get('hash')
        memo = tx_details_response.get('tx').get('value').get('memo') or ''
        block_height = int(tx_details_response.get('height'))
        output = tx_info.get('value').get('outputs')[0]
        _input = tx_info.get('value').get('inputs')[0]
        if cls.validator.validate_input_output(output) and cls.validator.validate_input_output(_input):
            transfers.append(
                TransferTx(
                    tx_hash=tx_hash,
                    success=True,
                    from_address=_input.get('address'),
                    to_address=output.get('address'),
                    value=BlockchainUtilsMixin.from_unit(int(output.get('coins')[0].get('amount')),
                                                         precision=cls.precision),
                    symbol=cls.symbol,
                    confirmations=0,
                    block_height=block_height,
                    block_hash=None,
                    date=None,
                    memo=memo,
                    tx_fee=None,
                    token=None,
                )
            )

        return transfers

    @classmethod
    def parse_block_head_response(cls, block_head_response):
        if not cls.validator.validate_block_head_response(block_head_response):
            return None
        return block_head_response.get('sync_info', {}).get('latest_block_height')

    @classmethod
    def parse_balance_response(cls, balance_response) -> Decimal:
        if not cls.validator.validate_balance_response(balance_response):
            return Decimal(0)
        balances = balance_response.get('balances', [])
        bnb_item = list(filter(lambda item: item.get('symbol') == 'BNB', balances))  # just bnb balance matters
        amount = Decimal(bnb_item[0].get('free'))
        return amount


class BnbBinanceApi(GeneralApi):
    parser = BnbBinanceResponseParser
    cache_key = 'bnb'
    symbol = 'BNB'
    rate_limit = 1
    _base_url = 'https://dex-european.binance.org'
    testnet_url = 'https://testnet-dex.binance.org'
    need_block_head_for_confirmation = False
    TRANSACTIONS_LIMIT = 100
    supported_requests = {
        'get_address_txs': '/api/v1/transactions?address={address}&limit={limit}&txType=TRANSFER&offset=0',
        'get_tx_details': '/api/v1/tx/{tx_hash}?format=json',
        'get_block_head': '/api/v1/node-info',
        'get_balance': '/api/v1/account/{address}',
    }

    @classmethod
    def get_address_txs(cls, address, **kwargs):
        response = cls.request(request_method='get_address_txs', address=address, limit=cls.TRANSACTIONS_LIMIT)
        return response
