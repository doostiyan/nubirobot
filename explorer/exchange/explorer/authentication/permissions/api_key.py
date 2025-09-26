from django.conf import settings
from django.utils.translation import gettext_lazy as _

from rest_framework_api_key.permissions import BaseHasAPIKey

from ...utils.request import get_client_ip
from ..models import UserAPIKey
from ..utils.exceptions import APIKeyNotProvidedException


class UserHasAPIKey(BaseHasAPIKey):
    model = UserAPIKey
    API_KEY_HEADER = settings.API_KEY_CUSTOM_HEADER

    def has_permission(self, request, view) -> bool:
        assert self.model is not None, (
                "%s must define `.model` with the API key model to use"
                % self.__class__.__name__
        )
        client_ip = get_client_ip(request)
        if client_ip in settings.ALLOWED_CLIENT_IPS:
            return True
        else:
            key = self.get_key(request)
            if not key:
                return False
            model_manager = self.model.objects
            api_key = model_manager.get_from_key(key)
            request.api_key = api_key
            return model_manager.is_valid(api_key)

    @classmethod
    def get_key(cls, request):
        format = request.accepted_renderer.format
        if format == 'html':
            key = request.COOKIES.get('api_key')
        else:
            key = request.META.get(cls.API_KEY_HEADER)
        if not key:
            raise APIKeyNotProvidedException(
                _('Pass API key {} in header').format(settings.API_KEY_CUSTOM_HEADER_CLIENT_FORMAT))
        return key
