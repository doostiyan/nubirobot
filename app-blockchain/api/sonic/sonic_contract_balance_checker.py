from exchange.blockchain.api.contract_balance_checker.contract_balance_checker_config import BalanceCheckerConfig
from exchange.blockchain.api.contract_balance_checker.contract_balance_checker_v2 import (
    ContractBalanceCheckerV2, ContractBalanceCheckerParserV2
)

from exchange.blockchain.contracts_conf import sonic_ERC20_contract_currency, sonic_ERC20_contract_info


class SonicContractBalanceCheckerParserV2(ContractBalanceCheckerParserV2):
    network_config = BalanceCheckerConfig.SONIC

    @classmethod
    def contract_currency_list(cls):
        return sonic_ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return sonic_ERC20_contract_info.get(cls.network_mode)


class SonicContractBalanceCheckerV2Api(ContractBalanceCheckerV2):
    parser = SonicContractBalanceCheckerParserV2
    network_config = BalanceCheckerConfig.SONIC

    @classmethod
    def get_tokens(cls):
        return [cls.main_token] + list(cls.parser.contract_currency_list())
