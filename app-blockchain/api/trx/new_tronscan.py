import random
from decimal import Decimal
from typing import Dict, List, Union

from django.conf import settings

from exchange.base.models import Currencies
from exchange.base.parsers import parse_utc_timestamp_ms
from exchange.blockchain.api.general.dtos import Balance, TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.contracts_conf import TRC20_contract_currency, TRC20_contract_info
from exchange.blockchain.utils import BlockchainUtilsMixin


class TronscanTronValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.001')
    precision = 6

    @classmethod
    def validate_balance_response(cls, balance_response: Dict[str, any]) -> bool:
        if not balance_response:
            return False
        if balance_response.get('error'):
            return False
        if balance_response.get('message'):
            return False
        if not balance_response.get('balance'):
            return False
        return True

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: Dict[str, any]) -> bool:
        if not tx_details_response:
            return False
        if not tx_details_response.get('contractData') or not isinstance(tx_details_response.get('contractData'), dict):
            return False
        if not (tx_details_response.get('contractData').get('amount') or tx_details_response.get('contractData').get(
                'data')):
            return False
        if tx_details_response.get('contractRet') != 'SUCCESS' or tx_details_response.get('revert'):
            return False
        if not tx_details_response.get('confirmed'):
            return False
        if tx_details_response.get('riskTransaction'):
            return False

        return True

    @classmethod
    def validate_tx_details_transaction(cls, transaction: Dict[str, any]) -> bool:
        if not transaction.get('contractData', {}).get('amount'):
            return False
        if BlockchainUtilsMixin.from_unit(transaction.get('contractData', {}).get('amount'),
                                          precision=cls.precision) < cls.min_valid_tx_amount:
            return False
        if transaction.get('contractType') != 1:  # Only accept TRX transfers
            return False
        if transaction.get('cheat_status') != 0:
            return False

        return True

    @classmethod
    def validate_token_tx_details_transaction(cls, transaction: Dict[str, any]) -> bool:
        if not transaction.get('trc20TransferInfo'):
            return False
        if transaction.get('contract_type') != 'trc20':
            return False

        return True

    @classmethod
    def validate_token_transfer(cls, transfer: Dict[str, any], _: Dict[str, Union[str, any]]) -> bool:
        if transfer.get('type') != 'Transfer':
            return False
        if transfer.get('tokenType') != 'trc20':
            return False

        return True

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: Dict[str, any]) -> bool:
        if not address_txs_response:
            return False
        if address_txs_response.get('message'):
            return False
        if not address_txs_response.get('data'):
            return False

        return True

    @classmethod
    def validate_address_tx_transaction(cls, transaction: Dict[str, any]) -> bool:
        if transaction.get('contractRet') != 'SUCCESS' or transaction.get('revert'):
            return False
        if transaction.get('tokenName') != '_':  # token: '_' shows only TRX transfers;
            return False
        if not transaction.get('amount'):
            return False
        if BlockchainUtilsMixin.from_unit(transaction.get('amount'),
                                          precision=cls.precision) < cls.min_valid_tx_amount:
            return False
        if transaction.get('transferFromAddress') == transaction.get('transferToAddress'):
            return False
        if transaction.get('transferFromAddress') in ['TM9RwJndZHmDVLSZcY6J76ci22AzPp2krj',
                                                      'TVCAuYMw5afP96y5Wep866AXVWZJRH8fdo']:
            return False
        if transaction.get('riskTransaction'):
            return False
        if transaction.get('cheat_status'):
            return False
        return True

    @classmethod
    def validate_token_txs_response(cls, token_txs_response: Dict[str, any]) -> bool:
        if not token_txs_response:
            return False
        if not token_txs_response.get('token_transfers'):
            return False
        if token_txs_response.get('message'):
            return False

        return True

    @classmethod
    def validate_token_transaction(cls,
                                   transaction: Dict[str, any],
                                   contract_info: Dict[str, Union[str, int]],
                                   _: str = '') -> bool:
        if transaction.get('contract_type') != 'trc20':
            return False
        if transaction.get('contractRet') != 'SUCCESS':
            return False
        if transaction.get('finalResult') != 'SUCCESS':
            return False
        if not transaction.get('confirmed'):
            return False
        if transaction.get('revert'):
            return False
        if not transaction.get('trigger_info') or not isinstance(transaction.get('trigger_info'), dict):
            return False
        if transaction.get('trigger_info').get('methodName') != 'transfer':
            return False
        if transaction.get('trigger_info').get('data')[:8] != 'a9059cbb':  # Indicates 'transfer' transactions
            return False
        if not transaction.get('trigger_info').get('parameter'):
            return False
        if transaction.get('from_address') in ['TM9RwJndZHmDVLSZcY6J76ci22AzPp2krj',
                                               'TVCAuYMw5afP96y5Wep866AXVWZJRH8fdo']:
            return False
        if not transaction.get('trigger_info').get('parameter').get('_value'):
            return False
        if contract_info.get('address') != transaction.get('contract_address'):
            return False
        if contract_info.get('address') != transaction.get('trigger_info').get('contract_address'):
            return False

        return True


class TronscanTronParser(ResponseParser):
    validator = TronscanTronValidator
    symbol = 'TRX'
    precision = 6
    currency = Currencies.trx

    @classmethod
    def parse_balance_response(cls, balance_response: Dict[str, any]) -> Balance:
        if not cls.validator.validate_balance_response(balance_response):
            return Balance(
                balance=Decimal('0'),
            )
        return Balance(
            balance=Decimal(BlockchainUtilsMixin.from_unit(balance_response.get('balance'), precision=cls.precision)),
            address=balance_response.get('address'),
            symbol=cls.symbol
        )

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: Dict[str, any], _: int) -> List[TransferTx]:
        if not cls.validator.validate_tx_details_response(tx_details_response):
            return []

        transfers: List[TransferTx] = []

        # Parse TRX transfer
        if tx_details_response.get('contractData').get('amount'):
            if not cls.validator.validate_tx_details_transaction(tx_details_response):
                return []
            transfers.append(TransferTx(
                block_height=tx_details_response.get('block'),
                block_hash=None,
                tx_hash=tx_details_response.get('hash'),
                date=parse_utc_timestamp_ms(tx_details_response.get('timestamp')),
                success=True,
                confirmations=tx_details_response.get('confirmations'),
                from_address=tx_details_response.get('ownerAddress'),
                to_address=tx_details_response.get('toAddress'),
                value=BlockchainUtilsMixin.from_unit(tx_details_response.get('contractData', {}).get('amount'),
                                                     precision=cls.precision),
                symbol=cls.symbol,
                tx_fee=None,
                token=None)
            )

        # Parse Token transfers
        elif tx_details_response.get('contractData').get('data'):
            if not cls.validator.validate_token_tx_details_transaction(tx_details_response):
                return []
            for transfer in tx_details_response.get('trc20TransferInfo'):
                if not cls.validator.validate_token_transfer(transfer, {}):
                    return []
                currency = cls.contract_currency_list().get(transfer.get('contract_address'))
                contract_info = cls.contract_info_list().get(currency)
                if not currency:
                    return []
                transfers.append(TransferTx(
                    block_height=tx_details_response.get('block'),
                    block_hash=None,
                    tx_hash=tx_details_response.get('hash'),
                    date=parse_utc_timestamp_ms(tx_details_response.get('timestamp')),
                    success=True,
                    confirmations=tx_details_response.get('confirmations'),
                    from_address=transfer.get('from_address'),
                    to_address=transfer.get('to_address'),
                    value=BlockchainUtilsMixin.from_unit(int(transfer.get('amount_str'), ),
                                                         precision=contract_info.get('decimals')),
                    symbol=contract_info.get('symbol'),
                    tx_fee=None,
                    token=transfer.get('contract_address'))
                )
        return transfers

    @classmethod
    def parse_address_txs_response(cls,
                                   _: str,
                                   address_txs_response: Dict[str, any],
                                   __: int) -> List[TransferTx]:
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return []

        address_txs: List[TransferTx] = []
        for tx in address_txs_response.get('data'):
            if cls.validator.validate_address_tx_transaction(tx):
                confirmations = 20 if tx.get('confirmed') else 0
                address_tx = TransferTx(
                    block_height=tx.get('block'),
                    block_hash=None,
                    tx_hash=tx.get('transactionHash'),
                    date=parse_utc_timestamp_ms(tx.get('timestamp')),
                    success=True,
                    confirmations=confirmations,
                    from_address=tx.get('transferFromAddress'),
                    to_address=tx.get('transferToAddress'),
                    value=BlockchainUtilsMixin.from_unit(tx.get('amount'),
                                                         precision=cls.precision),
                    symbol=cls.symbol
                )
                address_txs.append(address_tx)

        return address_txs

    @classmethod
    def parse_token_txs_response(cls,
                                 _: str,
                                 token_txs_response: Dict[str, any],
                                 __: int,
                                 contract_info: Dict[str, Union[int, str]],
                                 ___: str = '') -> List[TransferTx]:
        if not cls.validator.validate_token_txs_response(token_txs_response):
            return []
        address_txs: List[TransferTx] = []
        for tx in token_txs_response.get('token_transfers'):
            if not cls.validator.validate_token_transaction(tx, contract_info):
                continue

            address_tx = TransferTx(
                block_height=tx.get('block'),
                block_hash=None,
                tx_hash=tx.get('transaction_id'),
                date=parse_utc_timestamp_ms(tx.get('block_ts')),
                success=True,
                confirmations=20 if tx.get('confirmed') else 0,
                from_address=tx.get('from_address'),
                to_address=tx.get('to_address'),
                value=BlockchainUtilsMixin.from_unit(
                    int(tx.get('trigger_info').get('parameter').get('_value')),
                    precision=contract_info.get('decimals')),
                symbol=contract_info.get('symbol'),
                token=tx.get('trigger_info').get('contract_address')
            )
            address_txs.append(address_tx)

        return address_txs

    @classmethod
    def contract_currency_list(cls) -> Dict[str, int]:
        return TRC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls) -> Dict[int, Dict[str, Union[str, int]]]:
        return TRC20_contract_info.get(cls.network_mode)


class TronscanTronApi(GeneralApi):
    parser = TronscanTronParser
    _base_url = 'https://apilist.tronscan.org/api'
    cache_key = 'trx'
    need_block_head_for_confirmation = False
    TRANSACTIONS_LIMIT = 25
    USE_PROXY = True

    supported_requests = {
        'get_balance': '/account?address={address}',
        'get_tx_details': '/transaction-info?hash={tx_hash}',
        'get_address_txs': '/transfer?sort=-timestamp&count=true&limit=' + str(
            TRANSACTIONS_LIMIT) + '&start=0&token=_&address={address}',
        'get_token_txs': '/token_trc20/transfers?limit=40&start=0&sort=-timestamp&count=true&relatedAddress={address}'
    }

    @classmethod
    def get_headers(cls) -> Dict[str, any]:
        return {
            'TRON-PRO-API-KEY': cls.get_api_key(),
            'User-Agent': 'Mozilla/5.0 (X11; Untu; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0',
            'Content-Type': 'application/json',
        }

    @classmethod
    def get_api_key(cls) -> str:
        return random.choice(settings.TRONSCAN_API_KEYS)
