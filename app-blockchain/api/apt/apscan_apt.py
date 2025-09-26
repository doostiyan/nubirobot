from typing import List
from decimal import Decimal
from django.conf import settings

from exchange.blockchain.api.apt.aptos_general import AptosParser, AptosGeneral
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.utils import BlockchainUtilsMixin
from exchange.blockchain.api.general.general import ResponseValidator

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_timestamp_microseconds

else:
    from exchange.base.parsers import parse_timestamp_microseconds


class ApscanValidator(ResponseValidator):
    valid_transfer_types = ['0x1::coin::WithdrawEvent', '0x1::coin::DepositEvent']
    valid_token = ['0x1::aptos_coin::AptosCoin']
    valid_function_types = ['0x1::coin::transfer', '0x1::aptos_account::transfer', '0x1::aptos_account::transfer_coins']
    min_valid_tx_amount = Decimal('0.025')
    precision = 8

    @classmethod
    def validate_general_response(cls, response):
        if response:
            return True
        return False

    @classmethod
    def validate_block_head_response(cls, block_head_response) -> bool:
        if (cls.validate_general_response(block_head_response)
                and isinstance(block_head_response, list)
                and block_head_response[0].get('latest_transaction_version')):
            return True
        return False

    @classmethod
    def validate_tx_details_response(cls, tx_details_response) -> bool:
        return cls.validate_general_response(tx_details_response)

    @classmethod
    def validate_address_txs_response(cls, address_txs_response) -> bool:
        return cls.validate_general_response(address_txs_response)

    @classmethod
    def validate_address_tx_transaction(cls, transaction) -> bool:
        if not (any(transaction.get(key) for key in ['transaction_version', 'type', 'move_resource_generic_type_params',
                                                     'coin_info', 'counter_party', 'data'])):
            return False
        if (not transaction.get('transaction_version')  # not empty version
                or transaction.get('type') not in cls.valid_transfer_types
                or transaction.get('move_resource_generic_type_params') != cls.valid_token
                or transaction.get('coin_info') != {'symbol': 'APT', 'decimals': '8', 'name': 'Aptos Coin'}
                or not transaction.get('counter_party')  # not empty main field for to_address or from_address
                or BlockchainUtilsMixin.from_unit(int(transaction.get('data').get('amount')),
                                                  cls.precision) < cls.min_valid_tx_amount):
            return False
        return True

    @classmethod
    def validate_tx_details_transaction(cls, transaction) -> bool:
        if not (any(transaction.get(key) for key in ['version', 'success', 'vm_status', 'type', 'payload'])):
            return False
        if (not transaction.get('version')  # not empty version
                or not transaction.get('success')  # for success tx must be true
                or transaction.get('vm_status') != 'Executed successfully'  # status of success tx
                or transaction.get('type') != 'user_transaction'  # type of success tx
                or transaction.get('payload').get('type') != 'entry_function_payload'
                or transaction.get('payload').get('function') not in cls.valid_function_types
                or len(transaction.get('payload').get('arguments')) != 2
                or (transaction.get('payload').get('type_arguments') != cls.valid_token
                    and transaction.get('payload').get('type_arguments'))
                # The first index of the argument contains to_address and the second index contains the value
                or BlockchainUtilsMixin.from_unit(int(transaction.get('payload').get('arguments')[1]),
                                                  cls.precision) <= cls.min_valid_tx_amount):
            return False
        return True


class ApscanParser(AptosParser):
    validator = ApscanValidator

    @classmethod
    def parse_block_head_response(cls, block_head_response):
        if cls.validator.validate_block_head_response(block_head_response):
            return block_head_response[0].get('latest_transaction_version')

    @classmethod
    def parse_tx_details_response(cls, tx_details_response, block_head) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=int(tx_details_response[0].get('version')),
                block_hash=None,
                tx_hash=str(tx_details_response[0].get('version')),
                date=parse_timestamp_microseconds(int(tx_details_response[0].get('time_microseconds')), cls.precision),
                success=True,
                confirmations=block_head - int(tx_details_response[0].get('version')),
                from_address=cls.unify_address(tx_details_response[0].get('sender')),
                to_address=cls.unify_address(tx_details_response[0].get('payload').get('arguments')[0]),
                value=BlockchainUtilsMixin.from_unit(
                    int(tx_details_response[0].get('payload').get('arguments')[1]), cls.precision),
                symbol=cls.symbol,
                memo=None,
                tx_fee=BlockchainUtilsMixin.from_unit(
                    int(tx_details_response[0].get('gas_used'))
                    * int(tx_details_response[0].get('user_transaction_detail').get('gas_unit_price')), cls.precision),
                token=None,
            )
        ] if (cls.validator.validate_tx_details_response(tx_details_response)
              and cls.validator.validate_tx_details_transaction(tx_details_response[0])) else []

    @classmethod
    def parse_address_txs_response(cls, address, address_txs_response, block_head) -> List[TransferTx]:
        if cls.validator.validate_address_txs_response(address_txs_response):
            transfers = []
            for tx in address_txs_response:
                if cls.validator.validate_address_tx_transaction(tx):
                    to_address = None
                    from_address = None
                    if tx.get('type') == '0x1::coin::DepositEvent':
                        to_address = tx.get('address')
                        from_address = tx.get('counter_party').get('address')
                    elif tx.get('type') == '0x1::coin::WithdrawEvent':
                        from_address = tx.get('address')
                        to_address = tx.get('counter_party').get('address')
                    transfers.append(
                        TransferTx(
                            block_height=int(tx.get('transaction_version')),
                            block_hash=None,
                            tx_hash=str(tx.get('transaction_version')),
                            date=parse_timestamp_microseconds(int(tx.get('time_microseconds'))),
                            success=True,
                            confirmations=block_head - int(tx.get('transaction_version')),
                            from_address=cls.unify_address(from_address),
                            to_address=cls.unify_address(to_address),
                            value=BlockchainUtilsMixin.from_unit(int(tx.get('data').get('amount')), cls.precision),
                            symbol=cls.symbol,
                            memo=None,
                            tx_fee=None,
                            token=None,
                        )
                    )
            return transfers

    @classmethod
    def unify_address(cls, address):
        if address and type(address) is str:
            if address.startswith('0x'):
                address = address[2:]
            padded_address = address.rjust(cls.EXPECTED_ADDRESS_LENGTH, '0')
            return '0x' + padded_address
        return address


class ApscanApi(AptosGeneral):
    parser = ApscanParser
    # This Api does NOT have testnet yet.
    _base_url = 'https://api.apscan.io'
    instance = None
    USE_PROXY = True
    supported_requests = {
        'get_block_head': '/blockchain_stats',
        'get_address_txs': '/coin_transfers?address=eq.{address}&limit=25',
        'get_tx_details': '/transactions?version=eq.{tx_hash}'
    }
