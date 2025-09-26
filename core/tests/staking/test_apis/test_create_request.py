from datetime import datetime
from decimal import Decimal
from typing import Optional

from django.test import TestCase
from django.utils.timezone import timedelta
from rest_framework import status

from exchange.accounts.models import User, VerificationProfile
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.staking.models import StakingTransaction
from exchange.staking.service.reject_requests.subscription import reject_user_subscription
from exchange.wallet.models import Transaction, Wallet

from ..utils import PlanTestDataMixin


class CreateRequestTest(PlanTestDataMixin, TestCase):
    URL = '/earn/request/create'

    def setUp(self):
        self.user = User.objects.get(id=201)
        self.user.user_type = User.USER_TYPES.level2
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=True)
        self.user.save()
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'

        self.plan = self.create_plan(**self.get_plan_kwargs())
        self.wallet = Wallet.get_user_wallet(self.user, self.plan.currency)
        self.wallet.balance = 1000
        self.wallet.save(
            update_fields=('balance',),
        )
        self.plan.total_capacity = Decimal('1000000')
        self.plan.filled_capacity = Decimal('0')
        self.plan.save(
            update_fields=('total_capacity', 'filled_capacity'),
        )

    def call_api(
        self,
        amount: str,
        plan_id: Optional[int] = None,
        status_code: Optional[int] = None,
        auto_extend: Optional[bool] = None,
    ):
        plan_id = plan_id or self.plan.id
        request_data = {
            'planId': plan_id,
            'type': 'create',
            'amount': amount,
        }
        if auto_extend is not None:
            request_data['autoExtend'] = auto_extend
            request_data['autoExtend'] = auto_extend
        response = self.client.post(path=self.URL, data=request_data)
        if status_code is not None:
            assert status_code == response.status_code
        return response.json()

    def assert_transactions(
        self, staking_transaction_amount: Decimal, wallet_transaction_amount: Decimal, filled_capacity: Decimal
    ):
        self.plan.refresh_from_db(fields=['filled_capacity'])
        assert self.plan.filled_capacity == filled_capacity
        staking_transaction = StakingTransaction.objects.get(
            user=self.user, plan=self.plan, amount=staking_transaction_amount
        )
        wallet_transaction = Transaction.objects.get(
            wallet=self.wallet,
            ref_module=132,
            ref_id=staking_transaction.id,
            tp=130,
            description=f'درخواست مشارکت در {self.plan.fa_description}',
            amount=wallet_transaction_amount,
        )
        assert staking_transaction.wallet_transaction == wallet_transaction

    def assert_auto_extension(self):
        return StakingTransaction.objects.filter(
            user_id=self.user.id,
            plan_id=self.plan.id,
            child=None,
            tp=StakingTransaction.TYPES.auto_end_request,
        )

    def test_subscribe_to_a_plan_with_one_create_request_successfully(self):
        response_data = self.call_api(amount='200', status_code=status.HTTP_200_OK)
        assert response_data['status'] == 'ok'
        datetime.strptime(response_data['result']['createdAt'], '%Y-%m-%dT%H:%M:%S.%f+03:30')
        response_data['result'].pop('createdAt')
        assert response_data['result'] == {
            'id': StakingTransaction.objects.order_by('-created_at').first().id,
            'planId': self.plan.id,
            'type': 'create',
            'amount': '200',
        }
        self.assert_transactions(
            staking_transaction_amount=Decimal('200'),
            wallet_transaction_amount=-Decimal('200'),
            filled_capacity=Decimal('200'),
        )

    def test_subscribe_to_a_plan_with_multiple_create_request_successfully(self):
        response_data = self.call_api(amount='300', status_code=status.HTTP_200_OK)
        assert response_data['status'] == 'ok'
        response_data['result'].pop('createdAt')
        assert response_data['result'] == {
            'id': StakingTransaction.objects.order_by('-created_at').first().id,
            'planId': self.plan.id,
            'type': 'create',
            'amount': '300',
        }
        self.assert_transactions(
            staking_transaction_amount=Decimal('300'),
            wallet_transaction_amount=-Decimal('300'),
            filled_capacity=Decimal('300'),
        )

        response_data = self.call_api(amount='500', status_code=status.HTTP_200_OK)
        response_data['result'].pop('createdAt')
        assert response_data['result'] == {
            'id': StakingTransaction.objects.order_by('-created_at').first().id,
            'planId': self.plan.id,
            'type': 'create',
            'amount': '800',
        }
        self.assert_transactions(
            staking_transaction_amount=Decimal('800'),
            wallet_transaction_amount=-Decimal('500'),
            filled_capacity=Decimal('800'),
        )

    def test_subscribe_to_a_plan_when_user_has_not_verified_email_then_subscription_fails(self):
        VerificationProfile.objects.filter(id=self.user.get_verification_profile().id).update(email_confirmed=False)
        response_data = self.call_api(amount='200', status_code=status.HTTP_400_BAD_REQUEST)
        assert response_data['status'] == 'failed'
        assert response_data['code'] == 'UnverifiedEmail'
        assert response_data['message'] == 'User does not have a verified email.'
        assert (
            StakingTransaction.objects.filter(user=self.user, plan=self.plan, amount=Decimal('200')).exists() is False
        )

    def test_subscription_is_successful_when_user_type_is_trader(self):
        User.objects.filter(id=self.user.id).update(user_type=User.USER_TYPES.trader)
        response_data = self.call_api(amount='200', status_code=status.HTTP_200_OK)
        assert response_data['status'] == 'ok'
        self.assert_transactions(
            staking_transaction_amount=Decimal('200'),
            wallet_transaction_amount=-Decimal('200'),
            filled_capacity=Decimal('200'),
        )

    def test_when_user_has_lower_balance_then_subscription_fails(self):
        response_data = self.call_api(amount='1001', status_code=status.HTTP_400_BAD_REQUEST)
        assert response_data['status'] == 'failed'
        assert response_data['code'] == 'FailedAssetTransfer'
        assert (
            StakingTransaction.objects.filter(user=self.user, plan=self.plan, amount=Decimal('1001')).exists() is False
        )

    def test_when_user_does_not_have_plan_currency_then_asset_transfer_error_raises(self):
        self.wallet.currency = Currencies.usdt
        self.wallet.save(update_fields=['currency'])
        response_data = self.call_api(amount='100', status_code=status.HTTP_400_BAD_REQUEST)
        assert response_data['status'] == 'failed'
        assert response_data['code'] == 'FailedAssetTransfer'
        assert (
            StakingTransaction.objects.filter(user=self.user, plan=self.plan, amount=Decimal('100')).exists() is False
        )

    def test_when_plan_is_not_open_yet_then_subscription_fails(self):
        self.plan.opened_at = ir_now() + timedelta(days=2)
        self.plan.save(
            update_fields=('opened_at',),
        )
        response_data = self.call_api(amount='1000', status_code=status.HTTP_400_BAD_REQUEST)
        assert response_data['status'] == 'failed'
        assert response_data['code'] == 'TooSoon'
        assert (
            StakingTransaction.objects.filter(user=self.user, plan=self.plan, amount=Decimal('1000')).exists() is False
        )

    def test_subscribe_after_plan_request_period_fails(self):
        self.plan.opened_at -= timedelta(days=4)
        self.plan.save(
            update_fields=('opened_at',),
        )
        response_data = self.call_api(amount='1000', status_code=status.HTTP_400_BAD_REQUEST)
        assert response_data['status'] == 'failed'
        assert response_data['code'] == 'TooLate'
        assert (
            StakingTransaction.objects.filter(user=self.user, plan=self.plan, amount=Decimal('1000')).exists() is False
        )

    def test_when_admin_recently_rejected_user_request_in_plan_then_new_subscription_requests_fails(self):
        response = self.call_api(amount='100', status_code=status.HTTP_200_OK)
        assert response['status'] == 'ok'
        response['result'].pop('createdAt')
        assert response['result'] == {
            'id': StakingTransaction.objects.order_by('-created_at').first().id,
            'planId': self.plan.id,
            'type': 'create',
            'amount': '100',
        }
        # admin reject
        reject_user_subscription(self.user.id, self.plan.id, Decimal('100'))
        response = self.call_api(amount='122', status_code=status.HTTP_400_BAD_REQUEST)
        assert response['status'] == 'failed'
        assert response['code'] == 'RecentlyCanceled'
        assert (
            StakingTransaction.objects.filter(user=self.user, plan=self.plan, amount=Decimal('122')).exists() is False
        )

    def test_default_auto_extend(self):
        self.call_api(amount='200')
        assert not self.assert_auto_extension()

    def test_true_auto_extend(self):
        self.call_api(amount='200', auto_extend=True)
        assert not self.assert_auto_extension()
        self.call_api(amount='200')
        assert not self.assert_auto_extension()

    def test_false_auto_extend(self):
        self.call_api(amount='200', auto_extend=False)
        assert self.assert_auto_extension()
        self.call_api(amount='200')
        assert self.assert_auto_extension()

    def test_false_to_true_auto_extend(self):
        self.call_api(amount='200', auto_extend=False)
        assert self.assert_auto_extension()
        self.call_api(amount='200', auto_extend=True)
        assert not self.assert_auto_extension()

    def test_true_to_false_auto_extend(self):
        self.call_api(amount='200', auto_extend=True)
        assert not self.assert_auto_extension()
        self.call_api(amount='200', auto_extend=False)
        assert self.assert_auto_extension()

    def test_un_extendable_plan_are_not_extendable(self):
        self.plan.is_extendable = False
        self.plan.save()
        self.call_api(amount='200', auto_extend=True)
        assert not self.assert_auto_extension()
        self.call_api(amount='200', auto_extend=False)
        assert not self.assert_auto_extension()
