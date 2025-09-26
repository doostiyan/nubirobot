import enum
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from exchange.accounts.models import UserRestriction
from exchange.asset_backed_credit.exceptions import ClientError, FeatureUnavailable, InternalAPIError
from exchange.asset_backed_credit.externals.base import NOBITEX_BASE_URL, InternalAPI
from exchange.asset_backed_credit.models.user_service import UserService
from exchange.base.decorators import measure_time_cm
from exchange.base.internal.idempotency import IDEMPOTENCY_HEADER
from exchange.base.internal.services import Services
from exchange.base.logging import report_event
from exchange.base.models import Settings


class UserRestrictionProvider:
    @classmethod
    def add_restriction(cls, user_service: UserService, restriction: str, description_key: str, considerations: str):
        if Settings.get_flag('abc_use_restriction_internal_api'):
            UserAddRestrictionAPI().request(
                user_id=user_service.user.uid,
                data=UserAddRestrictionRequest(
                    restriction=restriction,
                    ref_id=user_service.id,
                    description=description_key,
                    considerations=considerations,
                ),
                idempotency=user_service.external_id,
            )
        else:
            UserRestriction.objects.get_or_create(
                user=user_service.user,
                restriction=UserRestrictionType.get_db_value(restriction),
                source=Services.ABC,
                ref_id=user_service.id,
                defaults={
                    'description': UserRestrictionsDescriptionType.get_db_value(description_key),
                    'considerations': considerations,
                },
            )

    @staticmethod
    def remove_restriction(user_service: UserService, restriction: str):
        if Settings.get_flag('abc_use_restriction_internal_api'):
            UserRemoveRestrictionAPI().request(
                user_id=user_service.user.uid,
                data=UserRemoveRestrictionRequest(restriction=restriction, ref_id=user_service.id),
                idempotency=user_service.external_id,
            )
        else:
            try:
                UserRestriction.objects.get(
                    user=user_service.user,
                    restriction=UserRestrictionType.get_db_value(restriction),
                    source=Services.ABC,
                    ref_id=user_service.id,
                ).delete()
            except UserRestriction.DoesNotExist:
                pass


class UserRestrictionType(str, Enum):
    CHANGE_MOBILE = 'ChangeMobile'

    @staticmethod
    def get_db_value(restriction: str):
        map = {UserRestrictionType.CHANGE_MOBILE.value: 22}
        return map.get(restriction)


class UserRestrictionsDescriptionType(str, enum.Enum):
    ACTIVE_TARA_CREDIT = 'ACTIVE_TARA_CREDIT'

    @staticmethod
    def get_db_value(key: str) -> str:
        return {
            UserRestrictionsDescriptionType.ACTIVE_TARA_CREDIT.value: 'به دلیل فعال بودن اعتبار تارا،‌ امکان ویرایش شماره موبایل وجود ندارد.'
        }[key]


class UserAddRestrictionRequest(BaseModel):
    restriction: UserRestrictionType
    ref_id: int
    considerations: Optional[str] = None
    description: UserRestrictionsDescriptionType = None
    duration_hours: Optional[int] = None

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class UserAddRestrictionAPI(InternalAPI):
    url = f'{NOBITEX_BASE_URL}/internal/users/%s/add-restriction'
    method = 'post'
    need_auth = True
    service_name = 'account'
    endpoint_key = 'userAddRestriction'
    error_message = 'UserAddRestriction'

    @measure_time_cm(metric='abc_account_userAddRestriction')
    def request(self, user_id: UUID, data: UserAddRestrictionRequest, idempotency: UUID) -> None:
        if not Settings.get_flag('abc_use_restriction_internal_api'):
            raise FeatureUnavailable

        self.url = self.url % user_id
        try:
            self._request(
                json=data.model_dump(mode='json', by_alias=True), headers={IDEMPOTENCY_HEADER: str(idempotency)}
            )
        except (ValueError, ClientError, InternalAPIError) as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise InternalAPIError(f'{self.error_message}: Failed to add restriction to user') from e


class UserRemoveRestrictionRequest(BaseModel):
    restriction: UserRestrictionType
    ref_id: int

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class UserRemoveRestrictionAPI(InternalAPI):
    url = NOBITEX_BASE_URL + '/internal/users/%s/remove-restriction'
    method = 'post'
    need_auth = True
    service_name = 'account'
    endpoint_key = 'userRemoveRestriction'
    error_message = 'UserRemoveRestriction'

    @measure_time_cm(metric='abc_account_userRemoveRestriction')
    def request(self, user_id: UUID, data: UserRemoveRestrictionRequest, idempotency: UUID) -> None:
        if not Settings.get_flag('abc_use_restriction_internal_api'):
            raise FeatureUnavailable

        self.url = self.url % user_id
        try:
            self._request(
                json=data.model_dump(mode='json', by_alias=True), headers={IDEMPOTENCY_HEADER: str(idempotency)}
            )
        except (ValueError, ClientError, InternalAPIError) as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise InternalAPIError(f'{self.error_message}: Failed to remove restriction from user') from e
