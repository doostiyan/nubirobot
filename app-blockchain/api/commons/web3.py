import json
from decimal import Decimal
from typing import Dict, List, Optional, Union

from django.conf import settings

from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.general.dtos.dtos import TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.decorators import handle_exception
from exchange.blockchain.utils import (
    BlockchainUtilsMixin,
    get_currency_symbol_from_currency_code,
    split_batch_input_data,
)


class Web3ResponseValidator(ResponseValidator):
    non_batch_token_input_data = '0xa9059cbb'  # noqa: S105
    batch_token_input_data = '0xe6930a22'  # noqa: S105
    valid_input_len = [138]

    @classmethod
    def validate_balance_response(cls, balance_response: int) -> bool:
        return isinstance(balance_response, int)

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: dict) -> bool:
        return cls.validate_transaction(tx_details_response)

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, any]) -> bool:
        input_ = transaction.get('input').to_0x_hex()
        if transaction is None:
            return False
        if input_ not in ('0x', '0x0000000000000000000000000000000000000000'):
            return False
        if Decimal(transaction.get('value')) <= cls.min_valid_tx_amount:
            return False
        if transaction.get('from') == transaction.get('to'):
            return False
        if transaction.get('from') in cls.invalid_from_addresses_for_ETH_like:
            return False
        return True

    @classmethod
    def validate_token_transaction(cls, transaction: Dict[str, any]) -> bool:
        input_ = transaction.get('input').to_0x_hex()
        if transaction is None:
            return False
        if not ((input_[0:10] == cls.non_batch_token_input_data and len(input_) in cls.valid_input_len) or
                input_[0:10] == cls.batch_token_input_data):
            return False
        if transaction.get('from') == transaction.get('to'):
            return False
        if transaction.get('from') in cls.invalid_from_addresses_for_ETH_like:
            return False
        return True

    @classmethod
    def validate_tx_receipt_response(cls, tx_receipt_response: Dict[str, any]) -> bool:
        if not tx_receipt_response:
            return False
        if not tx_receipt_response.get('status') or not isinstance(tx_receipt_response.get('status'), int):
            return False
        return tx_receipt_response.get('status') == 1

    @classmethod
    def validate_block_head_response(cls, block_head_response: int) -> bool:
        return isinstance(block_head_response, int)

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: Dict[str, any]) -> bool:
        if block_txs_response.get('transactions') is None or len(block_txs_response.get('transactions')) < 1:
            return False
        return True

    @classmethod
    def validate_block_txs_raw_response(cls, block_txs_raw_response: Dict[str, any]) -> bool:
        if not block_txs_raw_response:
            return False
        if not cls.validate_block_txs_response(block_txs_raw_response):
            return False
        return True


class Web3ResponseParser(ResponseParser):
    validator = Web3ResponseValidator
    precision = 18

    @classmethod
    def parse_balance_response(cls, balance_response: int) -> Decimal:
        if not cls.validator.validate_balance_response(balance_response):
            return Decimal(0)
        return BlockchainUtilsMixin.from_unit(balance_response, precision=cls.precision)

    @classmethod
    def parse_token_balance_response(cls, balance_response: int, contract_info: Dict[str, Union[str, int]]) -> Decimal:
        if not cls.validator.validate_balance_response(balance_response):
            return Decimal(0)
        return BlockchainUtilsMixin.from_unit(balance_response, precision=contract_info.get('decimals'))

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, any], block_head: int) -> \
            Optional[List[TransferTx]]:
        if cls.validator.validate_transaction(tx_details_response):
            amount = tx_details_response.get('value')
            to_address = tx_details_response.get('to').lower()
            symbol = cls.symbol
            precision = cls.precision
            token = None

        elif cls.validator.validate_token_transaction(tx_details_response):
            input_ = tx_details_response.get('input').to_0x_hex()
            if input_[0:10] == cls.validator.batch_token_input_data:
                return cls.parse_batch_token_transfers(tx_details_response, block_head)
            amount = int(input_[74:138], 16)
            to_address = '0x' + input_[34:74]
            contract_address = tx_details_response.get('to').lower()
            currency, contract_address = cls.get_currency_by_contract(contract_address)
            if not currency:
                return None
            contract_info = cls.get_currency_info_by_contract(currency, contract_address)
            symbol = get_currency_symbol_from_currency_code(currency)
            precision = contract_info.get('decimals')
            token = contract_info.get('address')
        else:
            return None

        block = tx_details_response.get('blockNumber')
        confirmations = block_head - block

        return [TransferTx(
            block_height=block,
            block_hash=tx_details_response.get('blockHash').to_0x_hex(),
            tx_hash=tx_details_response.get('hash').to_0x_hex(),
            success=True,
            confirmations=confirmations,
            from_address=tx_details_response.get('from').lower(),
            to_address=to_address,
            value=BlockchainUtilsMixin.from_unit(amount, precision=precision),
            symbol=symbol,
            token=token,
        )]

    @classmethod
    def parse_batch_token_transfers(cls, batch_token_transfers_response: Dict[str, any],
                                    block_head: Optional[int] = None) -> List[TransferTx]:
        input_ = batch_token_transfers_response.get('input').to_0x_hex()
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
                tx_hash=batch_token_transfers_response.get('hash').to_0x_hex(),
                block_hash=batch_token_transfers_response.get('blockHash').to_0x_hex(),
                block_height=batch_token_transfers_response.get('blockNumber'),
                success=True,
                confirmations=confirmations
            )
            transfers.append(transfer)
        return transfers

    @classmethod
    def parse_tx_receipt_response(cls, tx_receipt_response: Dict[str, any]) -> bool:
        return cls.validator.validate_tx_receipt_response(tx_receipt_response)

    @classmethod
    def parse_block_head_response(cls, block_head_response: int) -> Optional[int]:
        if not cls.validator.validate_block_head_response(block_head_response):
            return None
        return block_head_response

    @classmethod
    def parse_block_txs_response(cls, block_txs_response: Dict[str, any]) -> List[TransferTx]:
        if not cls.validator.validate_block_txs_response(block_txs_response):
            return []
        transactions = block_txs_response.get('transactions')
        block_txs: List[TransferTx] = []
        for tx in transactions:
            if not tx.get('from') or not tx.get('to'):
                continue
            input_ = tx.get('input').to_0x_hex()
            if cls.validator.validate_transaction(tx):
                symbol = cls.symbol
                precision = cls.precision
                amount = int(tx.get('value'))
                to_address = tx.get('to').lower()
                contract_address = None

            elif cls.validator.validate_token_transaction(tx):
                if input_[0:10] == cls.validator.batch_token_input_data:
                    transfers = cls.parse_batch_token_transfers(tx)
                    block_txs.extend(transfers)
                    continue
                contract_address = tx.get('to').lower()
                currency, contract_address = cls.get_currency_by_contract(contract_address)
                if currency is None:
                    continue
                contract_info = cls.get_currency_info_by_contract(currency, contract_address)
                symbol = get_currency_symbol_from_currency_code(currency)
                precision = contract_info.get('decimals')
                amount = int(input_[74:138], 16)
                to_address = '0x' + input_[34:74]

            else:
                continue

            block_height = block_txs_response.get('number')

            block_tx = TransferTx(
                block_height=block_height,
                block_hash=tx.get('blockHash').to_0x_hex(),
                tx_hash=tx.get('hash').to_0x_hex(),
                success=True,
                from_address=tx.get('from').lower(),
                to_address=to_address,
                value=BlockchainUtilsMixin.from_unit(amount, precision=precision),
                symbol=symbol,
                token=contract_address,
                date=parse_utc_timestamp(block_txs_response.get('timestamp')),
            )
            block_txs.append(block_tx)
        return block_txs


class Web3Api(GeneralApi):
    parser = Web3ResponseParser
    need_transaction_receipt = True
    erc20_simple_abi = json.loads('[{"inputs":[{"internalType":"address","name":"account","type":"address"}],'
                                  '"name":"balanceOf","outputs":[{"internalType":"uint256","name":"","type":"uint256"}],"stateMutability":"view","type":"function"}]')

    def __init__(self) -> None:
        super().__init__()
        import asyncio
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())
        """
         The code above checks if an event loop exists, if not, create one. This is needed when code runs in a thread
         other than main thread(e.g. UpdateBlockHeadDiffCron in this project) because python does not create an event
         loop for it automatically.
        """
        from web3 import Web3
        requests_kwargs = {'timeout': 30}
        if self.USE_PROXY and not settings.IS_VIP:
            requests_kwargs['proxies'] = settings.DEFAULT_PROXY
        self.web3 = Web3(Web3.HTTPProvider(self._base_url, request_kwargs=requests_kwargs))

    @handle_exception
    def get_balance(self, address: str) -> int:
        checksum_address = self.web3.toChecksumAddress(address)
        return self.web3.eth.get_balance(checksum_address)

    @handle_exception
    def get_tx_details(self, tx_hash: str) -> dict:
        return self.web3.eth.get_transaction(tx_hash)

    @handle_exception
    def get_tx_receipt(self, tx_hash: str) -> dict:
        return self.web3.eth.get_transaction_receipt(tx_hash)

    @handle_exception
    def get_block_head(self) -> int:
        return self.web3.eth.get_block_number()

    @handle_exception
    def get_block_txs(self, block_height: int) -> dict:
        return self.web3.eth.get_block(block_identifier=block_height, full_transactions=True)

    @handle_exception
    def get_token_balance(self, address: str, contract_info: Dict[str, Union[str, int]]) -> int:
        checksum_address = self.web3.toChecksumAddress(address)
        contract_address = self.web3.toChecksumAddress(contract_info.get('address'))
        contract = self.web3.eth.contract(contract_address, abi=self.erc20_simple_abi)
        return contract.functions.balanceOf(checksum_address).call()
