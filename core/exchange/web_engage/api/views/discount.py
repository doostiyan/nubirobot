from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework.status import HTTP_200_OK

from exchange.base.decorators import measure_api_execution
from exchange.base.parsers import parse_str, parse_uuid
from exchange.marketing.services.campaign.base import CampaignType, UserIdentifier, UserIdentifierType
from exchange.marketing.services.campaign.selector import choose_campaign_by_name, choose_campaign_by_type
from exchange.web_engage.api.authentication import DiscountAuthentication
from exchange.web_engage.api.exceptions import discount_exception_mapper
from exchange.web_engage.api.views.base import WebEngageAPIView


class CheckActiveUserDiscountApi(WebEngageAPIView):
    authentication_classes = [DiscountAuthentication]

    @method_decorator(ratelimit(key='ip', rate='1000/m', method='POST', block=True))
    @method_decorator(discount_exception_mapper)
    def post(self, request, *args, **kwargs):
        discount_id = parse_str(request.data.get('discountId'), required=True)
        webengage_user_id = parse_uuid(request.data.get('userId'), required=True)
        user_identifier = UserIdentifier(id=webengage_user_id, type=UserIdentifierType.WEBENGAGE_USER_ID)

        service = choose_campaign_by_type(CampaignType.DISCOUNT)
        service.check_reward_conditions(user_identifier, discount_id=discount_id)
        return JsonResponse(status=HTTP_200_OK, data={'status': 'ok'})


class CreateUserDiscountApi(WebEngageAPIView):
    authentication_classes = [DiscountAuthentication]

    @method_decorator(ratelimit(key='ip', rate='1000/m', method='POST', block=True))
    @method_decorator(discount_exception_mapper)
    def post(self, request, *args, **kwargs):
        discount_id = parse_str(request.data.get('discountId'), required=True)
        webengage_user_id = parse_uuid(request.data.get('userId'), required=True)
        user_identifier = UserIdentifier(id=webengage_user_id, type=UserIdentifierType.WEBENGAGE_USER_ID)

        service = choose_campaign_by_type(CampaignType.DISCOUNT)
        service.send_reward(user_identifier, discount_id=discount_id)
        return JsonResponse(status=HTTP_200_OK, data={'status': 'ok'})


class SendExternalDiscountApi(WebEngageAPIView):
    authentication_classes = [DiscountAuthentication]

    @method_decorator(ratelimit(key='ip', rate='1000/m', method='POST', block=False))
    @method_decorator(measure_api_execution(api_label='sendExternalDiscount'))
    @method_decorator(discount_exception_mapper)
    def post(self, request, *args, **kwargs):
        campaign_name = parse_str(request.data.get('campaignName'), required=True)
        webengage_user_id = parse_uuid(request.data.get('userId'), required=True)

        user_identifier = UserIdentifier(id=webengage_user_id, type=UserIdentifierType.WEBENGAGE_USER_ID)
        service = choose_campaign_by_name(campaign_name)
        service.send_reward(user_identifier)
        return JsonResponse(status=HTTP_200_OK, data={'status': 'ok'})
