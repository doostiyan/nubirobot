from django.http import JsonResponse
from rest_framework import status
from rest_framework.request import Request
from rest_framework.views import APIView

from exchange.blockchain import apis_conf
from exchange.blockchain.api.general.dtos.get_wallet_staking_reward_response import GetWalletStakingRewardResponse
from exchange.explorer.staking.reward_record_service import RewardRecordService
from exchange.explorer.utils.logging import get_logger


class StakingRewardsView(APIView):
    logger = get_logger()

    def get(self, request: Request, wallet_address: str) -> JsonResponse:
        network: str = request.query_params.get('network', '').upper()
        if not network:
            return JsonResponse(
                {'error': 'network parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            explorer_interface = apis_conf.STAKING_EXPLORER_INTERFACE.get(network.lower())
            if not explorer_interface:
                self.logger.error('STAKING_EXPLORER_INTERFACE for %s not exist!', network.upper())
                return JsonResponse(
                    {'error': f'{network.upper()} Does not supported yet!'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            wallet_staking_reward = explorer_interface.get_staking_reward(wallet_address)

            RewardRecordService.save_daily_reward(
                wallet_address=wallet_address,
                network=network.upper(),
                reward_response=GetWalletStakingRewardResponse(
                    staked_balance=wallet_staking_reward.staked_balance,
                    daily_rewards=wallet_staking_reward.daily_rewards,
                    reward_rate=wallet_staking_reward.reward_rate,
                    target_validators=wallet_staking_reward.target_validators
                )
            )

            return JsonResponse(wallet_staking_reward.model_dump())

        except Exception:
            self.logger.exception('Error in staking rewards view')
            return JsonResponse(
                {'error': 'Internal Error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ValidatorListView(APIView):
    logger = get_logger()
    MAX_LIMIT = 5

    def get(self, request: Request) -> JsonResponse:
        network: str = request.query_params.get('network', '').upper()
        offset: int = int(request.query_params.get('offset', '0'))
        limit: int = int(request.query_params.get('limit', '5'))

        if limit > self.MAX_LIMIT:
            return JsonResponse(
                {'error': f'limit should be less than {self.MAX_LIMIT + 1}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not network:
            return JsonResponse(
                {'error': 'network parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            explorer_interface = apis_conf.STAKING_EXPLORER_INTERFACE.get(network.lower())
            return JsonResponse(explorer_interface.get_all_validators(offset, limit).model_dump())
        except Exception:
            self.logger.exception('Error in validator list view')
            return JsonResponse(
                {'error': 'Internal Error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
