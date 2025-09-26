from dj_rest_auth.registration.serializers import RegisterSerializer
from django.utils.translation import gettext_lazy as _

from exchange.accounts.exceptions import EmailRegistrationDisabled, IncompleteRegisterError, InvalidUserNameError
from exchange.accounts.models import User
from exchange.accounts.serializers import EmailRegisterSerializer, MobileRegisterSerializer
from exchange.base.models import Settings
from exchange.base.normalizers import normalize_mobile
from exchange.base.validators import validate_email, validate_mobile


class BaseRegisterHandler:
    HANDLER_NAME = None

    def __init__(self, request_data: dict) -> None:
        self.request_data = request_data

    def get_serializer_class(self) -> RegisterSerializer:
        raise NotImplementedError()

    def validate_request_data(self) -> None:
        raise NotImplementedError()

    def run_post_create_actions(self, user: User, request: dict) -> None:
        raise NotImplementedError()


class EmailRegisterHandler(BaseRegisterHandler):
    HANDLER_NAME = 'email'

    def get_serializer_class(self):
        return EmailRegisterSerializer

    def validate_request_data(self) -> None:
        if not Settings.get_flag("email_register"):
            raise EmailRegistrationDisabled("ثبت نام با ایمیل غیرفعال شده است.")
        username = self.request_data.get('username') or ''
        email = self.request_data.get('email') or ''
        if not username == email:
            raise InvalidUserNameError('آدرس ایمیل با نام کاربری مطابقت ندارد.')

    def run_post_create_actions(self, user, request):
        user.send_welcome_email(request)


class MobileRegisterHandler(BaseRegisterHandler):
    HANDLER_NAME = 'mobile'

    def get_serializer_class(self):
        return MobileRegisterSerializer

    def validate_request_data(self):
        username = self.request_data.get('username') or ''
        mobile = self.request_data.get('mobile') or ''
        MobileRegisterHandler._validate_mobile(
            mobile=normalize_mobile(mobile.strip()),
        )
        if not username == mobile:
            raise InvalidUserNameError('شماره موبایل قابل قبول نیست')

        otp = self.request_data.get('otp')
        if otp in [None, '']:
            raise IncompleteRegisterError('کد تایید را ارسال کنید.')
        self._validate_otp()

    @classmethod
    def _validate_mobile(cls, mobile: str) -> None:
        if not Settings.get_flag('mobile_register'):
            raise InvalidUserNameError('ثبت نام با موبایل امکان پذیر نیست.')
        if User.objects.filter(mobile=mobile).exists():
            raise InvalidUserNameError(
                _("A user is already registered with this mobile number.")
            )

    @classmethod
    def send_mobile_otp(cls, mobile: str) -> None:
        from exchange.accounts.models import UserOTP
        mobile = normalize_mobile(mobile.strip())
        cls._validate_mobile(mobile)
        UserOTP.create_otp(
            tp=UserOTP.OTP_TYPES.mobile,
            usage=UserOTP.OTP_Usage.welcome_sms,
            phone_number=mobile,
        ).send()

    def _validate_otp(self) -> None:
        from exchange.accounts.models import UserOTP
        mobile = normalize_mobile(self.request_data.get('mobile').strip())
        _, err = UserOTP.verify(
            phone_number=mobile,
            code=self.request_data.get('otp'),
            tp=UserOTP.OTP_TYPES.mobile,
            usage=UserOTP.OTP_Usage.welcome_sms,
        )
        if err is not None:
            raise InvalidUserNameError('کد تایید به درستی ارسال نشده.')

    def run_post_create_actions(self, user, request):
        verification_profile = user.get_verification_profile()
        verification_profile.mobile_confirmed = True
        verification_profile.save(update_fields=['mobile_confirmed',])
        user.update_verification_status()


def get_register_handler(request_data: dict) -> BaseRegisterHandler:
    username = request_data.get('username') or ''
    if not username:
        raise InvalidUserNameError("نام کاربری ارسال نشده است.")

    if validate_email(username):
        return EmailRegisterHandler(request_data)
    elif validate_mobile(username):
        return MobileRegisterHandler(request_data)
    else:
        types_text = ''
        if Settings.get_flag('email_register') and Settings.is_feature_active('kyc2'):
            types_text = '، ایمیل و شماره‌ موبایل'
        elif Settings.get_flag('email_register'):
            types_text = ' و ایمیل'
        elif Settings.is_feature_active('kyc2'):
            types_text = ' و شماره موبایل'
        error_text = f'ثبت نام با حساب گوگل{types_text} امکان پذیر است.'
        raise InvalidUserNameError(error_text)
