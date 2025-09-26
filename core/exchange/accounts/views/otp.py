""" API views for OTP and 2FA """
import datetime

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.shortcuts import get_object_or_404
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_ratelimit.core import is_ratelimited
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.response import Response

from exchange.accounts.exceptions import InvalidUserNameError
from exchange.accounts.functions import validate_request_captcha
from exchange.accounts.merge import MergeHandler
from exchange.accounts.models import (
    ChangeMobileRequest,
    User,
    UserEvent,
    UserMergeRequest,
    UserOTP,
    UserSms,
    UserVoiceMessage,
)
from exchange.accounts.parsers import parse_otp_tp, parse_otp_usage
from exchange.accounts.register_handlers import MobileRegisterHandler
from exchange.accounts.userlevels import UserLevelManager
from exchange.accounts.views.merge import VerifyMergeRequestView
from exchange.accounts.views.profile import EMAIL_VERIFICATION_ATTEMPT_PREFIX_CACHE_KEY
from exchange.asset_backed_credit.exceptions import (
    ServiceAlreadyActivated,
    ServiceLimitNotSet,
    ServiceNotFoundError,
    ServiceUnavailableError,
)
from exchange.asset_backed_credit.models import Service, UserFinancialServiceLimit, UserServicePermission
from exchange.asset_backed_credit.utils import is_user_agent_android
from exchange.base.api import (
    NobitexAPIError,
    api,
    email_required_api,
    handle_ratelimit,
    public_post_api,
    raise_on_email_not_verified,
)
from exchange.base.calendar import ir_now
from exchange.base.decorators import measure_api_execution
from exchange.base.emailmanager import EmailManager
from exchange.base.formatting import read_number
from exchange.base.logstash_logging.loggers import logstash_logger
from exchange.base.parsers import parse_int
from exchange.base.validators import validate_mobile, validate_phone
from exchange.security.usersecurity import UserSecurityManager


def validate_mobile_otp_limit(user: User):
    limit = 3 if settings.IS_PROD else 50
    if UserSms.get_verification_messages(user).exclude(details='used').count() > limit:
        return {'status': 'failed', 'code': 'TooManySMS', 'message': 'Too many SMS requests'}


def social_user_set_password_otp_request(user: User):
    if not (user.can_social_login_user_set_password and user.get_verification_profile().email_confirmed):
        return {'status': 'failed', 'code': 'invalidUsageForUser', 'message': 'Can not get otp for set password'}

    otp = user.generate_otp(tp=User.OTP_TYPES.email)
    should_sms_otp = user.get_verification_profile().mobile_confirmed
    if should_sms_otp:
        error_response = validate_mobile_otp_limit(user)
        if error_response:
            return error_response

    EmailManager.send_email(
        user.email,
        'social_login_set_password_otp',
        data={
            'otp': otp,
        },
        priority='high',
    )
    user.generate_otp_obj(
        tp=User.OTP_TYPES.email, usage=UserOTP.OTP_Usage.social_user_set_password, otp=otp
    )
    if should_sms_otp:
        UserSms.objects.create(
            user=user,
            tp=UserSms.TYPES.social_user_set_password,
            to=user.mobile,
            text=otp,
            template=UserSms.TEMPLATES.social_user_set_password,
        )
        user.generate_otp_obj(
            tp=User.OTP_TYPES.mobile, usage=UserOTP.OTP_Usage.social_user_set_password, otp=otp,
        )
    return {
        'status': 'ok',
    }


def merge_otp_request(user: User, tp: int):
    last_request = VerifyMergeRequestView.get_merge_request(user)
    is_mobile_otp = tp == UserOTP.OTP_TYPES.mobile and last_request.merge_by == UserMergeRequest.MERGE_BY.mobile
    is_email_otp = tp == UserOTP.OTP_TYPES.email and last_request.merge_by == UserMergeRequest.MERGE_BY.email

    if is_mobile_otp:
        error_response = validate_mobile_otp_limit(user)
        if error_response:
            return error_response

    if is_mobile_otp or is_email_otp:
        MergeHandler.retry_send_otp(last_request)
        return {
            'status': 'ok',
        }
    return {
        'status': 'failed',
    }


def grant_financial_service_otp(request, user: User, service_id: int):
    service_id = parse_int(service_id, required=True)

    error_response = validate_mobile_otp_limit(user)
    if error_response:
        return error_response

    if not user.get_verification_profile().mobile_confirmed:
        raise NobitexAPIError(message='InvalidUsageForUser', description='User has not confirmed mobile.')

    try:
        service = Service.get_available_service(pk=service_id)
    except ServiceNotFoundError:
        raise NobitexAPIError(
            message='ServiceNotFoundError', description='Service not found.', status_code=status.HTTP_404_NOT_FOUND
        )
    except ServiceUnavailableError as e:
        if is_user_agent_android(request=request):
            message = str(e)
            description = e.__class__.__name__
        else:
            message = e.__class__.__name__
            description = str(e)

        raise NobitexAPIError(
            message=message,
            description=description,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    if service.provider == Service.PROVIDERS.azki and is_user_agent_android(request=request, max_version='7.0.3'):
        raise NobitexAPIError(
            message='PleaseUpdateApp', description='Please Update App', status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    try:
        user_limitation = UserFinancialServiceLimit.get_user_service_limit(user, service)
    except ServiceLimitNotSet as e:
        raise NobitexAPIError(
            message='ServiceLimit', description='Service Limitation does not found.', status_code=422
        ) from e

    if user_limitation.max_limit == 0:
        raise NobitexAPIError(
            message='UserLimitation', description='You are limited to activate the service.', status_code=422
        )
    try:
        granted_permission = UserServicePermission.create_or_update_inactive_permission(user, service)
        otp = granted_permission.generate_user_otp(user, service)
        UserSms.objects.create(
            user=user,
            tp=UserSms.TYPES.grant_financial_service,
            to=user.mobile,
            text=service.readable_name + '\n' + otp,
            template=UserSms.TEMPLATES.grant_financial_service,
        )
    except ServiceAlreadyActivated as e:
        raise NobitexAPIError(message='ServiceAlreadyActivated', description=str(e), status_code=422) from e
    else:
        return {'status': 'ok'}


@ratelimit(key='user_or_ip', rate='60/h', block=False)
@ratelimit(key='user_or_ip', rate='2/m', block=False)
@measure_api_execution(api_label='authOTPPrivate')
@api
@ratelimit(key='user', rate='60/h', block=True)
@ratelimit(key='user', rate='2/m', block=True)
def otp_request(request):
    user: User = request.user
    if request.limited:
        return {'status': 'failed', 'code': 'TooManyRequests'}

    usage = request.g('usage')
    if usage == 'social_user_set_password':
        return social_user_set_password_otp_request(user)

    if usage == 'grant-financial-service':
        return grant_financial_service_otp(
            request,
            request.user,
            request.g('serviceId'),
        )

    tp = parse_otp_tp(request.g('type', 'email'), required=True)
    if usage == 'merge':
        return merge_otp_request(request.user, tp)

    if tp == User.OTP_TYPES.email and usage != 'email-verification':
        raise_on_email_not_verified(request.user)

    if tp == User.OTP_TYPES.mobile and UserOTP.objects.filter(
        user=user,
        otp_type=UserOTP.OTP_TYPES.mobile,
        created_at__gt=ir_now() - datetime.timedelta(minutes=2),
        otp_status=UserOTP.OTP_STATUS.new,
    ).exists():
        return {
            'status': 'ok',
        }
    otp = user.generate_otp(tp=tp)
    is_otp_object_generated = False
    if tp == User.OTP_TYPES.email:
        claimed_email = None
        if usage == 'email-verification' and user.email is None:
            claimed_email = cache.get(f'{EMAIL_VERIFICATION_ATTEMPT_PREFIX_CACHE_KEY}:{user.pk}', default=None)
            logstash_logger.info(
                'going to request email otp',
                extra={
                    'params': {
                        'verification_attempt_key': f'{EMAIL_VERIFICATION_ATTEMPT_PREFIX_CACHE_KEY}:{user.pk}',
                        'email': claimed_email
                    },
                    'index_name': 'otp.email',
                },
            )

        user.send_email_otp(usage=usage, claimed_email=claimed_email)  # this already generates an otp object.
        is_otp_object_generated = True
        # Send OTP as a telegram message
        if usage != 'email-verification':
            user.send_telegram_otp(otp)

    elif tp == User.OTP_TYPES.mobile:
        # Rate Limit
        error_response = validate_mobile_otp_limit(user)
        if error_response:
            return error_response

        user_mobile = user.mobile
        sms_template = UserSms.TEMPLATES.welcome
        sms_type = UserSms.TYPES.verify_phone
        if usage == 'address_book':
            sms_template = UserSms.TEMPLATES.verify_new_address
            sms_type = UserSms.TYPES.verify_new_address
        elif usage == 'deactivate_whitelist':
            sms_template = UserSms.TEMPLATES.deactivate_whitelist_mode_otp
            sms_type = UserSms.TYPES.deactivate_whitelist_mode_otp
        else:
            active_change_mobile = ChangeMobileRequest.get_active_request(user)
            if active_change_mobile:
                if active_change_mobile.status == ChangeMobileRequest.STATUS.new_mobile_otp_sent:
                    sms_template = UserSms.TEMPLATES.welcome if not user_mobile else UserSms.TEMPLATES.verification
                    usage = UserOTP.OTP_Usage.welcome_sms if not user_mobile else UserOTP.OTP_Usage.change_phone_number
                    user_mobile = active_change_mobile.new_mobile
                elif active_change_mobile.status == ChangeMobileRequest.STATUS.old_mobile_otp_sent:
                    sms_template = UserSms.TEMPLATES.verification
                    usage = UserOTP.OTP_Usage.change_phone_number
                    user_mobile = active_change_mobile.old_mobile

        UserSms.objects.create(
            user=user,
            tp=sms_type,
            to=user_mobile,
            text=otp,
            template=sms_template,
        )

    elif tp == User.OTP_TYPES.phone:
        # Rate Limit
        limit = 2 if settings.IS_PROD else 10
        if UserVoiceMessage.get_verification_messages(user).exclude(delivery_status='used').count() > limit:
            return {'status': 'failed', 'code': 'TooManyCalls', 'message': 'Too many call requests for this user'}
        phone_number = user.phone
        if not validate_phone(phone_number, code=user.province_phone_code):
            return {'status': 'failed', 'code': 'PhoneValidationError', 'message': 'Invalid phone number'}

        read_single_digits = True
        if read_single_digits:
            otp_digits = ' ، '.join([
                read_number(otp[0]),
                read_number(otp[1]),
                read_number(otp[2]),
                read_number(otp[3]),
            ])
        else:
            otp_digits = ' ، '.join([
                read_number(otp[0:2], zpad=True),
                read_number(otp[2:4], zpad=True),
            ])
        message = 'این تماس به منظور احرازِ هویت جهتِ ثبتنام در سایتِ نوبی تِکس گرفته شده است. به منظورِ جلوگیری از کلاهبرداری و سوء استفاده از حسابِ کاربری، حسابِ خود را در اختیارِ اشخاصِ غیر قرار ندهید و برای دیگران خرید و فروش نکنید. مسئولیتِ استفاده از این حساب به عهده کاربر بوده و بدین وسیله اعلام میدارید که تنها بر اساسِ قوانینِ جمهوری اسلامی از سایتِ نوبی تِکس استفاده خواهید نمود.'
        message += ' کد تایید شما: ' + otp_digits + ' میباشد. تکرار میشود ' + otp_digits
        UserVoiceMessage.objects.create(
            user=user,
            tp=UserVoiceMessage.TYPES.verify_phone,
            to=phone_number,
            text=message,
        )

    else:
        return {
            'status': 'failed',
        }

    if not is_otp_object_generated:
        user.generate_otp_obj(tp=tp, usage=usage, otp=otp)

    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='60/h', block=False)
@ratelimit(key='user_or_ip', rate='3/m', block=False)
@measure_api_execution(api_label='authOTPPublic')
@public_post_api
def otp_request_public(request):
    if request.g('mobile') is not None:
        if is_ratelimited(
            request=request,
            key='post:mobile',
            rate='10/h',
            group=f'mobile_otp_request{request.g("mobile")}',
            increment=True
        ):
            return handle_ratelimit()

        return mobile_otp_request(request, using_cache=True)
    return email_otp_request(request)


def mobile_otp_request(request, using_cache=False):
    mobile = request.g('mobile')
    usage = parse_otp_usage(request.g('usage'), required=True)
    if not validate_request_captcha(request, using_cache=using_cache, check_type=True):
        return Response({
            'status': 'failed',
            'code': 'InvalidCaptcha',
            'message': 'Invalid Captcha Message',
        }, status=400)
    if not validate_mobile(mobile):
        raise NobitexAPIError('InvalidMobile', 'شماره موبایل قابل قبول نیست')
    if not usage == UserOTP.OTP_Usage.welcome_sms:
        raise NobitexAPIError('InvalidUsageValue', 'مقدار usage وارد شده قابل قبول نیست')
    try:
        MobileRegisterHandler.send_mobile_otp(mobile)
    except InvalidUserNameError as e:
        raise NobitexAPIError('InvalidMobile', str(e)) from e
    return {
        'status': 'ok',
    }


@ratelimit(key='header:x-email', rate='5/h', block=True)
def email_otp_request(request):
    email = request.g('email')
    if email != request.headers.get('x-email'):
        return {
            'status': 'failed',
            'message': 'Please use otp/request endpoint',
        }

    # Verify user
    user = User.objects.filter(email=email).first()
    if not user:
        return {
            'status': 'failed',
            'message': 'کاربری با این ایمیل ثبت نشده است',
        }
    user.send_email_otp()
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='3/10m', block=True)
@ratelimit(key='user_or_ip', rate='10/h', block=True)
@measure_api_execution(api_label='authRequestTFA')
@api
@email_required_api
def users_tfa_request(request):
    # TODO: Not allow creating new device if OTP is already enabled for user
    user = request.user

    if not UserLevelManager.is_eligible_to_have_tfa(user):
        return {
            'status': 'failed',
            'code': 'UnverifiedMobile',
            'message': 'You must have a mobile phone and a verified email to enable tfa.',
        }
    device = user.tfa_create_new_device()

    # Send sms confirmation code for user
    # TODO: add tight ratelimit for sent SMS
    sms_confirmation_code = user.generate_otp(tp=User.OTP_TYPES.mobile)
    UserSms.objects.create(
        user=user,
        tp=UserSms.TYPES.tfa_enable,
        to=user.mobile,
        text=sms_confirmation_code,
        template=UserSms.TEMPLATES.tfa_enable,
    )

    return {
        'status': 'ok',
        'device': device,
    }


@ratelimit(key='user_or_ip', rate='10/10m', block=True)
@ratelimit(key='user_or_ip', rate='20/h', block=True)
@measure_api_execution(api_label='authEnableTFA')
@api
def users_tfa_confirm(request):
    user = request.user
    device_id = request.g('device')
    otp = request.g('otp')
    sms_otp = request.g('sms_otp')

    # Check TOTP code
    device = get_object_or_404(TOTPDevice, id=device_id, user=user)
    if not device.verify_token(otp):
        return {
            'status': 'failed',
            'message': 'Invalid OTP',
            'code': 'InvalidOTP',
        }

    # Check SMS code
    if not sms_otp:
        return {
            'status': 'failed',
            'message': 'Missing SMS OTP',
            'code': 'MissingSmsOTP',
        }
    if not user.verify_otp(sms_otp, User.OTP_TYPES.mobile):
        return {
            'status': 'failed',
            'message': 'Invalid SMS OTP',
            'code': 'InvalidSmsOTP',
        }

    user.tfa_confirm_device(device, enable=True)
    transaction.on_commit(lambda: EmailManager.send_enable_tfa_notif(user))
    UserEvent.objects.create(user_id=user.id, action=UserEvent.ACTION_CHOICES.users_tfa_confirm)
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='10/10m', block=True)
@api
def users_tfa_disable(request):
    """ POST /users/tfa/disable
    """
    user = request.user
    otp = request.g('otp')
    if not user.tfa_verify(otp):
        return {
            'status': 'failed',
            'message': 'Invalid OTP',
            'code': 'InvalidOTP',
        }
    # Disable TFA
    UserEvent.objects.create(
        user=user,
        action=UserEvent.ACTION_CHOICES.disable_2fa,
        action_type=2,
    )
    UserSecurityManager.apply_disable_tfa_limitations(user)
    user.tfa_disable()
    return {
        'status': 'ok',
    }
