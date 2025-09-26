from exchange.blockchain.api.contract_balance_checker.contract_balance_checker_config import BalanceCheckerConfig
from exchange.blockchain.api.contract_balance_checker.contract_balance_checker_v2 import (
    ContractBalanceCheckerV2, ContractBalanceCheckerParserV2
)

from exchange.blockchain.contracts_conf import opera_ftm_contract_currency, opera_ftm_contract_info, \
    harmony_ERC20_contract_currency, harmony_ERC20_contract_info


class ONEContractBalanceCheckerParserV2(ContractBalanceCheckerParserV2):
    network_config = BalanceCheckerConfig.ONE

    @classmethod
    def contract_currency_list(cls):
        return harmony_ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return harmony_ERC20_contract_info.get(cls.network_mode)


class ONEContractBalanceCheckerV2Api(ContractBalanceCheckerV2):
    parser = ONEContractBalanceCheckerParserV2
    network_config = BalanceCheckerConfig.ONE

    @classmethod
    def get_tokens(cls):
        return [cls.main_token] + list(cls.parser.contract_currency_list())
