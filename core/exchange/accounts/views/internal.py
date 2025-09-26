from datetime import timedelta
from uuid import UUID

from django.http import Http404, HttpResponse, JsonResponse
from django_ratelimit.decorators import ratelimit
from rest_framework.exceptions import AuthenticationFailed

from exchange.accounts.exceptions import UserRestrictionRemovalNotAllowed
from exchange.accounts.functions import check_user_otp
from exchange.accounts.models import User, UserOTP, UserRestriction, UserSms
from exchange.accounts.types import InternalUserProfileSchema
from exchange.accounts.user_restrictions import UserRestrictionsDescription
from exchange.base.api import HTTP401, NobitexAPIError, public_api
from exchange.base.api_v2_1 import get_ratelimit_key_from_path, internal_access_api, internal_get_api, internal_post_api
from exchange.base.decorators import measure_api_execution
from exchange.base.internal.authentications import InternalGatewayTokenAuthentication
from exchange.base.internal.services import Services
from exchange.base.parsers import parse_choices, parse_enum, parse_int, parse_str
from exchange.base.serializers import serialize_choices


@internal_access_api
@ratelimit(key='user_or_ip', rate='10000/m', block=True)
@measure_api_execution(api_label='InternalGetUser')
@public_api
def get_user_view(request):
    """This view, accessible only from internal remote addresses, would obtain
    an authorization token and return a user identifier id in response, which enables
    the gateway to inject the user identifier in requests routed to an upstream service.
    """

    try:
        user_token_tuple = InternalGatewayTokenAuthentication().authenticate(request)
    except AuthenticationFailed as ex:
        raise HTTP401 from ex

    if user_token_tuple is None:
        raise HTTP401

    return HttpResponse(
        headers={
            'User-ID': str(user_token_tuple[0].uid),
            'User-Level': serialize_choices(User.USER_TYPES, user_token_tuple[0].user_type),
        },
    )


@measure_api_execution(api_label='InternalGetUserProfile')
@internal_get_api(allowed_services=[Services.ABC])
def internal_user_profile(request, user_id: UUID):
    """API for internal user profile.
    GET /internal/users/<str:uuid>/profile
    """
    user = User.objects.select_related('verification_profile').filter(uid=user_id).first()

    if not user:
        raise Http404('User not found')

    return InternalUserProfileSchema.model_validate(user)


@ratelimit(key=get_ratelimit_key_from_path('user_id'), rate='60/h', block=True)
@ratelimit(key=get_ratelimit_key_from_path('user_id'), rate='2/m', block=True)
@measure_api_execution(api_label='InternalSendOtp')
@internal_post_api(allowed_services=[Services.ABC])
def internal_send_otp(request, user_id: UUID):
    """API for send otp internally.
    POST /internal/users/<str:uuid>/send-otp
    """

    otp_type = parse_choices(UserOTP.OTP_TYPES, request.g('otpType'), required=True)
    otp_usage = parse_choices(UserOTP.OTP_Usage, request.g('otpUsage'), required=True)

    user = User.objects.select_related('verification_profile').filter(uid=user_id).first()
    if not user:
        raise Http404('User not found')

    if otp_type == UserOTP.OTP_TYPES.mobile and not user.verification_profile.mobile_confirmed:
        raise NobitexAPIError(
            status_code=400,
            message='MobileNotConfirmed',
            description='User has not confirmed mobile',
        )

    if otp_type == UserOTP.OTP_TYPES.email and not user.verification_profile.email_confirmed:
        raise NobitexAPIError(
            status_code=400,
            message='EmailNotConfirmed',
            description='User has not confirmed email',
        )

    if otp_type == UserOTP.OTP_TYPES.phone and not user.verification_profile.phone_confirmed:
        raise NobitexAPIError(
            status_code=400,
            message='PhoneNotConfirmed',
            description='User has not confirmed phone',
        )

    otp = UserOTP.get_or_create_otp(user=user, tp=otp_type, usage=otp_usage)

    if otp_type == UserOTP.OTP_TYPES.mobile:
        UserSms.objects.create(
            user=user,
            tp=UserSms.OTP_USAGE_TO_TYPE_TEMPLATE[otp_usage]['tp'],
            to=user.mobile,
            text=otp.code,
            template=UserSms.OTP_USAGE_TO_TYPE_TEMPLATE[otp_usage]['template'],
        )

    return {}


def otp_error_to_camel_case(snake_str):
    components = snake_str.split(' ')
    return components[0] + ''.join(x.title() for x in components[1:])


@ratelimit(key=get_ratelimit_key_from_path('user_id'), rate='30/h', block=True)
@ratelimit(key=get_ratelimit_key_from_path('user_id'), rate='3/m', block=True)
@measure_api_execution(api_label='InternalVerifyOtp')
@internal_post_api(allowed_services=[Services.ABC])
def internal_verify_otp(request, user_id: UUID):
    """API for verify otp internally.
    POST /internal/users/<str:uuid>/verify-otp
    """

    otp_type = parse_choices(UserOTP.OTP_TYPES, request.g('otpType'), required=True)
    otp_usage = parse_choices(UserOTP.OTP_Usage, request.g('otpUsage'), required=True)
    otp_code = parse_str(request.g('otpCode'), required=True, max_length=8)

    user = User.objects.filter(uid=user_id).first()
    if not user:
        raise Http404('User not found')

    otp_obj, error = UserOTP.verify(
        code=otp_code,
        user=user,
        tp=otp_type,
        usage=otp_usage,
    )
    if not otp_obj:
        raise NobitexAPIError(
            status_code=400,
            message=otp_error_to_camel_case(error),
            description='OTP does not verified: ' + str(error),
        )

    otp_obj.mark_as_used()
    return {}


@ratelimit(key=get_ratelimit_key_from_path('user_id'), rate='30/h', block=True)
@ratelimit(key=get_ratelimit_key_from_path('user_id'), rate='3/m', block=True)
@measure_api_execution(api_label='InternalVerifyTotp')
@internal_post_api(allowed_services=[Services.ABC])
def internal_verify_totp(request, user_id: UUID):
    """API for verify totp internally.
    POST /internal/users/<str:uuid>/verify-totp
    """

    totp = parse_str(request.g('totp'), required=True, max_length=8)

    user = User.objects.filter(uid=user_id).first()
    if not user:
        raise NobitexAPIError(
            status_code=404,
            message='notFound',
            description='User not found',
        )

    result = check_user_otp(totp, user)
    if not result:
        raise NobitexAPIError(status_code=422, message='wrongTotp', description='TOTP is wrong')
    return {}


@measure_api_execution(api_label='InternalAddRestriction')
@internal_post_api(allowed_services=[Services.ABC])
def internal_add_restriction(request, user_id: UUID):
    """API for add restriction internally.
    POST /internal/users/<str:uuid>/add-restriction
    """

    restriction = parse_choices(UserRestriction.RESTRICTION, request.g('restriction'), required=True)
    considerations = parse_str(request.g('considerations'))
    description = parse_enum(UserRestrictionsDescription, request.g('description'))
    duration_hours = parse_int(request.g('durationHours'))
    ref_id = parse_int(request.g('refId'), required=True)

    duration = None
    if duration_hours is not None:
        duration = timedelta(hours=duration_hours)

    user = User.objects.filter(uid=user_id).first()
    if not user:
        raise Http404('User not found')

    UserRestriction.add_restriction(
        user=user,
        restriction=restriction,
        considerations=considerations,
        duration=duration,
        description=description,
        source=request.service,
        ref_id=ref_id,
    )
    return {}


@measure_api_execution(api_label='InternalRemoveRestriction')
@internal_post_api(allowed_services=[Services.ABC])
def internal_remove_restriction(request, user_id: UUID):
    """API for remove restriction internally.
    POST /internal/users/<str:uuid>/remove-restriction
    """

    user = User.objects.filter(uid=user_id).first()
    restriction = parse_choices(UserRestriction.RESTRICTION, request.g('restriction'), required=True)
    ref_id = parse_int(request.g('refId'), required=True)

    if not user:
        raise Http404('User not found')

    restriction = (
        UserRestriction.objects.filter(user=user, restriction=restriction, source=request.service, ref_id=ref_id)
        .order_by('-created_at')
        .first()
    )
    if not restriction:
        return {}
    try:
        restriction.delete_with_removals(source=request.service)
    except UserRestrictionRemovalNotAllowed:
        raise NobitexAPIError(
            status_code=403,
            message='RestrictionRemovalFailed',
            description='This service can not remove this restriction',
        )

    return {}
