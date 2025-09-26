from django.http import HttpRequest
from rest_framework.permissions import BasePermission

from exchange.base.http import get_client_ip
from exchange.base.logging import report_event
from exchange.base.models import Settings


class SSPEnabledPermission(BasePermission):
    def has_permission(self, request, view):
        is_enabled_ssp = Settings.get_value('is_enabled_ssp', default='true').strip().lower() == 'true'
        return is_enabled_ssp


class ESPEnabledPermission(BasePermission):
    def has_permission(self, request, view):
        is_enabled_ssp = Settings.get_value('is_enabled_esp', default='true').strip().lower() == 'true'
        return is_enabled_ssp


class WebEngageIPWhitelistPermission(BasePermission):
    ALLOWED_IPS = ["54.82.121.36", "34.192.48.6", "13.235.37.92", "13.234.183.246", "35.154.107.85"]

    def has_permission(self, request: HttpRequest, view):
        ip = get_client_ip(request) or request.META['REMOTE_ADDR']
        if ip in self.ALLOWED_IPS:
            return True

        self._report_event(ip, request, view.__class__.__name__)
        return False

    @staticmethod
    def _report_event(ip, request, view_name):
        if view_name == "CheckActiveUserDiscountApi" or view_name == "CreateUserDiscountApi":
            report_event(
                'PermissionDeniedDiscountError',
                extras={'src': 'checkAccessApiDiscount', 'ip': ip, 'request': request},
            )
