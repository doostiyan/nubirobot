import datetime
from typing import Optional, Tuple

from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from model_utils import Choices

from exchange.accounts.models import ChangeMobileRequest, User
from exchange.base.crypto import random_string_digit
from exchange.base.emailmanager import EmailManager
from exchange.base.logging import report_event, report_exception
from exchange.notification.models.sms import Sms


class OTP(models.Model):
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

    user = models.ForeignKey(User, related_name='new_otps', on_delete=models.CASCADE, null=True)
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
    def active_otps(
        cls,
        user: Optional[User] = None,
        phone_number: Optional[str] = None,
        tp: Optional[int] = None,
        usage: Optional[int] = None,
    ) -> 'QuerySet[OTP]':
        if user is None and phone_number is None:
            return None
        condition = {'otp_status': cls.OTP_STATUS.new}
        if user is not None:
            condition['user'] = user
        else:
            condition['phone_number'] = phone_number
        otps = cls.objects.filter(**condition).filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now())
        )
        if tp:
            otps = otps.filter(otp_type=tp)
        if usage:
            otps = otps.filter(otp_usage=usage)
        return otps

    @classmethod
    def generate_otp_code(
        cls, tp: int, user: Optional[User] = None, phone_number: Optional[str] = None, code: Optional[str] = None
    ) -> str:
        if user is None and phone_number is None:
            return None
        if code:
            otp = code
        else:
            otp = random_string_digit(6)
            if tp == OTP.OTP_TYPES.phone:
                otp = otp[:4].replace('0', '3')  # Hearing aid for phone OTP
        cls.active_otps(user=user, phone_number=phone_number, tp=tp).filter(code=otp).update(
            otp_status=cls.OTP_STATUS.disabled
        )
        return otp

    @classmethod
    def create_otp(
        cls,
        tp: int,
        usage: Optional[int] = None,
        otp: Optional[str] = None,
        user: Optional[User] = None,
        phone_number: Optional[str] = None,
    ) -> Optional['OTP']:
        if user is None and phone_number is None:
            return None
        if tp not in cls.OTP_TYPES:
            return None
        if not usage:
            usage = cls.OTP_Usage.generic
        if usage not in cls.OTP_Usage:
            return None
        expires_at = now() + datetime.timedelta(minutes=30)
        otp = cls.generate_otp_code(user=user, phone_number=phone_number, tp=tp, code=otp)

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
                    Sms.objects.create(
                        user=self.user,
                        tp=Sms.TYPES.tfa_disable,
                        to=self.user.mobile,
                        text=self.code,
                        template=Sms.TEMPLATES.tfa_disable,
                    )
                elif self.otp_usage == self.OTP_Usage.change_phone_number:
                    Sms.objects.create(
                        user=self.user,
                        tp=Sms.TYPES.verify_phone,
                        to=self.phone_number or self.user.mobile,
                        text=self.code,
                        template=Sms.TEMPLATES.verification,
                    )
                    change_obj = ChangeMobileRequest.get_active_request(self.user)
                    if change_obj and change_obj.status == ChangeMobileRequest.STATUS.new:
                        EmailManager.send_email(
                            self.user.email,
                            'otp',
                            data={'otp': self.code},
                            backend='critical',
                        )
                elif self.otp_usage == self.OTP_Usage.welcome_sms:
                    Sms.objects.create(
                        user=self.user,
                        tp=Sms.TYPES.verify_phone,
                        to=self.phone_number or self.user.mobile,
                        text=self.code,
                        template=Sms.TEMPLATES.welcome,
                    )
                elif self.otp_usage == self.OTP_Usage.campaign:
                    Sms.objects.create(
                        user=self.user,
                        tp=Sms.TYPES.verify_phone,
                        to=self.phone_number or self.user.mobile,
                        text=self.code,
                        template=Sms.TEMPLATES.verification,
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
                    backend='critical',
                )
            self.is_sent = True
            self.save()
            return True
        except:
            report_exception()
            return False

    @classmethod
    def verify(
        cls,
        code: str,
        tp: int,
        usage: int,
        user: Optional[User] = None,
        phone_number: Optional[str] = None,
    ) -> Tuple[Optional['OTP'], Optional[str]]:
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
