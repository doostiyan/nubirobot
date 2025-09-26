from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.exceptions import OTPProviderError, OTPValidationError
from exchange.asset_backed_credit.externals.otp import OTPProvider
from exchange.asset_backed_credit.models.otp import OTPLog
from exchange.base.models import Settings


def send_otp(user: User, otp_type: int, usage: int):
    if Settings.get_flag('abc_use_send_otp_internal_api'):
        otp_log = OTPLog.get_or_create_log(user, otp_type, usage)
        response_status = OTPProvider.send_otp_with_internal_api(
            user, otp_log.otp_type, otp_log.usage, otp_log.idempotency
        )
        otp_log.update_send_api_data(response_status)

        if response_status != status.HTTP_200_OK:
            raise OTPProviderError('OTPServiceUnavailable', description='OTP service is currency unavailable')

    else:
        OTPProvider.send_legacy_otp(user, otp_type, usage)


def verify_otp(user: User, otp_type: int, usage: int, otp_code: str):
    if Settings.get_flag('abc_use_verify_otp_internal_api'):
        otp_log = OTPLog.get_valid_logs_to_verify(user, otp_type, usage).first()
        if not otp_log:
            raise OTPValidationError('OTP verification failed.')

        response_status = OTPProvider.verify_otp_with_internal_api(
            user=user, otp_type=otp_log.otp_type, usage=otp_log.usage, code=otp_code, idempotency=otp_log.idempotency
        )
        otp_log.update_verify_api_data(response_status)

        if response_status != status.HTTP_200_OK:
            raise OTPValidationError('OTP verification failed.')
    else:
        OTPProvider.verify_legacy_otp(user, otp_type, usage, otp_code)
