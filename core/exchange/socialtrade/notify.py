from typing import List, Optional, Union

from exchange.accounts.models import Notification, User, UserSms, VerificationProfile
from exchange.base.emailmanager import EmailManager
from exchange.socialtrade.tasks import task_send_mass_emails, task_send_mass_notifications, task_send_mass_sms


def notify_user(
    user: User,
    sms_tp: Optional[int] = None,
    sms_template: Optional[int] = None,
    sms_text: Optional[str] = None,
    notification_message: Optional[str] = None,
    email_template: Optional[str] = None,
    email_data: Optional[dict] = None,
):
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
            priority='low',
        )


def notify_mass_users(
    users_ids: List[int],
    sms_tps: Union[List[int], int, None] = None,
    sms_templates: Union[List[int], int, None] = None,
    sms_texts: Union[List[str], str, None] = None,
    notification_messages: Union[List[str], str, None] = None,
    email_templates: Union[List[str], str, None] = None,
    email_data: Union[List[dict], dict, None] = None,
):
    if sms_tps:
        task_send_mass_sms.delay(users_ids, sms_tps, sms_texts, sms_templates)
    if notification_messages:
        task_send_mass_notifications.delay(users_ids, notification_messages)
    if email_templates:
        task_send_mass_emails.delay(users_ids, email_templates, email_data)
