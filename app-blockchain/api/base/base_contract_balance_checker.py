from typing import Dict, List

from exchange.blockchain.api.contract_balance_checker.contract_balance_checker_config import BalanceCheckerConfig
from exchange.blockchain.api.contract_balance_checker.contract_balance_checker_v2 import (
    ContractBalanceCheckerParserV2,
    ContractBalanceCheckerV2,
)
from exchange.blockchain.contracts_conf import BASE_ERC20_contract_currency, BASE_ERC20_contract_info


class BaseContractBalanceCheckerParserV2(ContractBalanceCheckerParserV2):
    network_config = BalanceCheckerConfig.Base

    @classmethod
    def contract_currency_list(cls) -> Dict[str, str]:
        return BASE_ERC20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls) -> Dict[str, Dict]:
        return BASE_ERC20_contract_info.get(cls.network_mode)


class BaseContractBalanceCheckerV2Api(ContractBalanceCheckerV2):
    parser = BaseContractBalanceCheckerParserV2
    network_config = BalanceCheckerConfig.Base

    @classmethod
    def get_tokens(cls) -> List[str]:
        return [cls.main_token, *cls.parser.contract_currency_list()]
