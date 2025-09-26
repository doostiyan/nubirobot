from exchange.blockchain.api.contract_balance_checker.contract_balance_checker_config import BalanceCheckerConfig
from exchange.blockchain.api.contract_balance_checker.contract_balance_checker_v2 import (
    ContractBalanceCheckerV2, ContractBalanceCheckerParserV2
)

from exchange.blockchain.contracts_conf import polygon_ERC20_contract_info, polygon_ERC20_contract_currency


class POLContractBalanceCheckerParserV2(ContractBalanceCheckerParserV2):
    network_config = BalanceCheckerConfig.POL

    @classmethod
    def contract_currency_list(cls):
        return polygon_ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return polygon_ERC20_contract_info.get(cls.network_mode)


class POLContractBalanceCheckerV2Api(ContractBalanceCheckerV2):
    parser = POLContractBalanceCheckerParserV2
    network_config = BalanceCheckerConfig.POL

    @classmethod
    def get_tokens(cls):
        return [cls.main_token] + list(cls.parser.contract_currency_list())
