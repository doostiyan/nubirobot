import abc
import datetime
import decimal
from abc import ABC

from exchange.accounts.models import Notification, User, UserSms
from exchange.base.calendar import to_shamsi_date
from exchange.base.tasks import send_email


class DirectDebitBaseNotification(ABC):
    event_name: str

    @property
    def email_template_name(self):
        return f'direct_debit/{self.event_name}'

    def __init__(self, user: User):
        self.user = user

    def send_email(self, **kwargs):
        pass

    def send_sms(self, **kwargs):
        pass

    def send_push_notification(self, **kwargs):
        pass

    @abc.abstractmethod
    def send(self, **kwargs):
        pass


class ContractSuccessfullyCreatedNotification(DirectDebitBaseNotification):
    event_name = 'contract_successfully_created'

    def send_email(self, bank_name: str, expires_at: datetime, max_amount: decimal.Decimal):
        if not self.user.is_email_verified:
            return
        data = {
            'email_title': 'ایجاد قرارداد واریز مستقیم',
            'bank_name': bank_name,
            'expires_at': to_shamsi_date(expires_at),
            'max_amount': f'{(max_amount // 10).normalize():f}',
        }
        send_email.delay(email=self.user.email, template=self.email_template_name, data=data)

    def send_sms(self, bank_name: str):
        if not self.user.has_verified_mobile_number:
            return
        UserSms.objects.create(
            user=self.user,
            tp=UserSms.TYPES.direct_debit_create_contract,
            to=self.user.mobile,
            template=UserSms.TEMPLATES.direct_debit_contract_successfully_created,
            text=bank_name,
        )

    def send_push_notification(self, bank_name: str, expires_at: datetime, max_amount: decimal.Decimal):
        message = direct_debit_notification[self.event_name].format(
            bank_name=bank_name,
            expires_at=to_shamsi_date(expires_at),
            max_amount=f'{(max_amount // 10).normalize():f}',
        )
        Notification.objects.create(user_id=self.user.id, message=message)

    def send(self, bank_name: str, expires_at: datetime, max_amount: decimal.Decimal):
        self.send_email(bank_name=bank_name, expires_at=expires_at, max_amount=max_amount)
        self.send_sms(bank_name=bank_name)
        self.send_push_notification(bank_name=bank_name, expires_at=expires_at, max_amount=max_amount)


class ContractSuccessfullyRemovedNotification(DirectDebitBaseNotification):
    event_name = 'contract_successfully_removed'

    def send_email(self, bank_name: str):
        if not self.user.is_email_verified:
            return
        data = {
            'email_title': 'لغو قرارداد واریز مستقیم',
            'bank_name': bank_name,
        }
        send_email.delay(email=self.user.email, template=self.email_template_name, data=data)

    def send_sms(self, bank_name: str):
        if not self.user.has_verified_mobile_number:
            return
        UserSms.objects.create(
            user=self.user,
            tp=UserSms.TYPES.direct_debit_remove_contract,
            to=self.user.mobile,
            template=UserSms.TEMPLATES.direct_debit_contract_successfully_removed,
            text=bank_name,
        )

    def send_push_notification(self, bank_name: str):
        message = direct_debit_notification[self.event_name].format(bank_name=bank_name)
        Notification.objects.create(user_id=self.user.id, message=message)

    def send(self, bank_name: str):
        self.send_email(bank_name=bank_name)
        self.send_sms(bank_name=bank_name)
        self.send_push_notification(bank_name=bank_name)


class ContractSuccessfullyEditedNotification(DirectDebitBaseNotification):
    event_name = 'contract_successfully_edited'

    def send_email(self, bank_name: str, edited_fields: str):
        if not self.user.is_email_verified:
            return
        data = {
            'email_title': 'ویرایش موفق قرارداد واریز مستقیم',
            'bank_name': bank_name,
            'edited_fields': edited_fields,
        }
        send_email.delay(email=self.user.email, template=self.email_template_name, data=data)

    def send_push_notification(self, bank_name: str, edited_fields: str):
        message = direct_debit_notification[self.event_name].format(bank_name=bank_name, edited_fields=edited_fields)
        Notification.objects.create(user_id=self.user.id, message=message)

    def send(self, bank_name: str, edited_fields: str):
        self.send_email(bank_name=bank_name, edited_fields=edited_fields)
        self.send_push_notification(bank_name, edited_fields)


class DirectDepositSuccessfulNotification(DirectDebitBaseNotification):
    event_name = 'deposit_successfully'

    def send_email(self, bank_name: str, amount: decimal.Decimal):
        if not self.user.is_email_verified:
            return
        data = {
            'email_title': 'واریز مستقیم موفق',
            'bank_name': bank_name,
            'amount': f'{(amount // 10).normalize():f}',
        }
        send_email.delay(email=self.user.email, template=self.email_template_name, data=data)

    def send_push_notification(self, amount: decimal.Decimal, bank_name: str):
        amount = f'{(amount // 10).normalize():f}'
        message = direct_debit_notification[self.event_name].format(amount=amount, bank_name=bank_name)
        Notification.objects.create(user_id=self.user.id, message=message)

    def send_sms(self, bank_name: str):
        if not self.user.has_verified_mobile_number:
            return
        UserSms.objects.create(
            user=self.user,
            tp=UserSms.TYPES.direct_debit_deposit,
            to=self.user.mobile,
            template=UserSms.TEMPLATES.direct_debit_deposit_successfully,
            text=bank_name,
        )

    def send(self, amount: decimal.Decimal, bank_name: str):
        self.send_email(amount=amount, bank_name=bank_name)
        self.send_push_notification(amount=amount, bank_name=bank_name)
        self.send_sms(bank_name=bank_name)


class CreateContractFailedNotification(DirectDebitBaseNotification):
    event_name = 'create_contract_failed'

    def send_push_notification(self, bank_name: str):
        message = direct_debit_notification[self.event_name].format(bank_name=bank_name)
        Notification.objects.create(user_id=self.user.id, message=message)

    def send(self, bank_name: str):
        self.send_push_notification(bank_name)


class EditContractFailedNotification(DirectDebitBaseNotification):
    event_name = 'edit_contract_failed'

    def send_push_notification(self, bank_name: str):
        message = direct_debit_notification[self.event_name].format(bank_name=bank_name)
        Notification.objects.create(user_id=self.user.id, message=message)

    def send(self, bank_name: str):
        self.send_push_notification(bank_name)


class RemoveContractFailedNotification(DirectDebitBaseNotification):
    event_name = 'remove_contract_failed'

    def send_push_notification(self, bank_name: str):
        message = direct_debit_notification[self.event_name].format(bank_name=bank_name)
        Notification.objects.create(user_id=self.user.id, message=message)

    def send(self, bank_name: str):
        self.send_push_notification(bank_name)


class DirectDepositFailedNotification(DirectDebitBaseNotification):
    event_name = 'deposit_failed'

    def send_push_notification(self, bank_name: str):
        message = direct_debit_notification[self.event_name].format(bank_name=bank_name)
        Notification.objects.create(user_id=self.user.id, message=message)

    def send(self, bank_name: str):
        self.send_push_notification(bank_name)


class AutoContractCanceledNotification(DirectDebitBaseNotification):
    event_name = 'auto_contract_canceled'

    def send_email(self, bank_name: str):
        if not self.user.is_email_verified:
            return
        data = {
            'email_title': 'لغو خودکار قرارداد واریز مستقیم',
            'bank_name': bank_name,
        }
        send_email.delay(email=self.user.email, template=self.email_template_name, data=data)

    def send_sms(self):
        if not self.user.has_verified_mobile_number:
            return
        reason = 'موجودی ناکافی'
        UserSms.objects.create(
            user=self.user,
            tp=UserSms.TYPES.direct_debit_auto_cancel,
            to=self.user.mobile,
            template=UserSms.TEMPLATES.direct_debit_contract_canceled,
            text=reason,
        )

    def send_push_notification(self, bank_name: str):
        message = direct_debit_notification[self.event_name].format(bank_name=bank_name)
        Notification.objects.create(user_id=self.user.id, message=message)

    def send(self, bank_name: str):
        self.send_email(bank_name)
        self.send_sms()
        self.send_push_notification(bank_name)


direct_debit_notification = {
    'contract_successfully_created': 'قرارداد واریز مستقیم {bank_name} شما تا تاریخ {expires_at} '
                                     'و با سقف هر تراکنش {max_amount} تومان در نوبیتکس ایجاد شد.',
    'contract_successfully_edited': '{edited_fields} واریز مستقیم {bank_name} شما ویرایش و به‌روزرسانی شد.',
    'contract_successfully_removed': 'قرارداد واریز مستقیم {bank_name} شما حذف شد.',
    'deposit_successfully': 'مبلغ {amount} تومان از حساب {bank_name} به کیف پول اسپات شما واریز مستقیم شد.',
    'create_contract_failed': 'ایجاد قرارداد واریز مستقیم {bank_name} انجام نشد.',
    'edit_contract_failed': 'متاسفانه قرارداد واریز مستقیم {bank_name} ویرایش نشد.',
    'remove_contract_failed': 'متاسفانه قرارداد واریز مستقیم {bank_name} حذف نشد.',
    'deposit_failed': 'واریز مستقیم {bank_name} شما انجام نشد.',
    'auto_contract_canceled': 'قرارداد واریز مستقیم {bank_name} شما در نوبیتکس به‌دلیل موجودی ناکافی لغو شد.',
}
