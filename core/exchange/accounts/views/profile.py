""" API views for user profile and settings """
import datetime
import json
import os
import re
import uuid
from decimal import Decimal

import magic
from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from django_ratelimit.decorators import Ratelimited, is_ratelimited, ratelimit

from exchange.accounts.constants import PROVINCES
from exchange.accounts.exceptions import IncompatibleUserLevelError, SameUserError
from exchange.accounts.forms import UploadFileForm
from exchange.accounts.functions import get_options_v1, get_options_v2, validate_request_captcha
from exchange.accounts.merge.merge_manager import MergeManager
from exchange.accounts.models import (
    BankAccount,
    BankCard,
    ChangeMobileRequest,
    Tag,
    UpgradeLevel3Request,
    UploadedFile,
    User,
    UserEvent,
    UserMergeRequest,
    UserOTP,
    UserPlan,
    UserPreference,
    UserRestriction,
    UserSms,
    UserVoiceMessage,
    VerificationRequest,
)
from exchange.accounts.parsers import (
    parse_account_id,
    parse_bank_id,
    parse_files,
    parse_gender,
    parse_telegram_chat_id,
    parse_verification_tp,
)
from exchange.accounts.serializers import serialize_change_mobile_status
from exchange.accounts.tasks import task_convert_iban_to_account_number
from exchange.accounts.user_levels_rejection_results import get_rejection_reasons
from exchange.accounts.userlevels import UserLevelManager
from exchange.accounts.userstats import UserStatsManager
from exchange.accounts.views.auth import check_user_otp
from exchange.asset_backed_credit.models import UserService
from exchange.base.api import (
    NobitexAPIError,
    SemanticAPIError,
    api,
    get_data,
    is_request_from_unsupported_app,
    post_api,
    public_get_and_post_api,
    public_post_api,
)
from exchange.base.calendar import get_earliest_time, ir_now, ir_today, parse_shamsi_date
from exchange.base.coins_info_old import CURRENCY_INFO
from exchange.base.crypto import random_string
from exchange.base.decorators import measure_api_execution
from exchange.base.helpers import is_from_unsupported_app, parse_request_channel
from exchange.base.logging import log_numerical_metric_avg, report_event
from exchange.base.logstash_logging.loggers import logstash_logger
from exchange.base.models import (
    ACTIVE_CURRENCIES,
    AMOUNT_PRECISIONS,
    CURRENCY_CODENAMES,
    MARKET_TESTING_CURRENCIES,
    PRICE_PRECISIONS,
    XCHANGE_ACTIVE_CURRENCIES,
    XCHANGE_TESTING_CURRENCIES,
    Currencies,
    Settings,
)
from exchange.base.normalizers import normalize_email, normalize_mobile, normalize_name, normalize_phone
from exchange.base.parsers import parse_bool, parse_int
from exchange.base.serializers import serialize, serialize_choices, serialize_dict_key_choices
from exchange.base.validators import (
    validate_email,
    validate_mobile,
    validate_name,
    validate_national_code,
    validate_phone,
    validate_postal_code,
)
from exchange.direct_debit.constants import DEFAULT_MIN_DEPOSIT_AMOUNT
from exchange.fcm.models import FCMDevice
from exchange.notification.switches import NotificationConfig
from exchange.web_engage.events import MobileVerifiedWebEngageEvent, TelephoneVerifiedWebEngageEvent
from exchange.web_engage.services.user import send_user_data_to_webengage

EMAIL_VERIFICATION_ATTEMPT_PREFIX_CACHE_KEY = 'email_verification_attempt'

@ratelimit(key='user_or_ip', rate='60/m', block=True)
@public_get_and_post_api
def v2_options(request):
    """System Options
       GET /v2/options
    """
    options = settings.NOBITEX_OPTIONS
    coins_info = cache.get('options_coins')
    if not coins_info:
        coins_info = list(get_options_v2(new_version=True).values())
        cache.set('options_coins', coins_info, 30)
    active_currencies = [CURRENCY_CODENAMES[c].lower() for c in ACTIVE_CURRENCIES]
    xchange_currencies = [CURRENCY_CODENAMES[c].lower() for c in XCHANGE_ACTIVE_CURRENCIES]
    testing_currencies = [CURRENCY_CODENAMES[c].lower() for c in MARKET_TESTING_CURRENCIES]
    xchange_testing_currencies = [CURRENCY_CODENAMES[c].lower() for c in XCHANGE_TESTING_CURRENCIES]

    opts = {'merge': True}
    deposit_limits = serialize_dict_key_choices(User.USER_TYPES, options['depositLimits'], opts)
    deposit_limits_with_identified_mobile = serialize_dict_key_choices(
        User.USER_TYPES, options['depositLimitsWithIdentifiedMobile'], opts
    )
    withdraw_limits = serialize_dict_key_choices(User.USER_TYPES, options['withdrawLimits'], opts)
    withdraw_limits_with_identified_mobile = serialize_dict_key_choices(
        User.USER_TYPES, options['withdrawLimitsWithIdentifiedMobile'], opts
    )
    min_orders = serialize_dict_key_choices(Currencies, options['minOrders'], opts)
    options['features']['autoKYC'] = Settings.is_feature_active(Settings.FEATURE_AUTO_KYC)
    options['features']['smsNotRequiredForRialWithdraw'] = Settings.get_flag('remove_rial_otp')

    return {
        'status': 'ok',
        'features': options.get('features', {}),
        'coins': coins_info,
        'nobitex': {
            'allCurrencies': active_currencies,  # This is not ALL_CURRENCIES because Xchange is not launched yet
            'activeCurrencies': active_currencies,
            'xchangeCurrencies': xchange_currencies,
            'topCurrencies': ['btc', 'eth', 'usdt', 'doge', 'shib', 'trx', 'ada', 'ltc', 'xrp'],
            'testingCurrencies': testing_currencies,
            'xchangeTestingCurrencies': xchange_testing_currencies,
            'withdrawLimits': withdraw_limits,
            'withdrawLimitsWithIdentifiedMobile': withdraw_limits_with_identified_mobile,
            'depositLimitsWithIdentifiedMobile': deposit_limits_with_identified_mobile,
            'depositLimits': deposit_limits,
            'minOrders': min_orders,
            'amountPrecisions': AMOUNT_PRECISIONS,
            'pricePrecisions': PRICE_PRECISIONS,
            'giftCard': {'physicalFee': settings.GIFT_CARD_PHYSICAL_FEE},
            'JibitPIP': {'feeRate': settings.JIBIT_PIP_FEE_RATE},
            'vandarDepositId': {
                'feeRate': settings.VANDAR_DEPOSIT_FEE_RATE,
                'maxFee': settings.VANDAR_DEPOSIT_FEE_MAX,
            },
            'tradingFees': options['tradingFees'],
            'shetabFee': {
                'min': settings.NOBITEX_OPTIONS['shetabFee']['min'],
                'max': settings.NOBITEX_OPTIONS['shetabFee']['max'],
                'rate': settings.NOBITEX_OPTIONS['shetabFee']['rate'],
            },
            'directDebitFee': settings.NOBITEX_OPTIONS['directDebitFee'],
            'coBankFee': settings.NOBITEX_OPTIONS['coBankFee'],
            'coBankLimits': settings.NOBITEX_OPTIONS['coBankLimits'],
            'directDebitMinDeposit': Decimal(
                Settings.get_value('direct_debit_min_amount_in_deposit', DEFAULT_MIN_DEPOSIT_AMOUNT)
            ),
            'userLevelNames': settings.NOBITEX_OPTIONS['userTypes'],
            'rialDepositGatewayLimit': settings.NOBITEX_OPTIONS['rialDepositGatewayLimit'],
            'rialWithdrawConfigs': {
                'maxRialWithdrawal': Decimal(
                    Settings.get_value(
                        'max_rial_withdrawal',
                        CURRENCY_INFO[Currencies.rls]['network_list']['FIAT_MONEY']['withdraw_max'],
                    )
                ),
                'minRialWithdrawal': Decimal(
                    CURRENCY_INFO[Currencies.rls]['network_list']['FIAT_MONEY']['withdraw_min']
                ),
            },
        },
    }


@api
def users_preferences(request):
    preferences = UserPreference.get_user_preferences(request.user)

    # Options
    options = cache.get('options_v1')
    if not options:
        options = get_options_v1()
        cache.set('options_v1', options)

    # Options Version 2
    options_v2 = cache.get('options_v2')
    if not options_v2:
        options_v2 = get_options_v2(new_version=True)
        cache.set('options_v2', options_v2)

    # Response
    return {
        'status': 'ok',
        'options': options,
        'optionsV2': options_v2,
        'preferences': preferences,
    }


@api
def users_set_preference(request):
    """Set user preferences, used for many purposes that can be categorized as
        setting a user-specific preference/option/flag/value.
        POST /users/set-preference
    """
    user = request.user
    preference = request.g('preference')
    value = request.g('value')
    if not preference or preference.startswith('system_') or value is None:
        return {
            'status': 'failed',
            'code': 'InvalidUserPreference',
            'message': f'Given value "{preference}" for user preference "{value}" is invalid',
        }

    # Handle special preference cases, or just set a UserPreference
    pref = {}
    if preference == 'fcm-deviceid':
        ua = request.headers.get('user-agent') or 'unknown'
        if ua.startswith('Android/'):
            device_type = FCMDevice.DEVICE_TYPES.android
        elif ua.startswith('iOSApp/'):
            device_type = FCMDevice.DEVICE_TYPES.ios
        else:
            device_type = FCMDevice.DEVICE_TYPES.web
        FCMDevice.set_user_token(user, device_type, value)
    elif preference == 'beta':
        user.set_beta_status(parse_bool(value))
    else:
        pref = UserPreference.set(user, preference, value)
    return {
        'status': 'ok',
        'preference': pref,
    }


@api
def users_profile(request):
    """API for user profile.
    POST /users/profile
    """
    from exchange.market.marketmanager import MarketManager

    # Force old apps to log out
    if is_request_from_unsupported_app(request):
        return JsonResponse({'detail': 'توکن غیر مجاز'}, status=401)

    return {
        'status': 'ok',
        'profile': serialize(request.user, {'level': 2}),
        'tradeStats': MarketManager.get_latest_user_stats(request.user),
        'we_id': request.user.get_webengage_id(),
    }


@ratelimit(key='user_or_ip', rate='30/h', block=True)
@ratelimit(key='user_or_ip', rate='10/m', block=True)
@measure_api_execution(api_label='profileEditUserProfile')
@post_api
@ratelimit(key='user_or_ip', rate='30/h', block=True)
@ratelimit(key='user_or_ip', rate='10/m', block=True)
def users_profile_edit(request):
    """Edit user profile.
        POST /users/profile-edit
    """
    user: User = User.objects.select_for_update(no_key=True).get(id=request.user.id)
    vprofile = user.get_verification_profile()
    is_user_level2 = user.user_type >= User.USER_TYPES.level2
    is_identity_confirmed = vprofile.identity_confirmed
    is_email_confirmed = vprofile.email_confirmed
    update_fields = []
    update_vprofile = False

    otp = request.headers.get('x-totp')
    request_data, _ = get_data(request)

    if Settings.is_feature_active('kyc2'):
        mobile_and_email_not_confirmed = not (vprofile.mobile_confirmed or is_email_confirmed)
        not_edit_email = not (request_data.get('email') and len(request_data) == 1)
        not_edit_mobile = not (request_data.get('mobile') and len(request_data) == 1)
        if mobile_and_email_not_confirmed and not_edit_email and not_edit_mobile:
            return {
                'status': 'failed',
                'code': 'UserLevelRestriction',
                'message': 'Email and Mobile are not confirmed',
            }
    elif not is_email_confirmed and not (request_data.get('email') and len(request_data) == 1):
        return {
            'status': 'failed',
            'code': 'UserLevelRestriction',
            'message': 'Email is not confirmed',
        }
    # Prevent profile edit for users without confirmed email or mobile
    if user.user_type < User.USER_TYPES.level0:
        return {
            'status': 'failed',
            'code': 'UserLevelRestriction',
            'message': 'Email or Mobile is not confirmed',
        }

    # Identity
    first_name = request.g('firstName')
    if first_name and first_name != user.first_name:
        if is_user_level2 or is_identity_confirmed:
            return {
                'status': 'failed',
                'code': 'UserLevelRestriction',
                'message': 'FirstNameUneditable',
            }
        first_name = normalize_name(first_name)
        if not validate_name(first_name):
            return {
                'status': 'failed',
                'code': 'ValidationError',
                'message': 'Firstname validation failed',
            }
        user.first_name = first_name
        vprofile.identity_confirmed = False
        update_vprofile = True
        update_fields.append('first_name')
    last_name = request.g('lastName')
    if last_name and last_name != user.last_name:
        if is_user_level2 or is_identity_confirmed:
            return {
                'status': 'failed',
                'code': 'UserLevelRestriction',
                'message': 'LastNameUneditable',
            }
        last_name = normalize_name(last_name)
        if not validate_name(last_name):
            return {
                'status': 'failed',
                'code': 'ValidationError',
                'message': 'Lastname validation failed',
            }
        user.last_name = last_name
        vprofile.identity_confirmed = False
        update_vprofile = True
        update_fields.append('last_name')
    national_code = request.g('nationalCode')
    if national_code and national_code != user.national_code:
        if is_user_level2 or is_identity_confirmed:
            return {
                'status': 'failed',
                'code': 'UserLevelRestriction',
                'message': 'NationalCodeUneditable',
            }
        if not validate_national_code(national_code):
            return {
                'status': 'failed',
                'code': 'ValidationError',
                'message': 'NationalCodeValidationFailed',
            }
        if not User.validate_national_code(user, national_code):
            return {
                'status': 'failed',
                'code': 'ValidationError',
                'message': 'NationalCodeAlreadyRegistered',
            }
        user.national_code = national_code
        vprofile.identity_confirmed = False
        update_vprofile = True
        update_fields.append('national_code')

    # Mobile
    change_mobile_request_obj = None
    mobile = request.g('mobile') or ''
    mobile = normalize_mobile(mobile)
    if mobile and mobile != user.mobile:
        if is_ratelimited(
            request=request,
            key='user_or_ip',
            rate='5/h',
            group='exchange.accounts.views.profile.users_profile_edit',
            increment=True,
        ) or is_ratelimited(
            request=request,
            key='user_or_ip',
            rate='10/d',
            group='exchange.accounts.views.profile.users_profile_edit',
            increment=True,
        ):
            raise Ratelimited

        if is_from_unsupported_app(request, 'change_mobile'):
            raise NobitexAPIError(
                message='PleaseUpdateApp',
                description='Please Update App',
                status_code=400,
            )

        if not validate_request_captcha(request, check_type=True):
            raise NobitexAPIError(
                message='کپچا به درستی تایید نشده',
                status_code=400,
            )

        if not UserLevelManager.is_eligible_to_change_mobile(user):
            return {
                'status': 'failed',
                'code': 'UserLevelRestriction',
                'message': 'MobileUneditable',
            }

        if not validate_mobile(mobile, strict=True):
            return {
                'status': 'failed',
                'code': 'ValidationError',
                'message': 'Mobile validation failed',
            }

        if UserMergeRequest.get_active_merge_requests(users=[user], merge_by=UserMergeRequest.MERGE_BY.mobile).exists():
            return {
                'status': 'failed',
                'code': 'HasActiveMergeRequestError',
                'message': 'User has active merge request.',
            }

        # TODO: remove if condition after decoupling abc
        if not Settings.get_flag('abc_use_restriction_internal_api') and UserService.has_user_active_tara_service(user):
            return {
                'status': 'failed',
                'code': 'UserHasActiveTaraService',
                'message': 'User has active tara service.',
            }

        if user.is_restricted(UserRestriction.RESTRICTION.ChangeMobile):
            return {
                'status': 'failed',
                'code': 'MobileChangeRestricted',
                'message': 'Mobile change is restricted for user.',
            }

        if not User.validate_mobile_number(user, mobile):
            second_account = User.objects.filter(mobile=mobile).first()
            can_merge = True
            try:
                MergeManager(user, second_account).check_user_conditions()
            except (SameUserError, IncompatibleUserLevelError):
                can_merge = False
            if can_merge:
                return {
                    'status': 'failed',
                    'code': 'ValidationError',
                    'message': 'MobileAlreadyRegistered',
                    'canMerge': True,
                }
            else:
                return {
                    'status': 'failed',
                    'code': 'ValidationError',
                    'message': 'NotOwnedByUser',
                }
        # Verify otp
        # TODO: remove if condition (keep body) after feature released by clients
        if Settings.get('tfa_for_change_mobile', default='disabled') == 'enabled':
            is_2fa_enabled = user.requires_2fa
            if is_2fa_enabled and not check_user_otp(otp, user):
                return {
                    'status': 'failed',
                    'code': 'Invalid2FA',
                    'message': 'msgInvalid2FA',
                }

        # check identity new mobile - Use Shahkar API
        if (settings.IS_PROD or user.is_user_considered_in_production_test) and user.national_code:
            result, error = user.check_mobile_identity(mobile=mobile)
            if not result:
                ChangeMobileRequest.log(
                    user,
                    UserEvent.EDIT_MOBILE_ACTION_TYPES.fail_identity,
                    description=f'NewMobile:{mobile} Error:"{error}"',
                )
                return {
                    'status': 'failed',
                    'code': 'ValidationError',
                    'message': error,
                }
        status = ChangeMobileRequest.STATUS.new if user.mobile else ChangeMobileRequest.STATUS.old_mobile_otp_sent
        change_mobile_request_obj = ChangeMobileRequest.create(user=user, new_mobile=mobile, status=status)
        result, error = change_mobile_request_obj.send_otp()
        if not result:
            return {
                'status': 'failed',
                'code': 'SendOTPFail',
                'message': error,
            }

    # Email
    email = request.g('email') or ''
    email = normalize_email(email)
    change_email_requested = False

    if not email or (email == user.email):
        pass
    elif is_email_confirmed:
        return {
            'status': 'failed',
            'code': 'UserLevelRestriction',
            'message': 'EmailUneditable',
        }
    elif not is_email_confirmed:
        if UserMergeRequest.get_active_merge_requests(users=[user], merge_by=UserMergeRequest.MERGE_BY.email).exists():
            return {
                'status': 'failed',
                'code': 'HasActiveMergeRequestError',
                'message': 'User has active merge request.',
            }
        if len(request_data) > 1:
            return {
                'status': 'failed',
                'code': 'ValidationError',
                'message': 'Email is not editable with other parameters.',
            }
        if not validate_email(email):
            return {
                'status': 'failed',
                'code': 'ValidationError',
                'message': 'EmailValidationFailed',
            }

        second_account = User.objects.filter(email=email).first()
        if second_account:
            can_merge = True
            try:
                MergeManager(user, second_account).check_user_conditions()
            except (SameUserError, IncompatibleUserLevelError):
                can_merge = False

            return {
                'status': 'failed',
                'code': 'ValidationError',
                'message': 'EmailAlreadyRegistered',
                'canMerge': can_merge,
            }

        user.otp = None
        UserOTP.active_otps(user=user, tp=UserOTP.OTP_TYPES.email).update(otp_status=UserOTP.OTP_STATUS.disabled)
        vprofile.email_confirmed = False
        update_vprofile = True
        cache.set(f'{EMAIL_VERIFICATION_ATTEMPT_PREFIX_CACHE_KEY}:{user.pk}', email, timeout=30 * 60)
        logstash_logger.info(
            'email change request accepted.',
            extra={
                'params': {
                    'verification_attempt_key': f'{EMAIL_VERIFICATION_ATTEMPT_PREFIX_CACHE_KEY}:{user.pk}',
                    'email': email
                },
                'index_name': 'profile.email_change_request',
            },
        )
        change_email_requested = True
        update_fields += ['otp']

    # City & Address
    province = request.g('province')
    if province and province != user.province:
        if is_user_level2:
            return {
                'status': 'failed',
                'code': 'UserLevelRestriction',
                'message': 'ProvinceUneditable',
            }
        if province not in PROVINCES:
            return {
                'status': 'failed',
                'code': 'ValidationError',
                'message': 'Province is not valid',
            }
        user.province = province
        update_fields.append('province')
    city = request.g('city')
    if city and city != user.city:
        if is_user_level2:
            return {
                'status': 'failed',
                'code': 'UserLevelRestriction',
                'message': 'CityUneditable',
            }
        user.city = city
        update_fields.append('city')
    address = request.g('address')
    if address and address != user.address:
        if is_user_level2:
            return {
                'status': 'failed',
                'code': 'UserLevelRestriction',
                'message': 'AddressUneditable',
            }
        user.address = address
        update_fields.append('address')

    # Phone
    phone = request.g('phone') or ''
    phone = normalize_phone(phone)
    if phone and phone != user.phone:
        if is_user_level2:
            return {
                'status': 'failed',
                'code': 'UserLevelRestriction',
                'message': 'PhoneUneditable',
            }
        if not validate_phone(phone, code=user.province_phone_code):
            return {
                'status': 'failed',
                'code': 'PhoneValidationError',
                'message': 'Invalid phone number',
            }
        user.phone = phone
        user.otp = None
        UserOTP.active_otps(user=user, tp=UserOTP.OTP_TYPES.phone).update(otp_status=UserOTP.OTP_STATUS.disabled)
        update_fields += ['phone', 'otp']

    # Postal Code
    postal_code = request.g('postalCode')
    if postal_code and postal_code != user.postal_code:
        if is_user_level2:
            return {
                'status': 'failed',
                'code': 'UserLevelRestriction',
                'message': 'PostalCodeUneditable',
            }
        if not validate_postal_code(postal_code):
            return {
                'status': 'failed',
                'code': 'PostalCodeValidationError',
                'message': 'Postal code validation failed',
            }
        user.postal_code = postal_code
        update_fields.append('postal_code')

    # Nickname
    nickname = request.g('nickname') or ''
    nickname = nickname.strip()
    if nickname and nickname != user.nickname:
        if len(nickname) < 4:
            return {
                'status': 'failed',
                'code': 'ValidationError',
                'message': 'Nickname is too short',
            }
        # Uniqueness check is soft which is intended, as it is not critical
        if User.objects.filter(nickname=nickname).exists():
            return {
                'status': 'failed',
                'code': 'ValidationError',
                'message': 'Nickname already registered',
            }
        user.nickname = nickname
        update_fields.append('nickname')

    # Social Login
    social_login_enabled = parse_bool(request.g('socialLoginEnabled'))
    if social_login_enabled is not None:
        if social_login_enabled is False and not user.has_usable_password():
            return {
                'status': 'failed',
                'code': 'UserAccountDoesNotHavePassword',
                'message': 'UserAccount does not have password.',
            }
        if user.social_login_enabled != social_login_enabled:
            user.social_login_enabled = social_login_enabled
            update_fields.append('social_login_enabled')

    # Gender
    gender = parse_gender(request.g('gender'))
    if gender and gender != user.gender and gender != User.GENDER.unknown:
        user.gender = gender
        update_fields.append('gender')

    # Birthday
    try:
        birthday = parse_shamsi_date(request.g('birthday'))
    except ValueError:
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'Birthday validation failed',
        }
    if birthday:
        birthday = birthday.date()
        if birthday != user.birthday:
            # Only allow 18 years old users
            user_days_old = (ir_today() - birthday).days
            if user_days_old < 18 * 365:
                return {
                    'status': 'failed',
                    'code': 'ValidationError',
                    'message': 'Minimum Age is 18',
                }
            # Update birthday
            user.birthday = birthday
            update_fields.append('birthday')

    # Testing Track
    track = parse_int(request.g('track'))
    if track is not None and track != user.track and 0 <= track <= 32767:
        user.track = track
        update_fields.append('track')

    if Settings.is_feature_active("kyc2") and bool(user.address) and bool(user.city):
        vprofile.address_confirmed = True
        update_vprofile = True

    # Save
    if update_fields:
        if update_vprofile:
            vprofile.save()
        user.save(update_fields=update_fields)

    if change_email_requested:
        user.send_email_otp('email-verification', claimed_email=email)

    if 'edit_profile' not in Settings.get_list('webengage_stopped_events'):
        transaction.on_commit(lambda: send_user_data_to_webengage(user))

    response = {
        'status': 'ok',
        'updates': len(update_fields) + int(change_email_requested),
    }
    if change_mobile_request_obj:
        response['change_mobile_status'] = serialize_change_mobile_status(change_mobile_request_obj)
    return response


@ratelimit(key='user_or_ip', rate='30/30m', block=True)
@measure_api_execution(api_label='profileAddBankCard')
@api
def users_cards_add(request):
    user = request.user
    number = request.g('number')
    bank_name = request.g('bank')

    # User must have completed previous verification steps first
    if not UserLevelManager.is_eligible_to_add_bank_info(user):
        return {
            'status': 'failed',
            'code': 'UserLevelRestriction',
            'message': 'Identity is not complete',
        }

    # Handle bank name
    # TODO: Detect bank automatically
    if not bank_name:
        bank_name = 'سایر'
    bank_name = bank_name[:20]

    old_card = BankCard.objects.filter(card_number=number, user=user, is_deleted=False).exists()
    if old_card:
        return {
            'status': 'failed',
            'code': 'DuplicatedCard',
            'message': 'Duplicated Card',
        }
    card = BankCard(
        user=user,
        card_number=number,
        bank_name=bank_name,
        owner_name=user.get_full_name(),
    )

    if not card.is_valid():
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'Validation Failed',
        }

    card.save()
    card.update_api_verification()
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='30/30m', block=True)
@measure_api_execution(api_label='profileAddBankAccount')
@api
def users_accounts_add(request):
    user = request.user
    shaba = request.g('shaba')
    account = request.g('number')
    if shaba and shaba.startswith('IRIR'):
        shaba = shaba[2:]

    # User must have completed previous verification steps first
    if not UserLevelManager.is_eligible_to_add_bank_info(user):
        return {
            'status': 'failed',
            'code': 'UserLevelRestriction',
            'message': 'Identity is not complete',
        }

    old_account = BankAccount.objects.filter(shaba_number=shaba, user=user, is_deleted=False).exists()
    if old_account:
        return {
            'status': 'failed',
            'code': 'DuplicatedShaba',
            'message': 'Duplicated Shaba',
        }
    account = BankAccount(
        user=user,
        account_number=account or '0',
        shaba_number=shaba,
        bank_name='سایر',
        owner_name=user.get_full_name(),
    )

    if not account.is_valid():
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'Validation Failed',
        }

    account.save()
    account.update_api_verification()

    if account.confirmed and account.account_number in ['0', '', None]:
        transaction.on_commit(lambda: task_convert_iban_to_account_number.apply_async((account.id,), expires=60 * 60))

    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='30/30m', block=True)
@measure_api_execution(api_label='profileAddPaymentAccount')
@api
def users_payment_accounts_add(request):
    user = request.user
    account = parse_account_id(request.g('account'), required=True)
    bank_id = parse_bank_id(request.g('service'), required=True)

    if not UserLevelManager.is_eligible_to_add_bank_info(user):
        raise NobitexAPIError('UserLevelRestriction', 'Identity is not complete')

    if bank_id == BankAccount.BANK_ID.vandar and UserPreference.get(user, 'system_enable_vandar_deposit') != 'true':
        raise NobitexAPIError('PaymentUnavailable', 'Vandar deposit is not enabled')

    old_account = BankAccount.objects.filter(bank_id=bank_id, account_number=account, user=user, is_deleted=False)
    if old_account.exists():
        raise NobitexAPIError('DuplicateAccount', 'Duplicate Account')

    account = BankAccount(
        user=user,
        account_number=account,
        bank_id=bank_id,
        owner_name=user.get_full_name(),
        shaba_number=BankAccount.generate_fake_shaba(bank_id, account_id=account),
    )
    account.update_bank_name()

    if not account.virtual or not account.is_valid():
        raise NobitexAPIError('ValidationError', 'Validation Failed')

    account.save()
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='30/30m', block=True)
@measure_api_execution(api_label='profileDeleteBankAccount')
@api
def users_accounts_delete(request):
    account = BankAccount.objects.filter(
        pk=request.g('id'), user=request.user, is_deleted=False, is_temporary=False
    ).first()
    if not account:
        return {
            'status': 'failed',
            'code': 'InvalidBankAccountID',
            'message': 'Invalid Bank Account ID',
        }
    account.soft_delete()
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='30/30m', block=True)
@measure_api_execution(api_label='profileDeleteBankCard')
@api
def users_cards_delete(request):
    account = BankCard.objects.filter(
        pk=request.g('id'), user=request.user, is_deleted=False, is_temporary=False
    ).first()
    if not account:
        return {
            'status': 'failed',
            'code': 'InvalidBankCardID',
            'message': 'Invalid Bank Card ID',
        }
    account.soft_delete()
    return {
        'status': 'ok',
    }


def verify_ratelimit(group, request):
    """ Ratelimit checker for profile verification. Used for increasing ratelimit for testnet.
    """
    return '5/h' if settings.IS_PROD else '30/h'


@ratelimit(key='user_or_ip', rate=verify_ratelimit, block=True)
@measure_api_execution(api_label='kycVerify')
@api
def users_verify(request):
    user = request.user
    explanations = request.g('explanations') or ''
    tp = parse_verification_tp(request.g('tp'), required=True)
    documents = parse_files(request.g('documents'))
    identity_types_level2 = [VerificationRequest.TYPES.auto_kyc, VerificationRequest.TYPES.selfie]

    # Check for any user restrictions
    has_no_level2_tag = Tag.objects.filter(users=user, name='عدم ارتقاء سطح ۲').exists()
    if has_no_level2_tag:
        return {
            'status': 'failed',
            'code': 'VerificationRestricted',
            'message': 'User is restricted.',
        }
    if user.user_type >= User.USER_TYPES.level2:
        return {
            'status': 'failed',
            'code': 'VerificationRestricted',
            'message': 'User is verified!',
        }

    # check eligibility of user to be level2
    if user.user_type < User.USER_TYPES.level2 and tp in identity_types_level2:
        vp = user.get_verification_profile()
        is_mobile_identity_confirmed = Settings.is_feature_active('kyc2') or vp.mobile_identity_confirmed
        is_eligible_upgrade_level2 = (
            vp.is_verified_level1 and is_mobile_identity_confirmed and user.is_address_confirmed()
        )
        if not is_eligible_upgrade_level2:
            return {
                'status': 'failed',
                'code': 'VerificationDenied',
                'message': 'مراحل قبل تکمیل نیست',
            }

    # check attachments count and file format
    # selfie
    if tp == VerificationRequest.TYPES.selfie:
        if not documents:
            return JsonResponse({
                'status': 'failed',
                'code': 'AttachmentNotFound',
                'message': 'تصویر هویت الزامی است.',
            }, status=400)

        doc_format = magic.from_file(documents[0].disk_path, mime=True)
        if doc_format not in ['image/jpeg', 'image/png', 'image/bmp', 'image/webp']:
            JsonResponse({
                'status': 'failed',
                'code': 'UnacceptableAttachments',
                'message': 'فرمت تصویر هویتی قابل قبول نمی‌باشد.',
            }, status=400)
    # auto_kyc
    elif tp == VerificationRequest.TYPES.auto_kyc:
        doc_types = [doc.tp for doc in documents]
        # Avoiding cases where we have two files, but one of types 3 or 4 are missing. We need at least types 3 and 4
        if len(documents) < 2 or not all(tp in doc_types for tp in UploadedFile.AUTO_KYC_ACTIVE_TYPES):
            return JsonResponse({
                'status': 'failed',
                'code': 'UnacceptableAttachments',
                'message': 'فایل های ارسالی کامل نمی باشد.',
            }, status=400)
        error_message = ''
        for doc in documents:
            doc_format = magic.from_file(doc.disk_path, mime=True)
            acceptable_formats = UploadedFile.AUTO_KYC_ACCEPTABLE_FILE_FORMATS[doc.tp]
            if doc.tp == UploadedFile.TYPES.kyc_main_image and doc_format not in acceptable_formats:
                error_message = 'فرمت عکس سلفی قابل قبول نمی‌باشد.'
            elif doc.tp == UploadedFile.TYPES.kyc_image and doc_format not in acceptable_formats:
                error_message = 'فرمت تصویر زنده قابل قبول نمی‌باشد.'
            if error_message:
                return JsonResponse({
                    'status': 'failed',
                    'code': 'UnacceptableAttachments',
                    'message': error_message,
                }, status=400)

    # check for existing same active request
    verification_type_list = identity_types_level2 if tp in identity_types_level2 else [tp]
    old_verification_request = (
        VerificationRequest.objects.filter(
            user=user,
            status__in=[VerificationRequest.STATUS.new, VerificationRequest.STATUS.confirmed],
            tp__in=verification_type_list,
        )
        .order_by('-created_at')
        .first()
    )
    if old_verification_request:
        error_message = 'درخواست {} وجود دارد.'.format(
            'فعال' if old_verification_request.status == VerificationRequest.STATUS.new else 'تایید شده',
        )
        return JsonResponse(
            {
                'status': 'failed',
                'code': 'VerificationRequestFail',
                'message': error_message,
            },
            status=409,
        )

    # Create verification request
    req = VerificationRequest(
        user=user,
        tp=tp,
        explanations=explanations,
        device=parse_request_channel(request=request),
    )
    req.save()
    for doc in documents:
        req.documents.add(doc)
    req.update_api_verification()
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='5/h', block=True)
@measure_api_execution(api_label='kycVerifyEmail')
@api
def users_verify_email(request):
    otp = request.g('otp')
    user = User.objects.select_for_update(no_key=True).get(id=request.user.id)
    is_valid = user.verify_otp(otp, tp=User.OTP_TYPES.email)
    logstash_logger.info(
        'going to verify email request.',
        extra={
            'params': {
                'verification_attempt_key': f'{EMAIL_VERIFICATION_ATTEMPT_PREFIX_CACHE_KEY}:{user.pk}',
                'email': cache.get(f'{EMAIL_VERIFICATION_ATTEMPT_PREFIX_CACHE_KEY}:{user.pk}'),
                'is_valid':is_valid,
                'otp':otp
            },
            'index_name': 'profile.verify_email',
        },
    )

    fail_response = {'status': 'failed'}
    if not is_valid:
        return fail_response

    claimed_email = cache.get(f'{EMAIL_VERIFICATION_ATTEMPT_PREFIX_CACHE_KEY}:{user.pk}')
    if claimed_email is None:
        return fail_response

    target_user = User.objects.filter(email=claimed_email).first()
    if target_user and target_user.id != request.user.id:
        return fail_response

    cache.delete(f'{EMAIL_VERIFICATION_ATTEMPT_PREFIX_CACHE_KEY}:{user.pk}')
    user.email = claimed_email
    user.do_verify_email(email_has_changed=True)
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='5/h', block=True)
@api
def users_reset_verification(request):
    user = request.user
    if settings.IS_PROD:
        # Verification reset is only available for Nobitex users to
        #  prevent losing KYC data
        if not user.is_nobitex_user:
            return {
                'status': 'failed',
                'message': 'Not available in production',
            }
    if user.user_type == User.USER_TYPES.trader:
        return {
            'status': 'failed',
            'message': 'Not available in trader plan',
        }

    user.user_type = User.USER_TYPES.level0
    user.verification_status = User.VERIFICATION.basic
    user.first_name = ''
    user.last_name = ''
    user.national_code = None
    user.phone = None
    user.mobile = None
    user.province = None
    user.city = None
    user.address = None
    user.gender = User.GENDER.unknown
    user.birthday = None
    user.save()
    vprofile = user.get_verification_profile()
    vprofile.mobile_confirmed = False
    vprofile.identity_confirmed = False
    vprofile.phone_confirmed = False
    vprofile.address_confirmed = False
    vprofile.bank_account_confirmed = False
    vprofile.selfie_confirmed = False
    vprofile.mobile_identity_confirmed = False
    vprofile.phone_code_confirmed = False
    vprofile.save()
    user.bank_cards.all().delete()
    user.bank_accounts.all().delete()
    user.verification_requests.all().update(status=VerificationRequest.STATUS.rejected)
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='12/m', block=True)
@measure_api_execution(api_label='kycGetVerificationStatus')
@api
def verification_status(request):
    """ POST /users/verification/status
    """
    user = request.user
    allowed_levels = ['level1']

    # Check if user is allowed to continue verification process
    user_level = user.user_type
    allow_level2 = True
    if allow_level2:
        pass
    elif user_level >= User.USER_TYPES.level2:
        allow_level2 = True
    elif user_level == User.USER_TYPES.trader:
        # Allow users with active trader plans
        trader_plan = UserPlan.get_user_plans(
            user, tp=UserPlan.TYPE.trader, only_active=True,
        ).first()
        if trader_plan:
            if now() - trader_plan.date_from >= datetime.timedelta(days=30):
                allow_level2 = True
            elif user.is_beta_user:
                allow_level2 = True
    if not allow_level2 and user_level >= User.USER_TYPES.level1:
        # Allow users with existing requests
        if user.verification_requests.filter(tp__in=[2, 3]).exists():
            allow_level2 = True
    if allow_level2:
        allowed_levels.append('level2')

    return {
        'status': 'ok',
        'allowedLevels': allowed_levels,
    }


@ratelimit(key='user_or_ip', rate='10/5m', block=True)
@measure_api_execution(api_label='kycVerifyMobile')
@api
def users_verify_mobile(request):
    user: User = User.objects.select_for_update(no_key=True).get(id=request.user.id)
    otp = request.g('otp')
    # TODO: remove if condition after decoupling abc
    if not Settings.get_flag('abc_use_restriction_internal_api') and UserService.has_user_active_tara_service(user):
        return {
            'status': 'failed',
            'code': 'UserHasActiveTaraService',
            'message': 'User has active tara service.',
        }

    if user.is_restricted(UserRestriction.RESTRICTION.ChangeMobile):
        return {
            'status': 'failed',
            'code': 'MobileChangeRestricted',
            'message': 'Mobile change is restricted for user.',
        }

    change_mobile_req = ChangeMobileRequest.get_active_request(user)
    if not change_mobile_req:
        is_valid = user.verify_otp(otp, tp=User.OTP_TYPES.mobile)
        if not is_valid:
            return {
                'status': 'failed',
                'code': 'VerificationError',
                'message': 'ChangeMobileRequestNotFound',
            }
        user.do_verify_mobile()
        UserSms.get_verification_messages(request.user).update(details='used')
        # Send fraud warning to users
        UserSms.objects.create(
            user=request.user,
            tp=UserSms.TYPES.process,
            to=user.mobile,
            text='حساب کاربری با شماره همراه و اطلاعات شخصی شما در وبسایت نوبیتکس ایجاد گردیده است.\nتوجه: قرار دادن آن در اختیار سایر اشخاص با بهانه هایی نظیر سرمایه گذاری و اجاره حساب طبق ماده ۲ قانون پول شویی پیگرد قانونی دارد و مجازات حبس تا هفت سال در انتظار متخلفین خواهد بود.',
        )
        MobileVerifiedWebEngageEvent(user=user, edited=False,
                                     device_kind=parse_request_channel(request=request)).send()
        return {
            'status': 'ok',
        }

    verify_result, error = change_mobile_req.do_verify(otp)
    if not verify_result:
        return {
            'status': 'failed',
            'code': 'VerifyMobileError',
            'message': error,
        }
    MobileVerifiedWebEngageEvent(user=user, edited=True,
                                 device_kind=parse_request_channel(request=request)).send()
    return {
        'status': 'ok',
        'change_mobile_status': serialize_change_mobile_status(change_mobile_req),
    }


@ratelimit(key='user_or_ip', rate='10/h', block=True)
@measure_api_execution(api_label='kycVerifyPhone')
@api
def users_verify_phone(request):
    otp = request.g('otp')
    user = request.user
    is_valid = user.verify_otp(otp, tp=User.OTP_TYPES.phone)
    if not is_valid:
        report_event('InvalidPhoneCode', extras={'enteredCode': otp, 'actualCode': user.otp})
        return {
            'status': 'failed',
        }
    user.do_verify_phone_code()
    UserVoiceMessage.get_verification_messages(user).update(delivery_status='used')
    TelephoneVerifiedWebEngageEvent(user=user, device_kind=parse_request_channel(request=request)).send()
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='10/h', block=True)
@measure_api_execution(api_label='kycUploadFile')
@api
def upload_file(request):
    form = UploadFileForm(request.POST, request.FILES)
    if not form.is_valid():
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'The file is necessary!',
        }
    if 'file' not in request.FILES:
        return {
            'status': 'failed',
            'code': 'UploadFileError',
            'message': 'No file uploaded',
        }
    tp = form.cleaned_data['tp'] if form.cleaned_data['tp'] else UploadedFile.TYPES.general
    if tp in UploadedFile.AUTO_KYC_TYPES and request.user.user_type >= User.USER_TYPES.level2:
        return {
            'status': 'failed',
            'code': 'UploadFileError',
            'message': 'User is verified!',
        }
    if (tp == UploadedFile.TYPES.general and request.FILES['file'].size > settings.MAX_UPLOAD_SIZE / 2) or (
        tp in UploadedFile.AUTO_KYC_TYPES and request.FILES['file'].size > settings.MAX_UPLOAD_SIZE
    ):
        log_numerical_metric_avg(
            'upload_file_size',
            request.FILES['file'].size / 1024,
            labels=(
                'LargeFile',
                tp,
            ),
            change_scale=Decimal(100),
        )
        return {
            'status': 'failed',
            'code': 'UploadFileError',
            'message': 'File size too large',
        }
    ufile = UploadedFile(filename=uuid.uuid4(), user=request.user, tp=tp)
    with open(ufile.disk_path, 'wb+') as destination:
        for chunk in request.FILES['file'].chunks():
            destination.write(chunk)

    # Check uploaded file type
    is_file_type_ok = True
    file_format = magic.from_file(ufile.disk_path, mime=True)
    if tp in UploadedFile.AUTO_KYC_TYPES:
        if file_format not in UploadedFile.AUTO_KYC_ACCEPTABLE_FILE_FORMATS[tp]:
            is_file_type_ok = False
    else:
        if not file_format.startswith(('image/', 'video/')):
            is_file_type_ok = False

    if not is_file_type_ok:
        os.remove(ufile.disk_path)  # TODO: this may be skipped by special timing of request canceling
        return JsonResponse({
            'status': 'failed',
            'code': 'UnacceptableFileType',
            'message': f'Invalid filetype: "{file_format}"',
        }, status=403)
    ufile.save()

    # Metric for file size in KB
    log_numerical_metric_avg(
        'upload_file_size',
        request.FILES['file'].size / 1024,
        labels=(
            'Uploaded',
            tp,
        ),
        change_scale=Decimal(100),
    )

    return {
        'status': 'ok',
        'file': {
            'id': ufile.filename.hex,
        },
    }


@ratelimit(key='user_or_ip', rate='30/m', block=True)
@api
def notifications_list(request):
    if NotificationConfig.is_notification_broker_enabled():
        from exchange.notification.models.in_app_notification import InAppNotification as Notification
    else:
        from exchange.accounts.models import Notification
    user = request.user
    if isinstance(user, int):
        notifications = Notification.objects.filter(user_id=user)
    else:
        notifications = Notification.objects.filter(user=user)
    notifications = notifications.order_by('-created_at')[:10]
    notifications_response = json.dumps(
        serialize(
            {
                'status': 'ok',
                'notifications': notifications,
            }
        ),
        ensure_ascii=False,
    )
    return HttpResponse(notifications_response, content_type='application/json')


@ratelimit(key='user_or_ip', rate='10/m', block=True)
@ratelimit(key='user_or_ip', rate='60/h', block=True)
@measure_api_execution(api_label='profileReadNotification')
@api
def notifications_read(request):
    """Mark one or many notifications as read
       POST notifications/read
    """
    if NotificationConfig.is_notification_broker_enabled():
        from exchange.notification.models.in_app_notification import InAppNotification as Notification
    else:
        from exchange.accounts.models import Notification

    param_id = request.g('id') or ''
    ids = str(param_id).split(',')
    for id in ids:
        parse_int(id, required=True)

    processed = Notification.mark_notifs_as_read(request.user.pk, ids)
    return {
        'status': 'ok',
        'processed': processed,
    }


@api
def users_limitations(request):
    """ POST /users/limitations
    """
    user = request.user
    # Set user activity
    UserStatsManager.update_last_activity(user)
    # Get Limitations
    up_to_level0 = user.user_type >= User.USER_TYPES.level0
    up_to_level1 = user.user_type >= User.USER_TYPES.level1
    withdraw_summations = UserLevelManager.get_user_withdraw_summations(user)
    deposit_summations = UserLevelManager.get_user_deposit_summations(user)
    return {
        'status': 'ok',
        'limitations': {
            'userLevel': serialize_choices(User.USER_TYPES, user.user_type),
            'features': {
                'crypto_trade': not up_to_level0,
                'rial_trade': not up_to_level1,
                'coin_deposit': not up_to_level0,
                'rial_deposit': not up_to_level1,
                'coin_withdrawal': not up_to_level0,
                'rial_withdrawal': not up_to_level1,
            },
            'limits': withdraw_summations,
            'depositLimits': deposit_summations,
        },
    }


@ratelimit(key='user_or_ip', rate='30/30m', block=True)
@measure_api_execution(api_label='kycAddNationalSerialNumber')
@api
def users_national_serial_add(request):
    """Update national card's serial number of user
    """
    user = request.user
    national_serial_number = request.g('national_serial_number')
    if not national_serial_number:
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'National card serial number is required!',
        }
    # User must have completed previous verification steps first
    if not UserLevelManager.is_eligible_to_start_verification_process(user):
        return {
            'status': 'failed',
            'code': 'UserLevelRestriction',
            'message': 'Identity is not complete',
        }
    user.national_serial_number = national_serial_number
    user.save(update_fields=['national_serial_number'])
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='30/30m', block=True)
@measure_api_execution(api_label='kycUpdateVerificationResult')
@api
def users_update_verification_result(request):
    """Create authorizing status of national card user from Alpha server
    """
    user = request.user
    result = parse_bool(request.g('result'))
    distance = Decimal(request.g('distance'))
    # User must have completed previous verification steps first
    if not UserLevelManager.is_eligible_to_start_verification_process(user):
        return {
            'status': 'failed',
            'code': 'UserLevelRestriction',
            'message': 'Identity is not complete',
        }
    vp = user.get_verification_profile()
    if result and distance <= 0.85:
        vp.identity_liveness_confirmed = True
        vp.save()
    else:
        vp.identity_liveness_confirmed = False
        vp.save()
        vr = VerificationRequest.objects.filter(user=user,
                                                tp=VerificationRequest.TYPES.auto_kyc,
                                                status=VerificationRequest.STATUS.new).first()
        if vr:
            vr.status = VerificationRequest.STATUS.rejected
            vr.explanations = f'Reject request because result is: {result} and distance is: {distance}'
            vr.save()
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='4/m', block=True)
@api
def telegram_generate_start_url(request):
    """Create a start url for Nobitex Telegram bot with a unique token for this user.
        POST /users/telegram/generate-url
    """
    user_token = random_string(8)
    cache.set(f'telegram_activation_token_{user_token}', request.user.id, 600)
    bot_username = 'nobitexbot' if settings.IS_PROD else 'testnobitexbot'
    return {
        'status': 'ok',
        'telegramActivationUrl': f'https://telegram.me/{bot_username}?start={user_token}',
    }


@ratelimit(key='user_or_ip', rate='60/m', block=True)
@public_post_api
def telegram_set_chat_id(request):
    """Set chat id for the user that started conversation with Nobitex Telegram bot
        using a valid start token. This API is called by our Telegram bot.
        POST /users/telegram/set-chat-id
        Note: Set chat_id to "@unsubscribe" to disable Telegram integration for user.
        # TODO: Limit for non-telegram IPs or at least decrease ratelimit
        Returns: user email
        Notice: Here we use startToken to find corresponding User.
        Tokens are only stored for 5 minutes in cache and are of length 8.
        The ratelimit (60/m) for this API ensures that finding a valid token by chance,
        that may lead to users` email enumeration attack, is improbable.
    """
    if request.g('bot_key') != settings.TELEGRAM_BOT_KEY:
        return {
            'status': 'failed',
            'code': 'InternalAPI',
            'message': 'Internal API',
        }
    # Validate Input
    chat_id = parse_telegram_chat_id(request.g('chat_id'))
    sent_token = (request.g('token') or '').strip()
    if not re.match(r'[a-zA-Z0-9]{8}$', sent_token):
        return {
            'status': 'failed',
            'code': 'InvalidToken',
            'message': 'Invalid Token',
        }
    # Check activation token
    cache_key = f'telegram_activation_token_{sent_token}'
    user_id = cache.get(cache_key)
    if not user_id:
        return {
            'status': 'failed',
            'code': 'InvalidToken',
            'message': 'Invalid Token',
        }
    # Set user's conversation_id
    cache.delete(cache_key)
    user = get_object_or_404(User, id=user_id)
    user.telegram_conversation_id = None if chat_id == '@unsubscribe' else chat_id
    user.save(update_fields=['telegram_conversation_id'])
    return {
        'status': 'ok',
        'email': user.email,
    }


@ratelimit(key='user_or_ip', rate='60/m', block=True)
@public_post_api
def telegram_reset_chat_id(request):
    """Reset chat id for the user from our Telegram bot.
        POST /users/telegram/reset-chat-id
    """
    if request.g('bot_key') != settings.TELEGRAM_BOT_KEY:
        return {
            'status': 'failed',
            'code': 'InternalAPI',
            'message': 'Internal API',
        }
    chat_id = parse_telegram_chat_id(request.g('chat_id'))
    user = get_object_or_404(User, telegram_conversation_id=chat_id)
    user.telegram_conversation_id = None
    user.save(update_fields=['telegram_conversation_id'])
    return {
        'status': 'ok',
    }


@ratelimit(key='user_or_ip', rate='15/m', block=True)
@measure_api_execution(api_label='kycGetRejectionReason')
@api
def user_level_up_rejection_reasons(request):
    user: User = request.user
    if not UserLevelManager.is_eligible_to_get_rejection_reason(user):
        raise SemanticAPIError(message='InvalidUserType', description='User is not eligible to get rejection reason')

    reason_list = get_rejection_reasons(user)
    return {
        'status': 'ok',
        'reasons': reason_list,
    }


def upgrade_level3_ratelimit(group, request):
    """Ratelimit checker for redeem landing. Used for increasing ratelimit for testnet."""
    return '10/h' if settings.IS_PROD else '1000/1h'


@ratelimit(key='user_or_ip', rate=upgrade_level3_ratelimit, block=True)
@measure_api_execution(api_label='kycUpgradeLevel3')
@api
def users_upgrade_level3(request):
    user: User = request.user

    if user.user_type >= User.USER_TYPES.verified:
        return {
            'status': 'failed',
            'code': 'UserAlreadyVerified',
            'message': 'User already is upgraded to level3',
        }

    try:
        _today = get_earliest_time(ir_now())
        if UpgradeLevel3Request.objects.filter(user=user, created_at__gte=_today).exists():
            return {
                'status': 'failed',
                'code': 'UpgradeLimitExceededError',
                'message': 'Upgrade request limit exceeded',
            }
        _request = UpgradeLevel3Request.objects.create(user=user)
    except IntegrityError:
        return {
            'status': 'failed',
            'code': 'DuplicateRequestError',
            'message': 'Another active request already exist!',
        }

    result, reason = UserLevelManager.is_eligible_to_upgrade_level3(user)
    if not result:
        _request.reject(reason)
        return {
            'status': 'failed',
            'code': reason,
            'message': 'User is not eligible to upgrade level3',
        }
    _request.approve_pre_conditions()

    return {
        'status': 'ok',
    }
