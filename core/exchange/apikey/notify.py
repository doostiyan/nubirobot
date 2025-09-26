import enum
from dataclasses import dataclass
from typing import Optional

from exchange.accounts.models import Notification, User, UserSms, VerificationProfile
from exchange.base.emailmanager import EmailManager


def notify_user(
    user: User,
    *,
    sms_tp: Optional[int] = None,
    sms_template: int = 0,
    sms_text: Optional[str] = None,
    email_template: Optional[str] = None,
    email_data: Optional[dict] = None,
    notification_message: Optional[str] = None,
) -> None:
    verification_profile: VerificationProfile = user.get_verification_profile()

    if sms_tp is not None and user.mobile and verification_profile.mobile_confirmed:
        UserSms.objects.create(
            user=user,
            tp=sms_tp,
            to=user.mobile,
            template=sms_template,
            text=sms_text,
        )

    if notification_message is not None:
        Notification.objects.create(
            user=user,
            message=notification_message,
        )

    if email_template is not None and verification_profile.email_confirmed:
        EmailManager.send_email(
            email=user.email,
            template=email_template,
            data=email_data,
            priority='high',
        )


@dataclass(frozen=True)
class APIKeyNotification:
    email_template: Optional[str] = None
    sms_tp: Optional[int] = None
    sms_text: Optional[str] = None
    notification_message: Optional[str] = None

    def send(self, user: User, *, email_data: Optional[dict] = None):
        notify_user(
            user=user,
            email_template=self.email_template,
            email_data=email_data,
            sms_tp=self.sms_tp,
            sms_text=self.sms_text,
            notification_message=self.notification_message,
        )


class APIKeyNotifications(enum.Enum):
    CREATION = APIKeyNotification(
        email_template='apikey/creation',
        sms_tp=UserSms.TYPES.api_key_create,
        sms_text=(
            'نوبیتکس: API Key جدید در حساب کاربری شما ایجاد شد. در '
            'صورت عدم تایید، سریعاً به حساب کاربری خود مراجعه نمایید.'
        ),
        notification_message='API Key جدید با موفقیت ایجاد شد. جزئیات را در بخش تنظیمات API مشاهده کنید.',
    )
    UPDATE = APIKeyNotification(
        email_template='apikey/update',
        sms_tp=UserSms.TYPES.api_key_update,
        sms_text=(
            'نوبیتکس: API Key شما ویرایش شد. در صورت مشاهده فعالیت مشکوک، سریعاً به حساب کاربری خود مراجعه نمایید.'
        ),
        notification_message=(
            'تغییراتی در یکی از API Keyهای شما اعمال شد. لطفاً صحت آن را ا مراجعه به حساب کاربری خود بررسی کنید.'
        ),
    )
    DELETION = APIKeyNotification(
        email_template='apikey/deletion',
        sms_tp=UserSms.TYPES.api_key_delete,
        sms_text='نوبیتکس: یک API Key از حساب شما حذف شد. در صورت عدم تایید، سریعاً به حساب کاربری خود مراجعه نمایید.',
        notification_message=(
            'API Key حذف شد. در صورت عدم تایید، لطفاً صحت آن را با مراجعه به حساب کاربری خود بررسی کنید.'
        ),
    )

    def send(self, user: User, *, email_data: Optional[dict] = None):
        self.value.send(user, email_data=email_data)
