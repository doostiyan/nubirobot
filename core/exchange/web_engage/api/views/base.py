from django.http import JsonResponse
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView as RestAPIView

from exchange.base.api import APIMixin
from exchange.web_engage.api.authentication import WebEngageAuthentication
from exchange.web_engage.api.exceptions import WebEngageError
from exchange.web_engage.api.permissions import WebEngageIPWhitelistPermission


class WebEngageAPIView(APIMixin, RestAPIView):
    authentication_classes = [WebEngageAuthentication]
    permission_classes = [WebEngageIPWhitelistPermission]
    renderer_classes = [JSONRenderer]

    def handle_exception(self, e):
        if not isinstance(e, WebEngageError):
            return super().handle_exception(e)

        return JsonResponse(status=e.status_code, data=self.encode_error(e))

    @staticmethod
    def encode_error(e):
        data = {"status": e.code, "statusCode": e.error_status_code, "message": e.description}
        if e.supported_version:
            data["supportedVersion"] = e.supported_version

        return data
