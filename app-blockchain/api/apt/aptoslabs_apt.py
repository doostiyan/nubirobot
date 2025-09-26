from typing import List
from decimal import Decimal
from django.conf import settings
from exchange.blockchain.api.apt.aptos_general import AptosGeneral, AptosParser
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_timestamp_microseconds

else:
    from exchange.base.parsers import parse_timestamp_microseconds


class AptoslabsAptValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.025')
    valid_token = ['0x1::aptos_coin::AptosCoin']
    valid_resources = ['0x1::coin::CoinStore<0x1::aptos_coin::AptosCoin>']
    valid_transfer_types = ['0x1::aptos_account::transfer', '0x1::coin::transfer', '0x1::aptos_account::transfer_coins']
    precision = 8

    @classmethod
    def validate_general_response(cls, response):
        if response:
            return True
        return False

    @classmethod
    def validate_block_head_response(cls, block_head_response) -> bool:
        if cls.validate_general_response(block_head_response) and block_head_response.get('ledger_version'):
            return True
        return False

    @classmethod
    def validate_balance_response(cls, balance_response) -> bool:
        if (balance_response.get('type')
                and balance_response.get('type') in cls.valid_resources
                and balance_response.get('data')
                and balance_response.get('data').get('coin')
                and balance_response.get('data').get('coin').get('value')
                and isinstance(balance_response.get('data').get('coin').get('value'), str)):
            return True
        return False

    @classmethod
    def validate_tx_details_response(cls, tx_details_response) -> bool:
        return cls.validate_general_response(tx_details_response)

    @classmethod
    def validate_transaction(cls, transaction) -> bool:
        # The fields of transaction should not be None
        if not any(transaction.get(key) for key in ('type', 'version', 'success', 'vm_status', 'payload')):
            return False
            # transaction type must be 'user_transaction'
        if (transaction.get('type').casefold() != 'user_transaction'.casefold()
                or not transaction.get('success')
                # status of success transaction
                or transaction.get('vm_status').casefold() != 'Executed successfully'.casefold()
                # check transfer type
                or not transaction.get('payload').get('function') in cls.valid_transfer_types
                or (transaction.get('payload').get('type_arguments')
                    # token validation
                    and transaction.get('payload').get('type_arguments') != cls.valid_token)
                or transaction.get('payload').get('type').casefold() != 'entry_function_payload'.casefold()
                or BlockchainUtilsMixin.from_unit(  # check amount of tx
                    # The first index of the argument contains to_address and the second index contains the value
                    int(transaction.get('payload').get('arguments')[1]), cls.precision) < cls.min_valid_tx_amount):
            return False
        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response) -> bool:
        return cls.validate_general_response(address_txs_response)

    @classmethod
    def validate_batch_block_txs_response(cls, block_txs_response) -> bool:
        return cls.validate_general_response(block_txs_response)

    @classmethod
    def validate_block_txs_raw_response(cls, block_txs_raw_response) -> bool:
        if not block_txs_raw_response or not isinstance(block_txs_raw_response, list):
            return False
        return True

class AptoslabsAptParser(AptosParser):
    validator = AptoslabsAptValidator

    @classmethod
    def parse_block_head_response(cls, block_head_response):
        if cls.validator.validate_block_head_response(block_head_response):
            return int(block_head_response.get('ledger_version'))

    @classmethod
    def parse_balance_response(cls, balance_response) -> Decimal:
        if cls.validator.validate_general_response(balance_response):
            for coin in balance_response:
                if cls.validator.validate_balance_response(coin):
                    return BlockchainUtilsMixin.from_unit(int(coin.get('data').get('coin').get('value')), cls.precision)
        return Decimal('0')

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=int(tx_details_response.get('version')),
                block_hash=None,
                tx_hash=str(tx_details_response.get('version')),
                date=parse_timestamp_microseconds(int(tx_details_response.get('timestamp'))),
                success=True,
                confirmations=block_head - int(tx_details_response.get('version')),
                from_address=cls.unify_address(tx_details_response.get('sender')),
                to_address=cls.unify_address(tx_details_response.get('payload').get('arguments')[0]),
                value=BlockchainUtilsMixin.from_unit(
                    int(tx_details_response.get('payload').get('arguments')[1]), cls.precision),
                symbol=cls.symbol,
                memo=None,
                tx_fee=BlockchainUtilsMixin.from_unit(
                    int(tx_details_response.get('gas_used')) * int(tx_details_response.get('gas_unit_price')),
                    cls.precision),
                token=None,
            )
        ] if (cls.validator.validate_tx_details_response(tx_details_response)
              and cls.validator.validate_transaction(tx_details_response)) else []

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=int(tx.get('version')),
                block_hash=None,
                tx_hash=str(tx.get('version')),
                date=parse_timestamp_microseconds(int(tx.get('timestamp'))),
                success=True,
                confirmations=block_head - int(tx.get('version')),
                from_address=cls.unify_address(tx.get('sender')),
                to_address=cls.unify_address(tx.get('payload').get('arguments')[0]),
                value=BlockchainUtilsMixin.from_unit(int(tx.get('payload').get('arguments')[1]), cls.precision),
                symbol=cls.symbol,
                memo=None,
                tx_fee=BlockchainUtilsMixin.from_unit(
                    int(tx.get('gas_used')) * int(tx.get('gas_unit_price')), cls.precision),
                token=None,
            )
            for tx in address_txs_response
            if cls.validator.validate_transaction(tx)
        ] if cls.validator.validate_address_txs_response(address_txs_response) else []

    @classmethod
    def parse_batch_block_txs_response(cls, block_txs_response) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=int(tx.get('version')),
                block_hash=None,
                tx_hash=str(tx.get('version')),
                date=parse_timestamp_microseconds(int(tx.get('timestamp'))),
                success=True,
                confirmations=None,
                from_address=cls.unify_address(tx.get('sender')),
                to_address=cls.unify_address(tx.get('payload').get('arguments')[0]),
                value=BlockchainUtilsMixin.from_unit(int(tx.get('payload').get('arguments')[1]), cls.precision),
                symbol=cls.symbol,
                memo=None,
                tx_fee=BlockchainUtilsMixin.from_unit(
                    int(tx.get('gas_used')) * int(tx.get('gas_unit_price')), cls.precision),
                token=None,
            )
            for block in block_txs_response
            for tx in [block]
            if cls.validator.validate_transaction(tx)
        ] if cls.validator.validate_batch_block_txs_response(block_txs_response) else []


class AptoslabsAptApi(AptosGeneral):
    """
    API docs: https://fullnode.devnet.aptoslabs.com/v1/spec#/
    """
    parser = AptoslabsAptParser
    _base_url = 'https://fullnode.mainnet.aptoslabs.com/v1'
    testnet_url = 'https://fullnode.testnet.aptoslabs.com/v1'
    USE_PROXY = True if not settings.IS_VIP else False
    supported_requests = {
        'get_block_head': '',
        'get_address_txs': '/accounts/{address}/transactions',
        'get_tx_details': '/transactions/by_version/{tx_hash}',
        'get_blocks_txs': '/transactions?start={start_versionid}&limit={limit}',
        'get_balance': '/accounts/{address}/resources'
    }
    SUPPORT_BATCH_GET_BLOCKS = True
    GET_BLOCK_ADDRESSES_MAX_NUM = 10000
    MAX_NUM_BLOCK_PER_REQUEST = 25
    instance = None

    @classmethod
    def get_headers(cls):
        return {'content-type': 'application/json'}

    @classmethod
    def get_batch_block_txs(cls, from_block, to_block):
        versions = []
        for min_chunk in range(from_block, to_block, cls.MAX_NUM_BLOCK_PER_REQUEST):
            response = cls.request('get_blocks_txs',
                                   start_versionid=min_chunk,
                                   limit=min(cls.MAX_NUM_BLOCK_PER_REQUEST, to_block - min_chunk + 1),
                                   headers=cls.get_headers(), apikey=cls.get_api_key())
            versions += response
        return versions
