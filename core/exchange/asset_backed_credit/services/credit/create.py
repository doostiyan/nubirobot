from decimal import Decimal

from django.db import IntegrityError, transaction

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import ExternalProviderError, ServiceAlreadyActivated, ThirdPartyError
from exchange.asset_backed_credit.models import InternalUser, Service, UserService, UserServicePermission
from exchange.asset_backed_credit.services.providers.dispatcher import api_dispatcher
from exchange.asset_backed_credit.services.user_service import check_margin_ratio, check_service_limit
from exchange.asset_backed_credit.tasks import add_user_restriction_task
from exchange.asset_backed_credit.types import (
    USER_SERVICE_PROVIDER_MESSAGE_MAPPING,
    UserInfo,
    UserServiceCreateRequest,
    UserServiceCreateResponse,
)
from exchange.base.logging import report_event


@transaction.atomic
def create_credit_service(
    user: User, internal_user: InternalUser, service: Service, permission: UserServicePermission, amount: Decimal
) -> UserService:
    InternalUser.get_lock(user.pk)
    check_service_limit(user=user, service=service, amount=amount)
    check_margin_ratio(user=user, amount=amount, service_type=service.tp)

    try:
        user_service = UserService.objects.create(
            user=user,
            internal_user=internal_user,
            service=service,
            user_service_permission=permission,
            initial_debt=amount,
            current_debt=amount,
        )
    except IntegrityError as e:
        report_event('UserServiceIntegrityError', extras={'error': str(e)})
        raise ServiceAlreadyActivated('service is already activated.') from e

    create_request = UserServiceCreateRequest(
        user_info=UserInfo(
            national_code=user.national_code,
            mobile=user.mobile,
            first_name=user.first_name,
            last_name=user.last_name,
            birthday_shamsi=user.birthday_shamsi,
        ),
        amount=int(user_service.initial_debt),
        unique_id=str(user_service.external_id),
    )

    data = api_dispatcher(user_service=user_service).create_user_service(request_data=create_request)

    if data.status == UserServiceCreateResponse.Status.FAILED:
        raise ExternalProviderError(USER_SERVICE_PROVIDER_MESSAGE_MAPPING[data.message])

    if data.status == UserServiceCreateResponse.Status.SUCCEEDED:
        user_service.current_debt = data.amount
        user_service.status = UserService.STATUS.initiated
        user_service.account_number = data.provider_tracking_id
        user_service.save(update_fields=('current_debt', 'status', 'account_number'))
    elif data.status == UserServiceCreateResponse.Status.REQUESTED:
        user_service.current_debt = data.amount
        user_service.status = UserService.STATUS.created
        user_service.account_number = data.provider_tracking_id
        user_service.save(update_fields=('current_debt', 'status', 'account_number'))
    else:
        raise ValueError()

    for restriction in api_dispatcher(user_service=user_service).get_user_restrictions():
        transaction.on_commit(
            lambda: add_user_restriction_task.delay(
                user_service_id=user_service.id,
                restriction=restriction.tp,
                description_key=restriction.description,
                considerations=restriction.consideration,
            )
        )

    return user_service
