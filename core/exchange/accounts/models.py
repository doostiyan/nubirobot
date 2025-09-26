import datetime
import functools
import hashlib
import itertools
import json
import os
import random
import re
import string
import time
import typing
import uuid
from hashlib import shake_128
from string import Formatter
from typing import TYPE_CHECKING, Iterable, List, Optional, Tuple, Type, Union

import jdatetime
import requests
from django.conf import settings
from django.contrib.auth.models import AbstractUser, Permission
from django.contrib.auth.models import UserManager as AbstractUserManager
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.shortcuts import get_current_site
from django.core import serializers
from django.core.cache import cache
from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.db import IntegrityError, connection, models, transaction
from django.db.models import JSONField, Q
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from django_otp.plugins.otp_totp.models import TOTPDevice
from model_utils import Choices, FieldTracker
from rest_framework.authtoken.models import Token

from exchange.accounts.bulk_create_manager import BulkCreateWithSignalManager
from exchange.accounts.captcha import CaptchaProviderError
from exchange.accounts.constants import (
    PROVINCE_PHONE_CODES,
    PROVINCES,
    SYSTEM_USER_IDS_CACHE_TIMEOUT,
    auto_tags,
    company_tags,
)
from exchange.accounts.exceptions import InvalidUserNameError, PasswordRecoveryError, UserRestrictionRemovalNotAllowed
from exchange.accounts.producer import notification_producer
from exchange.accounts.sms_integrations import SmsSender
from exchange.accounts.sms_templates import OLD_SMSIR_TEMPLATES
from exchange.accounts.user_restrictions import UserRestrictionsDescription
from exchange.accounts.verificationapi import AutoKYC
from exchange.base.calendar import get_readable_weekday_str, ir_now, to_shamsi_date
from exchange.base.crypto import random_string_digit
from exchange.base.decorators import ram_cache
from exchange.base.emailmanager import EmailManager
from exchange.base.internal.services import Services
from exchange.base.logging import log_event, metric_incr, report_event, report_exception
from exchange.base.models import Settings
from exchange.base.normalizers import normalize_mobile
from exchange.base.serializers import serialize
from exchange.base.tasks import send_email, send_telegram_message
from exchange.base.validators import validate_email, validate_mobile
from exchange.broker.broker.schema import (
    AdminTelegramNotificationSchema,
    NotificationSchema,
    TelegramNotificationSchema,
)
from exchange.broker.broker.topics import Topics
from exchange.integrations.verification import VerificationClient
from exchange.notification.switches import NotificationConfig
from exchange.web_engage.events import (
    BankAccountVerifiedWebEngageEvent,
    BankCardVerifiedWebEngageEvent,
    MobileEnteredWebEngageEvent,
    SuccessfulRegisterWithReferralCode,
)
from exchange.web_engage.events.base import WebEngageKnownUserEvent

if TYPE_CHECKING:
    from django.db.models.query import QuerySet

UPGRADE_LEVEL3_STATUS = Choices(
    (1, 'requested', 'Requested'),
    (2, 'pre_conditions_approved', 'Pre-conditions Approved'),
    (3, 'rejected', 'Rejected'),
    (4, 'approved', 'Approved'),
)


class UserManager(AbstractUserManager):
    @classmethod
    def normalize_email(cls, email):
        email = AbstractUserManager.normalize_email(email)
        # If no email is provided, normalized value is empty string
        return email or None


class User(AbstractUser):
    """ User object
    """
    USER_TYPES = Choices(
        (0, 'normal', 'Normal'),       # No email
        (10, 'inactive', 'Inactive'),  # Deprecated
        (20, 'suspicious', 'Suspicious'),  # Deprecated
        (30, 'blocked', 'Blocked'),    # Deprecated
        (40, 'level0', 'Level0'),      # Without KYC
        (42, 'level1p', 'Level1P'),    # Deprecated
        (44, 'level1', 'Level1'),      # Level1
        (45, 'trader', 'Trader'),      # Deprecated, ended on 1402-09-05
        (46, 'level2', 'Level2'),      # Level2
        (90, 'verified', 'Level3'),    # Level3
        (91, 'active', 'Active'),      # Deprecated
        (92, 'trusted', 'Trusted'),    # Level4
        (99, 'nobitex', 'Nobitex'),    # Nobitex Team
        (100, 'system', 'System'),     # System Users
        (101, 'bot', 'Bot'),           # Internal Market Making
        (102, 'staff', 'Staff'),       # Deprecated, use nobitex
    )
    # Only some user types are actively used, so use of these constants are recommended:
    USER_TYPE_LEVEL1 = USER_TYPES.level1
    USER_TYPE_LEVEL2 = USER_TYPES.level2
    USER_TYPE_LEVEL3 = USER_TYPES.verified
    USER_TYPE_LEVEL4 = USER_TYPES.trusted

    VERIFICATION = Choices(
        (0, 'none', 'None'),           # No verification done
        (1, 'basic', 'Basic'),         # Email or mobile verified
        (2, 'full', 'Full'),           # Also mobile, identity and address verified
        (3, 'extended', 'Extended'),   # Bank card and account verified
    )
    OTP_TYPES = Choices(
        (1, 'email', 'Email'),
        (2, 'mobile', 'Mobile'),
        (3, 'phone', 'Phone'),
    )
    GENDER = Choices(
        (0, 'unknown', 'Unknown'),
        (1, 'male', 'Male'),
        (2, 'female', 'Female'),
    )
    TRACK = Choices(
        (0, 'normal', 'Normal'),      # All users
        (4096, 'open', 'Open'),       # Any volunteer, Release candidate
        (8192, 'beta', 'Beta'),       # Beta users
        (12288, 'alpha', 'Alpha'),    # Alpha users
        (16384, 'closed', 'Closed'),  # Closed internal test
        (20480, 'dev', 'Dev'),        # Development team
    )

    # Inherited fields
    # username, first_name, last_name, email are inherited
    # username is always set to email for non-system users

    # Basic fields
    user_type = models.IntegerField(choices=USER_TYPES, default=USER_TYPES.normal)
    national_code = models.CharField(max_length=12, null=True, blank=True, verbose_name='کد ملی')
    national_serial_number = models.CharField(max_length=20, null=True, blank=True, verbose_name='سریال کارت ملی')
    phone = models.CharField(max_length=12, null=True, blank=True, verbose_name='تلفن ثابت')
    email = models.EmailField(_('email address'), blank=True, null=True, unique=True, default=None)
    mobile = models.CharField(max_length=12, null=True, blank=True, verbose_name='شماره موبایل', db_index=True)
    verification_status = models.IntegerField(choices=VERIFICATION, default=VERIFICATION.none)
    track = models.SmallIntegerField(choices=TRACK, null=True, blank=True, db_index=True, verbose_name='Test Track')

    # Other details
    nickname = models.CharField(max_length=50, null=True, blank=True)
    province = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    postal_code = models.CharField(max_length=10, null=True, blank=True)
    gender = models.IntegerField(choices=GENDER, default=GENDER.unknown)
    birthday = models.DateField(null=True, blank=True)
    father_name = models.CharField(max_length=50, null=True, blank=True)

    # Security-related details
    requires_2fa = models.BooleanField(default=False)
    social_login_enabled = models.BooleanField(default=False)
    logout_threshold = models.IntegerField(null=True, blank=True, help_text='دقیقه')
    telegram_conversation_id = models.CharField(max_length=20, null=True, blank=True)
    chat_id = models.UUIDField(default=uuid.uuid4, editable=False)

    # Market-related details
    base_fee = models.DecimalField(decimal_places=3, max_digits=6, null=True, blank=True, help_text='درصد')
    base_fee_usdt = models.DecimalField(decimal_places=3, max_digits=6, null=True, blank=True, help_text='درصد')
    base_maker_fee = models.DecimalField(decimal_places=3, max_digits=6, null=True, blank=True, help_text='درصد')
    base_maker_fee_usdt = models.DecimalField(decimal_places=3, max_digits=6, null=True, blank=True, help_text='درصد')
    referral_code = models.CharField(max_length=20, null=True, blank=True, unique=True)

    # OTP sending details (SMS & email)
    # TODO: These fields are essentially moved to UserOTP and should be removed from here
    otp = models.CharField(max_length=6, null=True, blank=True)
    otp_expiry = models.DateTimeField(null=True, blank=True)
    otp_type = models.IntegerField(choices=OTP_TYPES, null=True, blank=True)
    # uuid instead of id
    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, null=False, blank=False, db_index=True)

    webengage_cuid = models.UUIDField(db_index=True, editable=False, unique=True, null=True, blank=True)

    objects = UserManager()
    tracker = FieldTracker(fields=['user_type'])

    class Meta:
        verbose_name = 'کاربر'
        verbose_name_plural = verbose_name
        indexes = [models.Index(fields=['national_code'], name='idx_user_national_code')]

    def __str__(self):
        return self.get_full_name() or self.username

    def save(self, *args, update_fields=None, **kwargs):
        if not self.pk:
            if settings.IS_TESTNET and self.password == '!nobitex':
                pass
            elif self.mobile:
                mobile = normalize_mobile(self.mobile.strip())
                self.username = self.mobile = mobile
                if update_fields:
                    update_fields = (*update_fields, *('username', 'mobile'))
            elif self.email:
                email = self.email.lower().strip()
                self.username = self.email = email
                if update_fields:
                    update_fields = (*update_fields, *('username', 'email'))

        super().save(*args, update_fields=update_fields, **kwargs)

    def get_webengage_id(self) -> str:
        if not self.webengage_cuid:
            self.webengage_cuid = uuid.uuid4()
            self.save(update_fields=['webengage_cuid'])
        return str(self.webengage_cuid)

    @classmethod
    def by_email_or_mobile(cls, username: str) -> 'User':
        if validate_email(username):
            try:
                return cls.objects.get(email=username)
            except User.DoesNotExist:
                raise InvalidUserNameError('کاربری با این ایمیل وجود ندارد.')
        if validate_mobile(username):
            try:
                return cls.objects.get(mobile=username)
            except MultipleObjectsReturned:
                raise InvalidUserNameError('بیش از یک اکانت با این شماره موبایل وجود دارد.')
            except User.DoesNotExist:
                raise InvalidUserNameError('کاربری با این شماره موبایل وجود ندارد.')
        raise InvalidUserNameError('مقدار وارد شده صحیح نیست.')

    @property
    def is_email_verified(self):
        return self.get_verification_profile().email_confirmed

    @property
    def is_identity_verified(self):
        return self.get_verification_profile().identity_confirmed

    @property
    def is_internal_user(self):
        return self.user_type >= self.USER_TYPES.system

    @property
    def is_system_trader_bot(self):
        return self.id in settings.TRADER_BOT_IDS

    @property
    def is_system_user(self):
        return not self.is_customer_user

    @property
    def is_customer_user(self):
        return self.user_type < self.USER_TYPES.system

    @property
    def is_beta_user(self):
        """ Whether this user is in beta program and has access to near-launch features
        """
        return (self.track or 0) >= self.TRACK.beta

    @property
    def is_nobitex_user(self):
        """ Wether this user is a Nobitex team member and can see alpha features
        """
        return self.user_type >= self.USER_TYPES.nobitex or self.is_staff

    @property
    def is_company_user(self):
        return self.tags.filter(name__in=[company_tags['company_tag']]).exists()

    @property
    def birthday_shamsi(self):
        if not self.birthday:
            return None
        birth_date = jdatetime.date.fromgregorian(
            year=self.birthday.year,
            month=self.birthday.month,
            day=self.birthday.day,
        )
        return '{}/{}/{}'.format(
            str(birth_date.year).zfill(2),
            str(birth_date.month).zfill(2),
            str(birth_date.day).zfill(2),
        )

    @property
    def province_phone_code(self):
        if not self.province:
            return None
        try:
            province_id = PROVINCES.index(self.province)
            return PROVINCE_PHONE_CODES[province_id]
        except ValueError:
            return None

    @property
    def is_user_eligible_to_withdraw(self):
        """Property that shows if user eligible to withdraw at this time"""
        return True

    @property
    def stats(self):
        return ApiUsage.get(self)

    @property
    def is_online(self):
        from .userstats import UserStatsManager
        last_activity = UserStatsManager.get_last_activity(self)
        return last_activity > now() - datetime.timedelta(minutes=10)

    @property
    def has_verified_mobile_number(self):
        """Return True if the user has a valid and verified mobile number."""
        return self.mobile and self.get_verification_profile().has_verified_mobile_number

    @property
    def has_tag_cant_upgrade_level2(self):
        """return true if user_type cant upgrade to level2"""
        return self.tags.filter(name='عدم ارتقاء سطح ۲').exists()

    @property
    def can_social_login_user_set_password(self):
        return self.social_login_enabled and not self.has_usable_password()

    @property
    def user_type_label(self) -> str:
        return settings.NOBITEX_OPTIONS['userTypes'].get(self.user_type, None)

    def get_anonymized_name(self):
        name = self.email
        if not name or '@' not in name:
            return 'ناشناس'
        name, domain = name.split('@', 1)
        return name[:2] + '*' * (len(name) - 2) + '@' + domain

    def set_beta_status(self, is_beta):
        """Set high bits of user testing track to enable or disable beta status."""
        b = self.TRACK.beta
        current_track = self.track or 0
        if is_beta:
            if current_track < b:
                self.track = b + current_track % 4096
                self.save(update_fields=['track'])
        else:
            if self.track is None:
                return
            if current_track >= 4096:
                self.track = current_track % 4096
                self.save(update_fields=['track'])

        # Add user event
        UserEvent.objects.create(
            user = self,
            action = UserEvent.ACTION_CHOICES.change_user_track,
            action_type = (
                UserEvent.CHANGE_USER_TRACK_ACTION_TYPE.active_beta if is_beta \
                    else UserEvent.CHANGE_USER_TRACK_ACTION_TYPE.deactive_beta)
        )

    def set_profile_property(self, key: str, value: Union[str, int]) -> None:
        '''Set a property value in UserProfile object of this user.'''
        from exchange.accounts.userprofile import UserProfileManager
        UserProfileManager.set_user_property(self.id, key, value)

    def get_verification_profile(self) -> 'VerificationProfile':
        try:
            return self.verification_profile
        except VerificationProfile.DoesNotExist:
            try:
                with transaction.atomic():
                    return VerificationProfile.objects.create(user=self)
            except IntegrityError:
                return self.verification_profile

    def update_verification_status(self, extra_updated_fields: List = None):
        # Avoid updating verification status in trader plan
        if self.user_type == User.USER_TYPES.trader:
            return

        update_fields = ['verification_status', 'user_type']
        if extra_updated_fields:
            update_fields.extend(extra_updated_fields)

        vprofile = self.get_verification_profile()
        self.verification_status = vprofile.verification_status

        if self.user_type < self.USER_TYPES.inactive and vprofile.is_verified_level0:
            self.user_type = self.USER_TYPES.level0

        elif self.user_type < self.USER_TYPES.level1 and vprofile.is_verified_level1:
            self.user_type = self.USER_TYPES.level1

        elif self.user_type < self.USER_TYPES.level2 and vprofile.is_verified_level2:
            if not self.has_tag_cant_upgrade_level2:
                self.user_type = self.USER_TYPES.level2

        else:
            update_fields.remove('user_type')

        self.save(update_fields=update_fields)
        if 'user_type' in update_fields:
            VerificationProfile.notify_user_type_change(user=self)

    def generate_otp_obj(self, tp, usage, otp=None):
        if type(usage) == str:
            usage_str = usage
            usage = getattr(UserOTP.OTP_Usage, usage, None)
            if not usage and settings.CHECK_OTP_DIFFS:
                report_event('UserOtpImplementation:Usage', extras={'usage': usage_str, 'info': 'usage choice not exists'})

        otp = UserOTP.generate_otp_code(user=self, tp=tp, code=otp)

        for active_otp in UserOTP.active_otps(user=self, tp=tp, usage=usage):
            active_otp.disable_otp()

        return UserOTP.create_otp(user=self, otp=otp, tp=tp, usage=usage)

    def generate_otp(self, tp):
        # Do not regenerate if a recent OTP is unused
        if self.otp and self.otp_type == tp and self.otp_expiry > now() + datetime.timedelta(minutes=20):
            return self.otp
        self.otp = UserOTP.generate_otp_code(user=self, tp=tp)
        self.otp_expiry = now() + datetime.timedelta(minutes=30)
        self.otp_type = tp
        self.save(update_fields=['otp', 'otp_expiry', 'otp_type'])
        return self.otp

    def send_email_otp(self, usage=None, claimed_email=None):
        # TODO: do not resend if recently a successful OTP email is sent
        if usage == 'email-verification' and self.is_email_verified:
            metric_incr('metric_email_verification_request_for_confirmed_user')
            return
        # Generate OTP and send email
        otp = self.generate_otp(tp=self.OTP_TYPES.email)
        user_otp = self.generate_otp_obj(tp=self.OTP_TYPES.email, usage=usage, otp=otp)
        EmailManager.send_email(
            claimed_email if claimed_email else self.email,
            'otp',
            data={
                'otp': otp,
                'request_type': user_otp.usage_translation,
            },
            priority='high',
        )

    def send_telegram_otp(self, otp):
        Notification(user=self, message='کد تایید شما: {}'.format(otp)).send_to_telegram_conversation(
            save=False, is_otp=True
        )

    def verify_otp(self, otp, tp=None):
        if not otp or not self.otp or not self.otp_expiry:
            return False
        # Hearing aid for phone OTP
        if self.otp_type == self.OTP_TYPES.phone:
            self.otp = self.otp[:4].replace('0', '3')
            otp = otp[:4].replace('0', '3')
        if otp != self.otp:
            return False
        otp_obj = UserOTP.objects.filter(user=self, code=otp).order_by('-id').first()
        if not otp_obj and settings.CHECK_OTP_DIFFS:
            report_event('UserOtpImplementation',
                         extras={'user': self.id, 'otp': otp, 'tp': str(tp), 'info': 'related otp_obj not exists'})
        if tp and self.otp_type != tp:
            if otp_obj and not self.otp_type != tp and settings.CHECK_OTP_DIFFS:
                report_event('UserOtpImplementation',
                             extras={'otp_obj': otp_obj.id, 'tp': str(tp), 'info': 'otp type not matched'})
            return False
        if self.otp_expiry < now():
            if otp_obj and not otp_obj.expires_at < now() and settings.CHECK_OTP_DIFFS:
                report_event('UserOtpImplementation', extras={'otp_obj': otp_obj.id, 'info': 'time expiry not matched'})
            return False
        self.otp = None
        self.otp_expiry = None
        self.save(update_fields=['otp', 'otp_expiry'])
        if otp_obj:
            if otp_obj.otp_status != UserOTP.OTP_STATUS.new and settings.CHECK_OTP_DIFFS:
                report_event('UserOtpImplementation', extras={'status': otp_obj.otp_status, 'info': 'wrong otp status'})
            otp_obj.otp_status = UserOTP.OTP_STATUS.used
            otp_obj.save(update_fields=['otp_status'])
        return True

    def has_active_otp(self, tp=None):
        if tp and self.otp_type != tp:
            return False
        return self.otp and self.otp_expiry and self.otp_expiry > now()

    def do_verify_email(self, email_has_changed: bool = False):
        vprofile = self.get_verification_profile()
        vprofile.email_confirmed = True
        vprofile.save(update_fields=['email_confirmed'])
        self.update_verification_status(extra_updated_fields=(['email'] if email_has_changed else None))

    def do_verify_mobile(self):
        """
        verify mobiles fields in verification_profile (mobile_confirmed and mobile_identity_confirmed)
        and check mobile identity with shahkar
        """
        vprofile = self.get_verification_profile()
        vprofile.mobile_confirmed = True
        update_fields = ['mobile_confirmed']

        vprofile.save(update_fields=update_fields)
        self.update_verification_status()
        self.update_mobile_identity_status()

    def do_verify_phone_code(self):
        vprofile = self.get_verification_profile()
        vprofile.phone_code_confirmed = True
        vprofile.save(update_fields=['phone_code_confirmed'])
        # Also automatically accept address
        non_rejected_requests = VerificationRequest.objects.filter(
            user=self,
            tp=VerificationRequest.TYPES.address,
        ).exclude(
            status=VerificationRequest.STATUS.rejected,
        )
        if non_rejected_requests.count() > 0:
            # first we checked that the user has any non-rejected
            #  address requests to prevent passing without address KYC
            self.do_verify_address()

    def do_verify_address(self):
        vprofile = self.get_verification_profile()
        vprofile.address_confirmed = True
        vprofile.save(update_fields=['address_confirmed'])
        self.update_verification_status()
        VerificationRequest.get_active_requests(
            user=self,
            tp=VerificationRequest.TYPES.address,
        ).update(
            status=VerificationRequest.STATUS.confirmed,
        )

    def do_verify_liveness_alpha(self):
        vprofile = self.get_verification_profile()
        vprofile.identity_liveness_confirmed = True
        vprofile.save(update_fields=['identity_liveness_confirmed'])
        self.update_verification_status()

    def send_welcome_email(self, request):
        activation = EmailActivation.objects.get_or_create(user=self)[0]
        EmailManager.send_email(
            self.email,
            'welcome',
            data={
                'token': activation.token.hex,
                'domain': 'https://{}/'.format(get_current_site(request).domain),
            },
            priority='high',
        )

    def send_welcome_sms(self):
        ChangeMobileRequest.create(self,
                                   self.mobile,
                                   ChangeMobileRequest.STATUS.old_mobile_otp_sent).send_otp()

    def get_referral_code(self):
        if not self.referral_code:
            code = None
            for _ in range(100):
                code = random.randint(10000, 99999)
                if not User.objects.filter(referral_code=code).exists():
                    break
            self.referral_code = code
            self.save(update_fields=['referral_code'])
        return self.referral_code

    def get_referrer_user(self):
        user_referral = UserReferral.get_referrer(self)
        return user_referral.parent if user_referral else None

    def tfa_create_new_device(self, confirmed=False):
        return TOTPDevice.objects.create(
            user=self,
            name='App',
            confirmed=confirmed,
            tolerance=4,
        )

    def tfa_confirm_device(self, device, enable=True):
        TOTPDevice.objects.filter(user=self).update(confirmed=False)
        TOTPDevice.objects.filter(user=self, id=device.id).update(confirmed=True)
        if enable:
            self.tfa_enable()

    def tfa_disable(self):
        TOTPDevice.objects.filter(user=self).update(confirmed=False)  # Do not delete, only mark as deleted
        self.requires_2fa = False
        self.save(update_fields=['requires_2fa'])

    def tfa_enable(self):
        self.requires_2fa = True
        self.save(update_fields=['requires_2fa'])

    def tfa_verify(self, otp):
        device = TOTPDevice.objects.filter(user=self, confirmed=True).order_by('-pk').first()
        if not device:
            return False
        return device.verify_token(otp)

    def is_restricted(self, *restrictions):
        return UserRestriction.is_restricted(self, *restrictions)

    def get_restriction(self, restriction):
        return UserRestriction.get_restriction(self, restriction)

    def get_restrictions(self, *restrictions: Tuple[Union[int, str], ...]):
        return UserRestriction.get_restrictions(self, *restrictions)

    @classmethod
    def by_email(cls, email):
        try:
            return cls.objects.get(username=cls.username, email=email)
        except User.DoesNotExist:
            return None

    @classmethod
    def get_generic_system_user(cls):
        return cls.objects.get(pk=1000, username='system-1000')

    @classmethod
    def get_gift_system_user(cls):
        return cls.objects.get(pk=997, username='system-gift@nobitex.ir')

    @classmethod
    def get_nobitex_delegator(cls) -> 'User':
        return cls.objects.get(pk=400, username='nobitex-delegator')

    @classmethod
    def validate_national_code(cls, user, national_code):
        same_users = User.objects.filter(national_code=national_code)
        for same_user in same_users:
            if same_user != user:
                return False

        return True

    @classmethod
    def validate_mobile_number(cls, user, mobile):
        same_users = User.objects.filter(mobile=mobile)
        for same_user in same_users:
            if same_user != user and same_user.verification_profile.mobile_confirmed:
                return False
        return True

    def serialize(self):
        return serializers.serialize("json", [self, ], use_natural_foreign_keys=True, use_natural_primary_keys=True)

    def check_mobile_identity(self, mobile: str = None, national_code: str = None) -> Tuple[bool, Optional[str]]:
        national_code = national_code or self.national_code
        mobile = mobile or self.mobile
        if not national_code or not mobile:
            return False, 'InadequateInformation'
        if settings.IS_PROD or self.is_user_considered_in_production_test:
            # Use Shahkar API
            try:
                response = VerificationClient().is_user_owner_of_mobile_number(national_code, mobile)
            except ValueError:
                report_exception()
                return False, 'ShahkarError'
            result = response['result']
        else:
            # Is non-production environments, accept identity without checking
            result = True

        if result:
            return True, None
        return False, 'NotOwnedByUser'

    def update_mobile_identity_status(self) -> None:
        if not self.national_code or not self.mobile:
            return
        result, _ = self.check_mobile_identity()
        v_profile = self.get_verification_profile()
        v_profile.mobile_identity_confirmed = result
        v_profile.save(update_fields=['mobile_identity_confirmed'])

    def permission_required(self, permission):
        from django.core.exceptions import PermissionDenied
        if not self.has_perm(permission):
            raise PermissionDenied(permission)
        return

    def get_tags(self, tp=None):
        has_old_type = False
        if tp is not None:
            requested_type_tags = cache.get(f'user_{self.id}_{tp}_tags')
            if requested_type_tags:
                has_old_type = any(isinstance(tag, str) for tag in requested_type_tags)
            if not requested_type_tags or has_old_type:
                requested_type_tags = list(self.tags.filter(tp=tp))
                cache.set(f'user_{self.id}_{tp}_tags', requested_type_tags, 21600)
            return requested_type_tags
        user_tags = cache.get(f'user_{self.id}_tags')
        if user_tags:
            has_old_type = any(isinstance(tag, str) for tag in user_tags)
        if not user_tags or has_old_type:
            user_tags = list(self.tags.all().exclude(tp=Tag.TYPES.junk))
            cache.set(f'user_{self.id}_tags', user_tags, 21600)
        return user_tags

    def has_tag(self, tag: str) -> bool:
        """Check whether this user has the specified tag or not."""
        return self.tags.filter(name=tag).exists()

    ####################################
    #  Project-specific Modifications  #
    ####################################
    @property
    def assigned_staff(self):
        return None

    def notify_email_change(self):
        pass

    def is_address_confirmed(self) -> bool:
        address_confirmed = self.get_verification_profile().address_confirmed
        if Settings.is_feature_active('kyc2'):
            return address_confirmed
        return address_confirmed and bool(self.phone)

    def has_new_unknown_login(self, duration: datetime.timedelta):
        return self.login_attempts.filter(
            is_known=False,
            is_successful=True,
            created_at__gte=ir_now() - duration,
        ).exists()

    @property
    def is_user_considered_in_production_test(self):
        return settings.IS_TESTNET and self.username in Settings.get_list('username_test_accounts')

class UserOTP(models.Model):
    OTP_TYPES = Choices(
        (1, 'email', _('Email')),
        (2, 'mobile', _('Mobile')),
        (3, 'phone', _('Phone')),
    )

    OTP_STATUS = Choices(
        (1, 'new', _('New')),
        (2, 'used', _('Used')),
        (3, 'disabled', _('Disabled')),
    )

    OTP_Usage = Choices(
        (1, 'tfa_removal', _('TFA Removal')),
        (2, 'email-verification', _('Email Verification')),
        (3, 'generic', _('Generic')),
        (4, 'change_phone_number', _('Change Phone Number')),
        (5, 'welcome_sms', _('Welcome SMS')),
        (6, 'anti_phishing_code', _('Anti Phishing Code')),
        (7, 'address_book', _('Address Book')),
        (8, 'deactivate_whitelist', _('Deactivate Whitelist Mode')),
        (9, 'social_user_set_password', _('Social User Set Password')),
        (10, 'user_merge', _('User Merge')),
        (11, 'grant_permission_to_financial_service', _('Grant Permission To Financial Service')),
        (12, 'staff_password_recovery', _('Staff Password Recovery')),
        (13, 'campaign', _('Campaign')),
    )
    USAGE_TRANSLATIONS = {
        OTP_Usage.address_book: 'افزودن آدرس به دفتر‌ آدرس',
        OTP_Usage.deactivate_whitelist: 'غیر‌فعا‌ل‌سازی حالت برداشت امن',
    }

    user = models.ForeignKey(User, related_name='otps', on_delete=models.CASCADE, null=True)
    code = models.CharField(max_length=6)
    otp_type = models.IntegerField(choices=OTP_TYPES)
    otp_usage = models.IntegerField(choices=OTP_Usage, null=True, blank=True)
    otp_status = models.IntegerField(choices=OTP_TYPES, default=OTP_STATUS.new)
    is_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    phone_number = models.CharField(max_length=12, null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = 'کد یکبار مصرف کاربر'
        verbose_name_plural = 'کدهای یکبار مصرف کاربر'

    @classmethod
    def active_otps(cls,
        user: Optional[User] = None,
        phone_number: Optional[str] = None,
        tp: Optional[int] = None,
        usage: Optional[int] = None,
    ) -> 'QuerySet[UserOTP]':
        if user is None and phone_number is None:
            return None
        condition = {'otp_status': cls.OTP_STATUS.new}
        if user is not None:
            condition['user'] = user
        else:
            condition['phone_number'] = phone_number
        otps = cls.objects.filter(**condition).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now()))
        if tp:
            otps = otps.filter(otp_type=tp)
        if usage:
            otps = otps.filter(otp_usage=usage)
        return otps

    @classmethod
    def generate_otp_code(cls,
        tp: int,
        user: Optional[User] = None,
        phone_number: Optional[str] = None,
        code: Optional[str] = None
    ) -> str:
        if user is None and phone_number is None:
            return None
        if code:
            otp = code
        else:
            otp = random_string_digit(6)
            if tp == UserOTP.OTP_TYPES.phone:
                otp = otp[:4].replace('0', '3')  # Hearing aid for phone OTP
        cls.active_otps(user=user, phone_number=phone_number, tp=tp).filter(code=otp).update(otp_status=cls.OTP_STATUS.disabled)
        return otp

    @classmethod
    def create_otp(cls,
                   tp: int,
                   usage: Optional[int] = None,
                   otp: Optional[str] = None,
                   user: Optional[User] = None,
                   phone_number: Optional[str] = None,
                   ) -> Optional['UserOTP']:
        if user is None and phone_number is None:
            return None
        if tp not in cls.OTP_TYPES:
            return None
        if not usage:
            usage = cls.OTP_Usage.generic
        if usage not in cls.OTP_Usage:
            return None
        expires_at = now() + datetime.timedelta(minutes=30)
        otp = cls.generate_otp_code(
            user=user,
            phone_number=phone_number,
            tp=tp,
            code=otp
        )

        otp_obj = cls.objects.create(
            user=user,
            code=otp,
            otp_type=tp,
            otp_usage=usage,
            expires_at=expires_at,
            phone_number=phone_number,
        )
        return otp_obj

    def send(self) -> bool:
        try:
            if self.otp_type == self.OTP_TYPES.mobile:
                if self.otp_usage == self.OTP_Usage.tfa_removal:
                    UserSms.objects.create(
                        user=self.user,
                        tp=UserSms.TYPES.tfa_disable,
                        to=self.user.mobile,
                        text=self.code,
                        template=UserSms.TEMPLATES.tfa_disable,
                    )
                elif self.otp_usage == self.OTP_Usage.change_phone_number:
                    UserSms.objects.create(
                        user=self.user,
                        tp=UserSms.TYPES.verify_phone,
                        to=self.phone_number or self.user.mobile,
                        text=self.code,
                        template=UserSms.TEMPLATES.verification,
                    )
                    change_obj = ChangeMobileRequest.get_active_request(self.user)
                    if change_obj and change_obj.status == ChangeMobileRequest.STATUS.new:
                        EmailManager.send_email(
                            self.user.email,
                            'otp',
                            data={'otp': self.code},
                            priority='high',
                        )
                elif self.otp_usage == self.OTP_Usage.welcome_sms:
                    UserSms.objects.create(
                        user=self.user,
                        tp=UserSms.TYPES.verify_phone,
                        to=self.phone_number or self.user.mobile,
                        text=self.code,
                        template=UserSms.TEMPLATES.welcome,
                    )
                elif self.otp_usage == self.OTP_Usage.campaign:
                    UserSms.objects.create(
                        user=self.user,
                        tp=UserSms.TYPES.verify_phone,
                        to=self.phone_number or self.user.mobile,
                        text=self.code,
                        template=UserSms.TEMPLATES.verification,
                    )
                else:
                    # TODO: Move normal mobile code to new OTP system here
                    report_event('Unknown OTP SMS Send')
                    return False
            elif self.otp_type == self.OTP_TYPES.email:
                email_template = 'otp'
                data = {'otp': self.code}
                if self.otp_usage == self.OTP_Usage.tfa_removal:
                    email_template = 'tfa_otp'
                EmailManager.send_email(
                    self.user.email,
                    email_template,
                    data=data,
                    priority='high',
                )
            self.is_sent = True
            self.save()
            return True
        except:
            report_exception()
            return False

    @classmethod
    def verify(cls, code: str, tp: int, usage: int, user: Optional[User] = None,
               phone_number: Optional[str] = None, ) -> Tuple[Optional['UserOTP'], Optional[str]]:
        # todo: check core translation
        if user is None and phone_number is None:
            return None, 'both user and phone number are None'
        condition = {
            'code': code,
            'otp_type': tp,
            'otp_usage': usage,
        }
        if user is not None:
            condition['user'] = user
        else:
            condition['phone_number'] = phone_number

        error = None
        otp_obj = cls.objects.filter(**condition).order_by('-created_at').first()
        if not otp_obj:
            error = 'not found'
        elif otp_obj.otp_status != cls.OTP_STATUS.new:
            if otp_obj.otp_status == cls.OTP_STATUS.used:
                error = 'already used'
            elif otp_obj.otp_status == cls.OTP_STATUS.disabled:
                error = 'disabled'
            else:
                error = 'invalid status'
        elif otp_obj.expires_at and now() > otp_obj.expires_at:
            error = 'expired'

        if error:
            return None, error
        return otp_obj, None

    def disable_otp(self):
        self.otp_status = self.OTP_STATUS.disabled
        self.expires_at = now()
        self.save()

    def mark_as_used(self):
        self.otp_status = self.OTP_STATUS.used
        self.expires_at = now()
        self.save(update_fields=['expires_at', 'otp_status'])
        if self.user:
            self.user.otp = None
            self.user.save(update_fields=['otp'])

    @property
    def usage_translation(self) -> Optional[str]:
        return self.USAGE_TRANSLATIONS.get(self.otp_usage)

    @classmethod
    def get_or_create_otp(
        cls,
        tp: int,
        usage: Optional[int] = None,
        otp: Optional[str] = None,
        user: Optional[User] = None,
        phone_number: Optional[str] = None,
    ) -> Optional['UserOTP']:
        active_otp_qs = cls.active_otps(user=user, usage=usage, tp=tp)
        if active_otp_qs:
            return active_otp_qs.order_by('created_at').last()

        return cls.create_otp(tp=tp, usage=usage, user=user, otp=otp, phone_number=phone_number)


class CompanyDetail(models.Model):
    COMPANY_TYPE = Choices(
        (1, 'PrivatelyHeld', 'سهامی خاص'),
        (2, 'PubliclyHeldCompany', 'شرکت سهامی عام'),
        (3, 'PrivatelyHeldCompany', 'شرکت سهامی خاص'),
        (4, 'LimitedLiabilityCompany', 'شرکت با مسئولیت محدود'),
        (5, 'GeneralPartnershipCompany', 'شرکت تضامنی'),
        (6, 'SelfRelativeCompany', 'شرکت نسبی'),
        (7, 'CooperativeCompnay', 'شرکت تعاونی'),
        (8, 'NonbusinessCompany', 'شرکت غیرتجاری'),
    )

    company_type = models.IntegerField(choices=COMPANY_TYPE, default=None, null=True, blank=True,
                                       verbose_name='نوع شرکت')
    activity_field = models.CharField(max_length=30, default=None, null=True, blank=True, verbose_name='زمینه ی فعالیت')
    main_owner = models.ForeignKey("User", null=True, blank=True, on_delete=models.SET_NULL, related_name='+',
                                   verbose_name='نماینده', )
    regular_owners = models.ManyToManyField("User", blank=True, related_name='+', verbose_name='صاحب امضا ها')
    company = models.OneToOneField("User", null=True, blank=True, on_delete=models.CASCADE,
                                   related_name='company_detail', unique=True)

    def company_type_name(self):
        if self.company_type:
            return self.COMPANY_TYPE[self.company_type]
        return None

    def company_user_documents_waiting(self):
        return ' - '.join(set([x.name for x in self.company.company_user_documents.filter(status='0')]))

    def company_user_documents_not_sent(self):
        docs_dict = {
            '1': 'اگهی تاسیس',
            '2': 'اساسنامه',
            '3': 'اگهی تغییرات',
            '4': 'معرفی نامه',
            '5': 'کارت ملی نماینده',
            '6': 'گواهی امضا',
            '7': 'کد اقتصادی',
            '8': 'سایر مدارک',
        }
        query = self.company.company_user_documents.filter(Q(status='0') | Q(status='1')).values('type')
        all_set = {'1', '2', '3', '4', '5', '6', '7'}
        type_list = []
        for q in query:
            type_list.append(q.get('type'))
        return ' - '.join([docs_dict[x] for x in all_set - set(type_list)])

    @property
    def company_user_documents_experts(self):
        return ' - '.join(set([x.expert.get_full_name() for x in self.company.company_user_documents.filter(Q(status='1') | Q(status='2'))]))


class UserRestriction(models.Model):
    RESTRICTION = Choices(
        (10, 'WithdrawRequest', 'Withdraw'),
        (11, 'ShetabDeposit', 'Shetab Deposit'),
        (12, 'Gateway', 'Gateway'),
        (13, 'Trading', 'Trading'),
        (14, 'WithdrawRequestCoin', 'Withdraw Coin'),
        (15, 'WithdrawRequestRial', 'Withdraw Rial'),
        (16, 'Position', 'Position'),
        (17, 'Leverage', 'Leverage'),
        (18, 'StakingParticipation', 'مشارکت استیکینگ'),
        (19, 'StakingRenewal', 'تغییر وضعیت تمدید خودکار استیکینگ'),
        (20, 'StakingCancellation', 'لغو آنی استیکینگ'),
        (21, 'IranAccessLogin', 'Login restricted to Iran Only'),
        (22, 'ChangeMobile', 'Change Mobile'),
        (23, 'Convert', 'Convert'),
    )

    user = models.ForeignKey(User, related_name='restrictions', on_delete=models.CASCADE)
    restriction = models.IntegerField(choices=RESTRICTION)
    source = models.CharField(choices=Services.choices(), max_length=50, null=True, blank=True)
    ref_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(db_index=True, default=now, null=True, blank=True)

    # Admin fields
    considerations = models.TextField(default='', blank=True, null=True,
                                      help_text='این ملاحظات برای کاربر قابل مشاهده نیست', verbose_name='ملاحظات ادمین')

    description = models.TextField(blank=True, null=True, help_text='این توضیحات برای نمایش به کاربر میباشد')

    class Meta:
        verbose_name = 'محدودیت کاربر'
        verbose_name_plural = verbose_name
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'restriction', 'source', 'ref_id'],
                name='user_restriction_unique_user_restriction_source_ref_id',
                condition=models.Q(
                    source__isnull=False,
                    ref_id__isnull=False,
                ),
            )
        ]

    @classmethod
    def is_restricted(cls, user, *restrictions):
        restrictions = [
            getattr(cls.RESTRICTION, restriction) if isinstance(restriction, str) else restriction
            for restriction in restrictions
        ]
        return cls.objects.filter(user=user, restriction__in=restrictions).exists()

    @classmethod
    def get_restriction(cls, user: User, restriction: Union[str, int]) -> Optional['UserRestriction']:
        if isinstance(restriction, str):
            restriction = getattr(cls.RESTRICTION, restriction)
        return cls.objects.filter(user=user, restriction=restriction).first()

    @classmethod
    def get_restrictions(cls, user: User, *restrictions: Tuple[Union[int, str], ...]):
        restrictions = [
            getattr(cls.RESTRICTION, restriction) if isinstance(restriction, str) else restriction
            for restriction in restrictions
        ]
        return cls.objects.filter(user=user, restriction__in=restrictions)

    @transaction.atomic
    def delete_with_removals(self, source: Services = None):
        if source:
            if self.source != source:
                raise UserRestrictionRemovalNotAllowed('You are not allowed to remove this restriction')
            UserRestrictionChangeHistory.create(
                change_type=UserRestrictionChangeHistory.CHANGE_TYPE_CHOICES.remove,
                user_restriction=self,
                source=source,
            )

        UserRestrictionRemoval.objects.filter(
            restriction=self,
            is_active=True,
            ends_at__lte=now(),
        ).update(is_active=False)

        return self.delete()

    @classmethod
    def add_restriction(
        cls,
        user,
        restriction,
        considerations=None,
        duration=None,
        description: UserRestrictionsDescription = None,
        source=None,
        ref_id=None,
    ):
        """Create a restriction of given type for the user. This method only creates
        a restriction if there is no existing restriction of the same kind for the
        user.

            If the restriction is new, also an AdminConsideration is created to describe
            the restriction.

            If duration is given, a UserRestrictionRemoval is also created or updated,
            to remove the restriction on its end time.

            if internal_service is given and the restriction is new, a UserRestrictionChangeHistory
            is also created
        """
        description = description.value if description else None
        description = (
            description.format(duration=int(duration.total_seconds() / 3600))
            if description and duration
            else description
        )

        if isinstance(restriction, str):
            restriction = getattr(cls.RESTRICTION, restriction)
        created = False
        admin_user_id = 1000
        try:
            restriction_obj = cls.objects.get(user=user, restriction=restriction, source=source, ref_id=ref_id)
        except cls.MultipleObjectsReturned:
            restriction_obj = (
                cls.objects.filter(user=user, restriction=restriction, source=source, ref_id=ref_id)
                .order_by('id')
                .first()
            )
        except cls.DoesNotExist:
            created = True
            restriction_obj = cls.objects.create(
                user=user,
                restriction=restriction,
                considerations=considerations,
                description=description,
                source=source,
                ref_id=ref_id,
            )

        admin_consideration = 'محدودیت: ایجاد محدودیت' + ' ' + restriction_obj.get_restriction_display()
        if considerations:
            admin_consideration += ' --- ملاحظات: ' + considerations
        content_type = ContentType.objects.get(model='user')
        AdminConsideration.objects.create(
            admin_user_id=admin_user_id,
            user=user,
            content_type=content_type,
            object_id=user.id,
            consideration=admin_consideration,
        )

        if not created and considerations:
            restriction_obj.considerations += f' --- + --- {considerations}'
            restriction_obj.save(update_fields=['considerations'])

        # Schedule restriction removal for temporary restrictions
        if duration:
            if created:
                UserRestrictionRemoval.objects.create(
                    admin_user_id=admin_user_id,
                    restriction=restriction_obj,
                    is_active=True,
                    ends_at=now() + duration,
                )
            else:
                _end_at = ir_now() + duration
                removal = UserRestrictionRemoval.objects.filter(restriction=restriction_obj, ends_at__lt=_end_at)
                if removal.exists():
                    removal.update(ends_at=_end_at)
                    restriction_obj.description = description
                    restriction_obj.save(update_fields=['description'])

        # Remove RestrictionRemoval when user has temporary restriction, if the restriction is permanent
        if not duration and not created:
            UserRestrictionRemoval.objects.filter(restriction=restriction_obj).update(is_active=False)
            restriction_obj.description = description
            restriction_obj.save(update_fields=['description'])

        if source and created:
            UserRestrictionChangeHistory.create(
                user_restriction=restriction_obj,
                change_type=UserRestrictionChangeHistory.CHANGE_TYPE_CHOICES.add,
                source=source,
            )

        return restriction_obj

    @classmethod
    def freeze_user(cls, user_id: int) -> None:
        """This Method adds every restriction on the given user and disables all
            existing scheduled restriction removals. In other words, this method completely locks a user's account.
             This Method had been used in:
                1- Vip-credit: For uesrs with debt to asset ratio
                    greater than 2/3,user accounts will be freezed
                    (https://docs.google.com/document/d/1VBzljDeME1ti_bX31PkdS3K_De0NHTWwIRUXFVFqTTw/edit).
        """
        user = User.objects.get(pk=user_id)
        for restriction in cls.RESTRICTION._db_values:
            cls.add_restriction(user, restriction)


    def get_withdraw_default_description(self):
        withdraw_description_map = {
            self.RESTRICTION.WithdrawRequest: UserRestrictionsDescription.WITHDRAW_DEFAULT.value,
            self.RESTRICTION.WithdrawRequestRial: UserRestrictionsDescription.WITHDRAW_RIAL_DEFAULT.value,
            self.RESTRICTION.WithdrawRequestCoin: UserRestrictionsDescription.WITHDRAW_COIN_DEFAULT.value,
        }
        return withdraw_description_map.get(self.restriction, None)



class UserRestrictionChangeHistory(models.Model):
    """This model keeps track of changes on user restriction for Internal APIs"""

    CHANGE_TYPE_CHOICES = Choices(
        (1, 'add', 'Added'),
        (2, 'remove', 'Removed'),
    )
    change_type = models.PositiveSmallIntegerField(choices=CHANGE_TYPE_CHOICES)
    change_by_service = models.CharField(choices=Services.choices(), max_length=50)
    restriction = models.IntegerField(choices=UserRestriction.RESTRICTION)
    ref_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    # relations
    user_restriction = models.ForeignKey(UserRestriction, on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    @classmethod
    def create(
        cls, change_type: int, user_restriction: UserRestriction, source: Services
    ) -> 'UserRestrictionChangeHistory':
        return cls.objects.create(
            change_type=change_type,
            change_by_service=source,
            user_restriction=user_restriction,
            user_id=user_restriction.user_id,
            restriction=user_restriction.restriction,
            ref_id=user_restriction.ref_id,
        )

class AppToken(models.Model):
    token = models.OneToOneField(Token, primary_key=True, on_delete=models.CASCADE)
    user_agent = models.CharField(max_length=255, blank=True)
    last_use = models.DateField(null=True, blank=True)


class EmailActivation(models.Model):
    """Email Confirmation Links

    TODO: Expire links after a reasonable time
    TODO: Cleanup old activation links
    """
    STATUS = Choices(
        (1, 'new', 'New'),
        (2, 'used', 'Used'),
        (3, 'expired', 'Expired'),
    )
    token = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name='email_activations', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    status = models.IntegerField(choices=STATUS, default=STATUS.new)


class PasswordRecovery(models.Model):
    STATUS = Choices(
        (1, 'new', 'New'), # Sent to Email or Mobile
        (8, 'expired', 'Expired'), # Expired
        (2, 'confirmed', 'Confirmed'), # Used successfully
    )
    token = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name='recovery_records', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    status = models.IntegerField(choices=STATUS, default=STATUS.new, db_index=True)
    otp = models.CharField(max_length=6, null=True, blank=True, default=functools.partial(random_string_digit, 6))

    class Meta:
        verbose_name = 'بازیابی گذرواژه'
        verbose_name_plural = verbose_name

    @property
    def should_be_expired(self):
        return ir_now() - self.created_at > datetime.timedelta(minutes=10)

    @classmethod
    def get_or_create(cls, username) -> 'PasswordRecovery':
        user = User.by_email_or_mobile(username)
        instance, _ = cls.objects.get_or_create(
            user=user,
            status=cls.STATUS.new,
        )
        if instance.should_be_expired:
            instance.status = cls.STATUS.expired
            instance.save(update_fields=['status',])
            return cls.objects.create(
                user=user,
            )
        return instance

    def send(self, username: str, domain: str=None) -> None:
        if validate_email(username):
            accepted_domains = ['https://' + prod_domain for prod_domain in settings.PROD_DOMAINS]
            if not domain or (settings.IS_PROD and domain not in accepted_domains):
                domain = settings.PROD_FRONT_URL
            else:
                domain += '/'

            EmailManager.send_email(
                self.user.email,
                'reset_password',
                data={
                    'token': self.token.hex,
                    'domain': domain,
                },
                priority='high',
            )
        if validate_mobile(username):
            UserSms.objects.create(
                user=self.user,
                tp=UserSms.TYPES.verify_password_recovery,
                to=self.user.mobile,
                text=self.otp,
                template=UserSms.TEMPLATES.password_recovery,
            )

    @classmethod
    def get(cls, username: str, token: str) -> 'PasswordRecovery':
        try:
            instance: PasswordRecovery = cls.objects.get(**{
                'user': User.by_email_or_mobile(username),
                'token' if validate_email(username) else 'otp' : token,
            })
        except (
            ValidationError,
            PasswordRecovery.DoesNotExist,
        ):
            raise PasswordRecoveryError('توکن وارد شده نامعتبر است.')
        if instance.status == cls.STATUS.confirmed:
            raise PasswordRecoveryError('این توکن قبلا برای بازیابی رمز استفاده شده است. لطفا مجددا درخواست بازیابی بدهید.')
        if instance.status == cls.STATUS.expired:
            raise PasswordRecoveryError('این توکن منقضی شده است. لطفا مجددا درخواست بازیابی بدهید.')
        if instance.should_be_expired:
            instance.status = cls.STATUS.expired
            instance.save(update_fields=['status',])
            raise PasswordRecoveryError('این توکن منقضی شده است. لطفا مجددا درخواست بازیابی بدهید.')
        return instance


class Confirmed(models.Model):
    STATUS = Choices(
        (0, 'new', 'جدید'),
        (1, 'confirmed', 'تایید شده'),
        (2, 'rejected', 'رد شده'),
        (3, 'initial_approval', 'تایید اولیه')
    )

    confirmed = models.BooleanField(default=False)
    status = models.IntegerField(choices=STATUS, default=STATUS.new)

    class Meta:
        abstract = True

    @property
    def status_codename(self):
        for status in ['new', 'confirmed', 'rejected']:
            if self.status == getattr(self.STATUS, status):
                return status
        return 'unknown'

    def update_status(self, save=True):
        if self.confirmed and self.status == self.STATUS.new:
            self.status = self.STATUS.confirmed
            if save:
                self.save(update_fields=['status'])

    @classmethod
    def get_pending_requests(cls, user):
        return cls.objects.filter(user=user, status=cls.STATUS.new)

    @classmethod
    def get_confirmed_requests(cls, user):
        return cls.objects.filter(user=user, confirmed=True)

    @classmethod
    def has_confirmed_requests(cls, user):
        return cls.get_confirmed_requests(user).count() > 0


class APIVerified(models.Model):
    api_verification = models.TextField(blank=True, null=True)

    api_verification_verbose_message: str
    updating_from_cron: bool = False

    class Meta:
        abstract = True

    def api_verification_json(self) -> str:
        try:
            value = json.loads(self.api_verification or '{}')
        except:
            return 'Invalid Value'
        return json.dumps(value, indent=4, ensure_ascii=False)

    def get_api_verification_as_dict(self) -> dict:
        return json.loads(self.api_verification or '{}')

    def is_api_verified(self):
        if not self.api_verification:
            return None
        try:
            verification = json.loads(self.api_verification)
        except:
            return False
        if not isinstance(verification, dict):
            return False
        return verification.get('verification') is True

    def call_verification_api(self, **_):
        raise NotImplementedError

    def call_testnet_verification_api(self):
        return True

    def update_api_verification(self, force_update=False, retry=0):
        if self.api_verification and not force_update:
            return

        user: User = getattr(self, 'user', None)
        if settings.IS_PROD or force_update or (user and user.is_user_considered_in_production_test):
            # Use Finnotech API
            try:
                if isinstance(self, VerificationRequest):
                    response = self.call_verification_api(retry=retry)
                else:
                    response = self.call_verification_api()
            except CaptchaProviderError as ex:
                metric_incr('metric_verification_api_failed', labels=(ex.provider,))
            except ValueError:
                report_exception()
                return
            if not response:
                return
            result = response['result']
            confidence = response['confidence']
            api_response = response['apiresponse']
            api_response['verification'] = result
            # Debt: Transient attribute
            self.api_verification_verbose_message = response.get('message')

        # Is non-production environments, accept identity without checking
        elif self.call_testnet_verification_api():
            result = True
            confidence = 100
            api_response = {'verification': True}
        else:
            result = False
            confidence = 0
            api_response = {'verification': False}

        update_fields = ['api_verification']
        is_confirmed = result is True
        if isinstance(self, Confirmed):
            if self.status == self.STATUS.new and confidence == 100:
                self.confirmed = is_confirmed
                self.status = self.STATUS.confirmed if is_confirmed else self.STATUS.rejected
                update_fields += ['confirmed', 'status']
            self.api_verification = json.dumps(api_response)
        elif isinstance(self, VerificationRequest):
            if self.status != self.STATUS.confirmed and confidence == 100:
                self.status = self.STATUS.confirmed if is_confirmed else self.STATUS.rejected
                update_fields += ['status']
            if self.api_verification and self.tp == VerificationRequest.TYPES.auto_kyc:
                api_verif = json.loads(self.api_verification)
                api_verif.update(api_response)
                self.api_verification = json.dumps(api_verif)
            else:
                self.api_verification = json.dumps(api_response)

        self.save(update_fields=update_fields)

    api_verification_json.short_description = 'نتیجه استعلام'
    is_api_verified.short_description = 'نتیجه استعلام'
    is_api_verified.boolean = True


class KVData(models.Model):
    kv_data = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True

    def get_kv(self, k, default=None):
        obj = json.loads(self.kv_data or '{}')
        return obj.get(k, default)

    def set_kv(self, k, v, save=False):
        obj = json.loads(self.kv_data or '{}')
        obj[k] = v
        self.kv_data = json.dumps(obj)
        if save:
            self.save_kv()

    def save_kv(self):
        self.save(update_fields=['kv_data'])

    def kv_json(self):
        try:
            value = json.loads(self.kv_data or '{}')
        except:
            return 'Invalid Value'
        return json.dumps(value, indent=4, ensure_ascii=False)

    kv_json.short_description = 'مقادیر ذخیره شده'


class BaseBankAccount(Confirmed, APIVerified, KVData):
    BANK_ID = Choices(
        (10, 'centralbank', 'بانک‌مرکزی'),
        (11, 'sanatomadan', 'صنعت‌و‌معدن'),
        (12, 'mellat', 'ملت'),
        (13, 'refah', 'رفاه'),
        (14, 'maskan', 'مسکن'),
        (15, 'sepah', 'سپه'),
        (16, 'keshavarzi', 'کشاورزی'),
        (17, 'melli', 'ملی'),
        (18, 'tejarat', 'تجارت'),
        (19, 'saderat', 'صادرات'),
        (20, 'toseesaderat', 'توسعه‌صادرات'),
        (21, 'postbank', 'پست‌بانک'),
        (22, 'toseetaavon', 'توسعه‌تعاون'),
        (51, 'tosee', 'موسسه‌اعتباری‌توسعه'),
        (52, 'ghavamin', 'قوامین'),
        (53, 'karafarin', 'کار‌آفرین'),
        (54, 'parsian', 'پارسیان'),
        (55, 'eghtesadenovin', 'اقتصاد‌نوین'),
        (56, 'saman', 'سامان'),
        (57, 'pasargad', 'پاسارگاد'),
        (58, 'sarmayeh', 'سرمایه'),
        (59, 'sina', 'سینا'),
        (60, 'mehreiran', 'مهر‌ایران'),
        (61, 'shahr', 'شهر'),
        (62, 'ayandeh', 'آینده'),
        (63, 'ansar', 'انصار'),
        (64, 'gardeshgari', 'گردشگری'),
        (65, 'hekmateiraninan', 'حکمت‌ایرانیان'),
        (66, 'dey', 'دی'),
        (69, 'iranzamin', 'ایران‌زمین'),
        (70, 'resalat', 'رسالت'),
        (73, 'kowsar', 'کوثر'),
        (75, 'melal', 'موسسه‌ملل'),
        (78, 'khavarmiane', 'خاورمیانه'),
        (80, 'noor', 'موسسه‌نور'),

        (997, 'payir', 'پی'),
        (998, 'jibit', 'جیبیت'),
        (999, 'vandar', 'وندار'),
    )

    owner_name = models.CharField(max_length=100)
    bank_name = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    bank_id = models.IntegerField(choices=BANK_ID, null=True, blank=True, help_text='شناسه بانک')
    is_deleted = models.BooleanField(default=False)
    is_temporary = models.BooleanField(default=False)

    # Admin fields
    considerations = models.TextField(default='', blank=True, null=True,
                                      help_text='این ملاحظات برای کاربر قابل مشاهده نیست', verbose_name='ملاحظات ادمین')

    # the following two fields are just contracts that should be kept in the child classes (do more of these)
    user: User
    web_engage_class_for_confirmation: Type[WebEngageKnownUserEvent]
    tracker: FieldTracker

    class Meta:
        abstract = True

    def update_bank_name(self):
        if self.bank_id:
            self.bank_name = self.get_bank_id_display()

    def soft_delete(self):
        self.is_deleted = True
        self.confirmed = False
        self.status = self.STATUS.rejected
        self.save(update_fields=['is_deleted', 'confirmed', 'status'])

    def check_auto_tags(self):
        # delete open_all tag
        tag_open_all, created = Tag.objects.get_or_create(name=auto_tags['open_all'], tp=Tag.TYPES.kyc)
        tag_bank, created_tag = Tag.objects.get_or_create(name=auto_tags['open_bank'], tp=Tag.TYPES.kyc)
        system_user = User.objects.filter(pk=1000).first()
        UserTag.objects.filter(user=self.user, tag=tag_open_all).delete()
        if BankAccount.objects.filter(user=self.user, status=self.STATUS.confirmed).exists() or \
            BankCard.objects.filter(user=self.user, status=self.STATUS.confirmed).exists():
            UserTag.objects.filter(user=self.user, tag=tag_bank).delete()

        else:
            obj = UserTag.objects.filter(user=self.user, tag=tag_bank).exists()
            if not obj and system_user:
                auto_tag_created = UserTag.objects.create(user=self.user, tag=tag_bank)
                content_type = ContentType.objects.get(model='usertag')
                AdminConsideration.objects.create(admin_user=system_user,
                                                  user=self.user,
                                                  content_type=content_type,
                                                  object_id=auto_tag_created.id,
                                                  consideration=auto_tags['open_bank'])

    @property
    def has_confirmed_status(self):
        return self.confirmed and self.status == self.STATUS.confirmed

    @property
    def has_rejected_status(self):
        return (not self.confirmed) and self.status == self.STATUS.rejected


class BankCard(BaseBankAccount):
    user = models.ForeignKey(User, related_name='bank_cards', on_delete=models.CASCADE)
    card_number = models.CharField(max_length=16)
    web_engage_class_for_confirmation = BankCardVerifiedWebEngageEvent

    tracker = FieldTracker(fields=['confirmed', 'status'])

    class Meta:
        verbose_name = 'کارت بانکی'
        verbose_name_plural = verbose_name

    def __str__(self):
        return 'Card#{}: {}'.format(self.card_number[-4:], self.owner_name)

    def get_card_number_display(self):
        s = ''
        for i, ch in enumerate(self.card_number or ''):
            if i > 0 and i % 4 == 0:
                s += '-'
            s += ch
        return s

    def is_valid(self):
        if not self.card_number or not self.owner_name or not self.bank_name:
            return False
        self.card_number = self.card_number.replace('-', '')
        if len(self.card_number) != 16:
            return False
        return True

    def check_number_matches(self, other_number):
        if len(self.card_number) != len(other_number):
            return False
        confidence = 0
        for i in range(len(self.card_number)):
            if other_number[i] == '*':
                continue
            if self.card_number[i] != other_number[i]:
                return False
            confidence += 1
        return confidence >= 6

    def call_verification_api(self, **_):
        if not self.user.is_identity_verified:
            return None
        return VerificationClient().is_user_owner_of_bank_card(self)

    @classmethod
    def get_user_bank_cards(cls, user):
        return list(cls.get_confirmed_requests(user))


class BankAccountManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().exclude(account_number=settings.VANDAR_ID_DEPOSIT_PREFIX)


class VandarDepositIdManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(account_number=settings.VANDAR_ID_DEPOSIT_PREFIX)


class BankAccount(BaseBankAccount):
    user = models.ForeignKey(User, related_name='bank_accounts', on_delete=models.CASCADE)
    account_number = models.CharField(max_length=25)
    shaba_number = models.CharField(max_length=26, db_index=True)
    is_from_bank_card = models.BooleanField(default=False)  # indicates if the shaba number was received from API

    objects = BankAccountManager()
    vandar_objects = VandarDepositIdManager()
    web_engage_class_for_confirmation = BankAccountVerifiedWebEngageEvent

    tracker = FieldTracker(fields=['confirmed', 'status'])

    BLU_BANK_IBAN_PATTERN = re.compile('^IR\d{6}6118\d{14}')

    class Meta:
        verbose_name = 'حساب بانکی'
        verbose_name_plural = verbose_name

        indexes = (models.Index(fields=['account_number', 'confirmed']),)

    def __str__(self):
        return 'Account#{}: {}'.format(self.account_number, self.owner_name)

    @property
    def virtual(self):
        """Whether this is a virtual bank account, e.g. a Vandar internal account."""
        return self.bank_id and self.bank_id >= 999

    @property
    def display_name(self):
        return '{}: {}'.format(self.get_bank_id_display(), self.account_number if self.virtual else self.shaba_number)

    @property
    def is_blu(self):
        return self.bank_id == self.BANK_ID.saman and self.BLU_BANK_IBAN_PATTERN.match(self.shaba_number)

    def is_shaba_valid(self):
        if not self.shaba_number:
            return False
        if len(self.shaba_number) != 26:
            return False
        if not self.shaba_number.startswith('IR'):
            return False
        bank_id = int(self.shaba_number[4:7])
        if bank_id not in BankAccount.BANK_ID:
            return False
        return True

    def validate(self):
        if not self.account_number or len(self.account_number) > 25:
            return 'InvalidAccountNumber'
        if not self.owner_name or len(self.owner_name) > 100:
            return 'InvalidAccountHolder'
        if not self.virtual and not self.is_shaba_valid():
            return 'InvalidShaba'
        return 'ok'

    def is_valid(self):
        error_message = self.validate()
        if error_message != 'ok':
            return False
        return True

    def call_verification_api(self, **_):
        if not self.user.is_identity_verified or self.virtual:
            return None
        return VerificationClient().is_user_owner_of_bank_account(self)

    def update_bank_id(self):
        new_bank_id = None
        if self.is_shaba_valid():
            new_bank_id = int(self.shaba_number[4:7])    # shaba format => IRXXbidXXXXXXXXXXXXXXXXX
        if self.bank_id == new_bank_id or self.virtual:
            return
        self.bank_id = new_bank_id
        self.update_bank_name()
        self.save(update_fields=('bank_id', 'bank_name'))

    @staticmethod
    def generate_fake_shaba(bank_id, account_id):
        if not bank_id or not account_id or bank_id < 900:
            return ''
        account_number = int(shake_128(account_id.encode()).hexdigest(7).upper(), 16)
        checksum = - int(f'{bank_id}{account_number:0>19}182700') % 97 + 1
        return f'IR{checksum:0>2}{bank_id:0>3}{account_number:0>19}'

    @classmethod
    def get_user_bank_accounts(cls, user):
        return list(cls.get_confirmed_requests(user))

    @classmethod
    def get_generic_system_account(cls):
        user = User.get_generic_system_user()
        account_number = '88888888'
        shaba_number = 'IR000100000000000888888881'
        try:
            return cls.objects.get(
                user=user,
                shaba_number=shaba_number,
            )
        except cls.DoesNotExist:
            return cls.objects.create(
                user=user,
                account_number=account_number,
                shaba_number=shaba_number,
                owner_name='system',
                bank_name='بانک‌مرکزی',
                bank_id=10,
                confirmed=True,
                status=cls.STATUS.confirmed,
            )

    @classmethod
    def get_system_gift_account(cls):
        """returns system gift bank account"""
        return cls.objects.get(user=User.get_gift_system_user())

    def generate_account_number_combinations(s: str) -> list:
        parts = s.split('.')

        separator_count = len(parts) - 1  # The number of separators is one less than the number of parts
        separators = itertools.product(['.', '-'], repeat=separator_count)

        combinations = []
        for sep in separators:
            # Join the parts with the current combination of separators
            combined = parts[0]
            for i, separator in enumerate(sep):
                combined += separator + parts[i + 1]
            combinations.append(combined)

        return combinations


class UserSms(models.Model):
    """ UserSms represents SMS messages sent to users
    """
    objects = BulkCreateWithSignalManager()

    TASK_ID_CACHE_KEY = 'send_sms_task_{sms_id}'

    TYPES = Choices(
        (0, 'manual', 'Manual SMS'),
        (1, 'verify_phone', 'Verify Phone'),
        (2, 'verify_withdraw', 'Verify Withdraw'),
        (3, 'process', 'Process'),
        (4, 'android', 'android'),
        (7, 'tfa_enable', 'Enable TFA'),
        (5, 'tfa_disable', 'Disable TFA'),
        (6, 'price_alert', 'Price Alert'),
        (7, 'gift', 'Gift OTP'),
        (8, 'gift_password', 'Gift Password'),
        (8, 'gift_batch', 'Gift Batch'),
        (10, 'new_device_withdrawal_restriction_notif', 'Coin Withdrawal Restriction Due To New Device Notification'),
        (11, 'verify_password_recovery', 'Verify Password Recovery'),
        (12, 'change_password_notif', 'Verify Password Recovery'),
        (13, 'deactivate_whitelist_mode', 'Deactivate Whitelist Mode'),
        (14, 'new_address_in_address_book', 'New Address In AddressBook'),
        (15, 'verify_new_address', 'Verify New Address'),
        (16, 'affirm_withdraw', 'Affirm Withdraw'),
        (17, 'deactivate_whitelist_mode_otp', 'Send OTP to Deactivate Whitelist Mode'),
        (18, 'social_user_set_password', 'Social User Set Password'),
        (19, 'social_trade_leadership_acceptance', 'Social Trade Leadership Request Acceptance'),
        (20, 'social_trade_leadership_rejection', 'Social Trade Leadership Request Rejection'),
        (21, 'user_merge', 'User Merge'),
        (22, 'social_trade_notify_leader_of_deletion', 'Social Trade Notification to Leader for Deletion'),
        (
            23,
            'social_trade_notify_subscribers_of_leader_deletion',
            'Social Trade Notification to Subscribers for Leader Deletion',
        ),
        (
            24,
            'social_trade_notify_trials_of_leader_deletion',
            'Social Trade Notification to Trials for Leader Deletion',
        ),
        (25, 'kyc', 'KYC'),
        (26, 'kyc_parameter', 'KYC Parameter'),
        (27, 'grant_financial_service', 'Grant Financial Service'),
        (28, 'staff_user_password_recovery', 'Staff User Password Recovery'),
        (29, 'abc_margin_call', 'ABC Margin Call'),
        (30, 'abc_margin_call_liquidate', 'ABC Margin Call Liquidate'),
        (31, 'abc_liquidate_by_provider', 'ABC Liquidate By Provider'),
        (32, 'direct_debit_create_contract', 'Direct Debit Create Contract Successfully'),
        (33, 'direct_debit_remove_contract', 'Direct Debit Remove Contract Successfully'),
        (34, 'direct_debit_auto_cancel', 'Direct Debit Cancel Contract For Some Reason'),
        (35, 'abc_margin_call_adjustment', 'ABC Margin Call Adjustment'),
        (36, 'abc_debit_settlement', 'ABC Debit Settlement'),
        (37, 'direct_debit_deposit', 'Direct Deposit Successfully'),
        (38, 'abc_debit_card_issued', 'ABC Debit Card Issued'),
        (39, 'abc_debit_card_activated', 'ABC Debit Card Activated'),
        (40, 'cobank_deposit', 'Corporate Banking Deposit'),
        (41, 'api_key_create', 'API Key Creation'),
        (42, 'api_key_update', 'API Key Update'),
        (43, 'api_key_delete', 'API Key Deletion'),
    )
    TEMPLATES = OLD_SMSIR_TEMPLATES
    TEXTS = {
        TYPES.new_address_in_address_book: 'هشدار نوبیتکس!\nآدرس جدید به دفتر آدرس شما اضافه شد.',
        TYPES.affirm_withdraw: 'هشدار نوبیتکس!\nبرداشت به آدرس امن دفتر آدرس ثبت شد.',
    }
    CARRIERS = Choices(
        (0, 'restfulsms', 'رست فول اس ام اس'),
        (1, 'finnotext', 'فینوتکست'),
        (2, 'new_restfulsms', 'رست فول اس ام اس جدید'),
        (3, 'kavenegar', 'کاوه‌نگار'),
    )

    SMS_OTP_TEMPLATE = (
        TEMPLATES.welcome,
        TEMPLATES.verification,
        TEMPLATES.gift_redeem_otp,
        TEMPLATES.verify_new_address,
        TEMPLATES.deactivate_whitelist_mode_otp,
        TEMPLATES.user_merge_otp,
    )
    SMS_OTP_TYPES = (
        TYPES.tfa_disable,
        TYPES.staff_user_password_recovery,
        TYPES.verify_phone,
        TYPES.deactivate_whitelist_mode_otp,
        TYPES.user_merge,
        TYPES.verify_password_recovery,
        TYPES.social_user_set_password,
        TYPES.grant_financial_service,
        TYPES.verify_new_address,
        TYPES.tfa_enable,
        TYPES.verify_withdraw,
        TYPES.gift,
    )

    OTP_USAGE_TO_TYPE_TEMPLATE: typing.ClassVar = {
        UserOTP.OTP_Usage.grant_permission_to_financial_service: {
            'tp': TYPES.grant_financial_service,
            'template': TEMPLATES.grant_financial_service,
        },
    }

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(User, related_name='sent_sms_set', on_delete=models.CASCADE, null=True)
    admin = models.ForeignKey(User, related_name='sms_set', on_delete=models.CASCADE, null=True)
    tp = models.IntegerField(choices=TYPES)
    to = models.CharField(max_length=12)
    text = models.TextField()
    template = models.IntegerField(null=True, blank=True, choices=TEMPLATES, default=TEMPLATES.default)
    details = models.CharField(max_length=100, blank=True, default='')
    delivery_status = models.CharField(max_length=100, blank=True, null=True)
    provider_id = models.IntegerField(blank=True, null=True)
    carrier = models.IntegerField(null=True, blank=True, choices=CARRIERS, default=CARRIERS.restfulsms)
    tracking_id = models.UUIDField(null=True, blank=True, default=uuid.uuid4, editable=False)

    class Meta:
        verbose_name = 'پیامک کاربر'
        verbose_name_plural = verbose_name

    @property
    def text_display(self) -> str:
        if self.template:
            raw_text = self.TEMPLATES._display_map.get(self.template, 'UNKNOWN')
        else:
            raw_text = self.text
        return re.sub(r'\d{3,}', '…', raw_text)

    @property
    def sms_full_text(self) -> str:
        raw_text = self.text_display.replace('[', '{').replace(']', '}')
        keywords = [i[1] for i in Formatter().parse(raw_text) if i[1] is not None]
        variables = self.text.split('\n')
        return raw_text.format(**{k: v for k, v in zip(keywords, variables)})

    def get_receiving_numbers(self) -> List[str]:
        numbers = []
        for n in (self.to or '').split(','):
            n = n.strip()
            if n.startswith('+'):
                n = n[1:]
            if n.startswith('98'):
                n = n[2:]
            if not n.startswith('0'):
                n = '0' + n
            if len(n) != 11 or not n.startswith('09'):
                continue
            numbers.append(n)
        return numbers

    def _get_parameters_map(self):
        if not self.template:
            return {}
        parameters = re.findall(r'\[.*?\]', self.get_template_display())
        # removing brackets:
        parameters = [p[1:-1] for p in parameters]
        return dict(zip(parameters, self.text.split('\n')))

    def send(self):
        numbers = self.get_receiving_numbers()
        fast_send = self.template > 0
        if not numbers or not self.text:
            return
        if len(numbers) > 1 and fast_send:
            print('[Warning] FastSMS can be sent only to one number in each call, ignoring extra numbers')

        # Emulate SMS sending in test environments
        do_send_sms = settings.IS_PROD and Settings.get_flag('send_sms')
        if not do_send_sms:
            if not settings.IS_PROD:
                text = self.text
                if self.template:
                    text = self.get_template_display().replace('[', '{').replace(']', '}')
                    text = text.format(**self._get_parameters_map())
                if self.user is not None:
                    Notification.objects.create(
                        user=self.user,
                        message='شبیه‌سازی ارسال پیامک: {}'.format(text),
                    )
            self.details = 'Sent: faked'
            self.provider_id = 0
            self.delivery_status = 'Sent: faked'
            self.save(update_fields=['details', 'provider_id', 'delivery_status'])
            return

        SmsSender.send(self)

    @classmethod
    def get_verification_messages(cls, user: User) -> 'QuerySet[UserSms]':
        return cls.objects.filter(user=user, created_at__gte=now() - datetime.timedelta(minutes=20),
                                  tp=cls.TYPES.verify_phone)


class UserVoiceMessage(models.Model):
    TYPES = Choices(
        (0, 'manual', 'Manual message'),
        (1, 'verify_phone', 'Verify Phone'),
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(User, related_name='sent_voice_message_set', on_delete=models.CASCADE)
    admin = models.ForeignKey(User, related_name='voice_message_set', on_delete=models.CASCADE, null=True)
    tp = models.IntegerField(choices=TYPES)
    to = models.CharField(max_length=12)
    text = models.TextField()
    delivery_status = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        verbose_name = 'پیام صوتی'
        verbose_name_plural = verbose_name

    @property
    def text_display(self):
        if not getattr(self, 'is_private', False):
            return self.text
        if self.tp in [self.TYPES.verify_phone]:
            return 'محرمانه'
        return self.text

    def send(self):
        is_successful = False
        try:
            response = requests.post(
                'https://api.kavenegar.com/v1/{}/call/maketts.json'.format(settings.KAVENEGAR_API_KEY),
                data={
                    'receptor': self.to,
                    'message': self.text,
                },
                timeout=30,
            )
            data = response.json()
            status = data.get('return', {}).get('status')
            if status == 200:
                delivery_status = 'sent: ' + data['entries'][0]['statustext']
                is_successful = True
            else:
                delivery_status = 'error: ' + data.get('return', {}).get('message')
        except Exception as e:
            delivery_status = 'exception: ' + str(e)
        metric_incr('metric_api_voice_message__kavenegar_' + ('ok' if is_successful else 'failed'))
        self.delivery_status = delivery_status[:100]
        self.save(update_fields=['delivery_status'])

    @classmethod
    def get_verification_messages(cls, user):
        return cls.objects.filter(
            user=user,
            created_at__gte=now() - datetime.timedelta(minutes=20),
            tp=cls.TYPES.verify_phone,
        )


class VerificationProfile(models.Model):
    """
    provides user level verification services with the use of:

     -- confirmed email.
     -- confirmed mobile phone number.
     -- confirmed home phone number.
     -- confirmed identity.
     -- confirmed address.
     -- confirmed bank account.
     -- confirmed selfie photo.
     -- confirmed auto mobile phone ownership (future feature).

    for determination of user levels:

     1- is user level_0_ with confirmed email or mobile.
     2- is user level_1_ with mobile and identity.
     3- is user level_2_ with mobile, identity, location and (selfie or auto_kyc)
     4- inferring current user level status.
     5- inferring testnet( email, mobile, identity) confirmation status.

    """
    user = models.OneToOneField(User, related_name='verification_profile', verbose_name='کاربر',
                                on_delete=models.CASCADE)
    # Level0 Verifications
    email_confirmed = models.BooleanField(default=False, verbose_name='تایید ایمیل')
    # Level1 Verifications
    mobile_confirmed = models.BooleanField(default=False, verbose_name='تایید موبایل')
    identity_confirmed = models.BooleanField(default=False, verbose_name='تایید هویت')
    phone_confirmed = models.BooleanField(default=False, verbose_name='تایید تلفن')
    address_confirmed = models.BooleanField(default=False, verbose_name='تایید اطلاعات سکونتی')
    bank_account_confirmed = models.BooleanField(default=False, verbose_name='تایید اطلاعات بانکی')
    selfie_confirmed = models.BooleanField(default=False, verbose_name='تایید سلفی')
    mobile_identity_confirmed = models.BooleanField(null=True, default=None, verbose_name='تایید هویت صاحب موبایل')
    phone_code_confirmed = models.BooleanField(null=True, default=False, verbose_name='تایید خودکار تلفن')
    # Auto KYC Verifications
    identity_liveness_confirmed = models.BooleanField(default=False, verbose_name='تایید لایونس')
    identity_captcha_confirmed = models.BooleanField(default=False, verbose_name='تایید کپچا')

    # for each field `<name>` sets `_<name>` that stores the previous value
    confirmative_fields = [
        'email_confirmed',
        'mobile_confirmed',
        'identity_confirmed',
        'phone_confirmed',
        'address_confirmed',
        'bank_account_confirmed',
        'selfie_confirmed',
        'mobile_identity_confirmed',
        'phone_code_confirmed',
        'identity_liveness_confirmed',
        'identity_captcha_confirmed'
    ]
    tracker = FieldTracker(fields=confirmative_fields)

    class Meta:
        verbose_name = 'احراز هویت'
        verbose_name_plural = verbose_name

    def __str__(self):
        return 'VerificationProfile for {}: {}'.format(self.user, self.verification_status)

    @property
    def verification_status(self):
        if not self.email_confirmed:
            return User.VERIFICATION.none
        if not self.user.address or not self.mobile_confirmed or not self.identity_confirmed:
            return User.VERIFICATION.basic
        if not self.bank_account_confirmed:
            return User.VERIFICATION.full
        return User.VERIFICATION.extended

    @property
    def is_verified_level0(self):
        return self.email_confirmed or self.mobile_confirmed

    @property
    def is_verified_level1p(self):
        return False

    @property
    def is_verified_level1(self):
        if Settings.is_feature_active("kyc2"):
            return self.is_verified_level0 and self.mobile_confirmed and self.identity_confirmed

        if self.bank_account_confirmed:
            bank_confirmed = True
        else:
            bank_confirmed = BankAccount.has_confirmed_requests(self.user) and BankCard.has_confirmed_requests(
                self.user)
            if bank_confirmed:
                # Update calculated field if needed
                self.bank_account_confirmed = True
                self.save(update_fields=['bank_account_confirmed'])
        return all([
            self.is_verified_level0,
            self.mobile_confirmed,
            self.email_confirmed,
            self.identity_confirmed,
            bank_confirmed,
        ])

    @property
    def is_verified_level2(self):
        is_verified = self.is_verified_level1 and self.user.is_address_confirmed() and\
            (self.selfie_confirmed or self.identity_liveness_confirmed)

        if Settings.is_feature_active('kyc2'):
            return is_verified
        return self.mobile_identity_confirmed and is_verified

    @property
    def is_verified_level3(self):
        from exchange.accounts.userlevels import UserLevelManager
        result, _ = UserLevelManager.is_eligible_to_upgrade_level3(self.user)
        return result

    @property
    def has_verified_mobile_number(self):
        """ Wheter this user has a mobile number that is verified.
            Note that the mobile number may not have the same name as
            the user and that must be checked separately if needed.

            #TODO: Also validate mobile number to be a valid number
        """
        return self.user.mobile and self.mobile_confirmed

    @classmethod
    def notify_user_type_change(cls, user):
        pass


class VerificationRequest(APIVerified):
    """
    This is where some users verification data will be evaluated by nobitex customer services admins.
     1- identity.
     2- address.
     3- selfie photo.

    and there is a considerations field for admin's quote on user's verification documents.

     -- first data is in the "new" state then admins can review user's verification data and change
      their state to "confirmed" or "rejected" via their admin panels. --
    """
    TYPES = Choices(
        (1, 'identity', 'Identity'),
        (2, 'address', 'Address'),
        (3, 'selfie', 'Selfie'),
        (4, 'auto_kyc', 'AutoKYC'),
    )
    STATUS = Choices(
        (1, 'new', 'New'),
        (2, 'confirmed', 'Confirmed'),
        (3, 'rejected', 'Rejected'),
    )

    user = models.ForeignKey(User, related_name='verification_requests', on_delete=models.CASCADE)
    tp = models.IntegerField(choices=TYPES, verbose_name='Request Type')
    status = models.IntegerField(choices=STATUS, default=STATUS.new)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    documents = models.ManyToManyField('UploadedFile', blank=True, related_name='+')
    explanations = models.TextField(default='', blank=True)

    # Admin fields
    considerations = models.TextField(default='', blank=True, null=True,
                                      help_text='این ملاحظات برای کاربر قابل مشاهده نیست', verbose_name='ملاحظات ادمین')

    device: str
    tracker = FieldTracker(fields=['status'])

    class Meta:
        verbose_name = 'درخواست تایید هویت'
        verbose_name_plural = verbose_name

    def __init__(self, *args, **kwargs):
        self.device = kwargs.pop('device', None)
        super().__init__(*args, **kwargs)

    def update_user_verification(self):
        if self.status != self.STATUS.confirmed:
            return
        vprofile = self.user.get_verification_profile()
        if self.tp == self.TYPES.identity:
            vprofile.identity_confirmed = True
            vprofile.save(update_fields=['identity_confirmed'])
            self.user.update_verification_status()
        elif self.tp == self.TYPES.address:
            self.user.do_verify_address()
        elif self.tp == self.TYPES.selfie:
            vprofile.selfie_confirmed = True
            vprofile.save(update_fields=['selfie_confirmed'])
            self.user.update_verification_status()
        elif self.tp == self.TYPES.auto_kyc:
            self.user.update_verification_status()

    def save(self, *args, **kwargs):
        super(VerificationRequest, self).save(*args, **kwargs)
        self.update_user_verification()

    def confirm_request(self):
        self.status = self.STATUS.confirmed
        self.save(update_fields=['status'])

    def create_auto_tag(self):
        # delete open_all tag
        tag_open_all, created = Tag.objects.get_or_create(name=auto_tags['open_all'], tp=Tag.TYPES.kyc)
        UserTag.objects.filter(user=self.user, tag=tag_open_all).delete()
        if self.tp in [self.TYPES.identity, self.TYPES.selfie]:
            auto_tag = auto_tags['open_selfie'] if self.tp == self.TYPES.selfie else auto_tags['open_identity']
            tag, created = Tag.objects.get_or_create(name=auto_tag, tp=Tag.TYPES.kyc)
            if self.status != self.STATUS.confirmed:
                obj = UserTag.objects.filter(user=self.user, tag=tag).exists()
                system_user = User.objects.filter(id=1000).first()

                if not obj and system_user:
                    auto_tag_created = UserTag.objects.create(user=self.user, tag=tag)
                    content_type = ContentType.objects.get(model='usertag')
                    AdminConsideration.objects.create(admin_user=system_user, user=self.user, content_type=content_type,
                                                      object_id=auto_tag_created.id,
                                                      consideration=auto_tag)

    def remove_auto_tag(self):
        # delete open_all tag
        tag_open_all, created = Tag.objects.get_or_create(name=auto_tags['open_all'], tp=Tag.TYPES.kyc)
        UserTag.objects.filter(user=self.user, tag=tag_open_all).delete()

        if self.tp in [self.TYPES.identity, self.TYPES.selfie]:
            auto_tag = auto_tags['open_selfie'] if self.tp == self.TYPES.selfie else auto_tags['open_identity']
            tag, created = Tag.objects.get_or_create(name=auto_tag, tp=Tag.TYPES.kyc)
            if self.status == self.STATUS.confirmed:
                UserTag.objects.filter(user=self.user, tag=tag).delete()

    def reject_request(self):
        """ Explicitly reject request and update VerificationProfile.
            Normally when a VerificationProfile field is verified, rejecting
            related requests will not change its status. This method always
            updates the VerificationProfile.

            Note: No notification is sent in this method, as the message is
              supposed to be sent from the UI (rejection reason dropdown).
        """
        self.status = self.STATUS.rejected
        self.save(update_fields=['status'])

        # If there is any other accepted request of this type,
        #  rejecting other requests should not revert status.
        if VerificationRequest.objects.filter(
            user=self.user,
            tp=self.tp,
            status=self.STATUS.confirmed,
        ).exclude(id=self.id).exists():
            return

        # Update VerificationProfile
        vprofile = self.user.get_verification_profile()
        if self.tp == self.TYPES.identity:
            vprofile.identity_confirmed = False
            vprofile.save(update_fields=['identity_confirmed'])
            max_level = User.USER_TYPES.level0
        elif self.tp == self.TYPES.address:
            vprofile.address_confirmed = False
            vprofile.save(update_fields=['address_confirmed'])
            max_level = User.USER_TYPES.level1
        elif self.tp == self.TYPES.selfie:
            vprofile.selfie_confirmed = False
            vprofile.save(update_fields=['selfie_confirmed'])
            max_level = User.USER_TYPES.level1
        elif self.tp == self.TYPES.auto_kyc:
            vprofile.identity_liveness_confirmed = False
            vprofile.save(update_fields=['identity_liveness_confirmed'])
            max_level = User.USER_TYPES.level1
        else:
            return

        # Downgrade user level if required
        if self.user.user_type == User.USER_TYPES.trader:
            return
        if self.user.user_type > max_level:
            self.user.user_type = max_level
            self.user.save(update_fields=['user_type'])

    def call_verification_api(self, retry: int = 0, **_):
        from exchange.accounts.tasks import task_retry_calling_auto_kyc_api

        if self.tp == self.TYPES.identity:
            return VerificationClient().check_user_identity(self.user)
        elif self.tp == self.TYPES.auto_kyc:
            auto_kyc_instance = AutoKYC()
            liveness_result = auto_kyc_instance.check_user_liveness(self, retry)
            if auto_kyc_instance.failed_calling_api(liveness_result) and retry < 2:
                # Note that the task should only re-call the API when we haven't rejected or accepted the request with
                #  confidence = 100
                ten_minutes_in_seconds = 10 * 60
                task_retry_calling_auto_kyc_api.apply_async((self.id, retry + 1), countdown=ten_minutes_in_seconds)
            return liveness_result
        else:
            return None

    def call_testnet_verification_api(self):
        if self.tp == self.TYPES.address:
            return False
        elif self.tp == self.TYPES.auto_kyc:
            self.user.do_verify_liveness_alpha()
        return True

    @classmethod
    def get_active_requests(cls, user, tp):
        return cls.objects.filter(user=user, status=cls.STATUS.new, tp=tp)


class UserPreference(models.Model):
    """
    Reads user preferences data and can check if it is the default settings or it's been customized by the user.
    """
    user = models.ForeignKey(User, related_name='preferences', on_delete=models.CASCADE)
    preference = models.CharField(max_length=100)
    value = models.TextField(default='')

    class Meta:
        unique_together = ['user', 'preference']
        verbose_name = 'تنظیمات کاربر'
        verbose_name_plural = verbose_name

    @property
    def is_system_preference(self):
        return self.preference and self.preference.startswith('system_')

    def get_value(self):
        try:
            return json.loads(self.value) if self.value else None
        except ValueError:
            return None

    @classmethod
    def get(cls, user, preference, default=None):
        try:
            value = cls.objects.get(user=user, preference=preference).get_value()
        except cls.DoesNotExist:
            return default
        if value is None:
            return default
        return value

    @classmethod
    def set(cls, user, preference, value):
        value = json.dumps(value)
        try:
            pref = cls.objects.get(user=user, preference=preference)
            pref.value = value
            pref.save(update_fields=['value'])
        except cls.DoesNotExist:
            pref = cls.objects.create(user=user, preference=preference, value=value)
        return pref

    @classmethod
    def get_user_preferences(cls, user, include_system=False):
        from exchange.features.models import QueueItem
        preferences = {}
        for p in user.preferences.all():
            if p.is_system_preference and not include_system:
                continue
            preferences[p.preference] = p.get_value()
        track = user.track or 0
        if track & QueueItem.BIT_FLAG_PORTFOLIO:
            preferences['portfolio'] = True
        if user.is_beta_user:
            preferences['beta'] = True
        return preferences


class NotificationManager(models.Manager):
    def bulk_create(self, notifications: Iterable['Notification'], **kwargs):
        if not NotificationConfig.is_notification_broker_enabled():
            # Batch send_telegram_message tasks into groups of 100.
            notifs = []
            for notification in notifications:
                if notification.user.telegram_conversation_id and not notification.sent_to_telegram:
                    notifs.append((notification.get_telegram_text(), notification.user.telegram_conversation_id))
                    notification.sent_to_telegram = True

            send_telegram_message.chunks(notifs, n=100).apply_async(
                expires=Notification.TELEGRAM_TASK_TIMEOUT, queue=settings.TELEGRAM_CELERY_QUEUE
            )

        super().bulk_create(notifications, **kwargs)
        # send notification to queue
        Notification.send_to_broker(notifications)


class Notification(models.Model):
    """
     1- notifies the user via their telegram's bot conversations.
     2- leaves a log in management console, sends the text message to slack and sends the text to the nobitex-
        -admins telegram group.
    """

    TELEGRAM_TASK_TIMEOUT = 1800  # 30 Mins

    user = models.ForeignKey(User, related_name='notifications', on_delete=models.CASCADE)
    admin = models.ForeignKey(User, related_name='sent_notifications', on_delete=models.CASCADE, null=True)
    message = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_read = models.BooleanField(default=False)
    sent_to_telegram = models.BooleanField(default=False)
    sent_to_fcm = models.BooleanField(default=False, null=True)

    objects = NotificationManager()

    class Meta:
        verbose_name = 'اعلان‌ها'
        verbose_name_plural = verbose_name

    @property
    def text_display(self):
        # TODO this property was not used. remove it
        return self.message

    def get_telegram_text(self, title='🔵 Notification'):
        return f'*{title}*\n{self.message}'

    def sent_sms(self):
        # TODO remove, was not used
        return UserActionLog.objects.filter(object_id=self.id,
                                            action__codename__in=['send_user_sms', 'send_user_sms_template']).exists()

    def send_to_telegram_conversation(self, save=True, title='🔵 Notification', is_otp: bool = False):
        if NotificationConfig.is_notification_logging_enabled():
            topic = Topics.FAST_TELEGRAM_NOTIFICATION if is_otp else Topics.TELEGRAM_NOTIFICATION
            notif = TelegramNotificationSchema(
                user_id=str(self.user.uid),
                title=title,
                message=self.message,
            )
            notification_producer.write_event(topic.value, notif.serialize())
            if NotificationConfig.is_notification_broker_enabled():
                return  # it means: use logic in notification app for sending

        if self.user.telegram_conversation_id:
            text = self.get_telegram_text(title)
            send_telegram_message.apply_async(
                (text, self.user.telegram_conversation_id),
                expires=self.TELEGRAM_TASK_TIMEOUT,
                queue=settings.TELEGRAM_CELERY_QUEUE,
            )
        else:
            if settings.DEBUG:
                print('*Telegram Message for {}*\n{}'.format(self.user.username, self.message))
        self.sent_to_telegram = True
        if save:
            self.save(update_fields=['sent_to_telegram'])

    @classmethod
    def notify_admins(cls, message, title=None, channel=None, message_id=None,
                      codename=None, pin=False, cache_key=None, cache_timeout=None):
        """Send a notification to admins groups.

            Note: if codename is given, the message is ratelimited (to cache_timeout or 60s)
        """
        if NotificationConfig.is_notification_logging_enabled():
            notif = AdminTelegramNotificationSchema(
                message=str(message),
                title=str(title),
                channel=str(channel),
                message_id=str(message_id),
                codename=str(codename),
                pin=pin,
                cache_key=str(cache_key),
                cache_timeout=cache_timeout,
            )

            notification_producer.write_event(Topics.ADMIN_TELEGRAM_NOTIFICATION.value, notif.serialize())
            if NotificationConfig.is_notification_broker_enabled():
                return  # it means: use logic in notification app for sending

        channel = channel or 'notifications'
        title = title or '🔵 Notification'
        text = '*{}*\n{}'.format(title, message)
        text = text.replace('_', '-')
        # Log in console for development
        if settings.DEBUG:
            print(text)
        # Not resending same message too frequently
        if codename:
            lock_cache_key = 'lock_notification_{}'.format(codename)
            has_lock = cache.get(lock_cache_key)
            if has_lock:
                return
            cache.set(lock_cache_key, 1, cache_timeout or 60)
        # Send message to admins telegram group
        chat_id = settings.TELEGRAM_GROUPS_IDS.get(channel)
        if not chat_id or settings.IS_TESTNET:
            chat_id = settings.ADMINS_TELEGRAM_GROUP
        send_telegram_message.apply_async(
            (text, chat_id),
            {'message_id': message_id, 'pin': pin, 'cache_key': cache_key, 'cache_timeout': cache_timeout},
            expires=1200,
            queue=settings.TELEGRAM_ADMIN_CELERY_QUEUE,
        )
        if settings.IS_TESTNET:  # To receive some logs in testnet
            log_event(title, category='notice', details=message)

    @classmethod
    def mark_notifs_as_read(cls, user_id: int, notif_ids: List[int]) -> int:
        processed = cls.objects.filter(user_id=user_id, id__in=notif_ids, is_read=False).update(is_read=True)
        return processed

    @classmethod
    def send_to_broker(cls, notifications: Iterable['Notification']):
        if not NotificationConfig.is_notification_logging_enabled():
            return
        for notification in notifications:
            admin = str(notification.admin.uid) if notification.admin else ''
            notif = NotificationSchema(
                user_id=str(notification.user.uid),
                admin=admin,
                message=notification.message,
                sent_to_telegram=notification.sent_to_telegram,
                sent_to_fcm=notification.sent_to_fcm or False,
            )
            notification_producer.write_event(Topics.NOTIFICATION.value, notif.serialize())


class UploadedFile(models.Model):
    """
    Holds each user's uploaded file's name. path on disk and url.
    """
    TYPES = Choices(
        (1, 'general', 'General'),
        (2, 'kyc_video', 'KYCVideo'),
        (3, 'kyc_main_image', 'KYCMainImage'),
        (4, 'kyc_image', 'KYCImage'),
        (5, 'ticketing_attachment', 'Ticketing Attachment'),
        (6, 'discount', 'Discount'),
        (8, 'gift_package', 'GiftPackage'),
        (9, 'gift_card_design', 'GiftCardDesign'),
        (10, 'manual_deposit_request_video', 'Manual Deposit Request Video'),
    )
    AUTO_KYC_TYPES = [TYPES.kyc_video, TYPES.kyc_main_image, TYPES.kyc_image]
    AUTO_KYC_ACTIVE_TYPES = [TYPES.kyc_main_image, TYPES.kyc_image]
    AUTO_KYC_ACCEPTABLE_FILE_FORMATS = {
        TYPES.kyc_video: {'video/mp4', 'video/webm', 'video/x-matroska', 'application/x-matroska', 'application/octet-stream'},
        TYPES.kyc_main_image: {'image/jpeg', 'image/png', 'image/bmp', 'image/webp'},
        TYPES.kyc_image: {'image/gif', 'video/mp4', 'video/webm', 'video/x-matroska', 'application/x-matroska', 'application/octet-stream'}
    }

    filename = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, related_name='uploaded_files', on_delete=models.CASCADE)
    tp = models.IntegerField(choices=TYPES, default=TYPES.general, verbose_name='File Type')
    size = models.IntegerField(default=0, help_text='File size in bytes', null=True, blank=True)
    checksum = models.BinaryField(max_length=20, null=True, blank=True, help_text='sha1sum of file content')
    archive_folder_id = models.SmallIntegerField(
        default=0, help_text='Folder id in cold file storage', null=True, blank=True
    )

    class Meta:
        verbose_name = 'فایل آپلود شده'
        verbose_name_plural = verbose_name

    def __str__(self):
        if self.is_auto_kyc_file:
            return 'UploadedKYCFiles#{}'.format(self.filename.hex)
        return 'UploadedFile#{}'.format(self.filename.hex)

    def save(self, *args, update_fields=None, **kwargs):
        if update_fields:
            update_fields = (*update_fields, *('size', 'checksum'))

        self.size = self.get_size()
        self.checksum = self.get_checksum()
        return super().save(*args, update_fields=update_fields, **kwargs)

    @property
    def is_auto_kyc_file(self):
        """Whether this file is uploaded for auto KYC process."""
        return self.tp in self.AUTO_KYC_TYPES

    @property
    def directory_name(self):
        """Leaf directory used for these type of files."""
        if self.is_auto_kyc_file:
            return 'kyc'
        elif self.tp == self.TYPES.ticketing_attachment:
            return 'ticketing_attachments'
        elif self.tp == self.TYPES.discount:
            return 'discount'
        elif self.tp == self.TYPES.manual_deposit_request_video:
            return 'manual_deposit_request_video'
        else:
            return 'files'

    @property
    def relative_path(self):
        return os.path.join('uploads', self.directory_name, self.filename.hex)

    @property
    def disk_path(self):
        return os.path.join(settings.MEDIA_ROOT, self.relative_path)

    @property
    def serve_url(self):
        return f'/media/uploads/{self.directory_name}/{self.filename.hex}'

    def get_size(self):
        try:
            return os.path.getsize(self.disk_path)
        except FileNotFoundError:
            return 0

    def get_checksum(self):
        sha1 = hashlib.sha1()
        try:
            with open(self.disk_path, 'rb') as file:
                for chunk in iter(lambda: file.read(4096), b""):
                    sha1.update(chunk)
            return sha1.digest()
        except FileNotFoundError:
            return b''


class ReferralProgram(models.Model):
    """ Referral codes for each user, used to create referral links and set
        share of the referral to give back to the invited user.
    """

    AGENDA = Choices(
        (0, 'default', 'default'),
        (1, 'campaign', 'campaign'),
    )

    user = models.ForeignKey(User, related_name='user_referral_programs', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    user_share = models.IntegerField(verbose_name='سهم معرف', help_text='درصد')
    friend_share = models.IntegerField(default=0, verbose_name='سهم کاربر دعوت شده', help_text='درصد')
    referral_code = models.CharField(max_length=20, unique=True)
    description = models.CharField(max_length=1000, blank=True, null=True, verbose_name='توضیحات')
    agenda = models.IntegerField(choices=AGENDA, default=AGENDA.default, verbose_name='بابت')

    class Meta:
        verbose_name = 'لینک ریفرال'
        verbose_name_plural = verbose_name

    @classmethod
    def _generate_referral_code(cls):
        # Generate a random string of 3 alphanumeric characters
        random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=3))

        # Combine timestamp and random part, then hash it
        raw_code = str(time.time()) + random_part
        hashed_code = hashlib.sha256(raw_code.encode()).hexdigest()
        referral_code = ''.join([char for char in hashed_code if char.isalnum()])[:7]

        return referral_code.upper()

    @classmethod
    def create(cls, user, friend_share, ref_code=None, agenda=AGENDA.default, description=None):
        """Assign a referral code and create a new referral link for this user"""
        total_referral_share = settings.NOBITEX_OPTIONS['baseReferralPercent']
        if friend_share > total_referral_share or friend_share < 0:
            return None, 'InvalidGivebackShare'

        # Each user at most can have 30 links
        if cls.objects.filter(user=user).count() >= 30:
            return None, 'TooManyReferralLinks'

        # Generate a unique referral code (if not provided)
        if not ref_code:
            ref_code = cls._generate_referral_code()

        # Create the new program, also checking for any race-condition resulting in
        #  generated code already being present in DB
        try:
            with transaction.atomic():
                ref_program = cls.objects.create(
                    user=user,
                    user_share=total_referral_share - friend_share,
                    friend_share=friend_share,
                    referral_code=ref_code,
                    agenda=agenda,
                    description=description,
                )
        except IntegrityError:
            report_event('ReferralCodeAlreadyExist', extras={'code': ref_code})
            return None, 'ReferralCodeExists'
        return ref_program, None

    def get_referred_users_count(self):
        """ Return number of users registered using this referral code """
        return UserReferral.objects.filter(referral_program=self, child__user_type__gt=User.USER_TYPES.level0).count()


class UserReferral(models.Model):
    """ User Referral Relationship
    """
    child = models.OneToOneField(User, unique=True, related_name='userreferral_child', on_delete=models.CASCADE)
    parent = models.ForeignKey(User, related_name='userreferral_parent', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    referral_share = models.IntegerField(default=0, verbose_name='سهم معرف')
    child_referral_share = models.IntegerField(default=0, verbose_name='سهم کاربر دعوت شده')
    channel = models.CharField(max_length=50, null=True, blank=True)
    referral_program = models.ForeignKey(ReferralProgram, null=True, blank=True, related_name='user_referrals',
                                         on_delete=models.SET_NULL)

    class Meta:
        verbose_name = 'ارجاع کاربر'
        verbose_name_plural = verbose_name

    @classmethod
    def get_referrer(cls, user):
        """ Shortcut to get the referrer user of a given user

            Note: Accepts ID instead of the whole User object
        """
        return UserReferral.objects.filter(child=user).first()

    @classmethod
    def set_user_referrer(cls, new_user, referral_code, channel=None):
        """ Set referrer for the given user
        """
        if not referral_code:
            return False
        # Can not change referrer when it is set
        if cls.get_referrer(new_user) is not None:
            return False
        # Get the referrer
        try:
            referrer_program = ReferralProgram.objects.select_related('user').get(
                referral_code=str(referral_code).upper()
            )
        except ReferralProgram.DoesNotExist:
            return False
        # Check referrer validity
        referrer_chain = [new_user.pk]
        pointer = referrer_program.user
        while pointer:
            if pointer.pk in referrer_chain:
                return False
            pointer = cls.get_referrer(pointer)
            if pointer:
                pointer = pointer.parent
        # Set referrer
        UserReferral.objects.create(
            parent=referrer_program.user,
            child=new_user,
            channel=channel or None,
            referral_share=referrer_program.user_share,
            child_referral_share=referrer_program.friend_share,
            referral_program=referrer_program,
        )
        transaction.on_commit(lambda: SuccessfulRegisterWithReferralCode(user=referrer_program.user).send())
        return True


class ApiUsage(models.Model):
    """
    Stores user's last activity and trade logs and can update them.
    """
    user = models.OneToOneField(User, primary_key=True, on_delete=models.CASCADE)
    last_activity = models.DateTimeField(db_index=True, null=True, blank=True)
    last_trade = models.DateTimeField(db_index=True, null=True, blank=True)
    app_version = models.CharField(max_length=50, blank=True)
    last_app_signal = models.DateTimeField(null=True, blank=True)
    web_version = models.CharField(max_length=50, blank=True)
    last_web_signal = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'وضعیت کاربر'
        verbose_name_plural = verbose_name

    @classmethod
    def get(cls, user):
        return cls.objects.get_or_create(user_id=user.pk)[0]


class UserPlan(KVData):
    TYPE = Choices(
        (1, 'trader', 'Trader'),
    )
    ALLOWED_TRADER_INITIAL_LEVELS = [
        User.USER_TYPES.level1, User.USER_TYPES.level2, User.USER_TYPES.verified,
        User.USER_TYPES.trusted, User.USER_TYPES.nobitex,
    ]

    user = models.ForeignKey(User, related_name='user_plans', on_delete=models.CASCADE)
    type = models.IntegerField(choices=TYPE, verbose_name='پلن')
    date_from = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='تاریخ شروع')
    date_to = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ پایان')
    is_active = models.BooleanField(default=False, verbose_name='فعال؟')
    description = models.CharField(max_length=1000, blank=True, null=True, verbose_name='توضیحات')

    class Meta:
        verbose_name = 'طرح‌های ویژه'
        verbose_name_plural = verbose_name

    @classmethod
    def get_user_plans(cls, user, tp=None, only_active=False):
        plans = cls.objects.filter(user=user)
        if only_active:
            plans = plans.filter(is_active=True)
        if tp:
            plans = plans.filter(type=tp)
        return plans

    @classmethod
    def user_has_active_plan(cls, user, plan_tp):
        return cls.get_user_plans(user).filter(type=plan_tp, is_active=True).exists()

    @classmethod
    def get_user_active_plan_by_type(cls, user, tp):
        return cls.get_user_plans(user).filter(type=tp, is_active=True).first()

    def activate(self):
        if self.type == self.TYPE.trader:
            self.set_kv('initial_user_type', self.user.user_type)
            self.user.user_type = User.USER_TYPES.trader
            self.user.save(update_fields=['user_type'])
        self.is_active = True
        self.save()
        VerificationProfile.notify_user_type_change(user=self.user)

    def deactivate(self):
        """ Deactivate this plan for the user and applies necessary changes
        """
        from exchange.accounts.userstats import UserStatsManager
        if self.type == self.TYPE.trader:
            self.user.user_type = self.get_kv('initial_user_type')
            self.user.save(update_fields=['user_type'])
            self.user.update_verification_status()
            UserStatsManager.get_user_vip_level(self.user_id, force_update=True)
            # TODO: Also save total trade volume in kv_data
        self.is_active = False
        self.date_to = now()
        self.save(update_fields=['is_active', 'date_to'])


class UserActionLog(models.Model):
    user = models.ForeignKey(User, related_name='user_action_log', on_delete=models.CASCADE)
    action = models.ForeignKey(Permission, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    description = models.CharField(max_length=300, null=True, blank=True, default=None)
    response_time = models.FloatField(null=True, blank=True)

    # Generic Foreign Key
    content_type = models.ForeignKey(ContentType, related_name='UserActionLog', on_delete=models.CASCADE, null=True)
    object_id = models.BigIntegerField(null=True)
    log_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        verbose_name = 'تاریخچه فعالیت‌های پشتیبانی'
        verbose_name_plural = verbose_name


class AdminConsideration(models.Model):
    admin_user = models.ForeignKey(User, related_name='user_admin_consideration', on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name='user_consideration', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    consideration = models.TextField()
    # Generic Foreign Key
    content_type = models.ForeignKey(ContentType, related_name='content_admin_consideration', on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    object = GenericForeignKey('content_type', 'object_id')
    is_important = models.BooleanField(default=False)
    user_consideration = models.TextField(null=True, blank=True, help_text='در پنل کاربر قابل نمایش خواهد بود')

    class Meta:
        verbose_name = 'ملاحظات پشتیبانی'
        verbose_name_plural = verbose_name

    @property
    def edit_time_period_is_not_reached(self):
        """ Return whether this comment cannot be edited anymore """
        return self.created_at.timestamp() + 1800 > time.time()


class Tag(models.Model):
    TYPES = Choices(
        (0, 'normal', 'Normal Tag'),
        (1, 'auto', 'Auto Tag'),
        (2, 'kyc', 'KYC Tag'),
        (3, 'junk', 'Junk Tag'),
        (4, 'shaba_restriction_removal', 'رفع محدودیت شبا')
    )

    tp = models.IntegerField(choices=TYPES, default=TYPES.normal)
    name = models.CharField(max_length=63, unique=True, verbose_name='نام')
    users = models.ManyToManyField(User, related_name='tags', blank=True, through='UserTag')
    description = models.TextField(null=True, blank=True, verbose_name='توضیحات')

    class Meta:
        verbose_name = 'برچسب'
        verbose_name_plural = 'برچسب‌ها'

    def __str__(self):
        return self.name

    @classmethod
    def get_builtin_tag(cls, name):
        """ Get Tag object by name """
        return cls.objects.get_or_create(name=name)[0]

    @classmethod
    def get_sensitive_users_tag(cls):
        """ Return the tag object that shows sensitive users
        """
        return cls.get_builtin_tag('کاربر حساس')


class UserTag(models.Model):
    user = models.ForeignKey(User, related_name='user_tags', on_delete=models.CASCADE, verbose_name='کاربر')
    tag = models.ForeignKey(Tag, related_name='tag_users', on_delete=models.PROTECT, verbose_name='برچسب')
    created_at = models.DateTimeField(default=now, null=True, blank=True)

    def __str__(self):
        return f'{self.user} - {self.tag}'

    class Meta:
        verbose_name = 'برچسب کاربر'
        verbose_name_plural = 'برچسب‌های کاربران'


class UserRestrictionRemoval(models.Model):
    admin_user = models.ForeignKey(User, related_name='delayed_restriction_removals', on_delete=models.CASCADE)
    restriction = models.ForeignKey(UserRestriction, related_name='restriction_removals', on_delete=models.SET_NULL,
                                    null=True, blank=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    ends_at = models.DateTimeField(db_index=True)


class UserEvent(models.Model):
    CHANGE_USER_TRACK_ACTION_TYPE = Choices(
        (1, 'active_beta', 'فعال شدن حالت بتا'),
        (2, 'deactive_beta', 'غیرفعال شدن حالت بتا'),
    )

    EDIT_MOBILE_ACTION_TYPES = Choices(
        (1, 'requested', 'ثبت درخواست تغییر موبایل'),
        (2, 'fail_identity', 'عدم تایید هویت صاحب موبایل'),
        (3, 'fail_new_mobile_otp', 'عدم تایید کد یکبارمصرف شماره جدید'),
        (4, 'fail_old_mobile_otp', 'عدم تایید کد یکبارمصرف شماره قدیم'),
        (5, 'success', 'تغییر موبایل موفق'),
    )

    USER_MERGE_ACTION_TYPES = Choices(
        (1, 'requested', 'ثبت درخواست ادغام'),
        (2, 'fail_identity', 'عدم تایید هویت صاحب موبایل'),
        (3, 'fail_new_mobile_otp', 'عدم تایید کد یکبارمصرف شماره موبایل جدید'),
        (4, 'fail_old_mobile_otp', 'عدم تایید کد یکبارمصرف شماره موبایل قدیم'),
        (5, 'fail_email_otp', 'عدم تایید کد یکبارمصرف ایمیل'),
        (6, 'need_approval', 'در انتظار تایید پشتیبان'),
        (7, 'accepted', 'ادغام موفق حساب کاربری'),
        (8, 'rejected', 'رد درخواست ادغام'),
    )

    USER_KYC_ACTION_TYPES = Choices(
        (1, 'level0_not_active_sms_send', 'ارسال پیام برای کاربر غیرفعال'),
    )

    ACTION_CHOICES = Choices(
        (1, 'disable_2fa', 'غیر فعال سازی دوعاملی'),  # 1: admin, 2: user-disable, 3: user-forget
        (2, 'user_restriction_creation', 'اعمال محدودیت کاربر'),
        (3, 'add_withdraw_request_permit', 'افزودن مجوز برداشت'),
        (4, 'restriction_removal', 'حذف محدودیت'),
        (5, 'add_manual_transaction', 'افزودن تراکنش دستی'),
        (6, 'add_withdraw', 'افزودن درخواست برداشت'),
        (7, 'reject_withdraw', 'رد کردن درخواست برداشت'),
        (8, 'withdraw_request_permit_removal', 'حذف مجوز برداشت'),
        (9, 'disable_wallet_address', 'غیرفعال کردن آدرس ولت'),
        (10, 'confirmed_wallet_deposit_manual_creation', 'ثبت دستی واریز رمزارز'),
        (11, 'shetab_deposit_edit', 'ویرایش واریز شتابی'),
        (12, 'bank_deposit_edit', 'ویرایش واریزهای بانکی'),
        (13, 'add_transaction', 'افزودن تراکنش'),
        (14, 'users_tfa_confirm', 'فعالسازی شناسه دوعاملی'),
        (15, 'edit_mobile', 'تغییر شماره همراه'),
        (16, 'change_user_track', 'تغییر وضعیت کاربر'),
        (17, 'user_merge', 'ادغام کاربر'),
        (18, 'user_kyc', 'احراز کاربری'),
    )

    user = models.ForeignKey(User, related_name='user_events', on_delete=models.CASCADE)
    action = models.IntegerField(choices=ACTION_CHOICES)
    action_type = models.IntegerField(null=True)
    created_at = models.DateTimeField(default=now)
    description = models.CharField(max_length=500, null=True)


class UserDocuments(models.Model):
    """
    This is where users' extra documents can be uploaded.
    """
    Company_TYPE_CHOICES = Choices(
        (1, 'national_card', 'کارت ملی'),
        (2, 'registration_ad', 'آگهی تاسیس'),
        (3, 'introduction', 'معرفی‌نامه'),
        (4, 'economic_code', 'کد اقتصادی')
    )

    STATUS_CHOICES = Choices(
        (0, 'no_status', 'بدون وضعیت'),
        (1, 'confirmed', 'تایید شده'),
        (2, 'rejected', 'رد شده'),

    )
    creator = models.ForeignKey(User, related_name='staff_created_documents', null=True, blank=True,
                                on_delete=models.SET_NULL)
    user = models.ForeignKey(User, related_name='user_documents', on_delete=models.CASCADE)
    created_at = models.DateTimeField(default=now)
    title = models.CharField(max_length=50, null=True, blank=True, verbose_name='عنوان')
    file = models.ForeignKey(UploadedFile, related_name='user_documents', on_delete=models.CASCADE,
                             verbose_name='فایل مدرک')
    explanations = models.TextField(null=True, blank=True, verbose_name='توضیحات')

    # company_accounts
    document_type = models.IntegerField(choices=Company_TYPE_CHOICES, null=True, blank=True, verbose_name='نوع مدرک')
    status = models.IntegerField(choices=STATUS_CHOICES, default=0, verbose_name='وضعیت')

    class Meta:
        verbose_name = 'مدارک تکمیلی کاربر'
        verbose_name_plural = verbose_name


class UserCategory(models.Model):
    user = models.ForeignKey(User, related_name='categories', on_delete=models.CASCADE, verbose_name='کاربر')
    category = JSONField(verbose_name='دسته بندی ها')
    created_at = models.DateTimeField(default=now, null=True, blank=True)

    def __str__(self):
        return f'{self.user} - {self.category}'

    class Meta:
        verbose_name = 'دسته بندی کاربر'
        verbose_name_plural = 'دسته بندی های کاربران'


class UserProfile(User):
    labels = JSONField(blank=True, null=True, db_index=True)
    properties = JSONField(blank=True, null=True)

    class Meta:
        verbose_name = 'پروفایل کاربر'
        verbose_name_plural = verbose_name


class ChangeMobileRequest(models.Model):
    STATUS = Choices(
        (0, 'new', 'New'),
        (1, 'old_mobile_otp_sent', 'Old Mobile OTP Sent'),
        (2, 'new_mobile_otp_sent', 'New Mobile OTP Sent'),
        (3, 'success', 'Success'),
        (4, 'failed', 'Failed'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mobile_change_requests', null=False)
    status = models.IntegerField(choices=STATUS, default=STATUS.new, null=False)
    old_mobile = models.CharField(max_length=12, null=False)
    new_mobile = models.CharField(max_length=12, null=False)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def create(cls, user: User, new_mobile: str = None, status: int = 0) -> 'ChangeMobileRequest':
        """
        Disable all active request, create new one, use user's mobile as old_mobile and return it
        Active request's status is one of these (new, old_mobile_otp_sent, new_mobile_otp_sent)
        """
        with transaction.atomic():
            cls.log(user, UserEvent.EDIT_MOBILE_ACTION_TYPES.requested)
            cls.objects.exclude(status__in=[cls.STATUS.failed, cls.STATUS.success]).filter(user=user) \
                .update(status=cls.STATUS.failed)
            is_edit = bool(user.mobile)
            old_mobile = user.mobile if is_edit else new_mobile
            if not is_edit:
                transaction.on_commit(lambda: MobileEnteredWebEngageEvent(user=user).send())
            return cls.objects.create(user=user, old_mobile=old_mobile, new_mobile=new_mobile, status=status)

    @classmethod
    def get_active_request(cls, user: User) -> Optional['ChangeMobileRequest']:
        """
        Get active request of user, active request has status (new or old_mobile_otp_sent or new_mobile_otp_sent)
        """
        try:
            return cls.objects.exclude(status__in=[cls.STATUS.success, cls.STATUS.failed]).get(user=user)
        except cls.DoesNotExist:
            return None

    @classmethod
    def log(cls, user: User, action_type: int, description: Optional[str] = None) -> bool:
        if action_type not in UserEvent.EDIT_MOBILE_ACTION_TYPES:
            return False
        if description and len(description) > 500:
            description = description[:499] + '…'
        UserEvent.objects.create(
            user=user,
            action=UserEvent.ACTION_CHOICES.edit_mobile,
            action_type=action_type,
            description=description,
        )
        return True

    def send_otp(self) -> Tuple[Optional[UserOTP], Optional[str]]:
        """
        Create new OTP and send to user with SMS
        Return a pair of object, The first one is created OTP object and the second one is error description if exists.
        """
        if self.status not in [self.STATUS.new, self.STATUS.old_mobile_otp_sent]:
            return None, 'Request not valid for send OTP'

        if self.status == self.STATUS.old_mobile_otp_sent:
            request_status = self.STATUS.new_mobile_otp_sent
            to = self.new_mobile
        else:
            request_status = self.STATUS.old_mobile_otp_sent
            to = self.old_mobile

        UserOTP.active_otps(
            user=self.user,
            tp=UserOTP.OTP_TYPES.mobile,
            usage=UserOTP.OTP_Usage.change_phone_number
        ).update(otp_status=UserOTP.OTP_STATUS.disabled)

        change_mobile = bool(self.user.mobile) and self.new_mobile != self.user.mobile
        _otp_usage = UserOTP.OTP_Usage.change_phone_number if change_mobile else UserOTP.OTP_Usage.welcome_sms
        otp_obj = UserOTP.create_otp(
            user=self.user,
            tp=UserOTP.OTP_TYPES.mobile,
            usage=_otp_usage,
            phone_number=to,
        )
        if not otp_obj.send():
            otp_obj.disable_otp()
            return None, 'Send OTP sms failed'
        self.status = request_status
        self.save()
        return otp_obj, None

    def add_restriction(self) -> bool:
        if self.status != self.STATUS.success:
            return False
        UserRestriction.add_restriction(
            user=self.user,
            restriction=UserRestriction.RESTRICTION.WithdrawRequestCoin,
            considerations='ایجاد محدودیت 48 ساعته برداشت رمز ارز بعلت تغییر شماره موبایل',
            duration=datetime.timedelta(hours=48),
            description=UserRestrictionsDescription.CHANGE_PHONE_NUMBER,
        )
        return True

    def send_user_notif(self, change_mobile=True) -> bool:
        """
        Set change_mobile = False if you are setting mobile, not changing mobile.
        """
        if self.status == self.STATUS.success:
            if not change_mobile:
                # Send fraud warning to users
                UserSms.objects.create(
                    user=self.user,
                    tp=UserSms.TYPES.process,
                    to=self.user.mobile,
                    text='حساب کاربری با شماره همراه و اطلاعات شخصی شما در وبسایت نوبیتکس ایجاد گردیده است.\nتوجه: قرار دادن آن در اختیار سایر اشخاص با بهانه هایی نظیر سرمایه گذاری و اجاره حساب طبق ماده ۲ قانون پول شویی پیگرد قانونی دارد و مجازات حبس تا هفت سال در انتظار متخلفین خواهد بود.',
                )
                self.log(self.user, UserEvent.EDIT_MOBILE_ACTION_TYPES.success,
                         f'ثبت تلفن همراه به شماره {self.new_mobile}')
            else:
                if self.user.is_email_verified:
                    EmailManager.send_email(
                        self.user.email,
                        'change_mobile_notif',
                        data={
                            'change_date': get_readable_weekday_str(self.created_at),
                            'change_time': to_shamsi_date(self.created_at, '%H:%M'),
                            'new_mobile': self.new_mobile,
                            'old_mobile': self.old_mobile
                        },
                        priority='high',
                    )
                self.log(self.user, UserEvent.EDIT_MOBILE_ACTION_TYPES.success,
                         f'تغییر تلفن همراه از {self.old_mobile} به {self.new_mobile}')
            return True
        return False

    def do_verify(self, otp: str) -> Tuple[bool, Optional[str]]:
        is_new_mobile = self.status == self.STATUS.new_mobile_otp_sent
        change_mobile = bool(self.user.mobile) and self.new_mobile != self.user.mobile
        usage = UserOTP.OTP_Usage.change_phone_number if change_mobile else UserOTP.OTP_Usage.welcome_sms
        otp_result, error = UserOTP.verify(
            user=self.user,
            code=otp,
            tp=UserOTP.OTP_TYPES.mobile,
            usage=usage,
        )
        if not otp_result:
            self.log(self.user, UserEvent.EDIT_MOBILE_ACTION_TYPES.fail_new_mobile_otp if is_new_mobile else UserEvent.EDIT_MOBILE_ACTION_TYPES.fail_old_mobile_otp)
            return False, error
        if is_new_mobile:
            # check again
            from exchange.accounts.userlevels import UserLevelManager

            # check again
            if not UserLevelManager.is_eligible_to_change_mobile(self.user):
                return False, 'MobileUneditable'
            if not User.validate_mobile_number(self.user, self.new_mobile):
                return False, 'MobileAlreadyRegistered'

            self.status = ChangeMobileRequest.STATUS.success
            self.save(update_fields=['status'])

            update_fields = ['mobile']
            if self.user.username == self.user.mobile:
                self.user.username = self.new_mobile
                update_fields.append('username')
            self.user.mobile = self.new_mobile
            self.user.save(update_fields=update_fields)

            self.user.do_verify_mobile()
            UserSms.get_verification_messages(self.user).update(details='used')

            self.send_user_notif(change_mobile)
            if change_mobile:
                self.add_restriction()
        else:
            # old mobile confirm process
            result, error = self.send_otp()
            if error:
                return False, error

        return True, None


class AntiPhishing(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='anti_phishing_codes')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    code = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)

    @classmethod
    def get_anti_phishing_code_by_user(cls, user: User) -> str:
        anti_phishing = user.anti_phishing_codes.filter(is_active=True).order_by('-created_at').first()
        if anti_phishing:
            return anti_phishing.code
        else:
            return ''

    @classmethod
    def get_anti_phishing_code_by_email(cls, email: str) -> str:
        anti_phishing = cls.objects.filter(is_active=True, user__email=email).order_by('-created_at').first()
        if anti_phishing:
            return anti_phishing.code
        else:
            return ''

    @classmethod
    def hide_code(cls, code):
        return f"{code[0]}{'*' * (len(code) - 2)}{code[-1]}"

    @classmethod
    def set_anti_phishing_code(cls, user: User, code: str):
        if not connection.in_atomic_block:
            report_event('AntiPhishing.CantCreateInNonAtomicTransaction')
            raise Exception()
        AntiPhishing.objects.filter(user=user, is_active=True).update(is_active=False)
        AntiPhishing.objects.create(code=code, is_active=True, user=user)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user'], condition=Q(is_active=True), name='unique_active_anti_phishing')
        ]


class UserMergeRequest(models.Model):
    STATUS = Choices(
        (1, 'requested', 'Requested'),
        (2, 'rejected', 'Rejected'),
        (3, 'accepted', 'Accepted'),
        (4, 'failed', 'Failed'),
        (5, 'need_approval', 'Need approval'),
        (6, 'email_otp_sent', 'Email OTP sent'),
        (7, 'new_mobile_otp_sent', 'New Mobile OTP sent'),
        (8, 'old_mobile_otp_sent', 'Old Mobile OTP sent'),
    )
    MERGE_BY = Choices(
        (1, 'email', 'Email'),
        (2, 'mobile', 'Mobile'),
    )
    ACTIVE_STATUS = (
        STATUS.requested,
        STATUS.email_otp_sent,
        STATUS.new_mobile_otp_sent,
        STATUS.old_mobile_otp_sent,
        STATUS.need_approval,  # backward compatibility
    )

    status = models.SmallIntegerField(choices=STATUS, verbose_name='وضعیت درخواست')
    merge_by = models.SmallIntegerField(choices=MERGE_BY, verbose_name='نوع درخواست')
    main_user = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='کاربر اصلی', related_name='+')
    second_user = models.ForeignKey(User, on_delete=models.PROTECT, verbose_name='کاربر ثانوی', related_name='+')
    created_at = models.DateTimeField(default=now, verbose_name='تاریخ ایجاد')
    merged_at = models.DateTimeField(blank=True, null=True, verbose_name='زمان ادغام')
    description = models.TextField(blank=True, verbose_name='توضیحات')

    tracker = FieldTracker(fields=['status'])

    class Meta:
        verbose_name = 'درخواست ادغام کاربران'
        verbose_name_plural = 'درخواست‌های ادغام کاربران'

    @classmethod
    def get_active_merge_requests(cls, users: List[User], merge_by: Optional[int] = None):
        query = cls.objects.filter(status__in=cls.ACTIVE_STATUS).filter(
            Q(main_user__in=users) | Q(second_user__in=users),
        )
        if merge_by:
            query = query.filter(merge_by=merge_by)
        return query

    def change_to_rejected_status(self, description: str):
        self.status = UserMergeRequest.STATUS.rejected
        self.description = description
        self.save(update_fields=['status', 'description'])

    def change_to_accepted_status(self):
        self.status = UserMergeRequest.STATUS.accepted
        self.merged_at = now()
        from exchange.accounts.merge import MergeRequestStatusChangedContext

        merge_data = MergeRequestStatusChangedContext.from_users(main_user=self.main_user, second_user=self.second_user)
        self.description = merge_data.json
        self.save(update_fields=['status', 'merged_at', 'description'])


class UserLevelChangeHistory(models.Model):
    LEVELS = User.USER_TYPES
    changed_by = models.ForeignKey(User, related_name='+', on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(User, related_name='user_type_histories', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    from_level = models.SmallIntegerField(choices=LEVELS)
    to_level = models.SmallIntegerField(choices=LEVELS)

    class Meta:
        ordering = ['-created_at']

    @property
    def changed_self(self):
        return self.user == self.changed_by

    @property
    def description(self):
        return f'سطح کاربر از {self.LEVELS[self.from_level]} به {self.LEVELS[self.to_level]} تغییر پیدا کرد'


class UpgradeLevel3Request(models.Model):
    STATUS = UPGRADE_LEVEL3_STATUS

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='upgrade_level3_requests')
    status = models.SmallIntegerField(default=STATUS.requested, choices=STATUS, verbose_name='وضعیت درخواست')
    reject_reason = models.TextField(default='', blank=True, verbose_name='دلیل رد')

    created_at = models.DateTimeField(default=now, verbose_name='تاریخ ایجاد')
    closed_at = models.DateTimeField(null=True, verbose_name='تاریخ تصمیم پشتیبان')  # approve or reject datetime

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=['user'],
                condition=Q(
                    status__in=[UPGRADE_LEVEL3_STATUS.requested, UPGRADE_LEVEL3_STATUS.pre_conditions_approved]
                ),
                name='unique_active_user_request',
            ),
        )

    @classmethod
    def get_active_request(cls, user: User) -> 'UpgradeLevel3Request':
        return cls.objects.filter(user=user, status=cls.STATUS.pre_conditions_approved).first()

    def _send_notification(self):
        title = 'رد درخواست ارتقاء به سطح ۳'
        message = (
            'درخواست شما برای ارتقا به سطح سه، به دلیل سوابق گذشته شما، رد شد،'
            ' برای ارتباط بیشتر میتوانید از طریق چت آنلاین با پشتیبانی ارتباط بگیرید.'
        )
        send_email(
            email=self.user.email,
            template='template',
            data={'title': title, 'content': message},
            priority='medium',
        )

    def _upgrade_user(self):
        self.user.user_type = User.USER_TYPES.verified
        self.user.save(update_fields=['user_type'])

    def approve_pre_conditions(self) -> None:
        self.status = self.STATUS.pre_conditions_approved
        self.save(update_fields=['status'])

    def _finalize_request(self, reject_reason: str = '') -> None:
        _update_fields = ['status', 'closed_at']
        if reject_reason:
            self.status = self.STATUS.rejected
            self.reject_reason = reject_reason
            _update_fields.append('reject_reason')
        else:
            self.status = self.STATUS.approved
        self.closed_at = ir_now()
        self.save(update_fields=_update_fields)

    def reject(self, reject_reason: str) -> None:
        self._finalize_request(reject_reason)
        self._send_notification()

    def approve(self) -> None:
        self._upgrade_user()
        self._finalize_request()
