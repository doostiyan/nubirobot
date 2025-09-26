import random
from typing import List

from django.conf import settings

from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import (
    GeneralApi,
    ResponseParser,
    ResponseValidator,
)
from exchange.blockchain.utils import (
    BlockchainUtilsMixin,
    get_currency_symbol_from_currency_code,
    split_batch_input_data,
)


class EthLikeTatumResponseValidator(ResponseValidator):
    batch_token_input_data = '0xe6930a22'  # noqa: S105
    non_batch_token_input_data = '0xa9059cbb'  # noqa: S105
    precision = 18
    valid_input_len = 138

    @classmethod
    def validate_block_head_response(cls, block_head_response: int) -> bool:
        if not block_head_response:
            return False
        if not isinstance(block_head_response, int):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: dict) -> bool:
        if tx_details_response is None:
            return False
        if tx_details_response.get('transactionHash') is None:
            return False
        if tx_details_response.get('blockHash') is None:
            return False
        if tx_details_response.get('blockNumber') is None:
            return False
        if tx_details_response.get('from') is None:
            return False
        if tx_details_response.get('gas') is None:
            return False
        if tx_details_response.get('gasPrice') is None:
            return False
        if tx_details_response.get('input') is None:
            return False
        if tx_details_response.get('nonce') is None:
            return False
        if tx_details_response.get('value') is None:
            return False
        if tx_details_response.get('type') is None:
            return False
        if tx_details_response.get('chainId') is None:
            return False
        if tx_details_response.get('status') is not True:
            return False
        return True

    @classmethod
    def validate_token_tx_details_response(cls, tx_details_response: dict) -> bool:
        key2check = ['transactionHash', 'blockHash', 'blockNumber', 'transactionHash', 'status', 'from',
                     'to', 'logs']
        for key in key2check:
            if not tx_details_response.get(key):
                return False
        input_ = tx_details_response.get('input')
        if not ((input_[0:10] == cls.non_batch_token_input_data and len(input_) == cls.valid_input_len)
                or input_[
                   0:10] == cls.batch_token_input_data):
            return False
        # We need to check about the Transfer transactions
        # So when logs parameter has more than 1 its guaranty that we have swap or other type transaction
        if tx_details_response.get('from') == tx_details_response.get('to'):
            return False
        if tx_details_response.get('from') in cls.invalid_from_addresses_for_ETH_like:
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction: dict) -> bool:
        if not transaction or not isinstance(transaction, dict):
            return False
        if not transaction.get('blockNumber') or not isinstance(transaction.get('blockNumber'), int):
            return False
        if not transaction.get('transactionHash') or not isinstance(transaction.get('transactionHash'), str):
            return False
        if not transaction.get('status') or not isinstance(transaction.get('status'), bool):
            return False
        if not transaction.get('from') or not isinstance(transaction.get('from'), str):
            return False
        if not transaction.get('to') or not isinstance(transaction.get('to'), str):
            return False
        if transaction.get('from') == transaction.get('to'):
            return False
        if not transaction.get('value') or not isinstance(transaction.get('value'), str):
            return False
        value = BlockchainUtilsMixin.from_unit(int(transaction.get('value')), cls.precision)
        if value <= cls.min_valid_tx_amount:
            return False
        if not transaction.get('gasUsed') or not isinstance(transaction.get('gasUsed'), int):
            return False
        if transaction.get('from') in cls.invalid_from_addresses_for_ETH_like:
            return False
        return True


class EthLikeTatumResponseParser(ResponseParser):
    validator = EthLikeTatumResponseValidator
    symbol = ''
    currency = None
    precision = 18

    @classmethod
    def parse_block_head_response(cls, block_head_response: int) -> int:
        if cls.validator.validate_block_head_response(block_head_response):  # noqa: RET503
            return block_head_response

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: dict, block_head: int) -> List[TransferTx]:
        if cls.validator.validate_tx_details_response(tx_details_response) and cls.validator.validate_transaction(
                tx_details_response):
            return [TransferTx(
                block_height=tx_details_response.get('blockNumber'),
                block_hash=tx_details_response.get('blockHash'),
                tx_hash=tx_details_response.get('transactionHash'),
                success=True,
                confirmations=block_head - tx_details_response.get('blockNumber'),
                from_address=tx_details_response.get('from'),
                to_address=tx_details_response.get('to'),
                value=BlockchainUtilsMixin.from_unit(int(tx_details_response.get('value')),
                                                     precision=cls.precision),
                symbol=cls.symbol,
                tx_fee=
                BlockchainUtilsMixin.from_unit(
                    int(tx_details_response.get('gas', 0)) * int(tx_details_response.get('gasPrice', 0)),
                    precision=cls.precision
                )
            )]
        return []

    @classmethod
    def parse_token_tx_details_response(cls, token_tx_details_response: dict, block_head: int) -> List[TransferTx]:
        token_transfers = []
        if cls.validator.validate_token_tx_details_response(token_tx_details_response):
            log_events = token_tx_details_response.get('logs')
            input_ = token_tx_details_response.get('input')
            if input_[0:10] == cls.validator.batch_token_input_data:
                return cls.parse_batch_token_transfers(token_tx_details_response, block_head)
            contract_address_response = token_tx_details_response.get('to')
            currency = cls.contract_currency_list().get(contract_address_response)
            if currency is None:
                return []

            contract_info = cls.contract_info_list().get(currency)
            fee = BlockchainUtilsMixin.from_unit(
                int(token_tx_details_response.get('gas', 0)) * int(token_tx_details_response.get('gasPrice', 0)),
                precision=cls.precision
            )

            token_transfers.append(TransferTx(
                block_height=token_tx_details_response.get('blockNumber'),
                block_hash=token_tx_details_response.get('blockHash'),
                tx_hash=token_tx_details_response.get('transactionHash'),
                success=token_tx_details_response.get('status'),
                confirmations=block_head - token_tx_details_response.get('blockNumber'),
                from_address=token_tx_details_response.get('from'),
                # log_events[0]: the first log in the list of emitted logs for a transaction
                # .get('topics')[2]: the third topic (index 2), which often contains the to address.
                # [-40:]: takes the last 40 hex characters = 20 bytes (length of an Ethereum address).
                # '0x' + ...: formats it into a proper Ethereum address.
                to_address='0x' + log_events[0].get('topics')[2][-40:],
                value=BlockchainUtilsMixin.from_unit(int(log_events[0].get('data'), 16),
                                                     contract_info.get('decimals')),
                symbol=contract_info.get('symbol'),
                tx_fee=fee,
                token=contract_address_response,
            ))
        return token_transfers

    @classmethod
    def parse_batch_token_transfers(cls, batch_token_transfers_response: dict, block_head: int) -> List[TransferTx]:
        input_ = batch_token_transfers_response.get('input')
        _, tokens, addresses, values = split_batch_input_data(input_[10:], input_[10:][192:256])
        transfers_count = len(tokens)
        transfers: List[TransferTx] = []
        for i in range(0, transfers_count, 64):
            token = '0x' + tokens[i: i + 64][24:64]
            currency, contract_address = cls.get_currency_by_contract(token.lower())
            if not currency:
                continue
            contract_info = cls.get_currency_info_by_contract(currency, contract_address)
            if not contract_info:
                continue
            confirmations = block_head - batch_token_transfers_response.get('blockNumber') if block_head else 0
            # because the from address of token transfers is from the contract which is "to" address in tx
            transfer = TransferTx(
                from_address=batch_token_transfers_response.get('to').lower(),
                to_address='0x' + addresses[i: i + 64][24:64].lower(),
                value=BlockchainUtilsMixin.from_unit(int(values[i: i + 64], 16), contract_info.get('decimals')),
                symbol=get_currency_symbol_from_currency_code(currency),
                token=contract_info.get('address').lower(),
                tx_hash=batch_token_transfers_response.get('transactionHash'),
                block_hash=batch_token_transfers_response.get('blockHash'),
                block_height=batch_token_transfers_response.get('blockNumber'),
                success=True,
                confirmations=confirmations
            )
            transfers.append(transfer)
        return transfers


class EthLikeTatumApi(GeneralApi):
    symbol = ''
    cache_key = ''
    currency = None
    parser = EthLikeTatumResponseParser
    _base_url = ''
    supported_requests = {
        'get_block_head': 'block/current',
        'get_token_tx_details': 'transaction/{tx_hash}',
        'get_tx_details': 'transaction/{tx_hash}'
    }

    @classmethod
    def get_headers(cls) -> dict:
        return {
            'Content-Type': 'application/json',
            'X-API-KEY': cls.get_api_key()
        }

    @classmethod
    def get_api_key(cls) -> int:
        return random.choice(settings.TATUM_API_KEYS)
