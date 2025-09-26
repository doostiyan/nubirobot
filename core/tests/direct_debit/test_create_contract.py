import datetime
import uuid
from decimal import Decimal
from unittest.mock import patch

import responses
from django.core.cache import cache
from django.test import TestCase
from rest_framework import status

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.direct_debit.models import DirectDebitContract
from exchange.direct_debit.tasks import direct_debit_activate_contract_task
from tests.base.utils import check_response, mock_on_commit
from tests.direct_debit.helper import DirectDebitMixins


class CreateContractTests(DirectDebitMixins, TestCase):
    fixtures = ('test_data',)

    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)
        self.user.user_type = User.USER_TYPE_LEVEL1
        self.user.save()

        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'
        self.url = '/direct-debit/contracts/create'
        self.api_url = f'{self.base_url}/v1/payman/create'
        self.request_feature(self.user, 'done')
        self.bank = self.create_bank(max_daily_transaction_amount=Decimal(120000000), max_daily_transaction_count=50)
        cache.set('direct_debit_access_token', 'test_direct_debit_access_token')

    def _create_contract(self, data):
        return self.client.post(self.url, data=data)

    def test_create_contract_not_feature_active(self):
        self.request_feature(self.user)
        response = self._create_contract(data=None)
        check_response(
            response,
            200,
            'failed',
            'FeatureUnavailable',
            'DirectDebit feature is not available for your user',
        )

    def test_create_contract_not_valid_params(self):
        response = self._create_contract(data=None)
        check_response(
            response,
            400,
            'failed',
            'ParseError',
            'Missing integer value',
        )

        data = {
            'bankId': self.bank.id,
        }
        response = self._create_contract(data=data)
        check_response(
            response,
            400,
            'failed',
            'ParseError',
            'Missing date value',
        )

        data = {
            'bankId': self.bank.id,
            'toDate': (ir_now() + datetime.timedelta(days=60)).date().strftime('%Y-%m-%d'),
            'dailyMaxTransactionCount': 4,
        }
        response = self._create_contract(data=data)
        check_response(
            response,
            400,
            'failed',
            'ParseError',
            'Missing monetary value',
        )

    def test_create_contract_not_valid_start_dates(self):
        data = {
            'bankId': self.bank.id,
            'fromDate': (ir_now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d'),
            'toDate': (ir_now() + datetime.timedelta(days=60)).date().strftime('%Y-%m-%d'),
            'dailyMaxTransactionCount': 5,
            'dailyMaxTransactionAmount': '110000000',
            'maxTransactionAmount': '200000',
        }
        response = self._create_contract(data=data)
        check_response(
            response,
            400,
            'failed',
            'FromDateInvalidError',
            'fromDate should be greater than now',
        )

    def test_create_contract_not_valid_end_dates(self):
        data = {
            'bankId': self.bank.id,
            'toDate': (ir_now() - datetime.timedelta(days=60)).date().strftime('%Y-%m-%d'),
            'dailyMaxTransactionCount': 5,
            'dailyMaxTransactionAmount': '110000000',
            'maxTransactionAmount': '200000',
        }
        response = self._create_contract(data=data)
        check_response(
            response,
            400,
            'failed',
            'ToDateInvalidError',
            'toDate should be greater than the fromDate',
        )

    def test_create_contract_user_eligibility(self):
        self.user.user_type = User.USER_TYPES.level0
        self.user.save()

        response = self._create_contract(data=None)
        check_response(
            response,
            400,
            'failed',
            'UserLevelRestriction',
            'User level does not meet the requirements',
        )

    @responses.activate
    def test_create_contract_max_transaction_amount_over_the_bank_limit(self):
        _oauth_location = 'http://localhost.ir/test'
        responses.post(self.api_url, status=302, headers={'Location': _oauth_location})
        self.bank.max_transaction_amount = Decimal(100000)
        self.bank.save()
        data = {
            'bankId': self.bank.id,
            'toDate': (ir_now() + datetime.timedelta(days=60)).date().strftime('%Y-%m-%d'),
            'dailyMaxTransactionCount': 5,
            'dailyMaxTransactionAmount': '110000000',
            'maxTransactionAmount': '200000',
        }
        response = self._create_contract(data=data)
        expected_result = {
            'status': 'failed',
            'code': 'MaxTransactionAmountError',
            'message': 'Max transaction amount is more than the bank limit!',
        }
        assert expected_result == response.json()

    @responses.activate
    def test_create_contract_max_transaction_amount_without_bank_limit(self):
        _oauth_location = 'http://localhost.ir/test'
        responses.post(self.api_url, status=302, headers={'Location': _oauth_location})
        data = {
            'bankId': self.bank.id,
            'toDate': (ir_now() + datetime.timedelta(days=60)).date().strftime('%Y-%m-%d'),
            'dailyMaxTransactionCount': 5,
            'dailyMaxTransactionAmount': '110000000',
            'maxTransactionAmount': '200000',
        }
        response = self._create_contract(data=data)
        check_response(
            response=response,
            status_code=200,
            status_data='ok',
            special_key='location',
            special_value=_oauth_location,
        )
        _contract = DirectDebitContract.objects.first()
        assert _contract
        assert _contract.location == _oauth_location
        assert _contract.status == DirectDebitContract.STATUS.initializing

    @responses.activate
    def test_create_contract_max_transaction_amount_with_bank_limit_without_max_amount(self):
        _oauth_location = 'http://localhost.ir/test'
        responses.post(self.api_url, status=302, headers={'Location': _oauth_location})
        self.bank.max_transaction_amount = Decimal(60000000)
        self.bank.save()
        data = {
            'bankId': self.bank.id,
            'toDate': (ir_now() + datetime.timedelta(days=60)).date().strftime('%Y-%m-%d'),
            'dailyMaxTransactionCount': 5,
            'dailyMaxTransactionAmount': '110000000',
            'maxTransactionAmount': '50000000',
        }
        response = self._create_contract(data=data)
        check_response(
            response=response,
            status_code=200,
            status_data='ok',
            special_key='location',
            special_value=_oauth_location,
        )
        _contract = DirectDebitContract.objects.first()
        assert _contract
        assert _contract.location == _oauth_location
        assert _contract.status == DirectDebitContract.STATUS.initializing

    @responses.activate
    def test_create_contract_max_transaction_count_over_the_bank_limit(self):
        _oauth_location = 'http://localhost.ir/test'
        responses.post(self.api_url, status=302, headers={'Location': _oauth_location})
        self.bank.max_transaction_amount = Decimal(60000000)
        self.bank.save()
        data = {
            'bankId': self.bank.id,
            'toDate': (ir_now() + datetime.timedelta(days=60)).date().strftime('%Y-%m-%d'),
            'dailyMaxTransactionCount': 53,
            'dailyMaxTransactionAmount': '110000000',
            'maxTransactionAmount': '60000000',
        }
        response = self._create_contract(data=data)
        expected_result = {
            'status': 'failed',
            'code': 'DailyMaxTransactionCountError',
            'message': 'Daily max transaction count is more than the bank limit!',
        }
        assert expected_result == response.json()
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @responses.activate
    def test_create_contract_success(self):
        _oauth_location = 'http://localhost.ir/test'
        responses.post(self.api_url, status=302, headers={'Location': _oauth_location})
        data = {
            'bankId': self.bank.id,
            'toDate': (ir_now() + datetime.timedelta(days=60)).date().strftime('%Y-%m-%d'),
            'dailyMaxTransactionCount': 5,
            'dailyMaxTransactionAmount': '1500000',
            'maxTransactionAmount': '500000',
        }
        response = self._create_contract(data=data)
        check_response(
            response=response,
            status_code=200,
            status_data='ok',
            special_key='location',
            special_value=_oauth_location,
        )
        _contract = DirectDebitContract.objects.first()
        assert _contract
        assert _contract.location == _oauth_location
        assert _contract.status == DirectDebitContract.STATUS.initializing

    def test_create_contract_bank_disabled(self):
        self.bank.is_active = False
        self.bank.save()
        data = {
            'bankId': self.bank.id,
            'toDate': (ir_now() + datetime.timedelta(days=60)).date().strftime('%Y-%m-%d'),
            'dailyMaxTransactionCount': 5,
            'dailyMaxTransactionAmount': '1500000',
            'maxTransactionAmount': '500000',
        }
        response = self._create_contract(data=data)
        check_response(
            response=response,
            status_code=422,
            status_data='failed',
            code='DeactivatedBankError',
            message='The bank is not active',
        )
        assert not DirectDebitContract.objects.all().exists()

    def test_create_contract_integrity_case(self):
        _contract = self.create_contract(
            user=self.user,
            status=DirectDebitContract.STATUS.active,
            start_date=ir_now(),
            expire_date=ir_now() + datetime.timedelta(days=30),
            bank=self.bank,
        )
        response = self._create_contract(
            data={
                'bankId': self.bank.id,
                'fromData': ir_now().date().strftime('%Y-%m-%d'),
                'toDate': (ir_now() + datetime.timedelta(days=30)).date().strftime('%Y-%m-%d'),
                'dailyMaxTransactionCount': 3,
                'maxTransactionAmount': '10000000',
            }
        )
        check_response(
            response,
            422,
            'failed',
            'ContractIntegrityError',
            'The user has an active contract with this bank',
        )

        _contract.status = DirectDebitContract.STATUS.initializing
        _contract.save()

        response = self._create_contract(
            data={
                'bankId': self.bank.id,
                'fromData': ir_now().date().strftime('%Y-%m-%d'),
                'toDate': (ir_now() + datetime.timedelta(days=30)).date().strftime('%Y-%m-%d'),
                'dailyMaxTransactionCount': 3,
                'maxTransactionAmount': '10000000',
            }
        )
        check_response(
            response,
            422,
            'failed',
            'ContractIntegrityError',
            'The user has an active contract with this bank',
        )

        _contract.status = DirectDebitContract.STATUS.waiting_for_confirm
        _contract.save()

        response = self._create_contract(
            data={
                'bankId': self.bank.id,
                'fromData': ir_now().date().strftime('%Y-%m-%d'),
                'toDate': (ir_now() + datetime.timedelta(days=30)).date().strftime('%Y-%m-%d'),
                'dailyMaxTransactionCount': 3,
                'maxTransactionAmount': '10000000',
            }
        )
        check_response(
            response,
            422,
            'failed',
            'ContractIntegrityError',
            'The user has an active contract with this bank',
        )

    @responses.activate
    def test_ativate_contract(self):
        contract = _contract = self.create_contract(
            user=self.user,
            status=DirectDebitContract.STATUS.waiting_for_confirm,
            start_date=ir_now(),
            expire_date=ir_now() + datetime.timedelta(days=30),
            bank=self.bank,
        )
        responses.get(
            f'{self.base_url}/v1/payman/getId?payman_code={contract.contract_code}',
            status=200,
            json={
                'payman_id': 'test_code',
            },
        )
        direct_debit_activate_contract_task(contract_id=contract.id)
        contract.refresh_from_db()
        assert contract.status == contract.STATUS.active
        assert contract.contract_id == 'test_code'

    @responses.activate
    def test_create_contract_with_invalid_json_response(self):
        responses.post(self.api_url, status=500, body="Internal Server Error")

        data = {
            'bankId': self.bank.id,
            'toDate': (ir_now() + datetime.timedelta(days=60)).date().strftime('%Y-%m-%d'),
            'dailyMaxTransactionCount': 5,
            'dailyMaxTransactionAmount': '1500000',
            'maxTransactionAmount': '500000',
        }
        response = self._create_contract(data=data)
        check_response(
            response=response,
            status_code=503,
            status_data='failed',
            code='ThirdPartyClientError',
            message='An error occurred when trying to connect to third-party API',
        )
        assert not DirectDebitContract.objects.exists()


class CreateContractCallbackTests(DirectDebitMixins, TestCase):
    fixtures = ('test_data',)

    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)
        self.url = '/direct-debit/contracts/{}/callback'
        self.bad_trace_id = str(uuid.uuid4().hex)

    def _send_request(self, trace_id: str, data=None):
        url = self.url.format(trace_id)
        return self.client.get(url, data=data)

    def test_create_contract_callback_invalid_params(self):
        response = self._send_request(self.bad_trace_id)
        assert response.status_code == 200
        self.assertTemplateUsed(response, 'direct_debit_callback.html')
        self.assertContains(response, 'در ایجاد قرارداد مشکلی پیش آمد. لطفا بعد از کمی صبر، دوباره تلاش کنید.')

    def test_create_contract_callback_not_found_contract(self):
        data = {
            'payman_code': 'test_payman_code',
            'status': 'created',
        }
        response = self._send_request(self.bad_trace_id, data)
        assert response.status_code == 200
        self.assertTemplateUsed(response, 'direct_debit_callback.html')
        self.assertContains(response, 'در ایجاد قرارداد مشکلی پیش آمد. لطفا بعد از کمی صبر، دوباره تلاش کنید.')

    def test_create_contract_callback_unknown_error(self):
        contract = self.create_contract(self.user, DirectDebitContract.STATUS.initializing)
        data = {
            'payman_code': 'test_payman_code',
            'status': 'felaan',
        }
        response = self._send_request(contract.trace_id, data)
        assert response.status_code == 200
        self.assertTemplateUsed(response, 'direct_debit_callback.html')
        self.assertContains(response, 'در ایجاد قرارداد مشکلی پیش آمد. لطفا بعد از کمی صبر، دوباره تلاش کنید.')

    def test_create_contract_callback_invalid_contract_status(self):
        contract = self.create_contract(self.user, DirectDebitContract.STATUS.waiting_for_confirm)
        data = {
            'payman_code': 'test_payman_code',
            'status': 'created',
        }
        response = self._send_request(contract.trace_id, data)
        assert response.status_code == 200
        self.assertTemplateUsed(response, 'direct_debit_callback.html')
        self.assertContains(
            response,
            'در ایجاد قرارداد مشکلی پیش آمد. لطفا بعد از کمی صبر، دوباره تلاش کنید.',
        )

    @patch('django.db.transaction.on_commit', side_effect=mock_on_commit)
    @patch('exchange.direct_debit.api.views.direct_debit_activate_contract_task.apply_async')
    def test_create_contract_callback_created(self, mock_apply_async, _):
        contract = self.create_contract(self.user, DirectDebitContract.STATUS.initializing)
        data = {
            'payman_code': 'test_payman_code',
            'status': 'created',
        }
        response = self._send_request(contract.trace_id, data)
        assert response.status_code == 200
        self.assertTemplateUsed(response, 'direct_debit_callback.html')
        self.assertContains(response, 'قرارداد با موفقیت ایجاد شد')
        mock_apply_async.assert_called_once_with(args=(contract.id, 0))

        contract.refresh_from_db()
        assert contract.contract_code == 'test_payman_code'
        assert contract.status == DirectDebitContract.STATUS.waiting_for_confirm

    def test_create_contract_callback_cancelled(self):
        contract = self.create_contract(self.user, DirectDebitContract.STATUS.initializing)
        data = {
            'payman_code': 'test_payman_code',
            'status': 'canceled',
        }
        response = self._send_request(contract.trace_id, data)
        assert response.status_code == 200
        self.assertTemplateUsed(response, 'direct_debit_callback.html')
        self.assertContains(response, 'قرارداد لغو شد')

        contract.refresh_from_db()
        assert contract.status == DirectDebitContract.STATUS.cancelled

    def test_create_contract_callback_internal_error_without_code(self):
        contract = self.create_contract(self.user, DirectDebitContract.STATUS.initializing)
        data = {
            'payman_code': 'test_payman_code',
            'status': 'internal_error',
        }
        response = self._send_request(contract.trace_id, data)
        assert response.status_code == 200
        self.assertTemplateUsed(response, 'direct_debit_callback.html')
        self.assertContains(response, 'خطای فنی در هنگام ایجاد قرارداد رخ داده است. لطفا دقایقی بعد مجددا تلاش کنید.')

        contract.refresh_from_db()
        assert contract.status == DirectDebitContract.STATUS.failed

    def test_create_contract_callback_internal_error_with_code(self):
        contract = self.create_contract(self.user, DirectDebitContract.STATUS.initializing)
        data = {'payman_code': 'test_payman_code', 'status': 'internal_error', 'code': '2051'}
        response = self._send_request(contract.trace_id, data)
        assert response.status_code == 200
        self.assertTemplateUsed(response, 'direct_debit_callback.html')
        self.assertContains(response, 'خطای فنی در هنگام ایجاد قرارداد رخ داده است. لطفا دقایقی بعد مجددا تلاش کنید.')

        contract.refresh_from_db()
        assert contract.status == DirectDebitContract.STATUS.failed

    def test_create_contract_callback_timeout(self):
        contract = self.create_contract(self.user, DirectDebitContract.STATUS.initializing)
        data = {
            'payman_code': 'test_payman_code',
            'status': 'timeout',
        }
        response = self._send_request(contract.trace_id, data)
        assert response.status_code == 200
        self.assertTemplateUsed(response, 'direct_debit_callback.html')
        self.assertContains(response, 'در ایجاد قرارداد مشکلی پیش آمد. لطفا بعد از کمی صبر، دوباره تلاش کنید.')

        contract.refresh_from_db()
        assert contract.status == DirectDebitContract.STATUS.failed
