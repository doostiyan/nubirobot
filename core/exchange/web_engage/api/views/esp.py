import logging

from django.http.response import JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.status import HTTP_200_OK

from exchange.base.api import PublicAPIView
from exchange.base.decorators import measure_api_execution
from exchange.web_engage.api.authentication import ESPAuthentication
from exchange.web_engage.api.exceptions import esp_delivery_exception_mapper, esp_exception_mapper
from exchange.web_engage.api.parsers import ESPMessageParser
from exchange.web_engage.api.permissions import ESPEnabledPermission, WebEngageIPWhitelistPermission
from exchange.web_engage.api.views.base import WebEngageAPIView
from exchange.web_engage.services.esp import get_recipients_by_webengage_ids, process_delivery_status, send_email
from exchange.web_engage.types import ESPDeliveryStatusCode

logger = logging.getLogger(__name__)


class ESPMessageApi(WebEngageAPIView):
    permission_classes = [ESPEnabledPermission, WebEngageIPWhitelistPermission]
    authentication_classes = [ESPAuthentication]

    @method_decorator(measure_api_execution(api_label='webengageESP'))
    @method_decorator(esp_exception_mapper)
    def post(self, request, *args, **kwargs):
        send_email(self._decode_email_addresses(ESPMessageParser.parse(request.data)))
        return JsonResponse(
            status=status.HTTP_200_OK,
            data={'status': 'SUCCESS', 'statusCode': ESPDeliveryStatusCode.SUCCESS.value, 'message': 'NA'},
        )

    @classmethod
    def _decode_email_addresses(cls, data: dict) -> dict:
        result = []
        to_list = [r for r in data.get('email', {}).get('recipients', {}).get('to', {})]
        email_ids = list(map(lambda r: r['email'], filter(lambda r: r.get('email', '').strip() != '', to_list)))
        users = get_recipients_by_webengage_ids(email_ids)

        for recipient in to_list:
            if recipient.get('email') not in users:
                continue
            result.append({'name': recipient.get('name', ''), 'email': users[recipient.get('email')].email})

        data.get('email', {}).get('recipients', {}).update({"to": result})
        return data


class ESPDeliveryStatusApi(PublicAPIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='4/s', method='POST', block=True))
    @method_decorator(measure_api_execution(api_label='webengageESPDeliveryStatusWebhook'))
    @method_decorator(csrf_exempt)
    @method_decorator(esp_delivery_exception_mapper)
    def post(self, request, bulk_id):
        self.validate(request.data, bulk_id)
        process_delivery_status(request.data)
        return JsonResponse(status=HTTP_200_OK, data={'status': 'SUCCESS'})

    @staticmethod
    def validate(data, bulk_id):
        records = data.get("results", list())
        for record in records:
            if record.get('bulkId', '') != bulk_id:
                raise ValueError(f'Email request not found with bulk_id: {bulk_id}')
