from typing import Optional
from django.core.exceptions import ImproperlyConfigured
from rest_framework.views import APIView
from drf_yasg.utils import swagger_auto_schema

from exchange.blockchain.validators import validate_crypto_address_by_network, validate_crypto_address_v2
from ..utils.blockchain import parse_currency2code


class PermissionRequiredAPIView(APIView):
    permission_required = None

    def get_permission_required(self, request):
        """
        Override this method to override the permission_required attribute.
        Must return an iterable.
        """

        if self.permission_required is None:
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} is missing the "
                f"permission_required attribute. Define "
                f"{self.__class__.__name__}.permission_required, or override "
                f"{self.__class__.__name__}.get_permission_required()."
            )

        perms = self.permission_required.get(request.method.lower(), [])
        if isinstance(perms, str):
            perms = (self.permission_required,)
        return perms

    def check_permissions(self, request):
        super().check_permissions(request)
        perms = self.get_permission_required(request)
        if not self.request.user.has_perms(perms):
            self.permission_denied(request)


def validate_address(address: str, network: str, currency: Optional[str] = None):
    if currency:
        currency = currency.lower()
        currency_code = parse_currency2code(currency)
        if not validate_crypto_address_v2(address=address, currency=currency_code, network=network)[0]:
            return False
    else:
        if not validate_crypto_address_by_network(address=address, network=network):
            return False
    return True
