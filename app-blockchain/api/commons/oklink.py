import random
from decimal import Decimal
from typing import Dict, List, Optional, Union

from django.conf import settings

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from blockchain.parsers import parse_utc_timestamp_ms
else:
    from exchange.base.parsers import parse_utc_timestamp_ms

from exchange.blockchain.api.general.dtos import Balance, TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator


class OklinkResponseValidator(ResponseValidator):
    @classmethod
    def validate_general_response(cls, response: Dict[str, any]) -> bool:
        if response.get('code') != '0':
            return False
        if not response.get('data'):
            return False
        return True

    @classmethod
    def validate_token_transaction(cls, transaction: Dict[str, any], contract_info: Dict[str, Union[str, int]]) -> bool:
        if transaction is None:
            return False
        if transaction.get('methodId') != '':
            return False
        if transaction.get('from') == transaction.get('to'):
            return False
        if transaction.get('from') in cls.invalid_from_addresses_for_ETH_like:
            return False
        if not transaction.get('tokenContractAddress'):
            return False
        if transaction.get('tokenContractAddress').casefold() != contract_info.get('address').casefold():
            return False
        if transaction.get('state') != 'success':
            return False
        if transaction.get('challengeStatus') != '':
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction: Dict[str, any]) -> bool:
        if transaction is None:
            return False
        if transaction.get('methodId'):
            return False
        if transaction.get('from') == transaction.get('to'):
            return False
        if transaction.get('from') in cls.invalid_from_addresses_for_ETH_like:
            return False
        if transaction.get('isFromContract'):
            return False
        if transaction.get('tokenContractAddress'):
            return False
        if transaction.get('state') != 'success':
            return False
        if Decimal(transaction.get('amount')) < cls.min_valid_tx_amount:
            return False
        return True

    @classmethod
    def validate_address_tx_transaction(cls, transaction: Dict[str, any]) -> bool:
        if not cls.validate_transaction(transaction):
            return False
        if transaction.get('challengeStatus') != '':
            return False
        return True

    @classmethod
    def validate_tx_details_transaction(cls, transaction: Dict[str, any]) -> bool:
        if not cls.validate_general_response(transaction):
            return False

        tx_details = transaction.get('data')[0]
        if tx_details.get('methodId') == '0xa9059cbb':
            transfer = tx_details.get('tokenTransferDetails')
            if len(transfer) != 1:
                return False
            if transfer[0].get('from') == transfer[0].get('to'):
                return False
            if transfer[0].get('from') in cls.invalid_from_addresses_for_ETH_like:
                return False
        else:
            if tx_details.get('methodId'):
                return False
            if tx_details.get('tokenContractAddress'):
                return False
            if tx_details.get('inputDetails')[0].get('inputHash') == tx_details.get(
                    'outputDetails'
            )[0].get('outputHash'):
                return False
        return True

    @classmethod
    def validate_balances_response(cls, balances_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(balances_response):
            return False
        if not balances_response.get('data')[0].get('balanceList'):
            return False
        return True

    @classmethod
    def validate_token_balance_response(cls, token_balance_response: Dict[str, any]) -> bool:
        if not cls.validate_general_response(token_balance_response):
            return False
        if not token_balance_response.get('data')[0].get('tokenList'):
            return False
        if not token_balance_response.get('data')[0].get('tokenList')[0].get('holdingAmount'):
            return False
        return True

    @classmethod
    def validate_block_txs_raw_response(cls, block_txs_raw_response: Dict[str, any]) -> bool:
        if not block_txs_raw_response or not isinstance(block_txs_raw_response, dict):
            return False
        if not block_txs_raw_response.get('data') or not isinstance(block_txs_raw_response.get('data'), list):
            return False
        if not block_txs_raw_response.get('data')[0] or not isinstance(block_txs_raw_response.get('data')[0], dict):
            return False
        if (not block_txs_raw_response.get('data')[0].get('blockList') or
                not isinstance(block_txs_raw_response.get('data')[0].get('blockList'), list)):
            return False
        return True


class OklinkResponseParser(ResponseParser):
    validator = OklinkResponseValidator

    @classmethod
    def parse_block_head_response(cls, block_head_response: Dict[str, any]) -> Optional[int]:
        if not cls.validator.validate_general_response(block_head_response):
            return None
        return int(block_head_response.get('data')[0].get('blockList')[0].get('height'))

    @classmethod
    def parse_address_txs_response(
            cls, _: str, address_txs_response: Dict[str, any], block_head: int
    ) -> List[TransferTx]:
        if not cls.validator.validate_general_response(address_txs_response):
            return []
        transactions = address_txs_response.get('data')[0].get('transactionLists')
        address_txs: List[TransferTx] = []
        for transaction in transactions:
            if cls.validator.validate_address_tx_transaction(transaction):
                address_tx = cls._parse_token_address_block_transaction(
                    transaction, block_head
                )
                address_txs.append(address_tx)
        return address_txs

    @classmethod
    def parse_token_txs_response(
            cls, _: str, token_txs_response: Dict[str, any], block_head: int, contract_info: Dict[str, Union[str, int]],
            __: str = '') -> List[TransferTx]:
        if not cls.validator.validate_general_response(token_txs_response):
            return []
        transactions = token_txs_response.get('data')[0].get('transactionLists')
        token_transfers: List[TransferTx] = []
        for transaction in transactions:
            if cls.validator.validate_token_transaction(transaction, contract_info):
                token_transfer = cls._parse_token_address_block_transaction(
                    transaction, block_head, contract_info
                )
                token_transfers.append(token_transfer)
        return token_transfers

    @classmethod
    def _parse_token_address_block_transaction(
            cls, transaction: Dict[str, any], block_head: Optional[int] = None,
            contract_info: Optional[Dict[str, Union[str, int]]] = None
    ) -> TransferTx:
        if contract_info and 'scale' in contract_info:
            value = Decimal(transaction.get('amount')) / Decimal(contract_info.get('scale'))
        else:
            value = Decimal(transaction.get('amount'))
        block_height = int(transaction.get('height'))
        return TransferTx(
            block_height=block_height,
            block_hash=transaction.get('blockHash'),
            tx_hash=transaction.get('txId') or transaction.get('txid'),
            date=parse_utc_timestamp_ms(transaction.get('transactionTime')),
            success=True,
            confirmations=block_head - block_height if block_head else None,
            from_address=transaction.get('from'),
            to_address=transaction.get('to'),
            value=value,
            tx_fee=Decimal(transaction.get('txFee') or 0)
            if contract_info or not block_head
            else None,
            symbol=cls.symbol,
            token=contract_info.get('address') if contract_info else None,
        )

    @classmethod
    def parse_block_txs_response(cls, block_txs_response: Dict[str, any]) -> List[TransferTx]:
        if not cls.validator.validate_general_response(block_txs_response):
            return []
        transactions = block_txs_response.get('data')[0].get('blockList')
        address_txs: List[TransferTx] = []
        for transaction in transactions:
            if cls.validator.validate_transaction(transaction):
                address_tx = cls._parse_token_address_block_transaction(transaction)
                address_txs.append(address_tx)
        return address_txs

    @classmethod
    def parse_tx_details_response(
            cls, tx_details_response: Dict[str, any], _: int
    ) -> List[TransferTx]:
        transfer_tx = []
        if cls.validator.validate_tx_details_transaction(tx_details_response):
            tx_details = tx_details_response.get('data').pop()
            if tx_details.get('methodId') == '0xa9059cbb':
                transfer_tx.append(cls._parse_tx_details_token_transaction(tx_details))
            else:
                transfer_tx.append(cls._parse_tx_details_transaction(tx_details))
        return transfer_tx

    @classmethod
    def _parse_tx_details_token_transaction(cls, transaction: Dict[str, any]) -> TransferTx:
        token_transfer_details = transaction.get('tokenTransferDetails').pop()
        return TransferTx(
            block_height=int(transaction.get('height')),
            block_hash=None,
            tx_hash=transaction.get('txid'),
            date=parse_utc_timestamp_ms(transaction.get('transactionTime')),
            success=True,
            confirmations=transaction.get('confirm'),
            from_address=token_transfer_details.get('from'),
            to_address=token_transfer_details.get('to'),
            tx_fee=Decimal(transaction.get('txfee') or 0),
            value=Decimal(token_transfer_details.get('amount')),
            symbol=token_transfer_details.get('symbol'),
            token=token_transfer_details.get('tokenContractAddress'),
        )

    @classmethod
    def _parse_tx_details_transaction(cls, transaction: Dict[str, any]) -> TransferTx:
        return TransferTx(
            block_height=int(transaction.get('height')),
            block_hash=None,
            tx_hash=transaction.get('txid'),
            date=parse_utc_timestamp_ms(transaction.get('transactionTime')),
            success=True,
            confirmations=transaction.get('confirm'),
            from_address=transaction.get('inputDetails').pop().get('inputHash'),
            to_address=transaction.get('outputDetails').pop().get('outputHash'),
            tx_fee=Decimal(transaction.get('txfee') or 0),
            value=Decimal(transaction.get('amount')),
            symbol=cls.symbol,
        )

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, any]) -> Decimal:
        if not cls.validator.validate_general_response(balance_response):
            return Decimal(0)
        return Decimal(balance_response.get('data')[0].get('balance', 0))

    @classmethod
    def parse_balances_response(cls, balances_response: Dict[str, any]) -> List[Balance]:
        if not cls.validator.validate_balances_response(balances_response):
            return []
        data = balances_response.get('data').pop()
        balances = []
        for balance in data.get('balanceList'):
            balances.append(
                Balance(
                    balance=Decimal(balance.get('balance', 0)),
                    address=balance.get('address')
                )
            )
        return balances

    @classmethod
    def parse_token_balance_response(
            cls, balance_response: Dict[str, any], _: dict
    ) -> Decimal:
        if not cls.validator.validate_token_balance_response(balance_response):
            return Decimal(0)
        token_list = balance_response.get('data').pop().get('tokenList').pop()
        return Decimal(token_list.get('holdingAmount', 0))

    @classmethod
    def parse_token_balances_response(cls, token_balances_response: Dict[str, any]) -> List[Balance]:
        if not cls.validator.validate_balances_response(token_balances_response):
            return []

        data = token_balances_response.get('data').pop()
        balances = []
        for balance in data.get('balanceList'):
            for contract_info in cls.contract_info_list().values():
                # in "tokenContractAddress" addresses are lower case
                if balance.get('tokenContractAddress').casefold() == contract_info.get('address').casefold():
                    balances.append(
                        Balance(
                            balance=Decimal(balance.get('holdingAmount', 0)),
                            address=balance.get('address'),
                            token=contract_info.get('address'),
                            symbol=contract_info.get('symbol')
                        )
                    )
        return balances


class OklinkApi(GeneralApi):
    parser = OklinkResponseParser
    _base_url = 'https://www.oklink.com/api/v5/explorer'

    USE_PROXY = True

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.AVALANCHE_OKLINK_API_KEY)

    @classmethod
    def get_headers(cls) -> Dict[str, str]:
        return {'Ok-Access-Key': cls.get_api_key()}
