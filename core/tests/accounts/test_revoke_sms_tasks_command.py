import random
import string
import uuid
from unittest.mock import MagicMock, call, patch

from celery.result import AsyncResult
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import User, UserSms
from tests.base.utils import mock_on_commit


class RevokeSendSmsTasksBySmsTemplateCommandTest(TestCase):
    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user.mobile = '09' + ''.join(random.choices(string.digits, k=10))
        self.user.save()
        cache.clear()

    def tearDown(self):
        UserSms.objects.filter(template=UserSms.TEMPLATES.verify_new_address).delete()
        UserSms.objects.filter(template=UserSms.TEMPLATES.abc_margin_call_adjustment).delete()

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.accounts.signals.task_send_user_sms.apply_async', new_callable=MagicMock)
    def test_cache_task_ids_at_sms_post_save_signal(self, mock_send_sms_task, _):
        addressbook_sms_list, abc_sms_list, send_sms_task_list = [], [], []

        def task_send_sms_mock(args, expires):
            task_result = AsyncResult(str(uuid.uuid4()))
            send_sms_task_list.append(task_result.id)
            return task_result

        mock_send_sms_task.side_effect = task_send_sms_mock

        for _ in range(4):
            addressbook_sms_list.append(
                UserSms.objects.create(
                    user=self.user,
                    to=self.user.mobile,
                    template=UserSms.TEMPLATES.verify_new_address,
                    text='123',
                    tp=UserSms.TYPES.verify_new_address,
                ).id
            )
            abc_sms_list.append(
                UserSms.objects.create(
                    user=self.user,
                    to=self.user.mobile,
                    template=UserSms.TEMPLATES.abc_margin_call_adjustment,
                    text='456',
                    tp=UserSms.TYPES.abc_margin_call_adjustment,
                ).id
            )

        cache_keys = [
            UserSms.TASK_ID_CACHE_KEY.format(sms_id=sms_id) for sms_id in [*addressbook_sms_list, *abc_sms_list]
        ]
        task_ids = [v for _, v in (cache.get_many(cache_keys)).items()]
        assert sorted(task_ids) == sorted(send_sms_task_list)

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.accounts.functions.app.AsyncResult.revoke', new_callable=MagicMock)
    @patch('exchange.accounts.signals.task_send_user_sms.delay', new_callable=MagicMock)
    def test_revoke_called_on_tasks(self, mock_task_send_sms, mock_revoke, _):
        addressbook_sms_list, abc_sms_list, send_sms_task_list = [], [], []
        for i in range(4):
            addressbook_sms_list.append(
                UserSms.objects.create(
                    user=self.user,
                    to=self.user.mobile,
                    template=UserSms.TEMPLATES.verify_new_address,
                    text='123',
                    tp=UserSms.TYPES.verify_new_address,
                ).id
            )
            delivery_status = 'Sent: fake' if i % 2 == 0 else None
            abc_sms_list.append(
                UserSms.objects.create(
                    user=self.user,
                    to=self.user.mobile,
                    template=UserSms.TEMPLATES.abc_margin_call_adjustment,
                    text='456',
                    tp=UserSms.TYPES.abc_margin_call_adjustment,
                    delivery_status=delivery_status,
                ).id
            )

        call_command('revoke_send_sms_tasks_by_sms_template', 'abc_margin_call_adjustment')
        mock_revoke.assert_has_calls([call() for _ in range(2)])

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.accounts.functions.app.AsyncResult.revoke', new_callable=MagicMock)
    @patch('exchange.accounts.signals.task_send_user_sms.delay', new_callable=MagicMock)
    def test_revoke_called_on_tasks_with_multiple_templates(self, mock_task_send_sms, mock_revoke, _):
        for i in range(4):
            delivery_status = 'Sent: fake' if i == 0 else None
            UserSms.objects.create(
                user=self.user,
                to=self.user.mobile,
                template=UserSms.TEMPLATES.verify_new_address,
                text='123',
                tp=UserSms.TYPES.verify_new_address,
                delivery_status=delivery_status,
            )
            UserSms.objects.create(
                user=self.user,
                to=self.user.mobile,
                template=UserSms.TEMPLATES.abc_margin_call_adjustment,
                text='456',
                tp=UserSms.TYPES.abc_margin_call_adjustment,
                delivery_status=delivery_status,
            )

        call_command(
            'revoke_send_sms_tasks_by_sms_template', 'abc_margin_call_adjustment,verify_new_address,gift_redeem_otp'
        )
        mock_revoke.assert_has_calls([call() for _ in range(6)])

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.accounts.functions.app.AsyncResult.revoke', new_callable=MagicMock)
    @patch('exchange.accounts.signals.task_send_user_sms.delay', new_callable=MagicMock)
    def test_revoke_called_on_tasks_of_all_templates(self, mock_task_send_sms, mock_revoke, _):
        for i in range(4):
            delivery_status = 'Sent: fake' if i != 0 else None
            UserSms.objects.create(
                user=self.user,
                to=self.user.mobile,
                template=UserSms.TEMPLATES.verify_new_address,
                text='123',
                tp=UserSms.TYPES.verify_new_address,
                delivery_status=delivery_status,
            )
            UserSms.objects.create(
                user=self.user,
                to=self.user.mobile,
                template=UserSms.TEMPLATES.abc_margin_call_adjustment,
                text='456',
                tp=UserSms.TYPES.abc_margin_call_adjustment,
                delivery_status=delivery_status,
            )

        call_command('revoke_send_sms_tasks_by_sms_template', 'all')
        mock_revoke.assert_has_calls([call() for _ in range(2)])
