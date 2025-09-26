import random
from decimal import Decimal
from typing import List, Optional
import json

from exchange.base.parsers import parse_iso_date
from django.conf import settings

from exchange.blockchain.api.general.general import GeneralApi, ResponseValidator, ResponseParser
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies

from exchange.blockchain.api.general.dtos.dtos import TransferTx


class GraphQlAptosValidator(ResponseValidator):
    valid_transfer_types = ['0x1::aptos_account::transfer', '0x1::coin::transfer', '0x1::aptos_account::transfer_coins']
    valid_token = ['0x1::aptos_coin::AptosCoin']
    valid_resources = ['0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>']
    valid_activity_type = ['0x1::coin::DepositEvent', '0x1::coin::WithdrawEvent']
    min_valid_tx_amount = Decimal('0.025')
    EXPECTED_ADDRESS_LENGTH = 64
    precision = 8

    @classmethod
    def validate_general_response(cls, response):
        if not response:
            return False
        if not response.get('data'):
            return False
        return True

    @classmethod
    def validate_block_head_response(cls, block_head_response) -> bool:
        if not cls.validate_general_response(block_head_response):
            return False
        if not block_head_response.get('data').get('processor_status'):
            return False
        if block_head_response.get('data').get('processor_status')[0].get('last_success_version') is None:
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response) -> bool:
        if not cls.validate_general_response(address_txs_response):
            return False
        if not address_txs_response.get('data').get('processor_status'):
            return False
        if not address_txs_response.get('data').get('processor_status')[0].get('last_success_version'):
            return False
        if not address_txs_response.get('data').get('coin_activities'):
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction) -> bool:
        if not transaction.get('transaction_version'):
            return False
        if transaction.get('entry_function_id_str') not in cls.valid_transfer_types:
            return False
        if transaction.get('coin_type') not in cls.valid_token:
            return False
        if transaction.get('activity_type') not in cls.valid_activity_type:
            return False
        if not transaction.get('is_transaction_success'):
            return False
        if transaction.get('is_gas_fee'):
            return False
        if not transaction.get('owner_address') or not isinstance(transaction.get('owner_address'), str):
            return False
        if transaction.get('amount') is None:
            return False
        value = BlockchainUtilsMixin.from_unit(transaction.get('amount'), cls.precision)
        if value < cls.min_valid_tx_amount:
            return False
        return True

    @classmethod
    def validate_batch_block_txs_response(cls, batch_block_txs_response) -> bool:
        if not batch_block_txs_response:
            return False
        return True

    @classmethod
    def validate_block_txs_raw_response(cls, block_txs_raw_response) -> bool:
        if not block_txs_raw_response or not isinstance(block_txs_raw_response, list):
            return False
        return True

class GraphQlAptosResponseParser(ResponseParser):
    precision = 8
    symbol = 'APT'
    EXPECTED_ADDRESS_LENGTH = 64
    validator = GraphQlAptosValidator
    currency = Currencies.apt

    # Function below justifies the modified address to make sure it has a total length of
    # EXPECTED_ADDRESS_LENGTH characters( which is 64 in here ),
    # padding it with '0' (zero) characters on the left side if needed.
    # This padding ensures that the address always has a consistent length.
    # Finally, it adds back the '0x' prefix to the unified and padded address before returning it.
    @classmethod
    def unify_address(cls, address):
        if address.startswith('0x'):
            address = address[2:]
        padded_address = address.rjust(cls.EXPECTED_ADDRESS_LENGTH, '0')
        return '0x' + padded_address

    @classmethod
    def parse_block_head_response(cls, block_head_response):
        if cls.validator.validate_block_head_response(block_head_response):
            return block_head_response.get('data').get('processor_status')[0].get('last_success_version')

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        if cls.validator.validate_address_txs_response(address_txs_response):
            transactions = address_txs_response.get('data').get('coin_activities')
            block_head = block_head or address_txs_response.get('data').get('processor_status')[0].get('last_success_version')
            address_txs: List[TransferTx] = []
            for transaction in transactions:
                if cls.validator.validate_transaction(transaction):
                    value = BlockchainUtilsMixin.from_unit(transaction.get('amount'), cls.precision)
                    # Version in aptos shows the id of the transaction which is unique for each transaction.
                    # So we use it as the height. You might be confused about it, but it's ok because
                    # the point of confirmation is that we wait for an amount of time/
                    # and then we recognize it as a valid transaction so here we use version
                    version = transaction.get('transaction_version')
                    confirmations = block_head - version
                    # Activity type is for checking that the event is incoming or outgoing.
                    # If the type contains DepositEvent, it means incoming and /
                    # if it contains WithdrawEvent,it means outgoing
                    if transaction.get('activity_type') == '0x1::coin::WithdrawEvent':
                        from_address = cls.unify_address(transaction.get('owner_address'))
                        to_address = ''
                    else:
                        to_address = cls.unify_address(transaction.get('owner_address'))
                        from_address = ''
                    address_tx = TransferTx(
                        # We use version of transactions instead of tx_hash because the response
                        # doesn't include hash of transactions. So we use version instead(it's unique)
                        tx_hash=str(version),
                        from_address=from_address,
                        to_address=to_address,
                        value=value,
                        block_height=version,
                        confirmations=confirmations,
                        success=True,
                        symbol=cls.symbol,
                        date=parse_iso_date(f'{transaction.get("transaction_timestamp")}Z'),
                    )
                    address_txs.append(address_tx)
            return address_txs
        return []

    @classmethod
    def parse_batch_block_txs_response(cls, batch_block_txs_response) -> List[TransferTx]:
        blocks_txs: List[TransferTx] = []
        if cls.validator.validate_batch_block_txs_response(batch_block_txs_response):
            transactions = batch_block_txs_response
            for transaction in transactions:
                if cls.validator.validate_transaction(transaction):
                    value = BlockchainUtilsMixin.from_unit(transaction.get('amount'), cls.precision)
                    version = transaction.get('transaction_version')
                    if transaction.get('activity_type') == '0x1::coin::WithdrawEvent':
                        from_address = cls.unify_address(transaction.get('owner_address'))
                        to_address = None
                    else:
                        to_address = cls.unify_address(transaction.get('owner_address'))
                        from_address = None
                    block_tx = TransferTx(
                        tx_hash=str(version),
                        from_address=from_address,
                        to_address=to_address,
                        value=value,
                        block_height=version,
                        success=True,
                        symbol=cls.symbol,
                        date=parse_iso_date(f'{transaction.get("transaction_timestamp")}Z'),
                    )
                    blocks_txs.append(block_tx)
        return blocks_txs


class GraphQlAptosApi(GeneralApi):
    """
        playground: https://lucasconstantino.github.io/graphiql-online/
        """
    # _base_url = 'https://wqb9q2zgw7i7-mainnet.hasura.app/v1/graphql'
    _base_url = 'https://api.mainnet.aptoslabs.com/v1/graphql'
    SUPPORT_BATCH_GET_BLOCKS = True
    need_block_head_for_confirmation = True
    GET_BLOCK_ADDRESSES_MAX_NUM = 5000
    RESPONSE_BLOCK_MAX_NUM = 100
    currency = Currencies.apt
    cache_key = 'apt'
    symbol = 'APT'
    parser = GraphQlAptosResponseParser
    USE_PROXY = True
    back_off_time = 300

    supported_requests = {
        'get_txs': '',
        'get_block_head': '',
        'get_blocks_txs': ''
    }

    queries = {
        'get_block_head': """
                query block_head {
                processor_status(where: {processor: {_eq: "coin_processor"}}){
                    last_success_version
                    processor
                    }
                }
            """,
        'get_blocks_txs': """
                query get_block_txs($from: bigint, $to: bigint){
                  coin_activities(
                    where:{_and: [{transaction_version: {_gte: $from}}, {transaction_version: {_lt: $to}}],
                      entry_function_id_str: {_in: ["0x1::coin::transfer", "0x1::aptos_account::transfer", "0x1::aptos_account::transfer_coins"]},
                                    activity_type: {_in: ["0x1::coin::DepositEvent", "0x1::coin::WithdrawEvent"]},
                                    coin_type: {_eq: "0x1::aptos_coin::AptosCoin"},
                                    is_transaction_success: {_eq: true}
                    }
                    order_by:{transaction_version:asc}){
                    activity_type
                    amount
                    transaction_version
                    block_height
                    coin_type
                    entry_function_id_str
                    is_gas_fee
                    is_transaction_success
                    owner_address
                    transaction_timestamp
                    transaction_version
                  }
                }
            """,
        'get_txs': """
                query get_txs($address: String){
                    coin_activities(
                        limit: 25,
                        order_by: {transaction_version: desc},
                        where: {owner_address: {_eq: $address},
                        entry_function_id_str: {_in: ["0x1::coin::transfer", "0x1::aptos_account::transfer", "0x1::aptos_account::transfer_coins"]},
                        activity_type: {_in: ["0x1::coin::DepositEvent", "0x1::coin::WithdrawEvent"]},
                        coin_type: {_eq: "0x1::aptos_coin::AptosCoin"},
                        is_transaction_success: {_eq: true}}
                    )
                    {
                        activity_type
                        event_account_address
                        amount
                        transaction_version
                        block_height
                        coin_type
                        entry_function_id_str
                        is_gas_fee
                        is_transaction_success
                        owner_address
                        transaction_timestamp
                        transaction_version
                    }
                    processor_status(where: {processor: {_eq: "coin_processor"}}){
                            last_success_version
                            processor
                    }
                }
            """
    }

    @classmethod
    def get_headers(cls):
        headers = {
            'content-type': 'application/json',
            'Authorization': f'Bearer {cls.get_api_key()}',
        }
        return headers

    @classmethod
    def get_api_key(cls) -> Optional[str]:
        return random.choice(settings.APTOSLABS_API_KEY)

    @classmethod
    def get_block_head_body(cls):
        data = {
            'query': cls.queries.get('get_block_head'),
        }
        return json.dumps(data)

    @classmethod
    def get_address_txs_body(cls, address):
        data = {
            'query': cls.queries.get('get_txs'),
            'variables': {
                'address': address
            }
        }
        return json.dumps(data)

    @classmethod
    def get_blocks_txs_body(cls, from_block, to_block):
        params = {
            'query': cls.queries.get('get_blocks_txs'),
            'variables': {
                'from': from_block,
                'to': to_block
            }
        }
        return json.dumps(params)

    @classmethod
    def get_batch_block_txs(cls, from_block, to_block):
        blocks = []
        from_ = from_block
        while True:
            body = cls.get_blocks_txs_body(from_, to_block)
            response = cls.request('get_blocks_txs', body=body, headers=cls.get_headers())
            if response.get('data') and response.get('data').get('coin_activities') is not None:
                txs = response.get('data').get('coin_activities')
                blocks.extend(txs)
                # In here we check that the length of txs we get is more or less than the number of block responses/
                # and if it was more it means that we should request again to get the others
                if len(txs) < cls.RESPONSE_BLOCK_MAX_NUM:
                    break
                from_ = txs[-1].get('transaction_version') + 1
        return blocks
