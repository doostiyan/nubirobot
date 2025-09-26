import math
import random
from typing import List, Optional

from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.general.dtos import Balance
from exchange.blockchain.api.general.dtos.dtos import NewBalancesV2, SelectedCurrenciesBalancesRequest
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.utils import BlockchainUtilsMixin
from web3 import Web3
from web3.exceptions import Web3RPCError


class ContractBalanceCheckerValidatorV2(ResponseValidator):
    @classmethod
    def validate_balances_response(cls, balances_response) -> bool:
        if not balances_response:
            return False
        return True


class ContractBalanceCheckerParserV2(ResponseParser):
    validator = ContractBalanceCheckerValidatorV2
    network_config = None  # To be overridden by each subclass

    def __init_subclass__(cls, **kwargs):
        """
        Initializes network-specific settings and Web3 setup for the subclass.
        """
        super().__init_subclass__(**kwargs)
        cls.setup_network_config()

    @classmethod
    def setup_network_config(cls):
        """
        Configures network-specific settings based on the `network_config` provided by the subclass.
        """
        if cls.network_config:
            cls.contract_address = cls.network_config.contract_address
            cls.symbol = cls.network_config.symbol
            cls.main_token = cls.network_config.main_token
            cls.precision = cls.network_config.precision
            cls.currency = cls.network_config.currency
            cls.network = cls.network_config.network

    @classmethod
    def parse_balances_response(cls, balances_response: List[tuple]) -> List[NewBalancesV2]:
        """
        Parses the balances response from the contract.

        Args:
            balances_response (List[tuple]): A list of tuples, each containing:
                - [0] user (address): Address of the user.
                - [1] token (address): Token address or `main_token` for Native Coin balance.
                - [2] balance (uint): Balance of the specified token or Native Coin.

        Returns:
            List[Balance]: A list of Balance objects parsed from the response.
        """
        if not cls.validator.validate_balances_response(balances_response):
            return []

        parsed_balances = []
        for balance in balances_response:
            parsed_balance = cls._create_balance_object(balance)
            if parsed_balance:
                parsed_balances.append(parsed_balance)

        return parsed_balances

    @classmethod
    def _create_balance_object(cls, balance: tuple) -> Optional[NewBalancesV2]:
        user, token, amount, block_number, block_timestamp = balance

        if token == cls.main_token:
            return NewBalancesV2(
                address=user,
                balance=str(BlockchainUtilsMixin.from_unit(amount, cls.precision)),
                contract_address=cls.main_token,
                symbol=cls.symbol,
                network=cls.network,
                block_number=block_number,
                block_timestamp=parse_utc_timestamp(block_timestamp).isoformat()
            )

        currency = cls.contract_currency_list().get(token.lower())
        if not currency:
            currency = cls.contract_currency_list().get(token)

        if currency:
            contract_info = cls.contract_info_list().get(currency, {})
            return NewBalancesV2(
                address=user,
                balance=str(BlockchainUtilsMixin.from_unit(amount, contract_info.get('decimals'))),
                contract_address=token,
                symbol=contract_info.get('symbol', 'Unknown'),
                network=cls.network,
                block_number=block_number,
                block_timestamp=parse_utc_timestamp(block_timestamp).isoformat()
            )
        return None


class ContractBalanceCheckerV2(GeneralApi):
    parser = ContractBalanceCheckerParserV2
    network_config = None  # To be overridden by each subclass
    SUPPORT_GET_BALANCE_BATCH = True

    w3 = None
    contract = None

    CONTRACT_ABI = """
        [{"stateMutability":"payable","type":"fallback"},{"stateMutability":"payable","type":"receive"},{"inputs":
        [{"internalType":"address[]","name":"users","type":"address[]"},{"internalType":"address[]","name":"tokens","type":
        "address[]"}],"name":"getAllTokensBalances","outputs":[{"components":[{"internalType":"address","name":"user","type":
        "address"},{"internalType":"address","name":"token","type":"address"},{"internalType":"uint256","name":"balance","type":
        "uint256"},{"internalType":"uint256","name":"blockNumber","type":"uint256"},{"internalType":"uint256","name":
        "blockTimestamp","type":"uint256"}],"internalType":"structBalanceChecker.BalanceInfo[]","name":"","type":"tuple[]"}],
        "stateMutability":"view","type":"function"},{"inputs":[{"components":[{"internalType":"address","name":"user","type":
        "address"},{"internalType":"address","name":"token","type":"address"}],"internalType":
        "structBalanceChecker.BalanceRequest[]","name":"requests","type":"tuple[]"}],"name":"getSelectedTokenBalances","outputs":
        [{"components":[{"internalType":"address","name":"user","type":"address"},{"internalType":"address","name":"token","type":
        "address"},{"internalType":"uint256","name":"balance","type":"uint256"},{"internalType":"uint256","name":"blockNumber",
        "type":"uint256"},{"internalType":"uint256","name":"blockTimestamp","type":"uint256"}],"internalType":
        "structBalanceChecker.BalanceInfo[]","name":"","type":"tuple[]"}],"stateMutability":"view","type":"function"}]
    """

    def __init_subclass__(cls, **kwargs):
        """
        Initializes network-specific settings for the subclass.
        """
        super().__init_subclass__(**kwargs)
        cls.setup_network_config()

    @classmethod
    def setup_network_config(cls):
        """
        Configures network-specific settings based on the `network_config` provided by the subclass.
        """
        if cls.network_config:
            cls.contract_address = cls.network_config.contract_address
            cls.base_url_all_currencies = cls.network_config.base_url_all_currencies
            cls.base_url_selected_currencies = cls.network_config.base_url_selected_currencies
            cls.symbol = cls.network_config.symbol
            cls.main_token = cls.network_config.main_token
            cls.currency = cls.network_config.currency

    @classmethod
    def create_web3_and_contract(cls, base_urls: list):
        """
        Dynamically create a Web3 instance and contract object using a random base URL from the provided list.
        """
        if not base_urls or not cls.contract_address:
            raise ValueError("Base URLs or contract address is not configured.")
        selected_base_url = random.choice(base_urls)
        w3 = Web3(Web3.HTTPProvider(selected_base_url))
        contract = w3.eth.contract(
            address=w3.to_checksum_address(cls.contract_address),
            abi=cls.CONTRACT_ABI
        )
        return w3, contract

    @classmethod
    def get_all_currencies_balances(cls, addresses: List[str]) -> List[Balance]:
        result = []

        try:
            w3, contract = cls.create_web3_and_contract(cls.base_url_all_currencies)
            checksum_addresses = [w3.to_checksum_address(address) for address in addresses]
            tokens = [w3.to_checksum_address(token) for token in cls.get_tokens()]

            try:
                result = contract.functions.getAllTokensBalances(checksum_addresses, tokens).call()
            except Web3RPCError as e:
                if "exceeding --rpc.returndata.limit" in e.message:
                    slice_count = 3
                    slice_length = math.ceil(len(addresses) / slice_count)
                    for i in range(0, len(addresses), slice_length):
                        result += contract.functions.getAllTokensBalances(checksum_addresses[i:i + slice_length],
                                                                          tokens).call()
                else:
                    raise e

        except Exception as e:
            raise e

        return result

    @classmethod
    def get_selected_currencies_balances(cls, user_token_pairs: List[SelectedCurrenciesBalancesRequest]) -> List[
        NewBalancesV2]:
        try:
            w3, contract = cls.create_web3_and_contract(cls.base_url_selected_currencies)
            requests = [
                {
                    "user": w3.to_checksum_address(pair.address),
                    "token": w3.to_checksum_address(pair.contract_address)
                }
                for pair in user_token_pairs
            ]
            return contract.functions.getSelectedTokenBalances(requests).call()
        except Exception as e:
            raise e

    @classmethod
    def get_tokens(cls):
        return []
