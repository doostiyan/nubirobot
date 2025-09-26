import json

from django.contrib.auth.models import User
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from pydantic import ValidationError
from rest_framework import status

from exchange.base.api import NobitexAPIError, PublicAPIView
from exchange.base.decorators import measure_api_execution
from exchange.marketing.exceptions import InvalidCampaignException, InvalidOTPException, InvalidUserIDException
from exchange.marketing.services.campaign.base import (
    MobileVerificationBasedCampaign,
    UserIdentifier,
    UserIdentifierType,
    UTMParameters,
)
from exchange.marketing.services.campaign.selector import check_campaign_type, choose_campaign_by_name
from exchange.marketing.types import CampaignOTPRequest, CampaignOTPVerifyRequest, CampaignViewSchema, UTMParams


def get_campaign_service(campaign_name):
    service = choose_campaign_by_name(campaign_name)
    check_campaign_type(service, MobileVerificationBasedCampaign)
    return service


def rate_limit_mobile_number_key(group, request):
    return json.loads(request.body).get('mobileNumber')


class CampaignOTPRequestView(PublicAPIView):

    @method_decorator(ratelimit(key='ip', rate='5/m', method='POST'))
    @method_decorator(ratelimit(key=rate_limit_mobile_number_key, rate='5/m', method='POST'))
    @method_decorator(measure_api_execution(api_label='campaignOTPRequest'))
    def post(self, request):
        try:
            otp_request = CampaignOTPRequest(
                mobile_number=self.g('mobileNumber'), utm_params=UTMParams(**request.GET.dict())
            )
            self._request_otp(otp_request)
            return self.response({'status': 'ok'})

        except ValidationError as e:
            raise NobitexAPIError(
                message='ParseError',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from None
        except InvalidUserIDException as e:
            raise NobitexAPIError(
                message='InvalidUserID',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from None
        except InvalidOTPException as e:
            raise NobitexAPIError(
                message='InvalidOTP',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from None
        except InvalidCampaignException as e:
            raise NobitexAPIError(
                message='InvalidCampaign',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from None
        except User.DoesNotExist as e:
            raise NobitexAPIError(
                message='UserDoesNotExist',
                description='user does not exist with requested identifier',
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            ) from None

    @staticmethod
    def _request_otp(otp_request: CampaignOTPRequest):
        service = get_campaign_service(otp_request.utm_params.utm_campaign)
        service.send_otp(
            user_identifier=UserIdentifier(id=otp_request.mobile_number, type=UserIdentifierType.MOBILE),
            utm_params=UTMParameters(
                utm_source=otp_request.utm_params.utm_source,
                utm_medium=otp_request.utm_params.utm_medium,
                utm_campaign=otp_request.utm_params.utm_campaign,
            ),
        )


class CampaignOTPVerifyView(PublicAPIView):

    @method_decorator(ratelimit(key='ip', rate='5/m', method='POST'))
    @method_decorator(ratelimit(key=rate_limit_mobile_number_key, rate='5/m', method='POST'))
    @method_decorator(measure_api_execution(api_label='campaignOTPVerify'))
    def post(self, request):
        try:
            verify_request = CampaignOTPVerifyRequest(
                mobile_number=self.g('mobileNumber'),
                code=self.g('code'),
                utm_params=UTMParams(**request.GET.dict()),
            )
            result = self._verify_otp(verify_request)
            return self.response(
                CampaignViewSchema(
                    status='ok',
                    webengage_id=result.user_details.webengage_id,
                    campaign_details=result.campaign_details,
                ).model_dump(by_alias=True)
            )
        except ValidationError as e:
            raise NobitexAPIError(
                message='ParseError',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from None
        except InvalidUserIDException as e:
            raise NobitexAPIError(
                message='InvalidUserID',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from None
        except InvalidOTPException as e:
            raise NobitexAPIError(
                message='InvalidOTP',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from None
        except InvalidCampaignException as e:
            raise NobitexAPIError(
                message='InvalidCampaign',
                description=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from None
        except User.DoesNotExist as e:
            raise NobitexAPIError(
                message='UserDoesNotExist',
                description='user does not exist with requested identifier',
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            ) from None

    @staticmethod
    def _verify_otp(verify_request: CampaignOTPVerifyRequest):
        service = get_campaign_service(verify_request.utm_params.utm_campaign)
        return service.verify_otp(
            user_identifier=UserIdentifier(id=verify_request.mobile_number, type=UserIdentifierType.MOBILE),
            verification_code=verify_request.code,
            utm_params=UTMParameters(
                utm_source=verify_request.utm_params.utm_source,
                utm_medium=verify_request.utm_params.utm_medium,
                utm_campaign=verify_request.utm_params.utm_campaign,
            ),
        )
