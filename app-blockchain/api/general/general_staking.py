from decimal import Decimal
from typing import Dict, List, Tuple

import requests

from exchange.blockchain.api.general.dtos.get_validator_description_response import GetValidatorDescriptionResponse
from exchange.blockchain.api.general.dtos.get_validator_info_response import GetValidatorInfoResponse
from exchange.blockchain.utils import Service


class StakingParser:
    @classmethod
    def parse_get_validator_info(cls,
                                 response: any,
                                 is_address_in_validators: bool) -> GetValidatorInfoResponse:
        pass

    @classmethod
    def parse_get_validator_total_stake_from_contract(cls, response: any) -> Decimal:
        pass

    @classmethod
    def parse_get_validator_description(cls, response: any) -> GetValidatorDescriptionResponse:
        pass

    @classmethod
    def parse_get_validator_commission(cls, response: any) -> Decimal:
        pass

    @classmethod
    def parse_get_reward_rate(cls, response: any) -> Decimal:
        pass

    @classmethod
    def parse_get_all_operator_addresses(cls, response: any) -> List[str]:
        pass

    @classmethod
    def parse_get_txs_staked_balance(cls, response: any) -> Tuple[Decimal, List[str]]:
        pass

class GeneralStakingApi(Service):

    parser: StakingParser
    STAKING_REWARDS_API_URL = 'https://api.stakingrewards.com/public/query'

    @classmethod
    def get_staking_headers(cls) -> Dict[str, any]:
        pass

    @classmethod
    def get_validator_info(cls, operator_address: str) -> any:
        pass

    @classmethod
    def get_validator_total_stake_from_contract(cls, operator_address: str) -> any:
        pass

    @classmethod
    def get_validator_description(cls, operator_address: str) -> any:
        pass

    @classmethod
    def get_validator_commission(cls, operator_address: str) -> any:
        pass

    @classmethod
    def get_reward_rate(cls, asset_symbol: str) -> any:
        response = requests.post(
            cls.STAKING_REWARDS_API_URL,
            json=cls.get_reward_rate_body(asset_symbol),
            headers=cls.get_staking_headers(),
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    @classmethod
    def get_reward_rate_body(cls, asset_symbol: str) -> any:
        pass

    @classmethod
    def get_all_operator_addresses(cls, offset: int, limit: int) -> any:
        pass
