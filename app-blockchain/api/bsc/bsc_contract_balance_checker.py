from exchange.blockchain.api.contract_balance_checker.contract_balance_checker_config import BalanceCheckerConfig
from exchange.blockchain.api.contract_balance_checker.contract_balance_checker_v2 import (
    ContractBalanceCheckerV2, ContractBalanceCheckerParserV2
)

from exchange.blockchain.contracts_conf import BEP20_contract_currency, BEP20_contract_info


class BSCContractBalanceCheckerParserV2(ContractBalanceCheckerParserV2):
    network_config = BalanceCheckerConfig.BSC

    @classmethod
    def contract_currency_list(cls):
        return BEP20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls):
        return BEP20_contract_info.get(cls.network_mode)


class BSCContractBalanceCheckerV2Api(ContractBalanceCheckerV2):
    parser = BSCContractBalanceCheckerParserV2
    network_config = BalanceCheckerConfig.BSC

    @classmethod
    def get_tokens(cls):
        return [cls.main_token] + list(cls.parser.contract_currency_list())
