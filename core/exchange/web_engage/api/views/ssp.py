import logging

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework.status import HTTP_200_OK

from exchange.base.decorators import measure_api_execution
from exchange.web_engage.api.authentication import SSPAuthentication
from exchange.web_engage.api.exceptions import ssp_exception_mapper
from exchange.web_engage.api.parsers import SSPMessageParser
from exchange.web_engage.api.permissions import SSPEnabledPermission, WebEngageIPWhitelistPermission
from exchange.web_engage.api.views.base import WebEngageAPIView
from exchange.web_engage.services.ssp import queue_message_to_send

logger = logging.getLogger(__name__)


class SSPMessageApi(WebEngageAPIView):
    permission_classes = [SSPEnabledPermission, WebEngageIPWhitelistPermission]
    authentication_classes = [SSPAuthentication]

    @method_decorator(ratelimit(key='ip', rate='2000/1m', block=True, method='POST'))
    @method_decorator(measure_api_execution(api_label='webengageSSP'))
    @method_decorator(ssp_exception_mapper)
    def post(self, request, *args, **kwargs):
        queue_message_to_send(SSPMessageParser.parse(request.data))
        return JsonResponse(status=HTTP_200_OK, data={"status": "sms_accepted"})
