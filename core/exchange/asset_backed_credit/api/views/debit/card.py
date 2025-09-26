import re

from django.conf import settings
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from pydantic import ValidationError
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.api.parsers import parse_enable_debit_card_batch_request
from exchange.asset_backed_credit.api.serializers import DebitCardListSchema
from exchange.asset_backed_credit.api.views import InternalABCView, user_eligibility_api
from exchange.asset_backed_credit.exceptions import (
    CardAlreadyExists,
    CardInvalidStatusError,
    CardNotFoundError,
    DebitCardCreationServiceTemporaryUnavailable,
    DuplicateDebitCardRequestByUser,
    ServiceAlreadyActivated,
    ServiceLimitNotSet,
    ServiceNotFoundError,
    ServicePermissionNotFound,
    ServiceUnavailableError,
    ThirdPartyError,
    TransferCurrencyRequiredError,
    UserLevelRestrictionError,
    UserServiceNotFoundError,
)
from exchange.asset_backed_credit.models import Card, CardRequestAPISchema, Service
from exchange.asset_backed_credit.services.debit.card import (
    activate_debit_card,
    create_debit_card,
    disable_debit_card,
    enable_debit_card_batch,
    get_debit_card,
    get_debit_cards,
    request_debit_card_otp,
    suspend_debit_card,
    verify_debit_card_otp,
)
from exchange.asset_backed_credit.services.debit.limits import get_card_overview_info
from exchange.asset_backed_credit.types import DEBIT_FEATURE_FLAG
from exchange.asset_backed_credit.utils import parse_clients_error
from exchange.base.api import NobitexAPIError, ParseError
from exchange.base.api_v2_1 import internal_post_api
from exchange.base.decorators import measure_api_execution
from exchange.base.internal.services import Services
from exchange.base.parsers import parse_int, parse_str
from exchange.base.serializers import serialize_choices
from exchange.features.utils import require_feature


class DebitCardListCreateView(InternalABCView):
    @method_decorator(measure_api_execution(api_label='abcDebitCardList'))
    @method_decorator(ratelimit(key='user_or_ip', rate='10/m', method='GET', block=True))
    @method_decorator(require_feature(DEBIT_FEATURE_FLAG))
    @method_decorator(user_eligibility_api)
    def get(self, request):
        """
        This API returns users debit cards
        GET /asset-backed-credit/debit/cards
        """

        user = request.user
        try:
            cards = [
                DebitCardListSchema(
                    id=card.id,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    pan=card.masked_pan,
                    color=card.extra_info.get('color'),
                    status=serialize_choices(Card.STATUS, card.status),
                    issued_at=card.issued_at.isoformat() if card.issued_at else None,
                ).model_dump(by_alias=True)
                for card in get_debit_cards(user=user)
            ]
        except ServiceNotFoundError as e:
            raise NobitexAPIError(
                message=e.__class__.__name__, description=str(e), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            ) from e

        return self.response({'status': 'ok', 'cards': cards})

    @method_decorator(measure_api_execution(api_label='abcDebitCardCreate'))
    @method_decorator(ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True))
    @method_decorator(require_feature(DEBIT_FEATURE_FLAG))
    @method_decorator(user_eligibility_api)
    def post(self, request):
        """
        This API create a debit card
        POST /asset-backed-credit/debit/cards
        """

        try:
            card_info = CardRequestAPISchema.model_validate(request.data)
        except ValidationError as e:
            raise NobitexAPIError(
                message='ParseError',
                description=self._get_error_message(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            create_debit_card(user=request.user, internal_user=request.internal_user, card_info=card_info)
        except Service.DoesNotExist:
            raise NobitexAPIError(message='ServiceDoesNotExist', status_code=status.HTTP_404_NOT_FOUND)
        except (
            ServicePermissionNotFound,
            ServiceAlreadyActivated,
            ServiceLimitNotSet,
            UserLevelRestrictionError,
            ServiceUnavailableError,
            ServiceNotFoundError,
            DebitCardCreationServiceTemporaryUnavailable,
        ) as e:
            raise NobitexAPIError(
                message=e.__class__.__name__, description=str(e), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            ) from e
        except TransferCurrencyRequiredError as e:
            message, description = parse_clients_error(
                request=request,
                message=e.__class__.__name__,
                description='انتخاب رمزارز برای انتقال موجودی برای پرداخت هزینه صدور الزامی است.',
            )
            raise NobitexAPIError(
                message=message, description=description, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            )

        return self.response({'status': 'ok'})

    @staticmethod
    def _get_error_message(error):
        return None if settings.IS_PROD else str(error)


class DebitCardOTPRequestView(InternalABCView):
    @method_decorator(measure_api_execution(api_label='abcDebitCardOTPRequest'))
    @method_decorator(ratelimit(key='user_or_ip', rate='5/10m', method='POST', block=True))
    @method_decorator(ratelimit(key='user_or_ip', rate='10/h', method='POST', block=True))
    @method_decorator(require_feature(DEBIT_FEATURE_FLAG))
    @method_decorator(user_eligibility_api)
    def post(self, request):
        pan = parse_str(self.g('pan'), required=True)
        if not re.fullmatch(r'^[5-6][0-9]{15}$', pan):
            raise ParseError('Invalid string value')

        try:
            request_debit_card_otp(user=request.user, pan=pan)
        except (
            DuplicateDebitCardRequestByUser,
            UserLevelRestrictionError,
            ServiceLimitNotSet,
            UserServiceNotFoundError,
            ThirdPartyError,
        ) as e:
            raise NobitexAPIError(
                message=e.__class__.__name__, description=str(e), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            ) from e

        return self.response({'status': 'ok'})


class DebitCardOTPVerifyView(InternalABCView):
    @method_decorator(measure_api_execution(api_label='abcDebitCardOTPVerify'))
    @method_decorator(ratelimit(key='user_or_ip', rate='5/10m', method='POST', block=True))
    @method_decorator(ratelimit(key='user_or_ip', rate='10/h', method='POST', block=True))
    @method_decorator(require_feature(DEBIT_FEATURE_FLAG))
    @method_decorator(user_eligibility_api)
    def post(self, request):
        pan = parse_str(self.g('pan'), required=True)
        if not re.fullmatch(r'^[5-6][0-9]{15}$', pan):
            raise ParseError('Invalid string value')

        code = parse_str(self.g('code'), required=True)
        if not re.fullmatch(r'^[0-9]*$', code):
            raise ParseError('Invalid string value')

        try:
            verify_debit_card_otp(user=request.user, pan=pan, code=code)
        except (
            UserLevelRestrictionError,
            UserServiceNotFoundError,
            ServiceNotFoundError,
            ThirdPartyError,
        ) as e:
            raise NobitexAPIError(
                message=e.__class__.__name__, description=str(e), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            ) from e

        return self.response({'status': 'ok'})


class DebitCardSuspendView(InternalABCView):
    @method_decorator(measure_api_execution(api_label='abcDebitCardSuspend'))
    @method_decorator(ratelimit(key='user_or_ip', rate='5/10m', method='POST', block=True))
    @method_decorator(require_feature(DEBIT_FEATURE_FLAG))
    @method_decorator(user_eligibility_api)
    def post(self, request, card_id: int):
        try:
            suspend_debit_card(user=request.user, card_id=card_id)
        except (
            CardNotFoundError,
            CardInvalidStatusError,
            UserLevelRestrictionError,
            ServiceNotFoundError,
            ThirdPartyError,
        ) as e:
            raise NobitexAPIError(
                message=e.__class__.__name__, description=str(e), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            ) from e

        return self.response({'status': 'ok'})


class DebitCardActivateView(InternalABCView):
    @method_decorator(measure_api_execution(api_label='abcDebitCardActivate'))
    @method_decorator(ratelimit(key='user', rate='10/h', method='POST', block=True))
    @method_decorator(require_feature(DEBIT_FEATURE_FLAG))
    @method_decorator(user_eligibility_api)
    def post(self, request, card_id: int):
        """
        API to change debit card status
        POST internal/asset-backed-credit/debit/cards/<int:card_id>/activate
        """

        try:
            activate_debit_card(user=request.user, card_id=card_id)
            return self.response({'status': 'ok'})
        except ValueError as e:
            raise NobitexAPIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                message='ValueError',
                description=str(e),
            ) from e
        except Card.DoesNotExist as e:
            raise NobitexAPIError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message='CardNotFound',
                description='card not found.',
            ) from e
        except CardInvalidStatusError as e:
            raise NobitexAPIError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message='CardInvalidStatus',
                description='Card status is invalid!',
            ) from e
        except UserLevelRestrictionError as e:
            raise NobitexAPIError(
                message=e.__class__.__name__, description=str(e), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            ) from e


class DebitCardDisableView(InternalABCView):
    @method_decorator(measure_api_execution(api_label='abcDebitCardDisable'))
    @method_decorator(ratelimit(key='user', rate='10/h', method='POST', block=True))
    @method_decorator(require_feature(DEBIT_FEATURE_FLAG))
    @method_decorator(user_eligibility_api)
    def post(self, request, card_id: int):
        """
        API to change debit card status
        POST internal/asset-backed-credit/debit/cards/<int:card_id>/disable
        """

        try:
            disable_debit_card(user=request.user, card_id=card_id)
            return self.response({'status': 'ok'})
        except ValueError as e:
            raise NobitexAPIError(
                status_code=status.HTTP_400_BAD_REQUEST,
                message='ValueError',
                description=str(e),
            ) from e
        except Card.DoesNotExist as e:
            raise NobitexAPIError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message='CardNotFound',
                description='card not found.',
            ) from e
        except CardInvalidStatusError as e:
            raise NobitexAPIError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message='CardInvalidStatus',
                description='Card status is invalid!',
            ) from e
        except UserLevelRestrictionError as e:
            raise NobitexAPIError(
                message=e.__class__.__name__, description=str(e), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            ) from e


@measure_api_execution(api_label='abcDebitCardEnable')
@ratelimit(key='ip', rate='3/m', method='POST', block=True)
@internal_post_api(allowed_services=[Services.ADMIN])
def internal_enable_debit_card_batch(request):
    """API for internal user service creation
    POST internal/asset-backed-credit/debit/card/enable
    """

    data = parse_enable_debit_card_batch_request(request)

    try:
        enable_debit_card_batch(data=data)
    except UserLevelRestrictionError as e:
        raise NobitexAPIError(
            status_code=status.HTTP_400_BAD_REQUEST,
            message=e.message,
            description=e.description,
        ) from e
    except User.DoesNotExist as e:
        raise NobitexAPIError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message='UserNotFound',
            description='User not found! invalid user_id',
        ) from e
    except (
        ServiceNotFoundError,
        ServiceAlreadyActivated,
        CardAlreadyExists,
        DebitCardCreationServiceTemporaryUnavailable,
    ) as e:
        raise NobitexAPIError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message=e.__class__.__name__,
            description=e.message if hasattr(e, 'message') else str(e),
        ) from e

    return {'status': 'ok'}


class DebitCardOverviewView(InternalABCView):
    @method_decorator(measure_api_execution(api_label='abcDebitCardOverview'))
    @method_decorator(ratelimit(key='user_or_ip', rate='10/m', method='GET', block=True))
    @method_decorator(require_feature(DEBIT_FEATURE_FLAG))
    @method_decorator(user_eligibility_api)
    def get(self, request, card_id: int):
        """
        This API returns overview info of debit card
        GET asset-backed-credit/debit/cards/<int:card_id>/overview
        """

        try:
            user = request.user
            card = get_debit_card(user=user, card_id=card_id)
        except ServiceNotFoundError as e:
            raise NobitexAPIError(
                message=e.__class__.__name__, description=str(e), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
            ) from e
        except Card.DoesNotExist:
            raise NobitexAPIError(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                message='CardNotFound',
                description='card not found.',
            )

        card_overview = get_card_overview_info(card)

        return self.response(
            {
                'status': 'ok',
                'data': card_overview.model_dump(by_alias=True) if card_overview else {},
            }
        )
