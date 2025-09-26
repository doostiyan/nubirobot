from enum import Enum
from typing import Union
from uuid import UUID

from django.conf import settings
from django.utils.translation import gettext_lazy as _
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel
from rest_framework.response import Response

from exchange.accounts.models import User, UserOTP, UserSms
from exchange.asset_backed_credit.exceptions import (
    ClientError,
    FeatureUnavailable,
    InternalAPIError,
    OTPProviderError,
    OTPValidationError,
)
from exchange.asset_backed_credit.externals.base import NOBITEX_BASE_URL, InternalAPI
from exchange.asset_backed_credit.externals.notification import NotificationProvider, notification_provider
from exchange.asset_backed_credit.models.otp import OTPLog
from exchange.base.decorators import measure_time_cm
from exchange.base.internal.idempotency import IDEMPOTENCY_HEADER
from exchange.base.logging import report_event
from exchange.base.models import Settings


class OTPProvider:
    OTP_TYPES = OTPLog.OTP_TYPES
    OTP_USAGE = OTPLog.OTP_USAGE

    @staticmethod
    def disable_existing_user_otps(user: User):
        UserOTP.active_otps(
            user=user,
            tp=UserOTP.OTP_TYPES.mobile,
            usage=UserOTP.OTP_Usage.grant_permission_to_financial_service,
        ).update(otp_status=UserOTP.OTP_STATUS.disabled)

    @staticmethod
    def create_new_user_otp(user: User) -> UserOTP:
        return UserOTP.create_otp(
            user=user,
            tp=UserOTP.OTP_TYPES.mobile,
            usage=UserOTP.OTP_Usage.grant_permission_to_financial_service,
        )

    @staticmethod
    def create_new_or_reuse_user_otp(user: User, otp: str) -> UserOTP:
        return user.generate_otp_obj(
            tp=User.OTP_TYPES.mobile,
            usage=UserOTP.OTP_Usage.grant_permission_to_financial_service,
            otp=otp,
        )

    @staticmethod
    def _check_mobile_otp_limit(user: User):
        limit = 3 if settings.IS_PROD else 50
        if UserSms.get_verification_messages(user).exclude(details='used').count() > limit:
            raise OTPProviderError(message='TooManySMS', description='Too many SMS requests')

    @classmethod
    def send_legacy_otp(cls, user: User, otp_type: int, usage: int):
        cls._check_mobile_otp_limit(user)
        if not user.get_verification_profile().mobile_confirmed:
            raise OTPProviderError(message='OTPRequestFailure', description=_('User has not confirmed mobile'))

        otp = UserOTP.get_or_create_otp(user=user, tp=otp_type, usage=usage)
        if otp_type == cls.OTP_TYPES.mobile:
            notification_provider.send_sms(
                user=otp.user,
                tp=NotificationProvider.MESSAGE_TYPES.grant_financial_service,
                text=otp.code,
                template=NotificationProvider.TEMPLATE_TYPES.grant_financial_service,
            )

    @classmethod
    def verify_legacy_otp(cls, user: User, otp_type: int, usage: int, otp_code: str):
        otp_obj, error = UserOTP.verify(
            code=otp_code,
            user=user,
            tp=otp_type,
            usage=usage,
        )
        if not otp_obj:
            raise OTPValidationError('OTP does not verified:' + str(error))
        otp_obj.mark_as_used()

    @classmethod
    def send_otp_with_internal_api(cls, user, otp_type, usage, idempotency: UUID) -> int:
        send_api = SendOTPAPI()
        data = SendOTPRequest(
            otp_type=InternalOTPType.from_db_value(int(otp_type)), otp_usage=InternalOTPUsage.from_db_value(int(usage))
        )
        try:
            response = send_api.request(user.uid, data, idempotency)
            return response.status_code
        except InternalAPIError as _:
            return send_api.response.status_code

    @classmethod
    def verify_otp_with_internal_api(cls, user: User, otp_type: int, usage: int, code: str, idempotency: UUID) -> int:
        data = VerifyOTPRequest(
            otp_code=code,
            otp_type=InternalOTPType.from_db_value(int(otp_type)),
            otp_usage=InternalOTPUsage.from_db_value(int(usage)),
        )

        verify_api = VerifyOTPAPI()
        try:
            response = verify_api.request(user.uid, data, idempotency)
            return response.status_code
        except InternalAPIError as _:
            return verify_api.response.status_code


class InternalOTPType(Enum):
    EMAIL = 'email'
    MOBILE = 'mobile'
    PHONE = 'phone'

    @classmethod
    def from_db_value(cls, value: int):
        mapping = {1: cls.EMAIL, 2: cls.MOBILE, 3: cls.PHONE}
        return mapping.get(value)


class InternalOTPUsage(Enum):
    GRANT_PERMISSION_TO_FINANCIAL_SERVICE = 'grant_permission_to_financial_service'

    @classmethod
    def from_db_value(cls, value: int):
        mapping = {11: cls.GRANT_PERMISSION_TO_FINANCIAL_SERVICE}
        return mapping.get(value)


class SendOTPRequest(BaseModel):
    otp_type: InternalOTPType
    otp_usage: InternalOTPUsage

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class SendOTPAPI(InternalAPI):
    url = f'{NOBITEX_BASE_URL}/internal/users/{{}}/send-otp'
    method = 'post'
    need_auth = True
    service_name = 'account'
    endpoint_key = 'userSendOTP'
    error_message = 'UserSendOTP'

    @measure_time_cm(metric='abc_account_userSendOTP')
    def request(self, user_id: UUID, data: SendOTPRequest, idempotency: UUID) -> Union[None, Response]:
        if not Settings.get_flag('abc_use_send_otp_internal_api'):
            raise FeatureUnavailable
        self.url = self.url.format(user_id)
        try:
            return self._request(
                json=data.model_dump(mode='json', by_alias=True), headers={IDEMPOTENCY_HEADER: str(idempotency)}
            )
        except (TypeError, ValueError, ClientError) as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise InternalAPIError(f'{self.error_message}: send otp failure') from e


class VerifyOTPRequest(BaseModel):
    otp_code: str
    otp_type: InternalOTPType
    otp_usage: InternalOTPUsage

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class VerifyOTPAPI(InternalAPI):
    url = f'{NOBITEX_BASE_URL}/internal/users/{{}}/verify-otp'
    method = 'post'
    need_auth = True
    service_name = 'account'
    endpoint_key = 'userVerifyOTP'
    error_message = 'UserVerifyOTP'

    @measure_time_cm(metric='abc_account_userVerifyOTP')
    def request(self, user_id: UUID, data: VerifyOTPRequest, idempotency: UUID) -> Union[None, Response]:
        if not Settings.get_flag('abc_use_verify_otp_internal_api'):
            raise FeatureUnavailable
        self.url = self.url.format(user_id)
        try:
            return self._request(
                json=data.model_dump(mode='json', by_alias=True), headers={IDEMPOTENCY_HEADER: str(idempotency)}
            )
        except (TypeError, ValueError, ClientError) as e:
            report_event(f'{self.error_message}: request exception', extras={'exception': str(e)})
            raise InternalAPIError(f'{self.error_message}: verify otp failure') from e
