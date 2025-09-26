import datetime
import re
import uuid
from typing import List

from django.conf import settings
from django.db import models
from django.utils.timezone import now
from model_utils import Choices

from exchange.accounts.models import User
from exchange.base.models import Settings
from exchange.broker.broker.schema import SMSSchema
from exchange.notification.managers import BulkCreateWithSignalManager
from exchange.notification.models import InAppNotification
from exchange.notification.sms.sms_integrations import SmsSender
from exchange.notification.sms.sms_templates import OLD_SMSIR_TEMPLATES


class Sms(models.Model):
    """Sms represents SMS messages sent to users"""

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
        (38, 'abc_debit_card_issued', 'ABC Debit Card Issued'),
        (39, 'abc_debit_card_activated', 'ABC Debit Card Activated'),
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

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(User, related_name='new_sent_sms_set', on_delete=models.CASCADE, null=True)
    admin = models.ForeignKey(User, related_name='new_sms_set', on_delete=models.CASCADE, null=True)
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

    def send(self, is_fast: bool):
        numbers = self.get_receiving_numbers()
        fast_send = is_fast or self.template > 0
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
                    InAppNotification.objects.create(
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
    def create(cls, sms_data: SMSSchema) -> 'Sms':
        user = User.objects.filter(uid=sms_data.user_id).only('id').first() if sms_data.user_id else None
        sms = Sms(
            user=user,
            text=sms_data.text,
            to=sms_data.to,
            tp=sms_data.tp,
            template=sms_data.template,
        )
        numbers = sms.get_receiving_numbers()
        if len(numbers) > 1:
            sms.to = numbers[0]
        sms.save()
        return sms

    @classmethod
    def get_verification_messages(cls, user: User) -> 'QuerySet[UserSms]':
        return cls.objects.filter(
            user=user, created_at__gte=now() - datetime.timedelta(minutes=20), tp=cls.TYPES.verify_phone
        )
