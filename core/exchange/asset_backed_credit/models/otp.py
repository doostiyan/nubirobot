import uuid
from datetime import timedelta

from django.db import models
from django.db.models import QuerySet
from django.utils.translation import gettext_lazy as _
from model_utils import Choices

from exchange.accounts.models import User
from exchange.asset_backed_credit.models.user import InternalUser
from exchange.base.calendar import ir_now


class OTPLog(models.Model):
    OTP_VERIFY_DURATION_MINUTES = 30
    OTP_TYPES = Choices(
        (1, 'email', _('Email')),
        (2, 'mobile', _('Mobile')),
        (3, 'phone', _('Phone')),
    )
    OTP_USAGE = Choices(
        (11, 'grant_permission_to_financial_service', _('Grant Permission To Financial Service')),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    internal_user = models.ForeignKey(InternalUser, null=True, blank=True, on_delete=models.CASCADE)
    otp_type = models.SmallIntegerField(choices=OTP_TYPES)
    usage = models.SmallIntegerField(choices=OTP_USAGE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    idempotency = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, null=False, blank=False)

    send_api_response_code = models.SmallIntegerField(blank=True, null=True)
    send_api_called_at = models.DateTimeField(null=True)
    verify_api_response_code = models.SmallIntegerField(blank=True, null=True)
    verify_api_called_at = models.DateTimeField(null=True)

    @classmethod
    def get_valid_logs_to_verify(cls, user, otp_type: int, usage: int) -> QuerySet['OTPLog']:
        return (
            cls.objects.filter(
                user=user,
                otp_type=otp_type,
                usage=usage,
                created_at__gte=ir_now() - timedelta(minutes=cls.OTP_VERIFY_DURATION_MINUTES),
                send_api_response_code=200,
            )
            .select_for_update(no_key=True)
            .exclude(send_api_called_at__isnull=True)
            .order_by('-created_at')
        )

    @classmethod
    def get_valid_logs_to_send(cls, user, otp_type: int, usage: int) -> QuerySet['OTPLog']:
        return (
            cls.objects.filter(
                user=user,
                otp_type=otp_type,
                usage=usage,
                created_at__gte=ir_now() - timedelta(minutes=cls.OTP_VERIFY_DURATION_MINUTES),
            )
            .select_for_update(no_key=True)
            .exclude(verify_api_called_at__isnull=False)
            .order_by('-created_at')
        )

    @classmethod
    def get_or_create_log(cls, user: 'User', otp_type: int, usage: int) -> 'OTPLog':
        existing_log = OTPLog.get_valid_logs_to_send(user, otp_type, usage).first()
        if existing_log:
            return existing_log

        internal_user = InternalUser.objects.get(uid=user.uid)
        return cls.objects.create(
            user=user,
            internal_user=internal_user,
            otp_type=otp_type,
            usage=usage,
        )

    def update_send_api_data(self, response_status: int) -> 'OTPLog':
        self.send_api_called_at = ir_now()
        self.send_api_response_code = response_status
        self.save(update_fields=['send_api_response_code', 'send_api_called_at'])
        return self

    def update_verify_api_data(self, response_status: int) -> 'OTPLog':
        self.verify_api_called_at = ir_now()
        self.verify_api_response_code = response_status
        self.save(
            update_fields=[
                'verify_api_response_code',
                'verify_api_called_at',
            ]
        )
        return self
