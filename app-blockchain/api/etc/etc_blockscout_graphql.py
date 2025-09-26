import datetime
import json
from random import random
from typing import List
from decimal import Decimal, ROUND_DOWN
import requests
from django.conf import settings

from exchange.blockchain.api.general.general import GeneralApi, ResponseValidator, ResponseParser
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_timestamp
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.parsers import parse_timestamp
    from exchange.base.models import Currencies
    from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.utils import BlockchainUtilsMixin, APIError
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.metrics import metric_set


class EtcBlockscoutGraphqlEtcValidator(ResponseValidator):
    successful_code = 'successful'
    valid_operation = 'transfer'
    success_status = 'success'
    min_valid_tx_amount = Decimal(0)
    valid_block_status = 'on-chain'
    valid_mini_block_type = 'TxBlock'
    PRECISION = 18

    @classmethod
    def validate_tx_details_response(cls, tx_details_response) -> bool:
        if tx_details_response.get('data') is None or len(tx_details_response.get('data')) == 0:
            return False
        if tx_details_response.get('data').get('transaction') is None or len(
                tx_details_response.get('data').get('transaction')) == 0:
            return False
        if not cls.validate_transaction(tx_details_response.get('data').get('transaction')):
            return False

        return True

    @classmethod
    def validate_transaction(cls, transaction) -> bool:
        if not transaction.get('hash'):
            return False
        if transaction.get('error') is not None:
            return False
        if BlockchainUtilsMixin.from_unit(int(transaction.get('value')), cls.PRECISION) == 0:
            return False
        if transaction.get('status') != 'OK':
            return False
        if transaction.get('fromAddressHash') == transaction.get('toAddressHash'):
            return False
        if transaction.get('fromAddressHash') in cls.invalid_from_addresses_for_ETH_like:
            return False
        if transaction.get('input') != '0x' and transaction.get(
                'input') != '0x0000000000000000000000000000000000000000':
            return False
        return True


class EtcBlockscoutGraphqlEtcParser(ResponseParser):
    validator = EtcBlockscoutGraphqlEtcValidator
    symbol = 'ETC'
    currency = Currencies.etc
    PRECISION = 18
    rate_limit = 0.006

    # TODO confirmation, date,

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        if cls.validator.validate_tx_details_response(tx_details_response):
            transaction = tx_details_response.get('data').get('transaction')
            value = BlockchainUtilsMixin.from_unit(int(transaction.get('value')), cls.PRECISION)
            tx_fee = BlockchainUtilsMixin.from_unit(int(transaction.get('gasUsed')) * int(transaction.get('gasPrice')),
                                                    cls.PRECISION)
            return [TransferTx(
                tx_hash=transaction.get('hash'),
                success=True,
                block_height=transaction.get('blockNumber'),
                date=None,
                memo=None,
                tx_fee=tx_fee,
                confirmations=None,
                symbol=cls.symbol,
                from_address=transaction.get('fromAddressHash'),
                to_address=transaction.get('toAddressHash'),
                value=value,
                token=None,
                block_hash=None
            )]
        return None


class EtcBlockscoutGraphqlEtcApi(GeneralApi):
    parser = EtcBlockscoutGraphqlEtcParser
    cache_key = 'etc'
    _base_url = 'https://blockscout.com/etc/mainnet/graphiql'
    rate_limit = 0.006
    need_block_head_for_confirmation = False

    supported_requests = {
        'get_tx_details': ''
    }
    queries = {
        'get_tx_details': '''
                query get_tx_details($hash: FullHash!)
                    {transaction(hash: $hash) { hash, 
                    blockNumber, 
                    value,
                    input,
                     gasUsed,
                     gasPrice,
                     fromAddressHash,
                     status,
                     toAddressHash,
                     error,
                     gas }
                     }

             '''
    }

    @classmethod
    def get_headers(cls):
        return {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer YOUR_ACCESS_TOKEN'
        }

    @classmethod
    def get_tx_details_body(cls, tx_hash):
        if not tx_hash.startswith('0x'):
            tx_hash = '0x' + tx_hash
        data = {
            'query': cls.queries.get('get_tx_details'),
            'variables': {
                'hash': tx_hash
            }
        }

        return json.dumps(data)
