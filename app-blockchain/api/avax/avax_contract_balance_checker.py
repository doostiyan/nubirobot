from exchange.blockchain.api.contract_balance_checker.contract_balance_checker_config import BalanceCheckerConfig
from exchange.blockchain.api.contract_balance_checker.contract_balance_checker_v2 import (
    ContractBalanceCheckerV2, ContractBalanceCheckerParserV2
)

from exchange.blockchain.contracts_conf import avalanche_ERC20_contract_currency, avalanche_ERC20_contract_info


class AVAXContractBalanceCheckerParserV2(ContractBalanceCheckerParserV2):
    network_config = BalanceCheckerConfig.AVAX

    @classmethod
    def contract_currency_list(cls):
        return avalanche_ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return avalanche_ERC20_contract_info.get(cls.network_mode)


class AVAXContractBalanceCheckerV2Api(ContractBalanceCheckerV2):
    parser = AVAXContractBalanceCheckerParserV2
    network_config = BalanceCheckerConfig.AVAX

    @classmethod
    def get_tokens(cls):
        return [cls.main_token] + list(cls.parser.contract_currency_list())
