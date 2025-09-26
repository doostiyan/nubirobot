from typing import Optional, Tuple

from exchange.accounts.models import User, UserOTP
from exchange.marketing.exceptions import InvalidOTPException


def send_sms_otp(mobile_number, usage: UserOTP.OTP_Usage):
    existing_user = User.objects.filter(mobile=mobile_number).first()
    UserOTP.create_otp(
        user=existing_user,
        tp=UserOTP.OTP_TYPES.mobile,
        usage=usage,
        phone_number=mobile_number,
    ).send()


def verify_sms_otp(mobile_number, otp_code, usage: UserOTP.OTP_Usage) -> Tuple[Optional[User], str]:
    otp, err = UserOTP.verify(
        phone_number=mobile_number,
        code=otp_code,
        tp=UserOTP.OTP_TYPES.mobile,
        usage=usage,
    )
    if err is not None:
        raise InvalidOTPException(err)

    otp.mark_as_used()

    return otp.user, otp.phone_number
