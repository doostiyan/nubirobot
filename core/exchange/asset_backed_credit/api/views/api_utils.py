import json
import uuid
from abc import ABC, abstractmethod
from decimal import Decimal
from functools import wraps
from typing import Any, ClassVar, Dict, List, Optional, Type

from django.conf import settings
from django.db import transaction
from django.http import HttpResponseNotFound, JsonResponse
from django_ratelimit.core import is_ratelimited
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView as RestAPIView

from exchange.accounts.models import User
from exchange.asset_backed_credit.api.authentication import InternalTokenAuthentication
from exchange.asset_backed_credit.api.parsers import parse_abc_service_type
from exchange.asset_backed_credit.api.views.exceptions import (
    ServiceUnavailable,
    UserNotActivated,
    UserServiceNotFound,
    ValidationError,
)
from exchange.asset_backed_credit.exceptions import (
    DuplicateRequestError,
    InvalidIPError,
    InvalidProviderError,
    InvalidSignatureError,
    MissingSignatureError,
)
from exchange.asset_backed_credit.models import IncomingAPICallLog, Service, UserServicePermission
from exchange.asset_backed_credit.models.user_service import UserService
from exchange.asset_backed_credit.services.providers.provider import SignSupportProvider
from exchange.asset_backed_credit.services.providers.provider_manager import provider_manager
from exchange.asset_backed_credit.services.user import (
    get_or_create_internal_user,
    is_user_mobile_identity_confirmed,
    is_user_verified_level_one,
)
from exchange.base.api import APIMixin, NobitexAPIError, ParseError, PublicAPIView, handle_exception
from exchange.base.http import get_client_ip
from exchange.base.logging import report_exception
from exchange.base.models import Settings
from exchange.base.validators import validate_national_code


class AssetBackedCreditAPIView(PublicAPIView):
    parameters = ()
    provider = None
    user = None
    internal_user = None
    permission = None
    service = None
    body_data = {}
    cleaned_data = {}
    user_service: UserService = None

    def __init__(self, **kwargs):
        self.cleaner = ABCCleaner()
        super().__init__(**kwargs)

    def dispatch(self, request, *args, **kwargs):
        try:
            self.handle_rate_limit()

            self.provider = provider_manager.get_provider_by_ip(get_client_ip(self.request))

            self.body_data = self.get_body_data(request.body)

            self.verify_signature()

            self.cleaned_data = self.cleaner.clean(self.body_data, self.parameters)

            cached_response = self.get_cached_response()
            if cached_response:
                return cached_response

            self.service = self.identify_service(service_type=self.cleaned_data.get('serviceType'))
            self.user = self.identify_user(national_code=self.cleaned_data.get('nationalCode'))
            self.internal_user = get_or_create_internal_user(self.user.uid)
            self.permission = self.identify_user_service_permission(
                user=self.user,
                service_tp=self.service.tp,
                provider_id=self.provider.id,
            )

            with transaction.atomic():
                response = super().dispatch(request, *args, **kwargs)

        # specific error handling to prevent creating duplicate log.
        except DuplicateRequestError as e:
            return JsonResponse(
                {'status': 'failed', 'code': e.__class__.__name__, 'message': str(e)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # specific error handling to restrict access to these APIs. making the APIs visible only to the providers.
        except InvalidIPError:
            if settings.IS_TESTNET:
                report_exception()
            response = HttpResponseNotFound()
        except Exception as exc:
            response = self.handle_exception(exc)

        IncomingAPICallLog.create(
            api_url=self.request.path,
            service=self.service.tp if self.service else None,
            user=self.user if self.user else None,
            internal_user=self.internal_user if self.internal_user else None,
            response_code=response.status_code,
            provider=self.provider.id if self.provider else None,
            uid=self.cleaned_data.get('trackId', None),
            request_body=self.body_data if self.body_data else self.request.body.decode('utf-8'),
            response_body=json.loads(response.content) if response.content else None,
            user_service=self.user_service,
        )
        return response

    def verify_signature(self):
        try:

            signature = self.request.headers.get('x-request-signature', None)
            if not isinstance(self.provider, SignSupportProvider):
                raise InvalidProviderError()
            provider_manager.verify_signature(
                signature=signature, pub_key=self.provider.pub_key, body_data=self.body_data
            )

        except (AttributeError, json.JSONDecodeError) as ex:
            raise NobitexAPIError(
                message='ValidationError',
                description='Invalid or empty JSON in the request body',
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from ex

        except MissingSignatureError as ex:
            raise NobitexAPIError(
                message='ValidationError',
                description=str(ex),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from ex

        except InvalidSignatureError as ex:
            raise NobitexAPIError(
                message='AuthorizationError',
                description=str(ex),
                status_code=status.HTTP_401_UNAUTHORIZED,
            ) from ex

    def handle_rate_limit(self) -> None:
        old_limited = getattr(self.request, 'limited', False)
        rate_limited = is_ratelimited(
            request=self.request,
            key='ip',
            rate='1000/m',
            method='POST',
            increment=True,
            group=f'exchange.asset_backed_credit.api.views.{self.__class__.__name__}',
        )
        self.request.limited = rate_limited or old_limited
        if rate_limited:
            raise NobitexAPIError(
                message='TooManyRequests',
                description='Too many requests',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            )

    def identify_user(self, national_code: str) -> User:
        user = User.objects.filter(national_code=national_code).first()
        if not user:
            raise UserNotActivated()

        return user

    def identify_user_service_permission(self, user: User, service_tp: int, provider_id: int) -> UserServicePermission:
        user_service_permission = UserServicePermission.get_active_permission(user, provider_id, service_tp)
        if not user_service_permission:
            raise UserNotActivated()

        return user_service_permission

    def identify_service(self, service_type: int) -> Service:
        service = Service.get_matching_active_service(self.provider.id, service_type)

        if not service:
            raise ServiceUnavailable()

        return service

    def identify_user_service(self) -> UserService:
        user_service = (
            UserService.objects.select_for_update(of=('self',), no_key=True)
            .filter(service=self.service, user=self.user, closed_at__isnull=True)
            .select_related('user', 'service')
            .first()
        )
        if not user_service:
            raise UserServiceNotFound()

        self.user_service = user_service
        return user_service

    def handle_exception(self, exc):
        return handle_exception(exc)

    def get_body_data(self, body_data: bytes):
        try:
            return json.loads(body_data.decode('utf-8').replace("'", "\""))
        except (AttributeError, json.JSONDecodeError) as ex:
            raise NobitexAPIError(
                message='ValidationError',
                description='Invalid or empty JSON in the request body',
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from ex

    def get_cached_response(self) -> Optional[JsonResponse]:
        track_id = self.cleaned_data.get('trackId', None)
        if not track_id:
            return None

        same_log = IncomingAPICallLog.objects.filter(uid=track_id).first()
        if not same_log:
            return None

        if self.body_data != same_log.request_body:
            raise DuplicateRequestError('track-id key reused with different payload')

        return JsonResponse(
            data=same_log.response_body,
            status=same_log.response_code,
        )

class ABCParamCleaner(ABC):
    value = None

    def __init__(self, value):
        self.value = value

    @abstractmethod
    def clean(self):
        """
        Clean the param, and if it's not valid, raise ValidationError with an appropriate error message.

        Returns:
        str: The cleaned parameter.

        Raises:
        ValidationError: If the cleaned parameter is not valid.
        """
        raise NotImplementedError()


class NationalCodeCleaner(ABCParamCleaner):
    def clean(self) -> str:
        is_valid = validate_national_code(ncode=self.value)
        if not is_valid:
            raise ValidationError('Invalid nationalCode format.')
        return self.value


class ServiceTypeCleaner(ABCParamCleaner):
    def clean(self) -> int:
        error_message = 'The serviceType is not valid!'
        if not self.value:
            raise ValidationError(error_message)
        try:
            service_type_id = parse_abc_service_type(self.value, required=True)
        except (AttributeError, ParseError) as ex:
            raise ValidationError(error_message) from ex
        return service_type_id


class TrackIdCleaner(ABCParamCleaner):
    def clean(self) -> str:
        invalid_error_message = 'The trackId is not a valid uuid4 string value!'
        if not self.value:
            raise ValidationError('The trackId parameter is required!')
        try:
            uuid_obj = uuid.UUID(self.value, version=4)
            if not str(uuid_obj) == self.value:
                raise ValidationError(invalid_error_message)
        except ValueError as ex:
            raise ValidationError(invalid_error_message) from ex

        return self.value


class AmountCleaner(ABCParamCleaner):
    def clean(self) -> Decimal:
        if not self.value:
            raise ValidationError('The amount is required!')
        try:
            amount = int(self.value)
        except (ValueError, TypeError):
            raise ValidationError('The amount is not a valid number in rial format')

        amount = Decimal(amount)
        if amount <= Decimal('0'):
            raise ValidationError('The amount must be greater than zero')
        return amount


class ABCCleaner:
    """
    A class for cleaning parameters in abc

    Attributes:
    - CLEANERS (dict): A dictionary mapping parameter names to their corresponding cleaner classes.

    Methods:
    - clean(): Clean parameters using the specified cleaners.

    Raises:
    - NotImplementedError: If a cleaner is not defined for a parameter.
    """

    CLEANERS: ClassVar[Dict[str, Type[ABCParamCleaner]]] = {
        'nationalCode': NationalCodeCleaner,
        'serviceType': ServiceTypeCleaner,
        'trackId': TrackIdCleaner,
        'amount': AmountCleaner,
    }

    def clean(self, data: Dict, parameters: List) -> Dict[str, Any]:
        try:
            cleaned_data = {}
            for param in parameters:
                param_value = data.get(param)
                if not param_value:
                    # Because all ABC parameters are required!
                    raise ValidationError(f'The {param} is required!')
                cleaner = self.CLEANERS.get(param)
                if not cleaner:
                    continue
                cleaned_data[param] = cleaner(param_value).clean()
        except ValidationError as e:
            raise NobitexAPIError(
                message='ValidationError',
                description=str(e.message),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from e
        except DuplicateRequestError as e:
            raise NobitexAPIError(
                message='DuplicateRequestError',
                description='The request is duplicated!',
                status_code=status.HTTP_409_CONFLICT,
            ) from e
        else:
            return cleaned_data


def user_eligibility_api(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        user = request.user
        if not is_user_verified_level_one(user=user):
            raise NobitexAPIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                message='UserLevelRestriction',
                description='User is not verified as level 1.',
            )
        if not is_user_mobile_identity_confirmed(user=user):
            raise NobitexAPIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                message='UserLevelRestriction',
                description='User has no confirmed mobile number.',
            )

        return view(request, *args, **kwargs)

    return wrapped


class APIView(APIMixin, RestAPIView):
    authentication_classes = [InternalTokenAuthentication]
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]


class InternalABCView(APIView):
    @transaction.atomic
    def dispatch(self, request, *args, **kwargs):
        if not Settings.get_flag('abc_is_activated_apis'):
            return HttpResponseNotFound()

        return super().dispatch(request, *args, **kwargs)
