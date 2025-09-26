from typing import Optional

from django.conf import settings
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel
from rest_framework import status
from rest_framework.response import Response

from exchange.accounts.models import User
from exchange.asset_backed_credit.api.serializers import UserFinancialServiceLimitSerializer
from exchange.asset_backed_credit.models import Service, UserFinancialServiceLimit
from exchange.base.api import NobitexAPIError
from exchange.base.api_v2_1 import InternalAPIView
from exchange.base.decorators import measure_api_execution
from exchange.base.internal.permissions import AllowedServices
from exchange.base.internal.services import Services

ALLOWED_SERVICES_PERMISSION = AllowedServices((Services.ADMIN,))


class Limit(BaseModel):
    limit_type: int
    user_id: Optional[str] = None
    user_type: Optional[int] = None
    service_id: Optional[int] = None
    service_provider: Optional[int] = None
    service_type: Optional[int] = None
    min_limit: Optional[int] = None
    max_limit: Optional[int] = None

    model_config = ConfigDict(
        alias_generator=to_camel,
    )


VALIDATION_MAP = {
    UserFinancialServiceLimit.TYPES.user: {
        'user_id': True,
        'user_type': False,
        'service_id': False,
        'service_provider': False,
        'service_type': False,
    },
    UserFinancialServiceLimit.TYPES.user_service: {
        'user_id': True,
        'user_type': False,
        'service_id': True,
        'service_provider': False,
        'service_type': False,
    },
    UserFinancialServiceLimit.TYPES.user_service_provider: {
        'user_id': True,
        'user_type': False,
        'service_id': False,
        'service_provider': True,
        'service_type': False,
    },
    UserFinancialServiceLimit.TYPES.user_service_type: {
        'user_id': True,
        'user_type': False,
        'service_id': False,
        'service_provider': False,
        'service_type': True,
    },
    UserFinancialServiceLimit.TYPES.user_type: {
        'user_id': False,
        'user_type': True,
        'service_id': False,
        'service_provider': False,
        'service_type': False,
    },
    UserFinancialServiceLimit.TYPES.user_type_service: {
        'user_id': False,
        'user_type': True,
        'service_id': True,
        'service_provider': False,
        'service_type': False,
    },
    UserFinancialServiceLimit.TYPES.user_type_service_provider: {
        'user_id': False,
        'user_type': True,
        'service_id': False,
        'service_provider': True,
        'service_type': False,
    },
    UserFinancialServiceLimit.TYPES.user_type_service_type: {
        'user_id': False,
        'user_type': True,
        'service_id': False,
        'service_provider': False,
        'service_type': True,
    },
    UserFinancialServiceLimit.TYPES.service: {
        'user_id': False,
        'user_type': False,
        'service_id': True,
        'service_provider': False,
        'service_type': False,
    },
    UserFinancialServiceLimit.TYPES.service_provider: {
        'user_id': False,
        'user_type': False,
        'service_id': False,
        'service_provider': True,
        'service_type': False,
    },
    UserFinancialServiceLimit.TYPES.service_type: {
        'user_id': False,
        'user_type': False,
        'service_id': False,
        'service_provider': False,
        'service_type': True,
    },
}


class UserFinancialServiceLimitList(InternalAPIView):
    permission_classes = [ALLOWED_SERVICES_PERMISSION]

    @method_decorator(measure_api_execution(api_label='abcUserFinancialServiceLimitCreate'))
    @method_decorator(ratelimit(key='ip', rate='10/m', method='POST', block=True))
    def post(self, request, *args, **kwargs):
        try:
            limit = Limit.model_validate(request.data)
            limit = self.validate_limit(limit)
        except (ValidationError, ValueError) as e:
            raise NobitexAPIError(
                message='ParseError',
                description=self._get_error_message(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        UserFinancialServiceLimit.objects.update_or_create(
            tp=limit.limit_type,
            user_id=limit.user_id,
            user_type=limit.user_type,
            service_id=limit.service_id,
            service_provider=limit.service_provider,
            service_type=limit.service_type,
            defaults={
                'min_limit': limit.min_limit,
                'limit': limit.max_limit,
            },
        )

        data = {'status': 'ok', 'data': limit.model_dump()}
        return Response(data, status=status.HTTP_201_CREATED)

    @staticmethod
    def validate_limit(limit):
        validation = VALIDATION_MAP[limit.limit_type]
        for k, v in validation.items():
            if not v:
                setattr(limit, k, None)

        if limit.min_limit is None and limit.max_limit is None:
            raise ValueError('min and max limit cannot both be none')

        if limit.user_id:
            try:
                limit.user_id = User.objects.get(uid=limit.user_id).id
            except User.DoesNotExist:
                raise ValueError('invalid userId')

        if limit.user_type and limit.user_type not in User.USER_TYPES:
            raise ValueError('invalid userType')

        if limit.service_id:
            try:
                Service.objects.get(id=limit.service_id)
            except Service.DoesNotExist:
                raise ValueError('invalid serviceId')

        if limit.service_provider and limit.service_provider not in Service.PROVIDERS:
            raise ValueError('invalid serviceProvider')

        if limit.service_type and limit.service_type not in Service.TYPES:
            raise ValueError('invalid serviceType')

        return limit

    @staticmethod
    def _get_error_message(error):
        return None if settings.IS_PROD else str(error)


class UserFinancialServiceLimitDetail(InternalAPIView):
    permission_classes = [ALLOWED_SERVICES_PERMISSION]

    @method_decorator(measure_api_execution(api_label='abcUserFinancialServiceLimitDelete'))
    @method_decorator(ratelimit(key='ip', rate='10/m', method='POST', block=True))
    def delete(self, request, pk, *args, **kwargs):
        try:
            limit = UserFinancialServiceLimit.objects.get(pk=pk)
        except UserFinancialServiceLimit.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        limit.delete()
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)
