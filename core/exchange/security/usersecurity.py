"""User Security Utilities"""
import datetime
from decimal import Decimal

from django.utils.timezone import now

from exchange.accounts.models import UserRestriction, UserSms
from exchange.accounts.user_restrictions import UserRestrictionsDescription
from exchange.accounts.userstats import UserStatsManager
from exchange.base.emailmanager import EmailManager


class UserSecurityManager:
    """User Security Helper Utilities"""

    @classmethod
    def _send_alert_email(cls, email, eta=None, template='tfa_removal'):
        """Send an email alert to notify user that her TFA is disabled."""
        EmailManager.send_email(
            email,
            template,
            priority='high',
            scheduled_time=eta,
        )

    @classmethod
    def send_disable_tfa_notifications(cls, user):
        """Notify user of OTP disable action."""
        cls._send_alert_email(user.email)
        cls._send_alert_email(user.email, eta=now() + datetime.timedelta(hours=8))
        cls._send_alert_email(user.email, eta=now() + datetime.timedelta(hours=16))
        # TODO: Send SMS with action template
        UserSms.objects.create(
            user=user,
            tp=UserSms.TYPES.tfa_disable,
            to=user.mobile,
            text='شناسایی دوعاملی حساب کاربری نوبیتکس شما غیرفعال شد',
        )

    @classmethod
    def apply_disable_tfa_limitations(cls, user, send_notifications=True):
        """Apply withdraw restrictions to the user that has disabled TFA."""
        UserRestriction.add_restriction(
            user,
            UserRestriction.RESTRICTION.WithdrawRequestCoin,
            considerations='ایجاد محدودیت برداشت به علت غیر فعال سازی شناسایی دو عاملی',
            duration=datetime.timedelta(hours=24),
            description=UserRestrictionsDescription.INACTIVE_2FA,
        )
        if send_notifications:
            cls.send_disable_tfa_notifications(user)
