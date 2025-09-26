from unittest.mock import patch

import pytest
import responses
from django.test import TestCase
from responses import matchers

from exchange.accounts.models import BankAccount, User
from exchange.shetab.handlers.vandar import VandarException, VandarP2P
from exchange.shetab.models import VandarAccount, VandarPaymentId
from exchange.shetab.serializers import serialize_deposit_payment_id
from exchange.wallet.models import BankDeposit


class VandarP2PTest(TestCase):
    def get_sample_vandar_response(self, **kwargs):
        sample_vandar_response = {
            'id': 168136063976,
            'track_id': None,
            'uuid': '91fcdc30-da12-11ed-934b-bbd1bdaa3cb8',
            'amount': 1000000,  # Toman
            'wage': 1,
            'status': 1,
            'ref_id': '14020124190251ACH16636',
            'tracking_code': '402012401726164',
            'card_number': None,
            'cid': None,
            'verified': 0,
            'channel': 'واریز با شناسه',
            'payment_date': '19:18:01 - 1402/1/24',
            'payment_number': kwargs.get('payment_number', '935535593500073'),
            'created_at': '19:18:01 - 1402/1/24',
            'effective_at_jalali': '19:18:01 - 1402/1/24',
            'effective_time_stamp': 1681400881,
            'updated_at': '19:18:01 - 1402/1/24',
            'wallet': 56678,
            'result': 'تراکنش موفق',
            'description': 'تراکنش واریز بانکی',
            'factorNumber': None,
            'mobile': None,
            'callback_url': None,
            'form_id': None,
            'form_title': None,
            'settlement': None,
            'settlement_port': None,
            'port': None,
            'comments': [],
            'api_token': None,
            'logs': [],
            'revised_transaction_id': None,
            'refund': None,
            'refund_detail_ids': [],
            'is_shaparak_port': False,
            'payer': {
                'ip': None,
                'iban': 'IR260170000000354907429006',
                'name': None,
                'slug': None,
                'avatar': None,
                'legal_name': None,
                'business_owner': None,
                'email': None,
                'phone': None,
                'address': None,
                'mobile': None,
                'additional_fields': None,
                'description': 'تراکنش واریز بانکی'
            },
            'receiver': {
                'name': None,
                'legal_name': None,
                'slug': None,
                'avatar': None,
                'business_owner': None,
                'iban': None,
                'bank_name': None
            },
            'receipt_url': None,
            'time_prediction': {
                'settlement_done_time_prediction': None,
                'settlement_cancelable_time': None,
                'is_settlement_paya_report_finally': None,
                'settlement_paya_report_finally_time': None,
                'is_after_time_prediction': None,
                'p2p_time_prediction': None
            }
        }
        sample_vandar_response.update(kwargs)
        return sample_vandar_response

    def setUp(self) -> None:
        self.user = User.objects.get(id=201)
        self.bank_account = BankAccount.objects.create(
            user=self.user,
            bank_id=BankAccount.BANK_ID.vandar,
            shaba_number='',
            account_number='وندار',
            confirmed=True,
        )
        self.vandar_account = VandarAccount.objects.create(
            user=self.user,
            uuid='12345678901234567890',
        )
        self.vandar_payment_id = VandarPaymentId.objects.create(
            vandar_account=self.vandar_account,
            bank_account=self.bank_account,
            payment_id='935535593500073',
        )

    @patch('exchange.accounts.userlevels.is_feature_enabled')
    def test_create_or_update_vandar_payment(self, is_feature_enabled):
        is_feature_enabled.return_value = False
        VandarP2P.get_or_create_payment(self.get_sample_vandar_response())
        deposit = BankDeposit.objects.first()
        assert not deposit

        is_feature_enabled.return_value = True
        VandarP2P.get_or_create_payment(self.get_sample_vandar_response())
        deposit = BankDeposit.objects.first()
        assert deposit.src_bank_account == self.bank_account
        assert deposit.receipt_id == '402012401726164'
        assert deposit.amount == 10000000
        assert deposit.fee == 2000 # VANDAR_DEPOSIT_FEE_RATE * 10000000
        assert deposit.deposited_at.isoformat() == '2023-04-13'

    @patch('exchange.accounts.userlevels.is_feature_enabled')
    def test_create_or_update_vandar_payment_fee(self, is_feature_enabled):
        is_feature_enabled.return_value = True
        sample_response = self.get_sample_vandar_response()
        sample_response['amount'] = 100_000_000_000_0

        VandarP2P.get_or_create_payment(sample_response)
        deposit = BankDeposit.objects.first()
        assert deposit
        assert deposit.fee == 20_000_0 # VANDAR_DEPOSIT_FEE_MAX

    @patch('exchange.accounts.userlevels.is_feature_enabled')
    def test_create_or_update_vandar_payment_on_nonexsitant_payment_id(self, is_feature_enabled):
        is_feature_enabled.return_value = True
        deposit = VandarP2P.get_or_create_payment(self.get_sample_vandar_response(payment_number='123'))
        assert not deposit

    @patch('exchange.accounts.userlevels.is_feature_enabled')
    def test_create_or_update_vandar_payment_duplicate_call(self, is_feature_enabled):
        is_feature_enabled.return_value = True
        response = self.get_sample_vandar_response()
        VandarP2P.get_or_create_payment(response)
        VandarP2P.get_or_create_payment(response)
        assert BankDeposit.objects.count() == 1

    @responses.activate
    def test_get_or_create_vandar_account(self):
        VandarAccount.objects.filter(user=self.user).delete()
        responses.post(
            VandarP2P.API_URL + 'login', json={'access_token': 'token'},
        )

        responses.post(
            VandarP2P.API_V2_URL + f'business/{VandarP2P.BUSINESS_NAME}/customers',
            json={
                'status': '1',
                'message': 'مخاطب با موفقیت ثبت گردید.',
                'result': {'customer': {'id': '35e431e0-210c-11ec-9200-79b42496d8e0'}},
            },
            match=[
                matchers.json_params_matcher(
                    {
                        'type': 'INDIVIDUAL',
                        'mobile': self.user.mobile,
                        'individual_national_code': self.user.national_code,
                    }
                )
            ],
        )

        vandar_account1 = VandarP2P.get_or_create_vandar_account(self.user)
        assert vandar_account1.id is not None
        assert vandar_account1.user == self.user
        assert vandar_account1.uuid == '35e431e0-210c-11ec-9200-79b42496d8e0'

        # Calling when exists
        vandar_account2 = VandarP2P.get_or_create_vandar_account(self.user)
        assert vandar_account2.id == vandar_account1.id
        assert vandar_account2.user == vandar_account1.user
        assert vandar_account2.uuid == vandar_account1.uuid

        assert VandarAccount.objects.count() == 1

    @responses.activate
    def test_get_or_create_vandar_account_fail_response(self):
        VandarAccount.objects.filter(user=self.user).delete()
        responses.post(
            VandarP2P.API_URL + 'login',
            json={'access_token': 'token'},
        )

        responses.post(
            VandarP2P.API_V2_URL + f'business/{VandarP2P.BUSINESS_NAME}/customers',
            json={
                'status': '0',
                'message': 'خطا',
            },
        )

        with pytest.raises(VandarException):
            VandarP2P.get_or_create_vandar_account(self.user)

        assert VandarAccount.objects.count() == 0

    @responses.activate
    def test_get_or_create_vandar_payment_id(self):
        VandarAccount.objects.filter(user=self.user).delete()
        vandar_account = VandarAccount.objects.create(uuid='35e431e0-210c-11ec-9200-79b42496d8e0', user=self.user)

        responses.post(
            VandarP2P.API_URL + 'login', json={'access_token': 'token'},
        )

        responses.post(
            VandarP2P.API_V2_URL + f'business/{VandarP2P.BUSINESS_NAME}/customers/{vandar_account.uuid}/cash-in-code',
            json={
                'status': 1,
                'code': '143992020000736',
                'message': 'شناسه پرداخت با موفقیت ایجاد شد',
            },
        )

        vandar_payment_id1 = VandarP2P.get_or_create_payment_id(vandar_account)
        assert vandar_payment_id1.id is not None
        assert vandar_payment_id1.vandar_account == vandar_account
        assert vandar_payment_id1.payment_id == '143992020000736'

        # Calling when exists
        vandar_payment_id2 = VandarP2P.get_or_create_payment_id(vandar_account)
        assert vandar_payment_id2.id == vandar_payment_id1.id
        assert vandar_payment_id2.vandar_account == vandar_payment_id1.vandar_account
        assert vandar_payment_id2.payment_id == vandar_payment_id1.payment_id

        assert VandarPaymentId.objects.count() == 1

    @responses.activate
    def test_get_or_create_vandar_payment_id_fail_response(self):
        VandarAccount.objects.filter(user=self.user).delete()
        vandar_account = VandarAccount.objects.create(uuid='35e431e0-210c-11ec-9200-79b42496d8e0', user=self.user)

        responses.post(
            VandarP2P.API_URL + 'login', json={'access_token': 'token'},
        )

        responses.post(
            VandarP2P.API_V2_URL + f'business/{VandarP2P.BUSINESS_NAME}/customers/{vandar_account.uuid}/cash-in-code',
            json={
                'status': 0,
                'message': 'خطا',
            },
        )

        with pytest.raises(VandarException):
            VandarP2P.get_or_create_payment_id(vandar_account)

        assert VandarPaymentId.objects.count() == 0

    def test_serialize_vandar_payment_id(self):
        assert serialize_deposit_payment_id(self.vandar_payment_id) == {
            'id': self.vandar_payment_id.id,
            'accountId': self.bank_account.id,
            'bank': self.bank_account.get_bank_id_display(),
            'iban': self.bank_account.shaba_number,
            'destinationBank': self.vandar_payment_id.vandar_account.get_bank_display(),
            'destinationIban': self.vandar_payment_id.vandar_account.iban,
            'destinationOwnerName': self.vandar_payment_id.vandar_account.owner_name,
            'destinationAccountNumber': self.vandar_payment_id.vandar_account.account_number,
            'paymentId': self.vandar_payment_id.payment_id,
            'type': 'vandar',
        }
