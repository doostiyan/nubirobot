""" API views for login and registration """
import datetime
import random
import time
from typing import Callable

import jwt
import requests
from dj_rest_auth.registration.views import RegisterView as RestRegisterView
from dj_rest_auth.registration.views import VerifyEmailView as RestVerifyEmailView
from dj_rest_auth.utils import jwt_encode
from dj_rest_auth.views import LoginView as RestLoginView
from dj_rest_auth.views import LogoutView as RestLogoutView
from dj_rest_auth.views import UserDetailsView as RestUserDetailsView
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect, JsonResponse, QueryDict
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_ratelimit.decorators import ratelimit
from google.auth.exceptions import InvalidValue
from google.auth.transport import requests as grequests
from google.oauth2 import id_token
from rest_framework import status
from rest_framework.authtoken.models import Token as DRFToken
from rest_framework.response import Response
from rest_framework.views import APIView

from exchange.accounts.captcha import UnacceptableCaptchaTypeError
from exchange.accounts.exceptions import (
    EmailRegistrationDisabled,
    IncompleteRegisterError,
    InvalidUserNameError,
    PasswordRecoveryError,
)
from exchange.accounts.functions import check_user_otp, config_user_in_test_net, find_username, validate_request_captcha
from exchange.accounts.models import (
    AppToken,
    EmailActivation,
    PasswordRecovery,
    User,
    UserEvent,
    UserOTP,
    UserReferral,
    UserRestriction,
)
from exchange.accounts.notifications import send_change_password_notification, send_set_password_notification
from exchange.accounts.register_handlers import BaseRegisterHandler, EmailRegisterHandler, get_register_handler
from exchange.accounts.user_restrictions import UserRestrictionsDescription
from exchange.accounts.ws import generate_connection_token
from exchange.base.api import api, post_api, public_post_api
from exchange.base.decorators import measure_api_execution
from exchange.base.helpers import build_frontend_url, is_from_unsupported_app, paginate, parse_request_channel
from exchange.base.http import get_client_country, get_client_ip, is_client_iranian
from exchange.base.logging import log_event, metric_incr, report_exception
from exchange.base.models import Settings
from exchange.base.normalizers import normalize_name
from exchange.base.validators import validate_email, validate_mobile
from exchange.fcm.models import FCMDevice
from exchange.marketing.models import UTMParameter
from exchange.security.models import KnownDevice, LoginAttempt
from exchange.security.usersecurity import UserSecurityManager
from exchange.tokens.auth import create_token, get_user_token_ttl
from exchange.web_engage.events import EmailVerifiedWebEngageEvent, SignUpWebEngageEvent
from exchange.web_engage.events.user_attribute_verified_events import SignUpAndVerifiedWebEngageEvent
from exchange.web_engage.services.user import send_user_data_to_webengage


class LoginView(RestLoginView):
    def validate_user(self, request):
        self.user = None
        self.request = request
        self.serializer = self.get_serializer(data=self.request.data,  context={'request': self.request})
        try:
            self.serializer.is_valid(raise_exception=True)
            self.user = self.serializer.validated_data['user']
            return
        except Exception as e:
            # Log login problem
            log_event(
                f'Login exception "{e}"',
                level='warning',
                module='general',
                category='notice',
                runner='api',
            )

    @method_decorator(ratelimit(key='user_or_ip', rate='30/10m', block=True))
    @method_decorator(measure_api_execution(api_label='authLogin'))
    def post(self, request, *args, **kwargs):
        time.sleep(0.1)
        device_id = request.data.get('device')
        remember_me = request.data.get('remember') == 'yes'
        otp = request.headers.get('x-totp')
        if not otp or otp in ['-', '0', '000000']:
            otp = None

        # Log Attempt
        submitted_username = (request.data.get('username') or '')[:100]
        self.attempt = LoginAttempt(
            username=submitted_username,
        )
        self.attempt.fill_data_from_request(request)

        # Check Android app version
        if self.attempt.is_unsupported_app:
            return Response({'non_field_errors': ['Please Update App'], 'code': 'PleaseUpdateApp'}, status=422)

        # Check Captcha
        country = get_client_country(request)
        is_iran = country == 'IR'
        captcha = request.data.get('captcha')
        captcha_type = request.data.get('captchaType', request.data.get('client', 'web'))
        special_captcha = captcha in ['ip', 'app', 'api']
        captcha_provided = captcha and not special_captcha
        captcha_required = not otp

        # Special cases for not requiring captcha
        if settings.DISABLE_RECAPTCHA:
            captcha_required = False
        elif special_captcha:
            ua = self.attempt.user_agent
            is_allowed = ua.startswith('TraderBot/')
            if self.attempt.ip in ['195.201.230.189']:
                is_allowed = True
            if is_allowed:
                captcha_required = False

        # Metric labels
        captcha_tp = captcha_type if captcha_provided else 'none'
        metric_labels = '{}_{}_{}_{}_{}'.format(
            captcha_tp,
            0 if country == 'XX' else (2 if is_iran else 1),
            1 if otp else 0,
            1 if remember_me else 0,
            1 if device_id else 0,
        )

        # Check login feature status
        login_feature_status = Settings.get_value('feature_login', default='enabled')
        if login_feature_status == 'disabled':
            return Response({
                'code': 'LoginDisabled',
                'non_field_errors': ['Login Unavailable, Try Again Later'],
            }, status=400)
        if login_feature_status == 'iran-only':
            if not is_iran:
                metric_incr(f'metric_login__badIP_{metric_labels}')
                return Response({
                    'code': 'LoginIranOnly',
                    'non_field_errors': ['Login is currently restricted to Iranian IPs'],
                }, status=400)

        # Login blacklist checks
        is_blacklisted = False
        login_ip_blacklist = Settings.get_value('feature_login_ip_blacklist', default='')
        for blacklist_item in login_ip_blacklist.split(','):
            blacklist_item = blacklist_item.strip()
            if len(blacklist_item) == 2:
                if country == blacklist_item:
                    is_blacklisted = True
            elif len(blacklist_item) >= 6:
                if (self.attempt.ip or '').startswith(blacklist_item):
                    is_blacklisted = True
        if is_blacklisted:
            metric_incr(f'metric_login__badIP_{metric_labels}')
            return Response({
                'code': 'LoginIranOnly',
                'non_field_errors': ['Login is currently restricted to Iranian IPs'],
            }, status=400)

        # Check captcha is present
        if not captcha_provided and captcha_required:
            metric_incr(f'metric_captcha__{captcha_tp}_missing')
            if special_captcha:
                return Response({'non_field_errors': ['OTP not provided'], 'code': 'MissingOTP'}, status=400)
            return Response({'non_field_errors': ['Missing Captcha'], 'code': 'MissingCaptcha'}, status=400)
        # Validate captcha
        if captcha_provided:
            try:
                is_captcha_valid = validate_request_captcha(request, check_type=True)
            except UnacceptableCaptchaTypeError as e:
                metric_incr('metric_captcha__invalid_unacceptable')
                return Response({
                    'code': 'CaptchaTypeUnacceptable',
                    'non_field_errors': ['Please use another captcha type'],
                    'acceptableTypes': e.acceptable_types,
                }, status=400)
            if not is_captcha_valid:
                metric_incr(f'metric_captcha__{captcha_tp}_bad')
                return Response({'non_field_errors': ['Invalid Captcha'], 'code': 'InvalidCaptcha'}, status=400)
            metric_incr(f'metric_captcha__{captcha_tp}_ok')
        else:
            metric_incr(f'metric_captcha__{captcha_tp}_skip')

        # Validate Credentials
        username, err = find_username(submitted_username)
        if username != submitted_username:
            if isinstance(request.data, QueryDict):
                request.data._mutable = True
                request.data['username'] = username
                request.data._mutable = False
            else:
                request.data['username'] = username
        if err is not None and not settings.IS_TESTNET:
            if validate_mobile(username):
                existing_user = User.objects.filter(mobile=username).first()
            else:
                existing_user = User.objects.filter(email=username).first()
            err = 'badPass' if existing_user else 'badUser'
            metric_incr(f'metric_login__{err}_{metric_labels}')
            self.attempt.user = existing_user
            self.attempt.save()
            return Response({'non_field_errors': ['Unable to log in with provided credentials.']}, status=403)

        self.validate_user(request)
        if not self.user:
            if validate_mobile(username):
                existing_user = User.objects.filter(mobile=username).first()
            else:
                existing_user = User.objects.filter(email=username).first()
            err = 'badPass' if existing_user else 'badUser'
            metric_incr(f'metric_login__{err}_{metric_labels}')
            self.attempt.user = existing_user
            self.attempt.save()
            return Response({'non_field_errors': ['Unable to log in with provided credentials.']}, status=403)

        # Check 2fa
        #   based on: https://django-otp-official.readthedocs.io/en/latest/auth.html
        if self.user.requires_2fa:
            if not otp:
                return Response({'non_field_errors': ['OTP not provided'], 'code': 'MissingOTP'}, status=400)
            if not check_user_otp(otp, self.user):
                self.attempt.user = self.user
                self.attempt.save()
                metric_incr(f'metric_login__badOTP_{metric_labels}')
                return Response({'non_field_errors': ['Invalid OTP'], 'code': 'InvalidOTP'}, status=400)
        elif otp:
            return Response({'non_field_errors': ['Unable to log in with provided credentials.']}, status=403)

        self.attempt.user = self.user

        # Check for user restrictions
        if not is_client_iranian(request) and self.user.is_restricted('IranAccessLogin'):
            metric_incr(f'metric_login__restrictedIP_{metric_labels}')
            message = 'Your account is currently restricted to Iranian IPs'
            self.attempt.save()
            return Response({
                'status': 'failed',
                'code': 'ActionIsRestricted',
                'message': message,
                'non_field_errors': [message],
            }, status=400)

        # We have multiple auth backends, so specifying backend is required
        #  This occurs in cases where we manually set the user and not explicitly
        #  set its backend.
        if not getattr(self.user, 'backend', None):
            self.user.backend = settings.AUTHENTICATION_BACKENDS[-1]
        # Login Successful: do process django login
        metric_incr(f'metric_login__ok_{metric_labels}')
        self.login()
        if remember_me:
            # Create an AppToken if remember_me is set!!
            try:
                app_token = AppToken.objects.get(token=self.token)
            except AppToken.DoesNotExist:
                app_token = AppToken(token=self.token)
            app_token.user_agent = self.attempt.user_agent
            app_token.last_use = datetime.date.today()
            app_token.save()

            # Extend token cache lifetime
            self.user.remembered_login = True

        # Login is successful
        self.attempt.is_successful = True

        # Check if login is from a known device
        known_device, is_device_new = KnownDevice.get_or_create(self.attempt, device_id=device_id)

        # Log login attempt
        self.attempt.device = known_device
        self.attempt.is_known = not is_device_new
        self.attempt.save()

        if 'login' not in Settings.get_list('webengage_stopped_events'):
            transaction.on_commit(lambda: send_user_data_to_webengage(self.user))

        # Return login token
        return JsonResponse(
            {
                'status': 'success',
                'key': self.token.key,
                'expiresIn': get_user_token_ttl(self.user),
                'device': known_device.device_id,
                'we_id': self.user.get_webengage_id(),
            },
            status=200,
        )


class CheckedLoginView(LoginView):
    pass


@ratelimit(key='user_or_ip', rate='60/h', block=True)
@measure_api_execution(api_label='authSocialLogin')
@public_post_api
def google_social_login(request):
    """Google Social Login

    POST /auth/google/
    """
    device_id = request.data.get('device')
    remember_me = request.g('remember') == 'yes'
    token = request.g('token')
    if not token:
        metric_incr('metric_login_social', labels=('google', 'invalid', '-'))
        return {
            'status': 'failed',
            'message': 'No Google authentication token provided',
            'code': 'MissingSocialToken',
        }
    attempt = LoginAttempt()
    attempt.fill_data_from_request(request)

    # Check Android app version
    if attempt.is_unsupported_app:
        metric_incr('metric_login_social', labels=('google', 'outdated', '-'))
        return Response({'non_field_errors': ['Please Update App'], 'code': 'PleaseUpdateApp'}, status=422)

    # Verify signed data from Google
    try:
        session = requests.Session()
        session.proxies = settings.SANCTIONED_APIS_PROXY

        try:
            idinfo = id_token.verify_oauth2_token(token, grequests.Request(session=session))
        except InvalidValue as e:
            # TODO we recently encountered this error: "Token used too early" and the time difference is one second.
            # This is a temporary solution to avoid this error .
            time.sleep(1.1)
            idinfo = id_token.verify_oauth2_token(token, grequests.Request(session=session))

        # Verify token response
        if idinfo['aud'] not in settings.GOOGLE_CLIENT_IDS:
            raise ValueError('Could not verify audience')
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer')
        if not idinfo['email_verified']:
            raise ValueError('Email not verified')
        # Extract verified info
        user_email = idinfo['email'].lower().strip()
        user_first_name = normalize_name(idinfo.get('given_name')) or ''
        user_last_name = normalize_name(idinfo.get('family_name')) or ''
    except requests.exceptions.RequestException as ex:
        metric_incr('metric_login_social', labels=('google', 'failed', ex.__class__.__name__))
        return {
            'status': 'failed',
            'message': 'Social login token verification request failed.',
            'code': 'SocialLoginFailed',
        }
    except (ValueError, KeyError) as ex:
        metric_incr('metric_login_social', labels=('google', 'failed', ex.__class__.__name__))
        return {
            'status': 'failed',
            'message': 'Social login token verification failed',
            'code': 'SocialLoginFailed',
        }

    # Check fetched data
    if len(user_email) > 150:
        metric_incr('metric_login_social', labels=('google', 'invalid', '-'))
        return {
            'status': 'failed',
            'message': 'Maximum email length is 150 characters.',
            'code': 'EmailTooLong',
        }

    # Get or create corresponding user
    try:
        user = User.objects.get(email=user_email)
    except User.DoesNotExist:
        user = User.objects.create(
            username=user_email,
            email=user_email,
            password='!google',
            first_name=user_first_name[:30],
            last_name=user_last_name[:150],
            social_login_enabled=True,
        )
        config_user_in_test_net(user)
        transaction.on_commit(lambda: SignUpWebEngageEvent(with_mobile=False,
                              user=user, device_kind=parse_request_channel(request=request)).send())
    if not user.is_active:
        log_event(
            message='Login exception: user is not active', level='info',
            module='authentication', category='notice', runner='api'
        )
        return Response({'non_field_errors': ['Unable to log in with provided credentials.']}, status=403)
    if not user.is_email_verified:
        user.do_verify_email()
        transaction.on_commit(lambda: EmailVerifiedWebEngageEvent(
            user=user, device_kind=parse_request_channel(request=request)).send())

        transaction.on_commit(lambda: SignUpAndVerifiedWebEngageEvent(
            with_mobile=False,
            user=user,
            device_kind=parse_request_channel(request=request)).send())

    # Check if user can use social email
    if settings.IS_PROD and not user.social_login_enabled:
        metric_incr('metric_login_social', labels=('google', 'disabled', '-'))
        return {
            'status': 'failed',
            'message': 'Social login is disabled for this user',
            'code': 'SocialLoginDisabled',
        }
    if user.requires_2fa:
        otp = request.headers.get('x-totp')
        if not otp:
            return Response({'non_field_errors': ['OTP not provided'], 'code': 'MissingOTP', 'status': 'failed'}, status=400)
        if not check_user_otp(otp, user):
            metric_incr('metric_login_social', labels=('google', 'badOTP', '-'))
            return Response({'non_field_errors': ['Invalid OTP'], 'code': 'InvalidOTP', 'status': 'failed'}, status=400)

    # Log login attempt
    attempt.user = user
    attempt.username = user_email
    known_device, is_device_new = KnownDevice.get_or_create(attempt, device_id=device_id)
    attempt.device = known_device
    attempt.is_known = not is_device_new
    attempt.user_agent += ' (Google Login)'

    # Check for user restrictions
    if not is_client_iranian(request) and user.is_restricted('IranAccessLogin'):
        metric_incr('metric_login_social__google_restrictedIP')
        message = 'Your account is currently restricted to Iranian IPs'
        attempt.save()
        return Response({
            'status': 'failed',
            'code': 'ActionIsRestricted',
            'message': message,
            'non_field_errors': [message],
        }, status=400)

    attempt.is_successful = True
    attempt.save()

    # Issue internal token for user
    user.remembered_login = remember_me
    token = create_token(user)
    if remember_me:
        AppToken.objects.update_or_create(
            token=token, defaults={'user_agent': attempt.user_agent, 'last_use': now()}
        )

    if 'login' not in Settings.get_list('webengage_stopped_events'):
        transaction.on_commit(lambda: send_user_data_to_webengage(user))

    metric_incr('metric_login_social', labels=('google', 'ok', '-'))
    return {
        'status': 'ok',
        'key': token.key,
        'device': known_device.device_id,
    }


class LogoutView(RestLogoutView):

    def _fcm_deactive_device(self, request) -> None:
        """ Set FCMDevice.is_active for logout user is False """
        user = request.user
        ua = request.headers.get('user-agent') or 'unknown'
        if ua.startswith('Android/'):
            device_type = FCMDevice.DEVICE_TYPES.android
        elif ua.startswith('iOSApp/'):
            device_type = FCMDevice.DEVICE_TYPES.ios
        else:
            return
        devices = FCMDevice.objects.filter(user=user, device_type=device_type, is_active=True)
        if devices.count() == 1:
            devices.update(is_active=False)

    def logout(self, request):
        # deactive device for fcm
        self._fcm_deactive_device(request)
        response = super().logout(request)
        response.data['message'] = response.data['detail']
        return response


class UserDetailsView(RestUserDetailsView):
    http_method_names = ['get']


class RegisterView(RestRegisterView):

    def get_serializer_class(self):
        return self.register_handler.get_serializer_class()

    @method_decorator(ratelimit(key='user_or_ip', rate='20/h', block=True))
    @method_decorator(measure_api_execution(api_label='authRegister'))
    def create(self, request, *args, **kwargs):
        time.sleep(0.1)
        # Check Captcha
        using_cache_for_captcha_validation = validate_mobile(request.data.get('username') or '')
        if not validate_request_captcha(request, using_cache=using_cache_for_captcha_validation):
            return Response({'non_field_errors': ['کپچا به درستی تایید نشده']}, status=400)

        try:
            self.register_handler: BaseRegisterHandler = get_register_handler(request.data)
            self.register_handler.validate_request_data()
        except InvalidUserNameError as e:
            return Response({'username': [str(e)]}, status=400)
        except IncompleteRegisterError as _:
            return Response({
                'status': 'failed',
                'code': 'IncompleteRegisterError',
                'message': 'کد تایید را ارسال کنید.',
            }, status=200)
        except EmailRegistrationDisabled as _:
            return Response({
                'status': 'failed',
                'code': 'EmailRegistrationDisabled',
                'message': 'Email registration is disabled',
            }, status=418)
        except Exception as e:
            report_exception()
            return Response({}, status=400)

        # Create user by calling base class
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        user = serializer.save(self.request)
        if getattr(settings, 'REST_USE_JWT', False):
            self.token = jwt_encode(user)
        else:
            create_token(user)

        # Referral Program
        referrer_code = self.request.data.get('referrerCode')
        channel = self.request.data.get('channel')
        if referrer_code:
            UserReferral.set_user_referrer(user, referrer_code, channel=channel)

        # UTM
        utm_source = self.request.data.get('utmSource')
        utm_medium = self.request.data.get('utmMedium')
        utm_campaign = self.request.data.get('utmCampaign')
        utm_term = self.request.data.get('utmTerm')
        utm_content = self.request.data.get('utmContent')
        utm_id = self.request.data.get('utmId')
        UTMParameter.set_user_utm_parameters(user, utm_source, utm_medium, utm_campaign, utm_term, utm_content, utm_id)

        self.run_post_create_actions(user)
        return user

    def run_post_create_actions(self, user):
        """Run actions that should be done for each user after signup.

        Note: There is also an on_create signal for users, but this method
        is for actions that are only relevant when a user explicitly registers.
        """
        self.register_handler.run_post_create_actions(user, self.request)
        # Set registration channel
        registration_channel = parse_request_channel(self.request)
        if registration_channel:
            user.set_profile_property('regCh', registration_channel)
        # Set metrics
        registration_tp = self.register_handler.HANDLER_NAME
        metric_incr(f'metric_signup__{registration_tp}_{registration_channel}_ok')
        # todo if a new sign up method is added in the future, these events will not work
        with_mobile = False if registration_tp == EmailRegisterHandler.HANDLER_NAME else True
        transaction.on_commit(lambda: SignUpWebEngageEvent(with_mobile=with_mobile,
                              user=user, device_kind=registration_channel).send())

        if with_mobile:
            transaction.on_commit(lambda: SignUpAndVerifiedWebEngageEvent(
                with_mobile=True,
                user=user,
                device_kind=registration_channel).send())

        if 'register' not in Settings.get_list('webengage_stopped_events'):
            transaction.on_commit(lambda: send_user_data_to_webengage(user=user))

        # Testnet Onboarding
        config_user_in_test_net(user)

    def _add_login_attempt_and_known_device(self, user) -> str:
        """
            This function add a login data attempted and KnowDevice in the system.
        """
        attempt = LoginAttempt()
        attempt.user = user
        attempt.fill_data_from_request(self.request)
        # Login is successful
        attempt.is_successful = True

        known_device, is_device_new = KnownDevice.get_or_create(attempt)
        # Log login attempt
        attempt.device = known_device
        attempt.is_known = not is_device_new
        attempt.save()
        return known_device.device_id

    def get_response_data(self, user):
        response = super().get_response_data(user)
        response['expiresIn'] = get_user_token_ttl(user)
        response['device'] = self._add_login_attempt_and_known_device(user)
        response['we_id'] = user.get_webengage_id()
        response['status'] = 'ok'
        return response


class VerifyEmailView(RestVerifyEmailView):
    pass


def set_new_password(
    new_password: str, new_password_confirm: str, user: User, *,
    post_conditions_callback: Callable[[], None] = None,
):
    """Set password for user through different APIs.
    It does not matter whether you are setting the very first password of user or changing a former one.

    Args:
        new_password (str): new password for user.
        new_password_confirm (str): confirmation of the new password for user. Must be equal to ``new_password``
        user (User): the user to have a new password.
        post_conditions_callback (Callable[[], None]): a callback (handler) that gets executed if the password is set,
        INSIDE the transaction.

    """
    if new_password != new_password_confirm:
        return {
            'status': 'failed',
            'code': 'InvalidPasswordConfirm',
            'message': 'msgInvalidPasswordConfirm',
        }
    try:
        validate_password(new_password, user=user)
    except ValidationError as e:
        return {
            'status': 'failed',
            'code': 'UnacceptablePassword',
            'message': ','.join([str(err) for err in e]),
        }
    except:
        report_exception()
        return {
            'status': 'failed',
            'code': 'UnacceptablePassword',
            'message': 'msgUnacceptablePassword',
        }
    with transaction.atomic():
        user.set_password(new_password)
        user.save(update_fields=['password', ])
        token = DRFToken.objects.filter(user=user).first()
        if token is not None:
            token.delete()

        if post_conditions_callback:
            post_conditions_callback()

    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='10/10m', block=True)
@api
def change_password(request):
    time.sleep(0.1)
    current_password = request.g('currentPassword')
    new_password = request.g('newPassword')
    new_password_confirm = request.g('newPasswordConfirm')
    user = request.user
    if not user.check_password(current_password):
        return {
            'status': 'failed',
            'code': 'InvalidPassword',
            'message': 'msgInvalidPassword',
        }

    def callback():
        UserRestriction.add_restriction(
            user=user,
            restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin,
            considerations='ایجاد محدودیت 24 ساعته برداشت رمز ارز بعلت تغییر رمز عبور',
            duration=datetime.timedelta(hours=24),
            description=UserRestrictionsDescription.CHANGE_PASSWORD,
        )
        ip = get_client_ip(request)
        device_id = request.data.get('device')
        transaction.on_commit(lambda: send_change_password_notification(user, {
            'ip': ip,
            'device_id': device_id,
        }))

    return set_new_password(
        new_password, new_password_confirm, user,
        post_conditions_callback=callback
    )


@ratelimit(key='user_or_ip', rate='10/d', block=True)
@post_api
def set_password_for_social_users(request):
    time.sleep(1)
    new_password = request.g('newPassword')
    new_password_confirm = request.g('newPasswordConfirm')
    otp = request.g('otp')
    user: User = request.user
    if not user.can_social_login_user_set_password:
        return {
            'status': 'failed',
            'code': 'canNotSetPassword',
            'message': 'You do not have the access to set password!',
        }
    email_otp_object, email_otp_err = UserOTP.verify(
        code=otp, tp=UserOTP.OTP_TYPES.email, usage=UserOTP.OTP_Usage.social_user_set_password, user=user,
    )
    mobile_otp_object, mobile_otp_err = UserOTP.verify(
        code=otp, tp=UserOTP.OTP_TYPES.mobile, usage=UserOTP.OTP_Usage.social_user_set_password, user=user,
    )
    if not (email_otp_object or mobile_otp_object):
        return {
            'status': 'failed',
            'code': 'InvalidOTP',
            'message': email_otp_err or mobile_otp_err,
        }

    def callback():
        email_otp_object.mark_as_used()
        if mobile_otp_object:
            mobile_otp_object.mark_as_used()
        transaction.on_commit(lambda: send_set_password_notification(user=user))

    return set_new_password(
        new_password, new_password_confirm, user,
        post_conditions_callback=callback,
    )


@ratelimit(key='user_or_ip', rate='5/h', block=False)
@ratelimit(key='user_or_ip', rate='1/m', block=False)
@measure_api_execution(api_label='authForgotPassword')
@public_post_api
def forget_password(request):
    if is_from_unsupported_app(request, 'forget_password'):
        return Response({'status': 'failed', 'code': 'PleaseUpdateApp', 'message': 'Please Update App'}, status=422)
    time.sleep(1)
    if request.limited:
        return {'status': 'failed', 'message': 'تعداد درخواست شما بیش از حد معمول تشخیص داده شده. لطفا یک ساعت صبر نمایید.', 'code': 'TooManyRequests'}
    if not validate_request_captcha(request, check_type=True):
        return {'status': 'failed', 'message': 'کپچا به درستی تایید نشده'}

    domain = request.g('domain') or request.headers.get('origin')
    if Settings.get_flag('mobile_forget_password'):
        username  = request.g('email') or request.g('mobile')
    else:
        username  = request.g('email')
        if not validate_email(username):
            return {'status': 'failed', 'message': 'مقدار وارد شده صحیح نیست.'}

    try:
        recovery = PasswordRecovery.get_or_create(username)
    except InvalidUserNameError as e:
        time.sleep(random.randint(0, 500) / 1000)
        return {
            'status': 'ok',
        }
    except:
        report_exception()
        return {'status': 'failed', 'message': ''}
    recovery.send(username, domain)
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='30/h', block=False)
@measure_api_execution(api_label='authForgotPasswordCommit')
@public_post_api
def forget_password_commit(request):
    time.sleep(1)
    if request.limited:
        return {
            'status': 'failed',
            'message': 'تعداد درخواست شما بیش از حد معمول تشخیص داده شده. لطفا یک ساعت صبر نمایید.',
            'code': 'TooManyRequests'
        }
    if not validate_request_captcha(request, check_type=True):
        return {'status': 'failed', 'message': 'کپچا به درستی تایید نشده'}
    token = request.g('token')
    if Settings.get_flag('mobile_forget_password'):
        username  = request.g('email') or request.g('mobile')
    else:
        username  = request.g('email')
        if not validate_email(username):
            return {'status': 'failed', 'message': 'مقدار وارد شده صحیح نیست.'}

    password = request.g('password1')
    password2 = request.g('password2')
    if not token or not username:
        return {'status': 'failed', 'non_field_errors': ['اطلاعات کامل وارد نشده'] }
    if not password or password != password2:
        return {'status': 'failed', 'non_field_errors': ['گذرواژه و تکرار آن را به درستی وارد نمایید.'] }

    try:
        recovery = PasswordRecovery.get(username, token)
    except (
        InvalidUserNameError,
        PasswordRecoveryError,
    ) as e:
        return {'status': 'failed', 'message': str(e)}
    except:
        report_exception()
        return {'status': 'failed', 'message': ''}

    user = recovery.user
    try:
        validate_password(password, user)
    except ValidationError as e:
        return {'status': 'failed', 'non_field_errors': [str(err) for err in e] }
    except:
        report_exception()
        return {'status': 'failed', 'non_field_errors': ['گذرواژه قابل قبول نیست. لطفا گذرواژه بهتری انتخاب نمایید.'] }

    with transaction.atomic():
        user.set_password(password)
        user.save(update_fields=['password'])
        token = DRFToken.objects.filter(user=user).first()
        if token is not None:
            token.delete()
        recovery.status = PasswordRecovery.STATUS.confirmed
        recovery.save(update_fields=['status'])

        UserRestriction.add_restriction(
            user=user,
            restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin,
            considerations='ایجاد محدودیت 24 ساعته برداشت رمز ارز بعلت بازیابی رمز عبور',
            duration=datetime.timedelta(hours=24),
            description=UserRestrictionsDescription.RECOVERY_PASSWORD,
        )

        ip = get_client_ip(request)
        device_id = request.data.get('device')
        transaction.on_commit(lambda: send_change_password_notification(user, {
            'ip': ip,
            'device_id': device_id,
        }))

    return {
        'status': 'ok',
    }


@api
def users_login_attempts(request):
    """List of recent user logins, both successful and unsuccessful.

    POST /users/login-attempts
    """
    attempts = LoginAttempt.objects.filter(user=request.user).order_by('-created_at')
    attempts = paginate(attempts, page_size=15, request=request, max_page=100, max_page_size=100)
    return {
        'status': 'ok',
        'attempts': attempts,
    }


@ratelimit(key='user_or_ip', rate='30/h', block=True)
def email_activation_redirect(request):
    """Confirm user email address when an email activation link is clicked.

    GET /users/email-activation-redirect?token=…

    # TODO: Confirm email only with POST and show a form for GET requests

    Metrics: signup_email_confirm_link__{status}
    """
    token = request.GET.get('token')
    frontend_url = build_frontend_url(request, '/')
    try:
        activation = EmailActivation.objects.get(token=token)
    except ValidationError:
        metric_incr('metric_signup_email_confirm_link__invalid')
        return render(request, 'email_confirm_failure.html', {
            'url': frontend_url,
            'message': 'قالب آدرسی که روی آن کلیک کردید، نامعتبر است.',
        })
    except EmailActivation.DoesNotExist:
        metric_incr('metric_signup_email_confirm_link__notFound')
        return render(request, 'email_confirm_failure.html', {
            'url': frontend_url,
            'message': 'آدرسی که روی آن کلیک کردید، نامعتبر است.',
        })
    # Check if token is already used
    if activation.status != EmailActivation.STATUS.new:
        if activation.status == EmailActivation.STATUS.used:
            err = 'used'
            message = 'ایمیل شما قبلاً فعال شده است، می‌توانید هم‌اکنون از حساب خود استفاده نمایید.'
        elif activation.status == EmailActivation.STATUS.expired:
            err = 'expired'
            message = 'آدرسی که روی آن کلیک کردید منقضی شده است. لطفاً دوباره درخواست تایید خود را ارسال نمایید.'
        else:
            err = 'unknown'
            message = 'وضعیت آدرسی که روی آن کلیک کردید، نامعتبر است.'
        metric_incr(f'metric_signup_email_confirm_link__{err}')
        return render(request, 'email_confirm_failure.html', {
            'url': frontend_url,
            'message': message,
        })
    # Verify user's email
    activation.user.do_verify_email()
    activation.status = EmailActivation.STATUS.used
    activation.save(update_fields=['status'])
    metric_incr('metric_signup_email_confirm_link__ok')
    EmailVerifiedWebEngageEvent(
        user=activation.user,
        device_kind=parse_request_channel(request=request),
    ).send()
    if activation.user.mobile:
        SignUpAndVerifiedWebEngageEvent(
            with_mobile=False,
            user=activation.user,
            device_kind=parse_request_channel(request=request)).send()

    # Redirect user to login page on successful confirmation
    # TODO: Also show a message to user after redirect in front/app panel
    return HttpResponseRedirect(build_frontend_url(request, '/login/'))


class RemoveTFARequest(APIView):
    permission_classes = []

    @staticmethod
    def authenticate(request):
        """ authenticate user credentials
        """

        username = request.data.get('username')
        password = request.data.get('password')
        try:
            user = User.by_email_or_mobile(username)
        except InvalidUserNameError:
            return False, None

        if not user.check_password(password):
            return False, None

        return True, user

    @method_decorator(ratelimit(key='user_or_ip', rate='10/m', method='POST', block=True))
    @method_decorator(measure_api_execution(api_label='authRemoveTFARequest'))
    def post(self, request):
        """Send OTP for removing TFA."""
        # validate captcha
        if not validate_request_captcha(request):
            return Response({
                'status': 'failed',
                'code': 'InvalidCaptcha',
                'message': _('InvalidCaptchaMessage'),
            }, status=400)

        # authenticate user
        authenticated, user = self.authenticate(request)
        if not authenticated:
            return Response({'status': 'failed', 'code': 'AuthenticationFailed'}, status=status.HTTP_403_FORBIDDEN)

        if not user.requires_2fa:
            return Response({'status': 'failed', 'code': 'RedundantOTP', 'message': _('RedundantOTPMessage')},
                            status=status.HTTP_400_BAD_REQUEST)

        # send email and mobile codes
        mobile_otp = user.generate_otp_obj(tp=UserOTP.OTP_TYPES.mobile, usage=UserOTP.OTP_Usage.tfa_removal)
        mobile_otp.send()
        email_otp = user.generate_otp_obj(tp=UserOTP.OTP_TYPES.email, usage=UserOTP.OTP_Usage.tfa_removal)
        email_otp.send()

        return Response({'status': 'ok', 'data': {'username': user.username}})


class RemoveTFAConfirm(APIView):
    permission_classes = []

    @method_decorator(ratelimit(key='user_or_ip', rate='10/10m', block=True))
    @method_decorator(measure_api_execution(api_label='authRemoveTFAConfirm'))
    def post(self, request, username):
        """Remove TFA for user."""
        # Validate captcha
        if not validate_request_captcha(request):
            return Response({
                'status': 'failed',
                'code': 'InvalidCaptcha',
                'message': _('InvalidCaptchaMessage'),
            }, status=400)

        try:
            user = User.by_email_or_mobile(username)
        except InvalidUserNameError:
            user = None
        mobile_code = request.data.get('mobile_code')
        email_code = request.data.get('email_code')

        if not (user and mobile_code and email_code):
            return Response({
                    'status': 'failed',
                    'code': 'InadequateData',
                    'message': 'اطلاعات ورودی نادرست هستند.'
                }, status=400)

        # Check mobile and provided email codes
        mobile_otp, mobile_error = UserOTP.verify(
            user=user, code=mobile_code, tp=UserOTP.OTP_TYPES.mobile, usage=UserOTP.OTP_Usage.tfa_removal
        )
        email_otp, email_error = UserOTP.verify(
            user=user, code=email_code, tp=UserOTP.OTP_TYPES.email, usage=UserOTP.OTP_Usage.tfa_removal
        )
        if mobile_error or email_error:
            return Response({
                'status': 'failed',
                'message': 'کدهای وارد شده اشتباه هستند.',
                'code': 'OTPValidationFailed',
                'data': {'detail': [mobile_error] or [email_error]}
            }, status=400)

        # Mark OTPs as used
        mobile_otp.otp_status = UserOTP.OTP_STATUS.used
        mobile_otp.save()
        email_otp.otp_status = UserOTP.OTP_STATUS.used
        email_otp.save()

        # Disable TFA
        UserEvent.objects.create(
            user=user,
            action=UserEvent.ACTION_CHOICES.disable_2fa,
            action_type=3,
        )
        UserSecurityManager.apply_disable_tfa_limitations(user)
        user.tfa_disable()
        return Response({
            'status': 'ok',
        })


class WebsocketAuth(APIView):
    def get(self, request):
        token = generate_connection_token(user_uid=request.user.uid)
        return Response(
            {
                'token': token,
                'status': 'ok',
            },
            status=status.HTTP_200_OK,
        )


dummy_translations = [
    _('Successfully logged out.'),
]
