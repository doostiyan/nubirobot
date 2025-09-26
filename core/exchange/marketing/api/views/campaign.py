from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from pydantic import ValidationError
from rest_framework import status

from exchange.base.api import APIView, NobitexAPIError, PublicAPIView
from exchange.base.decorators import measure_api_execution
from exchange.marketing.exceptions import (
    InvalidCampaignException,
    MissionHasNotBeenCompleted,
    NoDiscountCodeIsAvailable,
    RewardHasBeenAlreadyAssigned,
)
from exchange.marketing.services.campaign.base import (
    RewardBasedCampaign,
    UserIdentifier,
    UserIdentifierType,
    to_user_info,
)
from exchange.marketing.services.campaign.selector import check_campaign_type, choose_campaign_by_name
from exchange.marketing.types import CampaignRewardCapacitySchema, CampaignViewSchema, UTMParams


class CampaignJoinRequestView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='5/m', block=True, method='POST'))
    @method_decorator(measure_api_execution(api_label='campaignJoinRequest'))
    def post(self, request):
        try:
            utm_params = UTMParams.model_validate(request.data)
            service = choose_campaign_by_name(utm_params.utm_campaign)
            result = service.join(to_user_info(request.user))

            return self.response(
                CampaignViewSchema(
                    status='ok',
                    webengage_id=result.user_details.webengage_id,
                    campaign_details=result.campaign_details,
                ).model_dump(by_alias=True),
            )

        except ValidationError as e:
            raise NobitexAPIError(
                message='ParseError',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from None
        except InvalidCampaignException as e:
            raise NobitexAPIError(
                message='InvalidCampaign',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from None


class CampaignInfoRequestView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='20/m', block=True, method='GET'))
    @method_decorator(measure_api_execution(api_label='campaignInfoRequest'))
    def get(self, request):
        try:
            utm_params = UTMParams(**request.GET.dict())
            service = choose_campaign_by_name(utm_params.utm_campaign)
            result = service.get_campaign_details(to_user_info(request.user))
            return self.response(
                CampaignViewSchema(
                    status='ok',
                    webengage_id=request.user.get_webengage_id(),
                    campaign_details=result,
                ).model_dump(by_alias=True),
            )

        except ValidationError as e:
            raise NobitexAPIError(
                message='ParseError',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from None
        except InvalidCampaignException as e:
            raise NobitexAPIError(
                message='InvalidCampaign',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from None


class CampaignRewardRequestView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='5/m', block=True, method='POST'))
    @method_decorator(measure_api_execution(api_label='campaignRewardRequest'))
    def post(self, request):
        try:
            utm_params = UTMParams.model_validate(request.data)
            identifier = UserIdentifier(id=request.user.pk, type=UserIdentifierType.SYSTEM_USER_ID)
            service = choose_campaign_by_name(utm_params.utm_campaign)
            check_campaign_type(service, RewardBasedCampaign)
            service.send_reward(identifier)
            details = service.get_campaign_details(to_user_info(request.user))

            return self.response(
                CampaignViewSchema(
                    status='ok',
                    webengage_id=request.user.get_webengage_id(),
                    campaign_details=details,
                ).model_dump(by_alias=True),
            )

        except ValidationError as e:
            raise NobitexAPIError(
                message='ParseError',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from None
        except InvalidCampaignException as e:
            raise NobitexAPIError(
                message='InvalidCampaign',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from None
        except NoDiscountCodeIsAvailable as e:
            raise NobitexAPIError(
                message='NoDiscountCodeIsAvailable',
                description=str(e),
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from None
        except MissionHasNotBeenCompleted as e:
            raise NobitexAPIError(
                message='MissionHasNotBeenCompleted',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from None
        except RewardHasBeenAlreadyAssigned as e:
            raise NobitexAPIError(
                message='RewardHasBeenAlreadyAssigned',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from None


class CampaignRewardCapacityView(PublicAPIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='20/m', block=True, method='GET'))
    @method_decorator(measure_api_execution(api_label='campaignRewardCapacity'))
    def get(self, request):
        try:
            utm_params = UTMParams(**request.GET.dict())
            service = choose_campaign_by_name(utm_params.utm_campaign)
            check_campaign_type(service, RewardBasedCampaign)
            details = service.get_capacity_details()

            return self.response(
                CampaignRewardCapacitySchema(
                    status='ok',
                    details=details,
                ).model_dump(by_alias=True),
            )

        except ValidationError as e:
            raise NobitexAPIError(
                message='ParseError',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from None
        except InvalidCampaignException as e:
            raise NobitexAPIError(
                message='InvalidCampaign',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from None
