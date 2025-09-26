import random
from typing import Dict, List, Tuple, Union

from django.conf import settings

if settings.IS_EXPLORER_SERVER:
    from tronpy import Contract, Tron
    from tronpy.providers import HTTPProvider

from exchange.blockchain.api.contract_balance_checker.contract_balance_checker_config import BalanceCheckerConfig
from exchange.blockchain.api.contract_balance_checker.contract_balance_checker_v2 import ContractBalanceCheckerParserV2
from exchange.blockchain.api.general.dtos.dtos import SelectedCurrenciesBalancesRequest
from exchange.blockchain.api.general.general import GeneralApi
from exchange.blockchain.contracts_conf import TRC20_contract_currency, TRC20_contract_info
from exchange.blockchain.models import Currencies


class TronContractBalanceCheckerParserV2(ContractBalanceCheckerParserV2):
    network_config = BalanceCheckerConfig.TRON
    symbol = network_config.symbol
    currency = network_config.currency
    precision = network_config.precision
    main_token = network_config.main_token
    network_mode = 'mainnet'

    @classmethod
    def contract_currency_list(cls) -> Dict[str, int]:
        return TRC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls) -> Dict[int, Dict[str, Union[str, int]]]:
        return TRC20_contract_info.get(cls.network_mode)


class TronContractBalanceCheckerV2Api(GeneralApi):
    parser = TronContractBalanceCheckerParserV2

    network_config = BalanceCheckerConfig.TRON
    contract_address = network_config.contract_address
    base_url_all_currencies = network_config.base_url_all_currencies
    base_url_selected_currencies = network_config.base_url_selected_currencies
    symbol = network_config.symbol
    main_token = network_config.main_token

    currency = Currencies.eth
    SUPPORT_GET_BALANCE_BATCH = True

    CONTRACT_ABI = [{'stateMutability': 'payable', 'type': 'fallback'},
                    {'inputs': [{'internalType': 'address[]', 'name':
                        'users', 'type': 'address[]'},
                                {'internalType': 'address[]', 'name': 'tokens', 'type': 'address[]'}], 'name':
                         'getAllTokensBalances',
                     'outputs': [{'components': [{'internalType': 'address', 'name': 'user', 'type': 'address'}
                         , {'internalType': 'address', 'name': 'token', 'type': 'address'},
                                                 {'internalType': 'uint256', 'name': 'balance', 'type':
                                                     'uint256'},
                                                 {'internalType': 'uint256', 'name': 'blockNumber', 'type': 'uint256'},
                                                 {'internalType': 'uint256', 'name'
                                                 : 'blockTimestamp', 'type': 'uint256'}],
                                  'internalType': 'structBalanceChecker.BalanceInfo[]', 'name': '', 'type'
                                  : 'tuple[]'}], 'stateMutability': 'view', 'type': 'function'},
                    {'inputs': [{'components': [{'internalType': 'address', 'name':
                        'user', 'type': 'address'}, {'internalType': 'address', 'name': 'token', 'type': 'address'}],
                                 'internalType':
                                     'structBalanceChecker.BalanceRequest[]', 'name': 'requests', 'type': 'tuple[]'}],
                     'name': 'getSelectedTokenBalances'
                        , 'outputs': [{'components': [{'internalType': 'address', 'name': 'user', 'type': 'address'},
                                                      {'internalType': 'address'
                                                          , 'name': 'token', 'type': 'address'},
                                                      {'internalType': 'uint256', 'name': 'balance', 'type': 'uint256'}
                        , {'internalType': 'uint256', 'name': 'blockNumber', 'type': 'uint256'},
                                                      {'internalType': 'uint256', 'name':
                                                          'blockTimestamp', 'type': 'uint256'}],
                                       'internalType': 'structBalanceChecker.BalanceInfo[]', 'name': '',
                                       'type': 'tuple[]'}], 'stateMutability': 'view', 'type': 'function'},
                    {'stateMutability': 'payable', 'type': 'receive'}]

    contract = None

    @classmethod
    def create_tron_web3_and_contract(cls, base_urls: list) -> Tuple['Tron', 'Contract']:
        """
        Dynamically create a Tron instance and contract object using a random base URL from the provided list.
        """
        if not base_urls or not cls.contract_address:
            raise ValueError('Base URLs or contract address is not configured.')

        selected_base_url = random.choice(base_urls)

        tron = Tron(provider=HTTPProvider(selected_base_url), network='mainnet')
        contract = tron.get_contract(cls.contract_address)
        contract.abi = cls.CONTRACT_ABI
        return tron, contract

    @classmethod
    def get_all_currencies_balances(cls, addresses: List[str]) -> any:
        tron, contract = cls.create_tron_web3_and_contract(cls.base_url_all_currencies)
        checksum_addresses = [tron.to_base58check_address(address) for address in addresses]
        tokens = [tron.to_base58check_address(token) for token in cls.get_tokens()]
        return contract.functions.getAllTokensBalances(checksum_addresses, tokens)

    @classmethod
    def get_selected_currencies_balances(cls, user_token_pairs: List[SelectedCurrenciesBalancesRequest]) -> any:
        tron, contract = cls.create_tron_web3_and_contract(cls.base_url_selected_currencies)
        requests = [
            (
                tron.to_base58check_address(pair.address),  # User address
                tron.to_base58check_address(pair.contract_address)  # Token address
            )
            for pair in user_token_pairs
        ]

        return contract.functions.getSelectedTokenBalances(requests)

    @classmethod
    def get_tokens(cls) -> list:
        return [cls.main_token, *list(cls.parser.contract_currency_list())]
