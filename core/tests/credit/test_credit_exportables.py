from functools import wraps
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase
import pytest

from exchange.credit import errors
from exchange.credit.exportables import check_if_user_could_withdraw
from exchange.credit.models import CreditPlan


def _patch_check_if_user_could_withdraw(test):
    patch_prefix = 'exchange.credit.exportables'

    @wraps(test)
    @patch(patch_prefix + '.models.CreditPlan.get_active_plan',)
    @patch('exchange.credit.helpers.ToUsdtConvertor.get_price',)
    @patch(patch_prefix + '.helpers.get_user_net_worth',)
    @patch(patch_prefix + '.helpers.get_user_debt_worth',)
    def decorated(*args, **kwargs):
        return test(*args, **kwargs)
    return decorated


class CheckIfUserCouldWithdrawTest(TestCase):

    @classmethod
    def setUpTestData(cls) -> None:
        class DummyCreditPlan:
            maximum_withdrawal_percentage = Decimal('30')
        cls.credit_plan = DummyCreditPlan()
        return super().setUpTestData()

    def setUp(self) -> None:
        CheckIfUserCouldWithdrawTest.credit_plan.maximum_withdrawal_percentage = Decimal('.30')
        return super().setUp()

    @_patch_check_if_user_could_withdraw
    def test_a_successful_call(
        self,
        get_user_debt_worth_mock: MagicMock,
        get_user_net_worth_mock: MagicMock,
        get_usdt_worth_mock: MagicMock,
        get_active_plan_mock: MagicMock,
    ):
        get_user_debt_worth_mock.return_value = Decimal('290')
        get_user_net_worth_mock.return_value = Decimal('5100')
        get_usdt_worth_mock.return_value = Decimal('2')
        get_active_plan_mock.return_value = CheckIfUserCouldWithdrawTest.credit_plan
        user_id = 123
        currency = 14
        amount = Decimal('22')

        assert check_if_user_could_withdraw(user_id, currency, amount,) is True

        get_user_debt_worth_mock.assert_called_once_with(user_id,)
        get_user_net_worth_mock.assert_called_once_with(user_id,)
        get_active_plan_mock.assert_called_once_with(user_id,)

    @_patch_check_if_user_could_withdraw
    def test_user_with_no_debt(
        self,
        get_user_debt_worth_mock: MagicMock,
        get_user_net_worth_mock: MagicMock,
        get_usdt_worth_mock: MagicMock,
        get_active_plan_mock: MagicMock,
    ):
        user_id = 123
        currency = 14
        amount = Decimal('22')
        get_user_debt_worth_mock.return_value = Decimal('0')
        assert check_if_user_could_withdraw(user_id, currency, amount,) is True
        get_active_plan_mock.assert_not_called()

    @_patch_check_if_user_could_withdraw
    def test_freezed_account(
        self,
        get_user_debt_worth_mock: MagicMock,
        get_user_net_worth_mock: MagicMock,
        get_usdt_worth_mock: MagicMock,
        get_active_plan_mock: MagicMock,
    ):
        get_user_debt_worth_mock.return_value = Decimal('150')
        get_active_plan_mock.side_effect = CreditPlan.DoesNotExist
        user_id = 123
        currency = 14
        amount = Decimal('22')
        assert check_if_user_could_withdraw(user_id, currency, amount,) is False

    @_patch_check_if_user_could_withdraw
    def test_not_enough_assets(
        self,
        get_user_debt_worth_mock: MagicMock,
        get_user_net_worth_mock: MagicMock,
        get_usdt_worth_mock: MagicMock,
        get_active_plan_mock: MagicMock,
    ):
        get_user_debt_worth_mock.return_value = Decimal('301')
        get_user_net_worth_mock.return_value = Decimal('1100')
        get_usdt_worth_mock.return_value = Decimal('100')
        get_active_plan_mock.return_value = CheckIfUserCouldWithdrawTest.credit_plan
        user_id = 123
        currency = 14
        amount = Decimal('22')
        assert check_if_user_could_withdraw(user_id, currency, amount,) is False
