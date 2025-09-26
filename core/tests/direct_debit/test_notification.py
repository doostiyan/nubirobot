import decimal
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import TestCase, override_settings
from post_office.models import Email
from requests import HTTPError

from exchange.accounts.models import Notification, User, UserSms
from exchange.base.calendar import ir_now, to_shamsi_date
from exchange.base.crypto import random_string
from exchange.direct_debit.exceptions import ThirdPartyError
from exchange.direct_debit.models import DirectDebitContract
from exchange.direct_debit.notifications import (
    AutoContractCanceledNotification,
    ContractSuccessfullyCreatedNotification,
    ContractSuccessfullyEditedNotification,
    ContractSuccessfullyRemovedNotification,
    CreateContractFailedNotification,
    DirectDepositFailedNotification,
    DirectDepositSuccessfulNotification,
    EditContractFailedNotification,
    RemoveContractFailedNotification,
)
from tests.direct_debit.helper import DirectDebitMixins, MockResponse


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
@override_settings(IS_PROD=True)
@patch('django.db.transaction.on_commit', lambda t: t())
class DirectDebitNotificationTestCase(DirectDebitMixins, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.get(pk=201)
        self.user.mobile = '09022552500'
        self.user.email = 'alikafy@gmail.com'
        self.user.user_type = User.USER_TYPE_LEVEL1
        self.user.save()
        call_command('update_email_templates')
        vp = self.user.get_verification_profile()
        vp.email_confirmed = True
        vp.mobile_confirmed = True
        vp.save()

    @patch('exchange.direct_debit.tasks.User.has_verified_mobile_number', return_value=True)
    def test_create_contract_notification(self, _):
        notif = ContractSuccessfullyCreatedNotification(self.user)
        expires_at = ir_now()
        notif.send_push_notification('بانک ملت', expires_at, decimal.Decimal(10000.0))
        notification = Notification.objects.filter(user=self.user).last()
        assert (
            notification.message == f'قرارداد واریز مستقیم بانک ملت شما تا تاریخ '
                                    f'{to_shamsi_date(expires_at)}'
                                    f' و با سقف هر تراکنش 1000 تومان در نوبیتکس ایجاد شد.'
        )

        notif.send_sms('ملت')
        user_sms = UserSms.objects.get(
            user=self.user,
            tp=UserSms.TYPES.direct_debit_create_contract,
            to=self.user.mobile,
        )
        assert user_sms.text == 'ملت'
        assert user_sms.template == 81281
        assert user_sms.TEMPLATES[user_sms.template] == 'قرارداد واریز مستقیم [BankName] شما در نوبیتکس ایجاد شد.'

        call_command('update_email_templates')
        notif.send_email('ملت', expires_at, decimal.Decimal('1000.000'))
        email = Email.objects.last()
        assert self.user.email in email.to
        assert email.subject == 'ایجاد قرارداد واریز مستقیم'

    @patch('exchange.direct_debit.tasks.User.has_verified_mobile_number', return_value=True)
    def test_remove_contract_notification(self, _):
        notif = ContractSuccessfullyRemovedNotification(self.user)
        notif.send_push_notification('بانک ملت')
        notification = Notification.objects.filter(user=self.user).last()
        assert notification.message == 'قرارداد واریز مستقیم بانک ملت شما حذف شد.'
        notif.send_sms('بانک ملت')
        user_sms = UserSms.objects.get(
            user=self.user,
            tp=UserSms.TYPES.direct_debit_remove_contract,
            to=self.user.mobile,
        )
        assert user_sms.text == 'بانک ملت'
        assert user_sms.template == 81282
        assert user_sms.TEMPLATES[user_sms.template] == 'قرارداد واریز مستقیم [BankName] شما در نوبیتکس حذف شد.'

        call_command('update_email_templates')
        notif.send_email('ملت')
        email = Email.objects.last()
        assert self.user.email in email.to
        assert email.subject == 'لغو قرارداد واریز مستقیم'

    def test_edit_contract_notification(self):
        notif = ContractSuccessfullyEditedNotification(self.user)
        notif.send_push_notification('بانک ملت', 'فیلدهای')
        notification = Notification.objects.filter(user=self.user).last()
        assert notification.message == 'فیلدهای واریز مستقیم بانک ملت شما ویرایش و به‌روزرسانی شد.'

        call_command('update_email_templates')
        notif.send_email('ملت', 'فیلدهای')
        email = Email.objects.last()
        assert self.user.email in email.to
        assert email.subject == 'ویرایش موفق قرارداد واریز مستقیم'

    def test_deposit_notification(self):
        notif = DirectDepositSuccessfulNotification(self.user)
        notif.send_push_notification(decimal.Decimal('12000.000'), 'ملت')
        notification = Notification.objects.filter(user=self.user).last()
        assert notification.message == 'مبلغ 1200 تومان از حساب ملت به کیف پول اسپات شما واریز مستقیم شد.'

        call_command('update_email_templates')
        notif.send_email('ملت', decimal.Decimal('12000.000'))
        email = Email.objects.last()
        assert self.user.email in email.to
        assert email.subject == 'واریز مستقیم موفق'

    def test_create_contract_failed_notification(self):
        notif = CreateContractFailedNotification(self.user)
        notif.send_push_notification('بانک ملت')
        notification = Notification.objects.filter(user=self.user).last()
        assert notification.message == 'ایجاد قرارداد واریز مستقیم بانک ملت انجام نشد.'

    def test_edit_contract_failed_notification(self):
        notif = EditContractFailedNotification(self.user)
        notif.send_push_notification('بانک ملت')
        notification = Notification.objects.filter(user=self.user).last()
        assert notification.message == 'متاسفانه قرارداد واریز مستقیم بانک ملت ویرایش نشد.'

        call_command('update_email_templates')

    def test_remove_contract_failed_notification(self):
        notif = RemoveContractFailedNotification(self.user)
        notif.send_push_notification('بانک ملت')
        notification = Notification.objects.filter(user=self.user).last()
        assert notification.message == 'متاسفانه قرارداد واریز مستقیم بانک ملت حذف نشد.'

    def test_direct_deposit_failed_notification(self):
        notif = DirectDepositFailedNotification(self.user)
        notif.send_push_notification('بانک ملت')
        notification = Notification.objects.filter(user=self.user).last()
        assert notification.message == 'واریز مستقیم بانک ملت شما انجام نشد.'

        call_command('update_email_templates')

    @patch('exchange.direct_debit.tasks.User.has_verified_mobile_number', return_value=True)
    def test_auto_cancel_contract_notification(self, _):
        notif = AutoContractCanceledNotification(self.user)
        notif.send_push_notification('بانک ملت')
        notification = Notification.objects.filter(user=self.user).last()
        assert notification.message == 'قرارداد واریز مستقیم بانک ملت شما در نوبیتکس به‌دلیل موجودی ناکافی لغو شد.'
        notif.send_sms()
        user_sms = UserSms.objects.get(
            user=self.user,
            tp=UserSms.TYPES.direct_debit_auto_cancel,
            to=self.user.mobile,
        )
        assert user_sms.text == 'موجودی ناکافی'
        assert user_sms.template == 81283
        assert user_sms.TEMPLATES[user_sms.template] == 'قرارداد واریز مستقیم شما در نوبیتکس به‌دلیل [Reason] لغو شد.'

        call_command('update_email_templates')
        notif.send_email('ملت')
        email = Email.objects.last()
        assert self.user.email in email.to
        assert email.subject == 'لغو خودکار قرارداد واریز مستقیم'

    @patch('exchange.direct_debit.models.FaraboomHandler.activate_contract')
    def test_create_contract_notif(self, mock_faraboom):
        call_command('update_email_templates')
        _contract = self.create_contract(user=self.user, status=DirectDebitContract.STATUS.created)
        mock_faraboom.return_value = MockResponse(
            json_data={
                'payman_id': random_string(10),
                'status': 'ACTIVE',
            },
            status_code=200,
        )
        _contract.activate()
        _sms = (
            UserSms.objects.filter(
                user=self.user,
                tp=UserSms.TYPES.direct_debit_create_contract,
                to=self.user.mobile,
                template=UserSms.TEMPLATES.direct_debit_contract_successfully_created,
            )
            .order_by('-created_at')
            .first()
        )
        assert _sms.text == _contract.bank.name

        _notif = Notification.objects.filter(user=self.user).order_by('-created_at').first()

        max_transaction_amount = f'{(_contract.max_transaction_amount // 10).normalize():f}'
        assert _notif.message == (
            f'قرارداد واریز مستقیم {_contract.bank.name} شما'
            f' تا تاریخ {to_shamsi_date(_contract.expires_at)} '
            f'و با سقف هر تراکنش {max_transaction_amount}'
            f' تومان در نوبیتکس ایجاد شد.'
        )

        _email = Email.objects.last()
        assert self.user.email in _email.to
        assert _email.subject == 'ایجاد قرارداد واریز مستقیم'

    @patch('exchange.direct_debit.models.FaraboomHandler.change_contract_status')
    def test_cancel_contract_notif(self, mock_faraboom):
        call_command('update_email_templates')
        _contract = self.create_contract(user=self.user)
        mock_faraboom.return_value = MockResponse(
            json_data={
                'payman_id': random_string(10),
                'status': 'CANCELLED',
            },
            status_code=200,
        )
        _contract.change_status(new_status='cancelled')
        _sms = (
            UserSms.objects.filter(
                user=self.user,
                tp=UserSms.TYPES.direct_debit_remove_contract,
                to=self.user.mobile,
                template=UserSms.TEMPLATES.direct_debit_contract_successfully_removed,
            )
            .order_by('-created_at')
            .first()
        )
        assert _sms.text == _contract.bank.name

        _notif = Notification.objects.filter(user=self.user).order_by('-created_at').first()
        assert _notif.message == f'قرارداد واریز مستقیم {_contract.bank.name} شما حذف شد.'

        _email = Email.objects.last()
        assert self.user.email in _email.to
        assert _email.subject == 'لغو قرارداد واریز مستقیم'

    @patch('exchange.direct_debit.models.FaraboomHandler.change_contract_status')
    def test_cancel_contract_notif_failure(self, mock_faraboom):
        call_command('update_email_templates')
        _contract = self.create_contract(user=self.user)
        mock_response = MockResponse(
            json_data={
                'error': 'وضعیت قابل تغییر نمی باشد',
                'code': '2016',
                'errors': [
                    {
                        'error': 'وضعیت قابل تغییر نمی باشد',
                        'code': '2016',
                    },
                ],
            },
            status_code=400,
        )
        mock_faraboom.side_effect = HTTPError('http_error_msg', response=mock_response)

        with pytest.raises(ThirdPartyError):
            _contract.change_status(new_status='cancelled')
        _notif = Notification.objects.filter(user=self.user).order_by('-created_at').first()
        assert _notif.message == f'متاسفانه قرارداد واریز مستقیم {_contract.bank.name} حذف نشد.'
