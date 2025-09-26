import datetime
import re
from decimal import Decimal

from dj_rest_auth.registration.serializers import RegisterSerializer
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from django.utils.translation import gettext_lazy as _
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import serializers

from exchange.accounts.constants import RESTRICTION_REMOVAL_INTERVAL_MINUTES
from exchange.accounts.functions import get_bank_info_cache_key
from exchange.accounts.user_levels_rejection_results import RejectionReason
from exchange.accounts.userlevels import UserLevelManager
from exchange.base.logging import report_event
from exchange.base.models import Settings
from exchange.base.serializers import register_serializer, serialize, serialize_choices
from exchange.features.models import QueueItem
from exchange.security.models import AddressBook

from .models import (
    BankAccount,
    BankCard,
    ChangeMobileRequest,
    Notification,
    ReferralProgram,
    UploadedFile,
    User,
    UserMergeRequest,
    UserOTP,
    UserPlan,
    UserRestriction,
    UserSms,
    VerificationRequest,
)
from .userstats import UserStatsManager
from .ws import create_ws_authentication_param


@register_serializer(model=User)
def serialize_user(user, opts):
    level = opts.get('level', 1)
    if level <= 1:
        return {
            'username': user.username,
            'name': user.get_full_name(),
        }

    # Bank info
    bank_info_cache_key = get_bank_info_cache_key(user.pk)
    bank_info = cache.get(bank_info_cache_key)
    if bank_info:
        all_bank_cards = bank_info.get('cards') or []
        all_bank_accounts = bank_info.get('accounts') or []
        all_payment_accounts = bank_info.get('paymentAccounts') or []
    else:
        all_bank_cards = user.bank_cards.filter(is_deleted=False, is_temporary=False)
        all_bank_cards = [serialize_bank_card(card) for card in all_bank_cards]
        all_bank_accounts = user.bank_accounts.filter(is_deleted=False, is_temporary=False)
        all_payment_accounts = [serialize_bank_account(account) for account in all_bank_accounts if account.virtual]
        all_bank_accounts = [serialize_bank_account(account) for account in all_bank_accounts if not account.virtual]
        # Cache results
        bank_info = {
            'cards': all_bank_cards,
            'accounts': all_bank_accounts,
        }
        if all_payment_accounts:
            # Only add key to cache for users with virtual accounts
            bank_info['paymentAccounts'] = all_payment_accounts
        cache.set(bank_info_cache_key, bank_info, 3600)

    # Bank info - calculated fields
    has_pending_bank_card = False
    has_confirmed_bank_card = False
    for card in all_bank_cards:
        if card.get('confirmed'):
            has_confirmed_bank_card = True
        if card.get('status') == 'new':
            has_pending_bank_card = True
    has_pending_bank_account = False
    has_confirmed_bank_account = False
    for account in all_bank_accounts:
        if account.get('confirmed'):
            has_confirmed_bank_account = True
        if account.get('status') == 'new':
            has_pending_bank_account = True

    # Fee options
    user_vip_level = UserStatsManager.get_user_vip_level(user.id)
    # amount is set to 100 to get fee rates in percent
    fee_kwargs = {
        'user_vip_level': user_vip_level,
        'user_fee': user.base_fee,
        'user_fee_usdt': user.base_fee_usdt,
        'user_maker_fee': user.base_maker_fee,
        'user_maker_fee_usdt': user.base_maker_fee_usdt,
        'amount': Decimal('100'),
    }
    options = {
        'fee': UserStatsManager.get_user_fee_by_fields(is_maker=False, is_usdt=False, **fee_kwargs),
        'feeUsdt': UserStatsManager.get_user_fee_by_fields(is_maker=False, is_usdt=True, **fee_kwargs),
        'makerFee': UserStatsManager.get_user_fee_by_fields(is_maker=True, is_usdt=False, **fee_kwargs),
        'makerFeeUsdt': UserStatsManager.get_user_fee_by_fields(is_maker=True, is_usdt=True, **fee_kwargs),
        'isManualFee': user.base_fee is not None,
        'vipLevel': user_vip_level,
        'discount': None,
    }

    # Other options
    options['tfa'] = user.requires_2fa
    options['socialLoginEnabled'] = user.social_login_enabled
    options['canSetPassword'] = user.can_social_login_user_set_password

    address_book = AddressBook.get(user=user)
    options['whitelist'] = address_book.whitelist_mode if address_book else False

    track = user.track or 0
    enabled_features = QueueItem.objects.filter(user=user, status=QueueItem.STATUS.done)
    features = [item.get_feature_display() for item in enabled_features]
    if 'Portfolio' not in features:
        if track & QueueItem.BIT_FLAG_PORTFOLIO:
            features.append('Portfolio')
    if user.is_beta_user:
        features.append('Beta')
    for default_feature in settings.NOBITEX_OPTIONS['features'].get('enabledFeatures', []):
        if default_feature in features:
            continue
        features.append(default_feature)

    # Check for Cobank Dynamic Flag
    if Settings.get_value('cobank_check_feature_flag', 'yes') == 'no' and 'CorporateBanking' not in features:
        features.append('CorporateBanking')

    if Settings.get_value('cobank_card_check_feature_flag', 'yes') == 'no' and 'CobankCards' not in features:
        features.append('CobankCards')

    if Settings.get_value('direct_debit_check_feature_flag', 'yes') == 'no' and 'DirectDebit' not in features:
        features.append('DirectDebit')

    if UserLevelManager.is_eligible_for_nobitex_id_deposit(user) and 'NobitexJibitIDeposit' not in features:
        features.append('NobitexJibitIDeposit')

    # Verification
    vprofile = user.get_verification_profile()
    has_pending_request_type = {1: False, 2: False, 3: False, 4: False}
    if user.user_type < User.USER_TYPES.level2:
        request_types = VerificationRequest.objects.filter(
            user=user, status=VerificationRequest.STATUS.new,
        ).values('tp').annotate(count=Count('*'))
        for r in request_types:
            if not r.get('count'):
                continue
            has_pending_request_type[r['tp']] = True

    # Pending Verifications
    pv_mobile = False
    if not vprofile.mobile_confirmed:
        pv_mobile = UserSms.get_verification_messages(user).exclude(details='used').exists()
    pv_email = False
    if not vprofile.email_confirmed:
        pv_email = user.has_active_otp(tp=User.OTP_TYPES.email)
        if settings.CHECK_OTP_DIFFS:
            if pv_email and not UserOTP.active_otps(user=user, tp=UserOTP.OTP_TYPES.email).exists():
                report_event('UserOtpImplementation:EmailMismatch')

    websocket_auth_param = create_ws_authentication_param(user.uid)

    return {
        # User details
        # user_id should be removed from the response
        'id': user.pk,
        'username': user.username,
        'email': None if user.email.endswith('@mobile.ntx.ir') else user.email,
        'level': user.user_type,
        'firstName': user.first_name,
        'lastName': user.last_name,
        'nationalCode': user.national_code,
        'nickname': user.nickname,
        'phone': user.phone,
        'mobile': user.mobile,
        'province': user.province,
        'city': user.city,
        'address': user.address,
        'postalCode': user.postal_code,
        # Related bank models
        'bankCards': all_bank_cards,
        'bankAccounts': all_bank_accounts,
        'paymentAccounts': all_payment_accounts,
        # Verification
        'verifications': {
            'email': vprofile.email_confirmed,
            'phone': vprofile.phone_confirmed or vprofile.address_confirmed,
            'mobile': vprofile.mobile_confirmed,
            'identity': vprofile.identity_confirmed,
            'selfie': vprofile.selfie_confirmed,
            'auto_kyc': vprofile.identity_liveness_confirmed,
            'bankAccount': has_confirmed_bank_account,
            'bankCard': has_confirmed_bank_card,
            'address': vprofile.address_confirmed,
            'city': bool(user.city),
            'phoneCode': bool(user.phone),
            'mobileIdentity': bool(vprofile.mobile_identity_confirmed),
            'nationalSerialNumber': bool(user.national_serial_number),
        },
        'pendingVerifications': {
            'email': pv_email,
            'phone': False,
            'mobile': pv_mobile,
            'identity': has_pending_request_type[VerificationRequest.TYPES.identity],
            'address': has_pending_request_type[VerificationRequest.TYPES.address],
            'selfie': has_pending_request_type[VerificationRequest.TYPES.selfie],
            'auto_kyc': has_pending_request_type[VerificationRequest.TYPES.auto_kyc],
            'bankAccount': has_pending_bank_account,
            'bankCard': has_pending_bank_card,
            'phoneCode': False,
            'mobileIdentity': not bool(vprofile.mobile_identity_confirmed) and bool(vprofile.identity_confirmed)
                              and bool(user.mobile) and bool(user.national_code),
        },
        # Options
        'track': track,
        'options': options,
        'features': features,
        # Other
        'chatId': str(user.chat_id).replace('-', ''),
        'withdrawEligible': True,  # Deprecated
        'websocketAuthParam': websocket_auth_param,
    }


@register_serializer(model=BankAccount)
def serialize_bank_account(account, opts=None):
    bank_name = account.get_bank_id_display()
    if re.match('IR\d{6}6118\d{14}', account.shaba_number):
        bank_name = 'بلوبانک'
    if account.virtual:
        custom_data = {
            'account': account.account_number,
            'service': bank_name,
        }
    else:
        custom_data = {
            'number': account.account_number,
            'shaba': account.shaba_number,
            'bank': bank_name,
        }
    return {
        'id': account.pk,
        **custom_data,
        'owner': account.owner_name,
        'confirmed': account.confirmed,
        'status': account.status_codename,
    }


@register_serializer(model=BankCard)
def serialize_bank_card(card, opts=None):
    return {
        'id': card.pk,
        'number': card.get_card_number_display(),
        'bank': card.bank_name,
        'owner': card.owner_name,
        'confirmed': card.confirmed,
        'status': card.status_codename,
    }


@register_serializer(model=Notification)
def serialize_notification(notification, opts):
    return {
        'id': notification.pk,
        'createdAt': notification.created_at,
        'read': notification.is_read,
        'message': notification.message,
    }


@register_serializer(model=TOTPDevice)
def serialize_totp_device(device, opts):
    return {
        'id': device.pk,
        'name': device.name,
        'confirmed': device.confirmed,
        'configUrl': device.config_url if not device.confirmed else None,
    }


@register_serializer(model=UserPlan)
def serialize_user_plan(plan, opts):
    return {
        'id': plan.pk,
        'plan': plan.get_type_display(),
        'startDate': plan.date_from,
        'endDate': plan.date_to,
        'isActive': plan.is_active,
    }


@register_serializer(model=ReferralProgram)
def serialize_referral_program(program, opts):
    from exchange.market.models import ReferralFee

    level = opts.get('level', 1)
    include_old_fees = opts.get('includeOldFees', False)
    data = {
        'id': program.pk,
        'referralCode': program.referral_code,
        'createdAt': program.created_at,
        'userShare': program.user_share,
        'friendShare': program.friend_share,
        'description': program.description,
        'agenda': serialize_choices(ReferralProgram.AGENDA, program.agenda),
    }
    if level >= 2:
        program_trade_stats = ReferralFee.get_referral_program_stats(program, include_old_fees=include_old_fees)
        data.update({
            'statsRegisters': program.get_referred_users_count(),
            'statsTrades': program_trade_stats['trades'],
            'statsProfit': program_trade_stats['profit'],
        })
    return data


@register_serializer(model=ChangeMobileRequest)
def serialize_change_mobile_status(change_mobile_request):
    return {
        'code': change_mobile_request.status,
        'text': change_mobile_request.get_status_display()
    }


class EmailRegisterSerializer(RegisterSerializer):
    pass


class MobileRegisterSerializer(RegisterSerializer):
    username = serializers.CharField(
        # Max and Min length based on length check in 'validate_mobile'
        max_length=12,
        min_length=10,
        required=True,
    )
    mobile = serializers.CharField(
        # Max and Min length based on length check in 'validate_mobile'
        max_length=12,
        min_length=10,
        required=True,
    )
    password1 = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    def validate_mobile(self, mobile):
        if User.objects.filter(mobile=mobile).exists():
            raise serializers.ValidationError(
                _("A user is already registered with this mobile number."))
        return mobile

    def get_cleaned_data(self):
        return {
            'username': self.validated_data.get('username', ''),
            'password': self.validated_data.get('password1', ''),
            'mobile': self.validated_data.get('mobile', ''),
            'email': self.validated_data.get('mobile', '') + '@mobile.ntx.ir',
        }

    def save(self, request):
        user = User.objects.create_user(
            **self.get_cleaned_data()
        )
        verification_profile = user.get_verification_profile()
        verification_profile.mobile_confirmed = True
        verification_profile.save(update_fields=['mobile_confirmed',])
        return user


@register_serializer(model=RejectionReason)
def serialize_rejection_reason(rejection: RejectionReason, opts=None):
    return {
        'reason': rejection.reason,
        'reasonFa': rejection.reason_fa,
        'description': rejection.description,
    }


@register_serializer(model=UploadedFile)
def serialize_uploaded_file(uploaded_file: UploadedFile, opts=None):
    return {
        'filename': str(uploaded_file.filename),
        'type': uploaded_file.tp,
    }


@register_serializer(model=UserMergeRequest)
def serialize_user_merge_request(request: UserMergeRequest, opts=None):
    return {
        'status': request.get_status_display(),
    }


@register_serializer(model=UserRestriction)
def serialize_user_restriction(restriction: UserRestriction, opts=None):
    removal = restriction.restriction_removals.filter(is_active=True)
    extra_time = datetime.timedelta(minutes=RESTRICTION_REMOVAL_INTERVAL_MINUTES)

    return {
        'action': restriction.get_restriction_display(),
        'reason': restriction.description or restriction.get_withdraw_default_description(),
        'endsAt': serialize(
            removal.first().ends_at + extra_time if removal and restriction.description else None
        ),  # We hide endsAt field when the restriction is created manually in the admin panel (restriction.description is None).
    }
