from exchange.blockchain.api.contract_balance_checker.contract_balance_checker_config import BalanceCheckerConfig
from exchange.blockchain.api.contract_balance_checker.contract_balance_checker_v2 import (
    ContractBalanceCheckerV2, ContractBalanceCheckerParserV2
)

from exchange.blockchain.contracts_conf import opera_ftm_contract_currency, opera_ftm_contract_info, \
    ETC_ERC20_contract_info


class ETCContractBalanceCheckerParserV2(ContractBalanceCheckerParserV2):
    network_config = BalanceCheckerConfig.ETC

    @classmethod
    def contract_currency_list(cls):
        return {}

    @classmethod
    def contract_info_list(cls):
        return ETC_ERC20_contract_info.get(cls.network_mode)


class ETCContractBalanceCheckerV2Api(ContractBalanceCheckerV2):
    parser = ETCContractBalanceCheckerParserV2
    network_config = BalanceCheckerConfig.ETC

    @classmethod
    def get_tokens(cls):
        return [cls.main_token] + list(cls.parser.contract_currency_list())
