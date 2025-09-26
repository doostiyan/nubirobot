from django.conf import settings
from model_utils import Choices

from exchange.accounts.models import Notification, User, UserSms
from exchange.base.emailmanager import EmailManager
from exchange.base.lazy_var import LazyVar
from exchange.base.models import Settings
from exchange.broker.broker.client.producer import EventProducer
from exchange.broker.broker.schema import EmailSchema, NotificationSchema, SMSSchema
from exchange.broker.broker.topics import Topics

producer = LazyVar(lambda: EventProducer(config=settings.KAFKA_PRODUCER_CONFIG))


class NotificationProvider:
    MESSAGE_TYPES = Choices(
        (27, 'grant_financial_service', 'Grant Financial Service'),
        (38, 'abc_debit_card_issued', 'ABC Debit Card Issued'),
        (39, 'abc_debit_card_activated', 'ABC Debit Card Activated'),
    )
    TEMPLATE_TYPES = Choices(
        (
            81287,
            'grant_financial_service',
            'کد تأیید جهت فعالسازی سرویس [FinancialService] در نوبیتکس\nکد: [VerificationCode]',
        ),
    )
    SMS_URGENT_TYPES = ()

    def send_notif(self, user: User, message: str):
        if Settings.get_flag('abc_use_notification_kafka'):
            self._produce_notif_event(user, message)
            return

        Notification.objects.create(
            user=user,
            message=message,
        )

    @staticmethod
    def _produce_notif_event(user: User, message: str):
        notif = NotificationSchema(
            user_id=str(user.uid),
            message=message,
            sent_to_telegram=False,
            sent_to_fcm=False,
        )
        producer.write_event(Topics.NOTIFICATION.value, notif.serialize())

    def send_sms(self, user: User, tp: str, text: str, template: int):
        if Settings.get_flag('abc_use_notification_kafka'):
            self._produce_sms_event(user=user, tp=tp, text=text, template=template)
            return

        UserSms.objects.create(
            user=user,
            tp=tp,
            to=user.mobile,
            text=text,
            template=template,
        )

    def _produce_sms_event(self, user: User, tp: str, text: str, template: int):
        sms = SMSSchema(
            user_id=str(user.uid),
            text=text,
            tp=tp,
            to=user.mobile,
            template=template,
        )
        topic = Topics.FAST_SMS.value if sms.tp in self.SMS_URGENT_TYPES else Topics.SMS.value
        producer.write_event(topic, sms.serialize())

    def send_email(self, to_email: str, template: str, priority='medium', data=None):
        if Settings.get_flag('abc_use_notification_kafka'):
            self._produce_email_event(to_email=to_email, template=template, data=data, priority=priority)
            return

        EmailManager.send_email(email=to_email, template=template, data=data)

    @staticmethod
    def _produce_email_event(to_email: str, template: str, priority, data=None):
        email_schema_object = EmailSchema(
            to=to_email,
            from_email=settings.EMAIL_FROM,
            template=template,
            context=data,
            priority=priority,
        )
        producer.write_event(Topics.EMAIL.value, email_schema_object.serialize())


notification_provider = NotificationProvider()
