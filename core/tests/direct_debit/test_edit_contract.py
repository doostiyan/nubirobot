import datetime
from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from post_office.models import Email
from rest_framework import status

from exchange.accounts.models import Notification, User
from exchange.base.calendar import get_earliest_time, get_latest_time, ir_now
from exchange.direct_debit.models import DirectDebitContract
from tests.direct_debit.helper import DirectDebitMixins, MockResponse


class EditContractTests(DirectDebitMixins, TestCase):
    fixtures = ('test_data',)

    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)
        self.user.user_type = User.USER_TYPES.level1
        self.user.save()

        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.url = '/direct-debit/contracts/{}'
        self.request_feature(self.user, 'done')
        self.bank = self.create_bank(max_daily_transaction_amount=Decimal(120000000), max_daily_transaction_count=50)

    def _send_request(self, pk: int, data: dict = None):
        url = self.url.format(pk)
        return self.client.put(url, data=data, content_type='application/json')

    @patch('exchange.direct_debit.models.FaraboomHandler.update_contract')
    def test_edit_contract_all_params(self, mock_update_contract_response):
        contract = self.create_contract(self.user, bank=self.bank)
        mock_update_contract_response.return_value = MockResponse(
            None, status.HTTP_302_FOUND, {'Location': 'http://localhost/oauth'}
        )
        toDate = ir_now() + datetime.timedelta(days=25)
        response = self._send_request(
            contract.id,
            {
                'toDate': toDate.strftime('%Y-%m-%d'),
                'dailyMaxTransactionCount': 10,
                'maxTransactionAmount': 50000000,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {'status': 'ok', 'location': 'http://localhost/oauth'}

        _contract = (
            DirectDebitContract.objects.filter(contract_code=contract.contract_code).order_by('-created_at').first()
        )
        assert _contract
        assert _contract.id != contract.id
        assert _contract.location == 'http://localhost/oauth'
        assert _contract.status == DirectDebitContract.STATUS.waiting_for_update

    @patch('exchange.direct_debit.models.FaraboomHandler.update_contract')
    def test_edit_contract_expire_date(self, mock_update_contract_response):
        contract = self.create_contract(self.user, bank=self.bank)
        mock_update_contract_response.return_value = MockResponse(
            None, status.HTTP_302_FOUND, {'Location': 'http://localhost/oauth'}
        )
        toDate = ir_now() + datetime.timedelta(days=35)
        response = self._send_request(
            contract.id,
            {
                'toDate': toDate.strftime('%Y-%m-%d'),
                'maxTransactionAmount': 60000000,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {'status': 'ok', 'location': 'http://localhost/oauth'}

    def test_edit_contract_expire_date_error(self):
        contract = self.create_contract(self.user, bank=self.bank)
        toDate = ir_now() - datetime.timedelta(minutes=5)
        response = self._send_request(
            contract.id,
            {
                'toDate': toDate.strftime('%Y-%m-%d'),
                'maxTransactionAmount': 60000000,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'status': 'failed',
            'code': 'ToDateInvalidError',
            'message': 'toDate should be greater than now',
        }

    @patch('exchange.direct_debit.models.FaraboomHandler.update_contract')
    def test_edit_contract_two_params(self, mock_update_contract_response):
        contract = self.create_contract(self.user, bank=self.bank)
        mock_update_contract_response.return_value = MockResponse(
            None, status.HTTP_302_FOUND, {'Location': 'http://localhost/oauth'}
        )
        response = self._send_request(
            contract.id,
            {
                'dailyMaxTransactionCount': 10,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {'status': 'ok', 'location': 'http://localhost/oauth'}

    def test_edit_contract_transaction_count_over_the_bank_limit(self):
        contract = self.create_contract(self.user, bank=self.bank)
        response = self._send_request(
            contract.id,
            {
                'dailyMaxTransactionCount': contract.bank.daily_max_transaction_count + 1,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'status': 'failed',
            'code': 'DailyMaxTransactionCountError',
            'message': 'Daily max transaction count is more than the bank limit!',
        }
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_edit_contract_transaction_amount_over_the_bank_limit(self):
        self.bank.max_transaction_amount = Decimal(200000)
        self.bank.save()
        contract = self.create_contract(self.user, bank=self.bank)
        response = self._send_request(
            contract.id,
            {
                'maxTransactionAmount': contract.bank.max_transaction_amount + 10,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'status': 'failed',
            'code': 'MaxTransactionAmountError',
            'message': 'Max transaction amount is more than the bank limit!',
        }
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('exchange.direct_debit.models.FaraboomHandler.update_contract')
    def test_edit_contract_transaction_amount_without_bank_limit(self, mock_update_contract_response):
        mock_update_contract_response.return_value = MockResponse(
            None, status.HTTP_302_FOUND, {'Location': 'http://localhost/oauth'}
        )
        contract = self.create_contract(self.user, bank=self.bank)
        response = self._send_request(
            contract.id,
            {
                'maxTransactionAmount': contract.bank.max_transaction_amount + 10,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {'status': 'ok', 'location': 'http://localhost/oauth'}

    def test_edit_contract_empty_params(self):
        contract = self.create_contract(self.user, bank=self.bank)
        response = self._send_request(contract.id, {})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'status': 'failed',
            'code': 'InvalidParams',
            'message': 'No changes detected',
        }

    def test_edit_contract_bank_disabled(self):
        contract = self.create_contract(self.user, bank=self.bank)
        self.bank.is_active = False
        self.bank.save()
        response = self._send_request(contract.id, {})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {
            'code': 'DeactivatedBankError',
            'message': 'The bank is not active',
            'status': 'failed',
        }

    def test_edit_contract_with_params_without_change(self):
        toDate = ir_now() + datetime.timedelta(days=35)
        contract = self.create_contract(
            self.user, bank=self.bank, expire_date=get_latest_time(toDate), count=10, amount=Decimal('10_000_000_0')
        )
        response = self._send_request(
            contract.id,
            {
                'toDate': toDate.strftime('%Y-%m-%d'),
                'dailyMaxTransactionCount': 10,
                'maxTransactionAmount': 1000000000,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'status': 'failed',
            'code': 'InvalidParams',
            'message': 'No changes detected',
        }

    @patch('exchange.direct_debit.models.FaraboomHandler.update_contract')
    def test_edit_contract_same_expire_date_but_offset_crosses_previous_day(self, mock_update_contract_response):
        to_date = get_earliest_time(ir_now()) + datetime.timedelta(days=35)
        contract = self.create_contract(
            self.user, bank=self.bank, expire_date=to_date, count=10, amount=Decimal('10_000_000_0')
        )
        new_to_date = to_date + datetime.timedelta(minutes=1)
        mock_update_contract_response.return_value = MockResponse(
            None, status.HTTP_302_FOUND, {'Location': 'http://localhost/oauth'}
        )
        response = self._send_request(
            contract.id,
            {
                'toDate': new_to_date.strftime('%Y-%m-%d'),
                'dailyMaxTransactionCount': 10,
                'maxTransactionAmount': 1000000000,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {'status': 'ok', 'location': 'http://localhost/oauth'}

    def test_set_expires_at_to_now(self):
        contract = self.create_contract(self.user, bank=self.bank, count=10, amount=Decimal('10_000_000_0'))
        new_to_date = ir_now()
        response = self._send_request(
            contract.id,
            {
                'toDate': new_to_date.strftime('%Y-%m-%d'),
                'dailyMaxTransactionCount': 10,
                'maxTransactionAmount': 1000000000,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'status': 'failed',
            'code': 'ToDateInvalidError',
            'message': 'toDate should be greater than now',
        }

    def test_edit_contract_with_params_daily_count_zero(self):
        to_date = ir_now() + datetime.timedelta(days=35)
        contract = self.create_contract(
            self.user,
            bank=self.bank,
            expire_date=get_latest_time(to_date),
            count=10,
            amount=Decimal('10_000_000_0'),
        )
        response = self._send_request(
            contract.id,
            {
                'dailyMaxTransactionCount': 0,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'status': 'failed',
            'code': 'InvalidParams',
            'message': 'No changes detected',
        }

    def test_edit_contract_invalid_status(self):
        contract = self.create_contract(self.user, bank=self.bank, status=DirectDebitContract.STATUS.cancelled)
        response = self._send_request(contract.id, {})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_edit_contract_parallel(self):
        contract = self.create_contract(self.user, bank=self.bank)
        self.create_contract(
            self.user,
            bank=self.bank,
            contract_code=contract.contract_code,
            status=DirectDebitContract.STATUS.waiting_for_update,
        )
        response = self._send_request(contract.id, {})

        assert response.status_code == status.HTTP_409_CONFLICT
        assert response.json() == {
            'status': 'failed',
            'code': 'ContractCannotBeUpdatedError',
            'message': 'There is already a waiting contract',
        }

    def test_edit_contract_user_eligibility(self):
        self.user.user_type = User.USER_TYPES.level0
        self.user.save()

        contract = self.create_contract(self.user, bank=self.bank)
        response = self._send_request(contract.id, {})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'UserLevelRestriction',
            'message': 'User level does not meet the requirements',
            'status': 'failed',
        }


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
@override_settings(IS_PROD=True)
class EditContractCallbackTests(DirectDebitMixins, TestCase):
    fixtures = ('test_data',)

    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)
        vp = self.user.get_verification_profile()
        vp.email_confirmed = True
        vp.mobile_confirmed = True
        vp.save()

        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.url = '/direct-debit/contracts/{}/update-callback'
        self.request_feature(self.user, 'done')
        self.bank = self.create_bank(
            max_daily_transaction_amount=Decimal(120000000), max_daily_transaction_count=50, name='بانک رسالت'
        )

        self.success_email_title = 'ویرایش موفق قرارداد واریز مستقیم'

        call_command('update_email_templates')

    def _send_request(self, trace_id: str, data: dict = None):
        url = self.url.format(trace_id)
        return self.client.get(url, data=data)

    def test_edit_contract_callback_updated(self):
        old_contract = self.create_contract(self.user, bank=self.bank)
        contract = self.create_contract(
            self.user,
            bank=self.bank,
            contract_code=old_contract.contract_code,
            status=DirectDebitContract.STATUS.waiting_for_update,
        )
        data = {
            'status': 'updated',
        }
        response = self._send_request(contract.trace_id, data)
        assert response.status_code == status.HTTP_200_OK
        contract.refresh_from_db()
        old_contract.refresh_from_db()
        self.assertContains(response, 'قرارداد با موفقیت ویرایش شد')

        assert contract.status == DirectDebitContract.STATUS.active
        assert old_contract.status == DirectDebitContract.STATUS.replaced

        _notif = Notification.objects.last()
        assert _notif.message == 'تاریخ انقضا واریز مستقیم بانک رسالت شما ویرایش و به‌روزرسانی شد.'

        _email = Email.objects.last()
        assert _email
        assert _email.subject == self.success_email_title
        assert self.user.email in _email.to

    def test_edit_contract_callback_cancelled(self):
        old_contract = self.create_contract(self.user, bank=self.bank)
        contract = self.create_contract(
            self.user,
            bank=self.bank,
            contract_code=old_contract.contract_code,
            status=DirectDebitContract.STATUS.waiting_for_update,
        )
        data = {
            'status': 'canceled',
        }
        response = self._send_request(contract.trace_id, data)
        assert response.status_code == status.HTTP_200_OK
        self.assertContains(response, 'ویرایش قرارداد لغو شد')

        contract.refresh_from_db()
        old_contract.refresh_from_db()
        assert contract.status == DirectDebitContract.STATUS.cancelled
        assert old_contract.status == DirectDebitContract.STATUS.active

        _notif = Notification.objects.last()
        assert _notif.message == 'متاسفانه قرارداد واریز مستقیم بانک رسالت ویرایش نشد.'

    def test_edit_contract_callback_internal_error(self):
        old_contract = self.create_contract(self.user, bank=self.bank)
        contract = self.create_contract(
            self.user,
            bank=self.bank,
            contract_code=old_contract.contract_code,
            status=DirectDebitContract.STATUS.waiting_for_update,
        )
        data = {'status': 'internal_error', 'code': '2165'}
        response = self._send_request(contract.trace_id, data)
        assert response.status_code == status.HTTP_200_OK
        self.assertContains(response, 'خطای فنی در هنگام ویرایش قرارداد رخ داده است. لطفا دقایقی بعد مجددا تلاش کنید.')

        contract.refresh_from_db()
        old_contract.refresh_from_db()
        assert contract.status == DirectDebitContract.STATUS.failed
        assert old_contract.status == DirectDebitContract.STATUS.active

        _notif = Notification.objects.last()
        assert _notif.message == 'متاسفانه قرارداد واریز مستقیم بانک رسالت ویرایش نشد.'

    def test_edit_contract_callback_timeout(self):
        old_contract = self.create_contract(self.user, bank=self.bank)
        contract = self.create_contract(
            self.user,
            bank=self.bank,
            contract_code=old_contract.contract_code,
            status=DirectDebitContract.STATUS.waiting_for_update,
        )
        data = {
            'status': 'timeout',
        }
        response = self._send_request(contract.trace_id, data)
        assert response.status_code == status.HTTP_200_OK
        self.assertContains(response, 'در ویرایش قرارداد مشکلی پیش آمد. لطفا بعد از کمی صبر، دوباره تلاش کنید.')

        contract.refresh_from_db()
        old_contract.refresh_from_db()
        assert contract.status == DirectDebitContract.STATUS.failed
        assert old_contract.status == DirectDebitContract.STATUS.active

        _notif = Notification.objects.last()
        assert _notif.message == 'متاسفانه قرارداد واریز مستقیم بانک رسالت ویرایش نشد.'

    def test_edit_contract_callback_unknown_status(self):
        old_contract = self.create_contract(self.user, bank=self.bank)
        contract = self.create_contract(
            self.user,
            bank=self.bank,
            contract_code=old_contract.contract_code,
            status=DirectDebitContract.STATUS.waiting_for_update,
        )
        data = {
            'status': 'unknown',
        }
        response = self._send_request(contract.trace_id, data)
        assert response.status_code == status.HTTP_200_OK
        self.assertContains(response, 'در ویرایش قرارداد مشکلی پیش آمد. لطفا بعد از کمی صبر، دوباره تلاش کنید.')

        contract.refresh_from_db()
        old_contract.refresh_from_db()
        assert contract.status == DirectDebitContract.STATUS.failed
        assert old_contract.status == DirectDebitContract.STATUS.active

    def test_edit_contract_callback_wrong_model_status(self):
        old_contract = self.create_contract(self.user, bank=self.bank)
        contract = self.create_contract(
            self.user,
            bank=self.bank,
            contract_code=old_contract.contract_code,
            status=DirectDebitContract.STATUS.cancelled,
        )
        data = {
            'status': 'updated',
        }
        response = self._send_request(contract.trace_id, data)
        assert response.status_code == status.HTTP_200_OK
        self.assertContains(response, 'در ویرایش قرارداد مشکلی پیش آمد. لطفا بعد از کمی صبر، دوباره تلاش کنید.')

        contract.refresh_from_db()
        old_contract.refresh_from_db()
        assert contract.status == DirectDebitContract.STATUS.cancelled
        assert old_contract.status == DirectDebitContract.STATUS.active

    def test_edit_contract_callback_old_contract_expired(self):
        old_contract = self.create_contract(self.user, bank=self.bank, status=DirectDebitContract.STATUS.expired)
        contract = self.create_contract(
            self.user,
            bank=self.bank,
            contract_code=old_contract.contract_code,
            status=DirectDebitContract.STATUS.waiting_for_update,
        )
        data = {
            'status': 'updated',
        }
        response = self._send_request(contract.trace_id, data)
        assert response.status_code == status.HTTP_200_OK
        self.assertContains(response, 'در ویرایش قرارداد مشکلی پیش آمد. لطفا بعد از کمی صبر، دوباره تلاش کنید.')

        contract.refresh_from_db()
        old_contract.refresh_from_db()
        assert contract.status == DirectDebitContract.STATUS.cancelled
        assert old_contract.status == DirectDebitContract.STATUS.expired

        _notif = Notification.objects.last()
        assert _notif.message == 'متاسفانه قرارداد واریز مستقیم بانک رسالت ویرایش نشد.'

    def test_edit_contract_callback_missing_status(self):
        old_contract = self.create_contract(self.user, bank=self.bank, status=DirectDebitContract.STATUS.active)
        contract = self.create_contract(
            self.user,
            bank=self.bank,
            contract_code=old_contract.contract_code,
            status=DirectDebitContract.STATUS.waiting_for_update,
        )
        data = {
            'code': 'failed',
        }
        response = self._send_request(contract.trace_id, data)
        assert response.status_code == status.HTTP_200_OK
        self.assertContains(response, 'در ویرایش قرارداد مشکلی پیش آمد. لطفا بعد از کمی صبر، دوباره تلاش کنید.')

        contract.refresh_from_db()
        old_contract.refresh_from_db()
        assert contract.status == DirectDebitContract.STATUS.waiting_for_update
        assert old_contract.status == DirectDebitContract.STATUS.active

    def test_edit_contract_callback_not_found_contract(self):
        data = {
            'status': 'updated',
        }
        response = self._send_request(1, data)
        assert response.status_code == status.HTTP_200_OK
        self.assertContains(response, 'در ویرایش قرارداد مشکلی پیش آمد. لطفا بعد از کمی صبر، دوباره تلاش کنید.')
