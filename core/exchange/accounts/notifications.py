from typing import Dict

from exchange.accounts.models import Notification, User, UserSms
from exchange.base.emailmanager import EmailManager


def send_change_password_notification(user: User, context: Dict[str, str]) -> None:
    if user.email and not user.email.endswith('mobile.ntx.ir') and user.is_email_verified:
        EmailManager.send_change_password_notif(user, context['ip'], context['device_id'])
    elif user.has_verified_mobile_number:
        UserSms.objects.create(
            user=user,
            tp=UserSms.TYPES.change_password_notif,
            to=user.mobile,
            text='۲۴ ساعت',
            template=UserSms.TEMPLATES.change_password_notif,
        )


def send_set_password_notification(user: User):
    message = 'رمزعبور برای حساب کاربری {} با موفقیت تعیین شد، ' \
              'از این پس علاوه بر ورود مستقیم با گوگل، می‌توانید با ایمیل و رمزعبور خود نیز وارد شوید.'.format(
        user.email
    )

    email_title = 'تعیین موفق رمزعبور'
    EmailManager.send_email(
        user.email,
        'template',
        data=dict(
            title=email_title,
            message=message,
        ),
    )
    Notification.objects.create(
        user=user,
        message=message,
    )
