import logging
from decimal import Decimal
from typing import Dict

from django.conf import settings

from exchange.blockchain.api.general.exceptions.invalid_response_exception import InvalidResponseError
from exchange.blockchain.api.general.general_staking import GeneralStakingApi, StakingParser

logger = logging.getLogger(__name__)


class StakingRewardParser(StakingParser):
    @classmethod
    def parse_get_reward_rate(cls, response: Dict[str, any]) -> Decimal:
        if response is None or 'data' not in response or response['data'] is None:
            raise InvalidResponseError(response=response)

        assets = response['data'].get('assets', [])
        if not assets:
            raise InvalidResponseError(response=response)

        metrics = assets[0].get('metrics', [])
        if not metrics:
            raise InvalidResponseError(response=response)

        value = metrics[0].get('defaultValue')
        if value is None:
            raise InvalidResponseError(response=response)

        return Decimal(str(value)) / 100 if value else Decimal(0)


class StakingRewardApi(GeneralStakingApi):
    @classmethod
    def get_staking_headers(cls) -> Dict[str, any]:
        return {
            'x-api-key': settings.STAKING_REWARDS_API_KEY,
            'Content-Type': 'application/json',
        }

    @classmethod
    def get_reward_rate_body(cls, asset_symbol: str) -> any:
        return {
            'query': """
                query GetRewardOptions($symbol: [String!]) {
                    assets(where: { symbols: $symbol }, limit: 1) {
                        name
                        symbol
                        metrics(where: { metricKeys: ["reward_rate"] }, limit: 1) {
                            metricKey
                            defaultValue
                        }
                    }
                }
            """,
            'variables': {'symbol': [asset_symbol]},
        }
