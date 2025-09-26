from abc import ABC, abstractmethod
from urllib.parse import urljoin

from django.conf import settings

from exchange.accounts.kyc_param_notifier.enums import KYCParamForNotify, KYCParamNotifyType
from exchange.accounts.kyc_param_notifier.policy import NotifierInterface
from exchange.accounts.models import Notification, User, UserSms
from exchange.base.emailmanager import EmailManager
from exchange.base.models import Settings


class Notifier(NotifierInterface):
    """
    The class that realizes the NotifierInterface interface and has the ability to notify user.

    This class realizes the ``NotifierInterface``.

    It has the ability to notify in all three types of email (``notify_email``),
    notification (``notify_notification``), and SMS (``notify_sms``).

    Since the text for notifying got changed so many times the responsibility of
    generating the notifying messages (message that is send via email, sms, and notification)
    is delegated to another module (check messages.py). ``KYCParamNotifier`` only requires
    the interface ``MessageBuilderInterface`` as its message builder.

    """
    class MessageBuilderInterface(ABC):

        @abstractmethod
        def get_message(self) -> str:
            pass

    def __init__(
        self, notify_type: KYCParamNotifyType, /,
        user: User, kyc_param: KYCParamForNotify, confirmed: bool, message_builder: MessageBuilderInterface
    ):
        self.notify_type = notify_type
        self.user = user
        self.kyc_param = kyc_param
        self.confirmed = confirmed
        self.message_builder = message_builder

    def get_message(self) -> str:
        return self.message_builder.get_message()

    def notify_email(self, message: str):
        title = f'احراز هویت نوبیتکس - عدم تایید در {self.kyc_param.value}'
        button_message = 'مشاهده احراز هویت در پنل کاربری'
        template = 'kyc_param_rejected'

        if self.confirmed:
            title = f'احراز هویت نوبیتکس - {self.kyc_param.value} شما تایید شد'
            button_message = 'ادامه احراز هویت'
            template = 'kyc_param_confirmed'

        skip_emails = Settings.get_cached_json(
            'kyc_skip_email',
            {
                'confirmed': [],
                'rejected': [],
            },
        )
        if self.kyc_param.name.lower() in skip_emails.get('confirmed' if self.confirmed else 'rejected', []):
            return

        domain = settings.PROD_FRONT_URL if settings.IS_PROD else settings.TESTNET_FRONT_URL
        EmailManager.send_email(
            self.user.email,
            template,
            data=dict(
                title=title,
                message=message,
                button_message=button_message,
                kyc_page=urljoin(domain, 'panel/verification/'),
            ),
            priority='low',
        )

    def notify_notification(self, message: str):
        Notification.objects.create(
            user=self.user,
            message=message,
        )

    def notify_sms(self, message: str):
        UserSms.objects.create(
            user=self.user,
            tp=UserSms.TYPES.kyc_parameter,
            to=self.user.mobile,
            text=message,
        )

    def notify_user(self):
        """
        Notify user with the message received from ``MessageBuilderInterface`` (in fact
        the object that provides this interface) based on the ``KYCParamNotifyType``.

        Returns:
            None
        """
        {
            KYCParamNotifyType.EMAIL: self.notify_email,
            KYCParamNotifyType.NOTIFICATION: self.notify_notification,
            KYCParamNotifyType.SMS: self.notify_sms,
        }[self.notify_type](message=self.get_message())
