import concurrent.futures
import sys
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
from itertools import chain
from typing import Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.core.cache import cache

from exchange.base.models import Currencies
from exchange.base.parsers import parse_currency
from exchange.blockchain.api.commons.web3 import Web3Api
from exchange.blockchain.api.general.dtos import Balance
from exchange.blockchain.api.general.dtos.dtos import (
    NewBalancesV2,
    SelectedCurrenciesBalancesRequest,
    TransferTx,
)
from exchange.blockchain.api.general.dtos.get_all_validators_response import (
    GetAllValidatorsResponse,
    ValidatorInfo,
)
from exchange.blockchain.api.general.dtos.get_wallet_staking_reward_response import (
    GetWalletStakingRewardResponse,
    TargetValidator,
)
from exchange.blockchain.api.general.general import GeneralApi
from exchange.blockchain.api.general.general_staking import GeneralStakingApi
from exchange.blockchain.contracts_conf import (
    BASE_ERC20_contract_info,
    BEP20_contract_info,
    ERC20_contract_info,
    TRC20_contract_info,
    arbitrum_ERC20_contract_info,
    sol_contract_info,
    ton_contract_info,
)
from exchange.blockchain.logger_util import logger
from exchange.blockchain.metrics import metric_incr, metric_set
from exchange.blockchain.utils import EXTRA_FIELD_NEEDED_CURRENCIES, APIError


class Meta(type):
    block_txs_apis = []

    def __init__(cls, name: str, bases: any, dct: dict) -> None:
        super().__init__(name, bases, dct)
        if cls.block_txs_apis:
            cls.threadpool = ThreadPoolExecutor(max_workers=cls.block_txs_apis[0].max_workers_for_get_block)
        else:
            cls.threadpool = ThreadPoolExecutor(max_workers=1)


class ExplorerInterface(metaclass=Meta):
    block_head_apis = []
    balance_apis = []
    token_balance_apis = []
    address_txs_apis = []
    token_txs_apis = []
    block_txs_apis = []
    tx_details_apis = []
    token_tx_details_apis = []
    staking_apis: List[GeneralStakingApi] = []
    symbol = ''
    network = None
    instance = None
    min_valid_tx_amount = 0
    max_block_per_time = 100
    max_workers_for_get_block = 1
    SUPPORT_BATCH_BLOCK_PROCESSING = False
    TRANSACTION_DETAILS_BATCH = False
    IS_PROVIDER_CHECK = False
    USE_BLOCK_HEAD_API = False
    USE_AGGREGATION_SERVICE = False

    @property
    def SUPPORT_GET_BALANCE_BATCH(self) -> bool:  # noqa: N802
        return self.balance_apis[0].SUPPORT_GET_BALANCE_BATCH

    @classmethod
    def get_api(cls, is_provider_check: bool = False, *args: any, **kwargs: any) -> 'ExplorerInterface':
        if is_provider_check:
            instance = cls()
            instance.IS_PROVIDER_CHECK = True
            return instance

        if cls.instance is None or cls.instance.__class__ != cls:
            cls.instance = cls()
        return cls.instance

    def get_provider(self, operation: str, apis: List[GeneralApi]) -> GeneralApi:
        if settings.IS_EXPLORER_SERVER:
            from exchange.explorer.utils.cache import CacheUtils

            symbol = self.network or self.symbol
            cache_key = f'check_{symbol}_{operation}' if self.IS_PROVIDER_CHECK else f'{symbol}_{operation}'

            provider_data = CacheUtils.read_from_external_cache(cache_key)

            for api in apis:
                if api.get_instance().get_name() == provider_data.provider_name:
                    provider = api if self.IS_PROVIDER_CHECK else api.get_instance()
                    provider._base_url = provider_data.base_url  # noqa: SLF001
                    if isinstance(provider, Web3Api):
                        provider.web3.manager._provider.endpoint_uri = provider._base_url  # noqa: SLF001
                    break
            else:
                from exchange.explorer.networkproviders.models import Provider
                raise Provider.DoesNotExist
        else:
            provider = apis[0].get_instance()
        return provider

    def sample_get_blocks(self, provider: str, min_block: int, max_block: int) -> List[TransferTx]:
        provider = self.find_api(provider, self.block_txs_apis)
        if not isinstance(provider, str):
            transfers, _ = self.fetch_latest_block(provider, min_block, max_block)
            return transfers
        return []

    def find_api(self, provider: str, apis: list) -> GeneralApi:
        for api in apis:
            if api.get_instance().get_name() == provider:
                provider = api.get_instance()
                break
        return provider

    def sample_get_tx_details(self, provider: str, tx_hash: str) -> list:
        provider = self.find_api(provider, self.tx_details_apis)
        if isinstance(provider, str):
            return []
        if provider.need_transaction_receipt:
            tx_receipt_api_response = provider.get_tx_receipt(tx_hash)
            if not provider.parser.parse_tx_receipt_response(tx_receipt_api_response):
                return []
        block_head = None
        if provider.need_block_head_for_confirmation:
            block_head_api_response = provider.get_block_head()
            block_head = provider.parser.parse_block_head_response(block_head_api_response)
        tx_details_api_response = provider.get_tx_details(tx_hash)
        return provider.parser.parse_tx_details_response(tx_details_api_response, block_head)

    def sample_get_token_tx_details(self, provider: str, tx_hash: str) -> list:
        provider = self.find_api(provider, self.token_tx_details_apis)
        if isinstance(provider, str):
            return []
        block_head = None
        if provider.need_block_head_for_confirmation:
            block_head_api_response = provider.get_block_head()
            block_head = provider.parser.parse_block_head_response(block_head_api_response)
        tx_details_api_response = provider.get_token_tx_details(tx_hash)
        return provider.parser.parse_token_tx_details_response(tx_details_api_response, block_head)

    def get_all_tokens_balances_standalone(self, addresses: List[str]) -> List['NewBalancesV2']:
        balance_api = self.get_provider('balance', self.balance_apis)
        balances_api_response = balance_api.get_all_currencies_balances(addresses)
        return balance_api.parser.parse_balances_response(balances_api_response)

    def get_selected_tokens_balances_standalone(self,
                                                user_token_pairs: List[SelectedCurrenciesBalancesRequest]
                                                ) -> List[NewBalancesV2]:
        balance_api = self.get_provider('balance', self.balance_apis)
        balances_api_response = balance_api.get_selected_currencies_balances(user_token_pairs)
        return balance_api.parser.parse_balances_response(balances_api_response)

    def get_balance(self, address: str) -> Dict[int, dict]:
        balance_api = self.get_provider('balance', self.balance_apis)
        balance_api_response = balance_api.get_balance(address)
        balance = balance_api.parser.parse_balance_response(balance_api_response)
        return self.convert_balance_to_dict(address, balance, balance_api)

    def get_balances(self, addresses: Union[str, List[str]]) -> List[Dict[int, dict]]:
        balance_api = self.get_provider('balance', self.balance_apis)
        chunk_addresses, parsed_balances, converted_balances = [], [], []
        addresses = [addresses] if not isinstance(addresses, list) else addresses
        if balance_api.SUPPORT_GET_BALANCE_BATCH:
            for i in range(0, len(addresses), balance_api.GET_BALANCES_MAX_ADDRESS_NUM):
                chunk_addresses.append(addresses[i:i + balance_api.GET_BALANCES_MAX_ADDRESS_NUM])
            for chunk_list in chunk_addresses:
                balances_api_response = balance_api.get_balances(chunk_list)
                parsed_balances = balance_api.parser.parse_balances_response(balances_api_response)
                if balance_api.BALANCES_NOT_INCLUDE_ADDRESS:
                    for balance, address in zip(parsed_balances, chunk_list):
                        converted_balances.append(self.convert_balance_to_dict(address, balance.balance, balance_api))
                else:
                    for balance in parsed_balances:
                        converted_balances.append(
                            self.convert_balance_to_dict(balance.address, balance.balance, balance_api))
        else:
            for address in addresses:
                balance_api_response = balance_api.get_balance(address)
                balance = balance_api.parser.parse_balance_response(balance_api_response)
                converted_balances.append(self.convert_balance_to_dict(address, balance, balance_api))
        return converted_balances

    @classmethod
    def convert_balance_to_dict(cls, address: str, balance: Decimal, balance_api: GeneralApi) -> Dict[int, dict]:
        if isinstance(balance, Balance):
            return {
                balance_api.parser.currency: {
                    'symbol': balance_api.parser.symbol,
                    'address': address,
                    'balance': balance.balance,
                    'unconfirmed_balance': balance.unconfirmed_balance,
                }
            }
        return {
            balance_api.parser.currency: {
                'symbol': balance_api.parser.symbol,
                'amount': balance,
                'address': address
            }
        }

    def get_token_balance(self, address: str, contracts_info: dict) -> dict:
        contract_info = next(iter(contracts_info.values()))
        token_balance_api = self.get_provider('token_balance', self.token_balance_apis)
        token_balance_api_response = token_balance_api.get_token_balance(address, contract_info)
        token_balance = token_balance_api.parser.parse_token_balance_response(token_balance_api_response, contract_info)
        return self.convert_token_balance_to_dict(address, token_balance, contract_info)

    def get_token_balances(self, addresses: List[str], contract_info: Optional[dict] = None) -> List[dict]:
        balance_api = self.get_provider('balance', self.balance_apis)
        chunk_addresses, parsed_balances, converted_balances = [], [], []
        addresses = [addresses] if not isinstance(addresses, list) else addresses
        if balance_api.SUPPORT_GET_TOKEN_BALANCE_BATCH:
            for i in range(0, len(addresses), balance_api.GET_BALANCES_MAX_ADDRESS_NUM):
                chunk_addresses.append(addresses[i:i + balance_api.GET_BALANCES_MAX_ADDRESS_NUM])
            for chunk_list in chunk_addresses:
                balances_api_response = balance_api.get_token_balances(chunk_list)
                parsed_balances = balance_api.parser.parse_token_balances_response(balances_api_response)
                for balance in parsed_balances:
                    converted_balances.append(
                        self.convert_token_balances_to_dict(balance))
        else:
            for address in addresses:
                if not contract_info:
                    raise TypeError("missing 1 required positional argument: 'contract_info'")
                balance_api_response = balance_api.get_token_balance(address, contract_info)
                balance = balance_api.parser.parse_token_balance_response(balance_api_response, contract_info)
                converted_balances.append(self.convert_token_balance_to_dict(address, balance, contract_info))
        return converted_balances

    @classmethod
    def convert_token_balance_to_dict(cls, address: str, balance: Decimal, contract_info: dict) -> dict:
        return {
            'symbol': contract_info.get('symbol'),
            'amount': balance,
            'address': address
        }

    @classmethod
    def convert_token_balances_to_dict(cls, balance: Balance) -> dict:
        return {
            'symbol': balance.symbol,
            'amount': balance.balance,
            'token': balance.token,
            'address': balance.address
        }

    @classmethod
    def aggregate_memo_based_tx_details_transfers(cls, transfers: List[TransferTx]) -> List[TransferTx]:
        """
        Aggregates transfers with the same from_address and to_address and memo by summing their value.
        Unique transfers (unique pair of from_address and to_address and memo with symbol) are added as they are.
        If a transfer doesn't have a memo, it won't participate in the aggregation process.

        """

        aggregated_transfers_keys: Dict[
            Tuple[str, str, str, str], TransferTx] = {}  # {(from_address, to_address, memo, symbol):TransferTx}
        if not transfers:
            return transfers
        no_memo_transfers: List[TransferTx] = []
        for tx in transfers:
            if not tx.memo:
                no_memo_transfers.append(tx)
                continue
            key = (tx.from_address, tx.to_address, tx.memo, tx.symbol)
            if key in aggregated_transfers_keys:
                # If we've seen this from/to pair before, add the value.
                aggregated_transfers_keys[key].value += tx.value
            else:
                # Otherwise, add this transfer to the aggregation.
                aggregated_transfers_keys[key] = tx
        aggregated_transfers = list(aggregated_transfers_keys.values())
        return aggregated_transfers + no_memo_transfers

    @classmethod
    def aggregate_account_based_tx_details_transfers(cls, transfers: List[TransferTx]) -> List[TransferTx]:
        """
        Aggregates transfers with the same from_address and to_address by summing their value.
        Unique transfers (unique pair of from_address and to_address with symbol) are added as they are.

        """

        aggregated_transfers_keys: Dict[
            Tuple[str, str, str], TransferTx] = {}  # {(from_address, to_address, symbol):TransferTx}
        if not transfers:
            return transfers
        for tx in transfers:
            key = (tx.from_address, tx.to_address, tx.symbol)
            if key in aggregated_transfers_keys:
                # If we've seen this from/to pair before, add the value.
                aggregated_transfers_keys[key].value += tx.value
            else:
                # Otherwise, add this transfer to the aggregation.
                aggregated_transfers_keys[key] = tx
        return list(aggregated_transfers_keys.values())

    @classmethod
    def aggregate_utxo_based_tx_details_transfers(cls, transfers: List[TransferTx]) -> List[TransferTx]:
        """
        Aggregates transfers with the same from_address first, then aggregates with the same to_address.
        If a to_address is in from_addresses, its value is reduced accordingly.
        If a transfer has a negative value, from_address is set to empty, and to_address is swapped with from_address.

        """
        if not transfers:
            return transfers

        # Step 1: Aggregate by from_address
        from_address_aggregated: Dict[str, TransferTx] = {}  # {from_address:TransferTx}
        to_address_aggregated: Dict[str, TransferTx] = {}  # {to_address: TransferTx}
        for tx in transfers:
            if not tx.from_address:
                continue
            key = tx.from_address
            if key in from_address_aggregated:
                from_address_aggregated[key].value += tx.value
            else:
                from_address_aggregated[key] = tx

        # Step 2: Aggregate by to_address
        for tx in transfers:
            if not tx.to_address:
                continue
            key = tx.to_address
            if key in from_address_aggregated:
                # Check if the to_address appeared in from_addresses too
                from_address_aggregated[key].value -= tx.value
            elif key in to_address_aggregated:
                to_address_aggregated[key].value += tx.value
            else:
                to_address_aggregated[key] = tx

        # Step 3: Merge from_address_aggregated and to_address_aggregated
        merged_transfers = list(from_address_aggregated.values()) + list(to_address_aggregated.values())

        # Step 4: Adjust negative values
        aggregated_transfers = []
        for tx in merged_transfers:
            if tx.value < 0:
                tx.value = abs(tx.value)
                tx.from_address, tx.to_address = '', tx.from_address
            aggregated_transfers.append(tx)

        return aggregated_transfers

    @classmethod
    def aggregate_transfers(cls, transfers: List[TransferTx]) -> List[TransferTx]:
        from exchange.explorer.networkproviders.models import Network
        network_name = cls.symbol

        try:
            network = Network.objects.get(name=network_name)  # Fetch network from DB
        except Network.DoesNotExist as err:
            raise ValueError(f'Network {network_name} not found in the database.') from err

        if network.type == Network.ACCOUNT_BASED:
            transfers = cls.aggregate_account_based_tx_details_transfers(transfers)
        elif network.type == Network.MEMO_BASED:
            transfers = cls.aggregate_memo_based_tx_details_transfers(transfers)
        elif network.type == Network.UTXO_BASED:
            transfers = cls.aggregate_utxo_based_tx_details_transfers(transfers)

        return transfers

    def get_tx_details(self, tx_hash: str) -> dict:
        tx_details_api = self.get_provider('tx_details', self.tx_details_apis)
        transfers = self.sample_get_tx_details(tx_details_api, tx_hash)
        if self.USE_AGGREGATION_SERVICE and settings.IS_EXPLORER_SERVER:
            transfers = self.aggregate_transfers(transfers)
        return self.convert_transfers2tx_details_dict(transfers)

    def get_tx_details_batch(self, tx_hashes: List[str]) -> Dict[str, dict]:
        tx_details_api = self.get_provider('tx_details', self.tx_details_apis)
        transfers = {}
        # Check if the API supports batch transaction details retrieval.
        if tx_details_api.TRANSACTION_DETAILS_BATCH:
            block_head = None
            if tx_details_api.need_block_head_for_confirmation:
                block_head_api_response = tx_details_api.get_block_head()
                block_head = tx_details_api.parser.parse_block_head_response(block_head_api_response)
            tx_details_api_response = tx_details_api.get_tx_details_batch(tx_hashes)
            txs_details = tx_details_api.parser.parse_batch_tx_details_response(tx_details_api_response, block_head)
            for tx_hash in tx_hashes:
                transfers_with_same_hash = []
                for tx_details in txs_details:
                    if tx_hash == tx_details.tx_hash:
                        transfers_with_same_hash.append(tx_details)
                transfers.update({tx_hash: self.convert_transfers2tx_details_dict(transfers_with_same_hash)})

        else:
            # If the API does not support batch retrieval, process each transaction hash individually.
            for tx_hash in tx_hashes:
                transfers.update({tx_hash: self.get_tx_details(tx_hash)})

        return transfers

    def get_token_tx_details(self, tx_hash: str) -> dict:
        tx_details_api = self.get_provider('token_tx_details', self.token_tx_details_apis)
        transfers = self.sample_get_token_tx_details(tx_details_api, tx_hash)
        return self.convert_transfers2tx_details_dict(transfers)

    def get_batch_token_tx_details(self, hashes: List[str], contract_info: dict) -> Dict[str, dict]:
        tx_details_api = self.get_provider('token_tx_details', self.token_tx_details_apis)
        chunk_hashes = []
        for i in range(0, len(hashes), tx_details_api.GET_TX_DETAILS_MAX_NUM):
            chunk_hashes.append(hashes[i:i + tx_details_api.GET_TX_DETAILS_MAX_NUM])
        block_head = None
        if tx_details_api.need_block_head_for_confirmation:
            block_head_api_response = tx_details_api.get_block_head()
            block_head = tx_details_api.parser.parse_block_head_response(block_head_api_response)
        transfer = {}
        for chunk_hash in chunk_hashes:
            batch_token_tx_details_api_response = tx_details_api.get_batch_token_tx_details(chunk_hash, contract_info)
            token_txs_details = tx_details_api.parser.parse_batch_token_tx_details_response(
                batch_token_tx_details_api_response, contract_info, block_head)
            for tx_hash in chunk_hash:
                transfers_with_same_hash = []
                for tx_details in token_txs_details:
                    if tx_hash == tx_details.tx_hash:
                        transfers_with_same_hash.append(tx_details)
                transfer.update({tx_hash: self.convert_transfers2tx_details_dict(transfers_with_same_hash)})
        return transfer

    @classmethod
    def convert_transfers2tx_details_dict(cls, transfers: Optional[List[TransferTx]] = None) -> dict:
        if not transfers:
            return {'success': False}

        first_transfer = transfers[0]
        return {
            'hash': first_transfer.tx_hash,
            'success': first_transfer.success,
            'block': first_transfer.block_height,
            'date': first_transfer.date,
            'fees': first_transfer.tx_fee,
            'memo': first_transfer.memo,
            'confirmations': first_transfer.confirmations,
            'raw': None,
            'inputs': [],
            'outputs': [],
            'transfers': [
                {
                    'type': 'Token' if transfer.token else 'MainCoin',
                    'symbol': transfer.symbol,
                    'currency': parse_currency(transfer.symbol.lower()),
                    'from': transfer.from_address,
                    'to': transfer.to_address,
                    'value': transfer.value,
                    'is_valid': True,
                    'token': transfer.token,
                    'memo': transfer.memo
                } for transfer in transfers
                if transfer.from_address != transfer.to_address
            ],
        }

    def get_txs(self, address: str, tx_direction_filter: Optional[str] = None) -> List[dict]:
        address_txs_api = self.get_provider('address_txs', self.address_txs_apis)
        transfers, address = self.get_txs_by_provider(address, address_txs_api, tx_direction_filter)
        if tx_direction_filter == 'incoming':
            transfers = [item for item in transfers if item.to_address.casefold() == address.casefold()]
        elif tx_direction_filter == 'outgoing':
            transfers = [item for item in transfers if item.from_address.casefold() == address.casefold()]

        return self.convert_transfers2list_of_address_txs_dict(address, transfers, address_txs_api.parser.currency)

    def sample_get_txs(self, address: str, provider: str) -> list:
        provider = self.find_api(provider, self.address_txs_apis)
        if isinstance(provider, str):
            return []
        address_txs, _ = self.get_txs_by_provider(address, provider)
        return [address_tx for address_tx in address_txs if
                (address_tx.from_address == address or address_tx.to_address == address)]  # noqa: PLR1714

    def get_txs_by_provider(self, address: str, address_txs_api: GeneralApi,
                            tx_direction_filter: Optional[str] = None) -> tuple:

        block_head = None
        if address_txs_api.need_block_head_for_confirmation:
            block_head_api = self.block_head_apis[0].get_instance() if self.USE_BLOCK_HEAD_API else address_txs_api
            block_head_api_response = block_head_api.get_block_head()
            block_head = block_head_api.parser.parse_block_head_response(block_head_api_response)
        address_txs_api_response = address_txs_api.get_address_txs(address, tx_direction_filter=tx_direction_filter)
        transfers = address_txs_api.parser.parse_address_txs_response(address, address_txs_api_response, block_head)
        if address_txs_api.NEED_ADDRESS_TRANSACTION_RECEIPT:
            address_txs_receipt_api_response = address_txs_api.get_address_txs_receipt(transfers)
            transfers = address_txs_api.parser.parse_address_txs_receipt(address_txs_receipt_api_response, block_head)

        address = address_txs_api.parser.convert_address(address)
        return transfers, address

    def get_token_txs_by_provider(self,
                                  address: str,
                                  contract_info: dict,
                                  token_txs_api: GeneralApi,
                                  direction: str = '',
                                  start_date: Optional[int] = None,
                                  end_date: Optional[int] = None) -> List[TransferTx]:
        block_head = None
        if token_txs_api.need_block_head_for_confirmation:
            block_head_api_response = token_txs_api.get_block_head()
            block_head = token_txs_api.parser.parse_block_head_response(block_head_api_response)
        token_txs_api_response = token_txs_api.get_token_txs(address, contract_info, direction, start_date, end_date)
        transfers = token_txs_api.parser.parse_token_txs_response(address, token_txs_api_response,
                                                                  block_head, contract_info, direction)
        if token_txs_api.NEED_TOKEN_TRANSACTION_RECEIPT:
            token_txs_receipt_api_response = token_txs_api.get_token_txs_receipt(transfers)
            transfers = token_txs_api.parser.parse_token_txs_receipt(token_txs_receipt_api_response, contract_info,
                                                                     block_head)

        return transfers

    def sample_get_token_txs(self, address: str, contract_info: dict, provider: str) -> List[TransferTx]:
        token_txs_provider = self.find_api(provider, self.address_txs_apis)
        if isinstance(token_txs_provider, str):
            return []
        token_txs = self.get_token_txs_by_provider(address, contract_info, token_txs_provider)
        return [token_tx for token_tx in token_txs if
                (token_tx.from_address == address or token_tx.to_address == address)]  # noqa: PLR1714

    def get_token_txs(self,
                      address: str,
                      contract_info: dict,
                      direction: str = '',
                      start_date: Optional[int] = None,
                      end_date: Optional[int] = None) -> List[dict]:
        token_txs_api = self.get_provider('token_txs', self.token_txs_apis)
        token_transfers = self.get_token_txs_by_provider(address, contract_info, token_txs_api, direction, start_date,
                                                         end_date)
        return self.convert_transfers2list_of_address_txs_dict(address, token_transfers, Currencies.__getattr__(
            contract_info.get('symbol').lower()))

    @staticmethod
    def get_list_of_valid_contract_addresses() -> List[str]:
        networks_contracts = [ton_contract_info, TRC20_contract_info]
        ton_usdt_contract = ton_contract_info.get('mainnet').get(Currencies.usdt).get('address')
        contract_addresses = []
        for network_contract in networks_contracts:
            for value in network_contract.get('mainnet').values():
                contract_addresses.append(value.get('address'))
        contract_addresses.remove(ton_usdt_contract)
        return contract_addresses

    @classmethod
    def convert_transfers2list_of_address_txs_dict(cls,
                                                   address: str,
                                                   transfers: List[TransferTx],
                                                   currency: int,
                                                   network: Optional[str] = None) -> List[dict]:
        if not transfers:
            return []

        contract_addresses = cls.get_list_of_valid_contract_addresses()

        return [
            {
                currency: {
                    'amount': transfer.value,
                    'from_address': transfer.from_address,
                    'to_address': transfer.to_address,
                    'hash': transfer.tx_hash,
                    'block': transfer.block_height,
                    'date': transfer.date,
                    'memo': transfer.memo,
                    'confirmations': transfer.confirmations,
                    'address': address,
                    'direction': 'incoming' if address.casefold() == transfer.to_address.casefold()
                                               and address.casefold() != transfer.from_address.casefold()
                    else 'outgoing',
                    **({'contract_address': transfer.token}
                       if (transfer.token and transfer.token in contract_addresses)
                       else {}),
                    'raw': None
                }
            } for transfer in transfers
            if address.casefold() in (transfer.from_address.casefold(), transfer.to_address.casefold())
            # The condition aboove is to prevent detecting transfers of another addresses
            # in multi transfers transactions if it mestakenly returned from api validators and parsers.
        ]

    @classmethod
    def check_blocks_raw_response(cls, api: GeneralApi, block_txs_api_response: dict) -> None:
        # Perform the validation
        valid_block_txs_raw_response = api.parser.validator.validate_block_txs_raw_response(block_txs_api_response)
        if not valid_block_txs_raw_response:
            # Log metric to have missing blocks as a result
            metric_incr('missed_block_txs_by_network_provider', labels=[api.get_name(), api.parser.symbol])

    @classmethod
    def get_block_in_thread(cls,
                            api: GeneralApi,
                            block_height: int) -> Tuple[Optional[int], Optional[List[TransferTx]]]:
        if api.SUPPORT_PAGING:
            block_height, block_txs = cls.get_block_in_thread_with_paging(api, block_height)
            return block_height, block_txs
        try:
            block_txs_api_response = api.get_block_txs(block_height)
            cls.check_blocks_raw_response(api, block_txs_api_response)
            block_txs = api.parser.parse_block_txs_response(block_txs_api_response)
            if block_txs is None or len(block_txs) == 0:
                return block_height, []
            return block_height, block_txs
        except Exception:
            traceback.print_exception(*sys.exc_info())
            return None, None

    @classmethod
    def get_block_in_thread_with_paging(cls,
                                        api: GeneralApi,
                                        block_height: int) -> Tuple[Optional[int], Optional[List[TransferTx]]]:
        initial_page = 1
        try:
            # Initially fetch the first page to determine total pages
            initial_response = api.get_block_txs(block_height, initial_page)
            cls.check_blocks_raw_response(api, initial_response)
            initial_block_txs = api.parser.parse_block_txs_response(initial_response)
            total_pages = api.parser.calculate_pages_from_block_response(initial_response)
            if not initial_block_txs:
                return block_height, []

            # Prepare for parallel fetching from the second page onwards
            with ThreadPoolExecutor():
                # Start from page 2 since we already have the first page
                futures = [cls.threadpool.submit(cls.fetch_block_txs_page, api, block_height, page) for page in
                           range(2, total_pages + 1)]
                block_txs = initial_block_txs  # Initialize with transactions from the first page

                # As each thread completes, extend the blocks_txs list
                for future in as_completed(futures):
                    block_txs.extend(future.result())

            return block_height, block_txs
        except Exception:
            traceback.print_exception(*sys.exc_info())
            return None, None

    @classmethod
    def fetch_block_txs_page(cls, api: GeneralApi, block_height: int, page: int) -> List[TransferTx]:
        block_txs_api_response = api.get_block_txs(block_height, page)
        cls.check_blocks_raw_response(api, block_txs_api_response)
        return api.parser.parse_block_txs_response(block_txs_api_response)

    @classmethod
    def get_batch_blocks(cls, api: GeneralApi, from_block: int, to_block: int) -> List[TransferTx]:
        batch_block_txs_api_response = api.get_batch_block_txs(from_block, to_block)
        cls.check_blocks_raw_response(api, batch_block_txs_api_response)
        return api.parser.parse_batch_block_txs_response(batch_block_txs_api_response)

    def get_block_head(self) -> int:
        block_txs_api = self.get_provider('block_head', (self.block_txs_apis or self.block_head_apis))
        return self.get_block_head_by_provider(block_txs_api)

    def sample_get_block_head(self, provider: str) -> int:
        provider = self.find_api(provider, self.block_head_apis)
        if isinstance(provider, str):
            return None
        return self.get_block_head_by_provider(provider)

    def get_block_head_by_provider(self, block_head_api: GeneralApi) -> int:
        block_head_api_response = block_head_api.get_block_head()
        return block_head_api.parser.parse_block_head_response(block_head_api_response)

    @classmethod
    def get_max_block_head_of_apis(cls) -> Optional[str]:
        def fetch_block_head(block_head_api: GeneralApi) -> Optional[str]:
            try:
                block_head_api = block_head_api.get_instance()
                response = block_head_api.get_block_head()
                return block_head_api.parser.parse_block_head_response(response)
            except Exception:
                return None  # Return None on failure

        with ThreadPoolExecutor(max_workers=len(cls.block_head_apis)) as executor:
            results = list(executor.map(fetch_block_head, cls.block_head_apis))

        # Filter out None values and return max block height
        results = [r for r in results if r is not None]
        return max(results) if results else None  # Return None if all attempts fail

    def get_latest_block(self, after_block_number: Optional[int] = None, to_block_number: Optional[int] = None,
                         include_inputs: bool = False, include_info: bool = False) -> tuple:
        block_txs_api = self.get_provider('block_txs', self.block_txs_apis)
        """
        calculate unprocessed block-height range and list all addresses in all transaction in all blocks in that range
        """
        max_height, min_height = self.calculate_unprocessed_block_range(after_block_number, to_block_number)
        transfers, latest_block_processed = self.fetch_latest_block(block_txs_api, min_height, max_height)
        if transfers is None:
            return None, None, latest_block_processed

        last_cache_value = cache.get(
            f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{block_txs_api.cache_key}') or 0
        if latest_block_processed and latest_block_processed > last_cache_value:
            metric_set(name='latest_block_processed', labels=[block_txs_api.cache_key],
                       amount=latest_block_processed)
            cache.set(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{block_txs_api.cache_key}',
                      latest_block_processed, 86400)

        # set metric ---- delay of block txs service
        if settings.USE_PROMETHEUS_CLIENT:
            from exchange.blockchain.metrics import block_txs_service_delay_seconds
            now_utc = datetime.now(timezone.utc)
            for block in range(min_height, max_height):
                if block > last_cache_value:
                    tx_times: list[datetime] = [tx.date for tx in transfers if tx.block_height == block and tx.date]
                    if tx_times:
                        earliest_tx_time = min(tx_times)
                        delay_of_block_txs_service = now_utc - earliest_tx_time
                        delay_of_block_txs_service_second = int(delay_of_block_txs_service.total_seconds())
                        block_txs_service_delay_seconds.labels(network=self.network or self.symbol).set(
                            delay_of_block_txs_service_second)
                    else:
                        logger.info(msg='empty_block_txs_date', extra={
                            'network': self.network or self.symbol,
                            'provider': block_txs_api.get_name(),
                            'block_number': block
                        })

        return (self.convert_transfers2txs_addresses_dict(transfers, include_inputs),
                self.convert_transfers2txs_info_dict(transfers, include_inputs, include_info),
                latest_block_processed)

    @classmethod
    def convert_transfers2txs_addresses_dict(cls, transfers: List[TransferTx], include_inputs: bool = False) -> dict:
        transactions_addresses = {'input_addresses': set(), 'output_addresses': set()}
        for transfer in transfers:
            if include_inputs and transfer.from_address:
                transactions_addresses['input_addresses'].add(transfer.from_address)
            if transfer.to_address:
                transactions_addresses['output_addresses'].add(transfer.to_address)
        return transactions_addresses

    @classmethod
    def convert_transfers2txs_info_dict(cls, transfers: List[TransferTx], include_inputs: bool = False,
                                        include_info: bool = False) -> dict:
        transactions_info = {'outgoing_txs': defaultdict(lambda: defaultdict(list)),
                             'incoming_txs': defaultdict(lambda: defaultdict(list))}

        extra_field_currency_form = [parse_currency(currency) for currency in EXTRA_FIELD_NEEDED_CURRENCIES]
        erc20_currencies = list(ERC20_contract_info.get('mainnet').keys())
        extra_field_currency_form += erc20_currencies
        bep20_currencies = list(BEP20_contract_info.get('mainnet').keys())
        extra_field_currency_form += bep20_currencies
        spl_token_currencies = list(sol_contract_info.get('mainnet').keys())
        extra_field_currency_form += spl_token_currencies
        arbitrum_currencies = list(arbitrum_ERC20_contract_info.get('mainnet').keys())
        extra_field_currency_form.extend(arbitrum_currencies)
        base_currencies = list(BASE_ERC20_contract_info.get('mainnet').keys())
        extra_field_currency_form.extend(base_currencies)

        if include_info:
            for transfer in transfers:
                currency = parse_currency(transfer.symbol.lower())
                if transfer.from_address != transfer.to_address:
                    if include_inputs and transfer.from_address:
                        duplicate_transfers = [tx for tx in
                                               transactions_info['outgoing_txs'][transfer.from_address][currency] if
                                               tx['tx_hash'] == transfer.tx_hash]
                        if duplicate_transfers:
                            index = transactions_info['outgoing_txs'][transfer.from_address][currency].index(
                                duplicate_transfers[0])
                            transactions_info['outgoing_txs'][transfer.from_address][currency][index][
                                'value'] += transfer.value
                        else:
                            transactions_info['outgoing_txs'][transfer.from_address][currency].append({
                                'tx_hash': transfer.tx_hash,
                                'value': transfer.value,

                                'contract_address': transfer.token,
                                **({'index': transfer.index} if currency in [Currencies.dot] else {}),
                                **({'block_height': transfer.block_height,
                                    'symbol': transfer.symbol} if currency in extra_field_currency_form else {}),
                            })
                    if transfer.to_address:
                        transactions_info['incoming_txs'][transfer.to_address][currency].append({
                            'tx_hash': transfer.tx_hash,
                            'value': transfer.value,
                            'contract_address': transfer.token,
                            **({'index': transfer.index} if currency in [Currencies.dot] else {}),
                            **({'block_height': transfer.block_height,
                                'symbol': transfer.symbol} if currency in extra_field_currency_form else {}),
                        })

        return transactions_info

    def calculate_unprocessed_block_range(self, after_block_number: int, to_block_number: int) -> Tuple[int, int]:
        block_txs_api = self.get_provider('block_txs', self.block_txs_apis)
        if self.USE_BLOCK_HEAD_API:
            block_head_api = self.get_provider('block_head', self.block_head_apis)
        else:
            block_head_api = block_txs_api
        if not to_block_number:
            block_head_api_response = block_head_api.get_block_head()
            latest_block_height_mined = (block_head_api.parser.parse_block_head_response(block_head_api_response)
                                         - block_head_api.block_height_offset)
            if not latest_block_height_mined:
                raise APIError(f'{block_head_api.parser.symbol}: API Not Return block height')
        else:
            latest_block_height_mined = to_block_number
        if not after_block_number:
            latest_block_height_processed = cache. \
                get(f'{settings.BLOCKCHAIN_CACHE_PREFIX}latest_block_height_processed_{block_head_api.cache_key}')
            if latest_block_height_processed is None:
                latest_block_height_processed = latest_block_height_mined - 5
        else:
            latest_block_height_processed = after_block_number

        if latest_block_height_mined > latest_block_height_processed:
            min_height = latest_block_height_processed + 1
        else:
            min_height = latest_block_height_mined + 1
        max_height = min(latest_block_height_mined + 1, min_height + block_txs_api.GET_BLOCK_ADDRESSES_MAX_NUM)
        return max_height, min_height

    def fetch_latest_block(self,
                           block_txs_api: GeneralApi,
                           min_height: int,
                           max_height: int) -> Tuple[List[TransferTx], int]:
        latest_block_processed = min_height - 1
        if block_txs_api.SUPPORT_BATCH_GET_BLOCKS:
            transfers = self.get_batch_blocks(block_txs_api, min_height, max_height - 1)
            if transfers is not None:
                latest_block_processed = max_height - 1
            else:
                return None, latest_block_processed
        else:
            futures = []
            blocks_txs_map = {}
            for block_height in range(min_height, max_height):
                future = self.threadpool.submit(self.get_block_in_thread, block_txs_api, block_height)
                futures.append(future)
            for future in concurrent.futures.as_completed(futures):
                # Wait for each task to complete
                block_height, txs = future.result()
                if block_height is not None:
                    blocks_txs_map[block_height] = txs
                else:
                    return None, latest_block_processed
            transfers = list(chain.from_iterable(blocks_txs_map.values()))
            processed_block_heights = list(blocks_txs_map.keys())

            if processed_block_heights:
                # We are trying to find the first unprocessed block from our concurrent requests
                # The solution is based on subtracting set of successfully processed_block_heights from set of processed
                # block heights. The +2 in the code snippet plays a critical role by ensuring the range of block heights
                # extends beyond the highest block that has been processed.
                # Subtracting one then adjusts this value back to the last successfully processed block height
                latest_block_processed = min(
                    set(range(min(processed_block_heights), max(processed_block_heights) + 2)) - set(
                        processed_block_heights)) - 1

        return transfers, latest_block_processed

    def get_staking_reward(self, wallet_address: str) -> GetWalletStakingRewardResponse:
        if len(self.staking_apis) < 1:
            raise Exception('no staking apis')
        if len(self.address_txs_apis) < 1:
            raise Exception('no staking apis')

        staking_api: GeneralStakingApi = self.staking_apis[0]()
        address_txs_api = self.address_txs_apis[0]

        get_txs_response = address_txs_api.get_address_txs(wallet_address)
        staked_balance, target_operator_addresses = staking_api.parser.parse_get_txs_staked_balance(get_txs_response)

        reward_rate_response = staking_api.get_reward_rate(self.symbol)
        reward_rate = staking_api.parser.parse_get_reward_rate(reward_rate_response)

        operator_addresses_response = staking_api.get_all_operator_addresses(0, 100)
        operator_addresses = staking_api.parser.parse_get_all_operator_addresses(
            operator_addresses_response)

        target_validators: List[TargetValidator] = []

        for operator_address in target_operator_addresses:
            validator_info_response = staking_api.get_validator_info(operator_address)
            validator_info = staking_api.parser.parse_get_validator_info(
                response=validator_info_response,
                is_address_in_validators=operator_address in operator_addresses
            )

            validator_description_response = staking_api.get_validator_description(operator_address)
            validator_description = staking_api.parser.parse_get_validator_description(
                response=validator_description_response)

            commission_rate_response = staking_api.get_validator_commission(operator_address)
            commission_rate = staking_api.parser.parse_get_validator_commission(commission_rate_response)

            target_validators.append(
                TargetValidator(
                    address=operator_address,
                    name=validator_description.validator_name,
                    website=validator_description.website,
                    status=validator_info.status,
                    commission_rate=commission_rate,
                )
            )

        return GetWalletStakingRewardResponse(
            staked_balance=staked_balance,
            daily_rewards=(staked_balance * reward_rate) / Decimal(365),
            reward_rate=reward_rate,
            target_validators=target_validators
        )

    def get_all_validators(self, offset: int, limit: int) -> GetAllValidatorsResponse:
        if len(self.staking_apis) < 1:
            raise Exception('no staking apis')

        staking_api: GeneralStakingApi = self.staking_apis[0]()

        operator_addresses_response = staking_api.get_all_operator_addresses(offset, limit)
        operator_addresses = staking_api.parser.parse_get_all_operator_addresses(
            operator_addresses_response)

        reward_rate_response = staking_api.get_reward_rate(self.symbol)
        reward_rate = staking_api.parser.parse_get_reward_rate(reward_rate_response)

        validators: List[ValidatorInfo] = []

        for operator_address in operator_addresses:
            validator_info_response = staking_api.get_validator_info(operator_address)
            validator_info = staking_api.parser.parse_get_validator_info(
                response=validator_info_response,
                is_address_in_validators=operator_address in operator_addresses
            )

            validator_description_response = staking_api.get_validator_description(operator_address)
            validator_description = staking_api.parser.parse_get_validator_description(validator_description_response)

            total_stake_response = staking_api.get_validator_total_stake_from_contract(operator_address)
            total_stake = staking_api.parser.parse_get_validator_total_stake_from_contract(total_stake_response)

            commission_rate_response = staking_api.get_validator_commission(operator_address)
            commission_rate = staking_api.parser.parse_get_validator_commission(commission_rate_response)

            validators.append(
                ValidatorInfo(
                    address=operator_address,
                    website=validator_description.website,
                    name=validator_description.validator_name,
                    status=validator_info.status,
                    total_staked=total_stake,
                    commission_rate=commission_rate,
                    annual_effective_reward_rate=reward_rate * (Decimal(1) - commission_rate),
                )
            )

        return GetAllValidatorsResponse(
            validators=validators,
            base_reward_rate=reward_rate,
        )
