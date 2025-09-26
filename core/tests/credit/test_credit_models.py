"""Staking Service Tests"""

from decimal import Decimal
from functools import wraps
from unittest.mock import patch, MagicMock, call
from typing import Optional

from django.test import TestCase
from django.utils.timezone import timedelta
import pytest

from exchange.base.calendar import ir_now
from exchange.wallet.helpers import RefMod
from exchange.credit.models import CreditPlan, CreditTransaction
from exchange.credit import errors


_plan_kwargs = {
    'user_id': 201,
    'starts_at': ir_now() - timedelta(days=1),
    'expires_at': ir_now() + timedelta(days=1),
    'maximum_withdrawal_percentage': Decimal('.5'),
    'credit_limit_percentage': Decimal('.2'),
    'credit_limit_in_usdt': Decimal('100'),
}


_plan = CreditPlan(**_plan_kwargs)


_credit_system_user_id = 10524456


def _patch_lend(test,):
    patch_prefix = 'exchange.credit.models'

    @wraps(test)
    @patch(patch_prefix + '.helpers.get_system_user_id', lambda *_: _credit_system_user_id,)
    @patch(patch_prefix + '.CreditPlan.get_active_plan', lambda _: _plan,)
    @patch(patch_prefix + '.create_and_commit_transaction',)
    @patch(patch_prefix + '.CreditTransaction.add_wallet_transactions',)
    @patch(patch_prefix + '.CreditTransaction.objects.create',)
    @patch(patch_prefix + '.helpers.get_user_debt_worth',)
    @patch(patch_prefix + '.helpers.get_user_net_worth',)
    @patch('exchange.credit.helpers.ToUsdtConvertor.get_price',)
    def decorated(*args, **kwargs,):
        return test(*args, **kwargs,)
    return decorated


class LendTest(TestCase):

    @classmethod
    def setUpTestData(cls) -> None:
        class DummyTransaction:
            def __init__(self, id,) -> None:
                self.id = id
        cls.user_id = 666
        cls.currency = 10
        cls.credit_transaction_id = 546
        cls.user_wallet_transaction_id = 54
        cls.system_wallet_transaction_id = 696
        cls.amount = Decimal('10')
        cls.transaction_class = DummyTransaction

    def setUp(self) -> None:
        for key, value in _plan_kwargs.items():
            _plan.__setattr__(key, value)

    def default_mocks(
        self,
        get_usdt_worth_mock: Optional[MagicMock],
        get_user_net_worth_mock: Optional[MagicMock],
        get_user_debt_worth_mock: Optional[MagicMock],
        create_credit_transaction_mock: Optional[MagicMock],
        create_and_commit_transaction_mock: Optional[MagicMock],
    ):
        if get_usdt_worth_mock is not None:
            get_usdt_worth_mock.return_value = Decimal('2')

        if get_user_net_worth_mock is not None:
            get_user_net_worth_mock.return_value = Decimal('220')

        if get_user_debt_worth_mock is not None:
            get_user_debt_worth_mock.return_value = Decimal('20')

        if create_credit_transaction_mock is not None:
            create_credit_transaction_mock.return_value = self.transaction_class(self.credit_transaction_id)

        if create_and_commit_transaction_mock is not None:
            create_and_commit_transaction_mock.side_effect = (
                self.transaction_class(self.system_wallet_transaction_id,),
                self.transaction_class(self.user_wallet_transaction_id,),
            )

    @_patch_lend
    def test_a_successful_call(
        self,
        get_usdt_worth_mock: MagicMock,
        get_user_net_worth_mock: MagicMock,
        get_user_debt_worth_mock: MagicMock,
        create_credit_transaction_mock: MagicMock,
        add_wallet_transactions_mock: MagicMock,
        create_and_commit_transaction_mock: MagicMock,
    ):
        add_wallet_transactions_mock.return_value = None
        self.default_mocks(
            get_usdt_worth_mock,
            get_user_net_worth_mock,
            get_user_debt_worth_mock,
            create_credit_transaction_mock,
            create_and_commit_transaction_mock,
        )
        CreditPlan.lend(self.user_id, self.currency, self.amount,)
        get_user_net_worth_mock.assert_called_once_with(self.user_id,)
        get_user_debt_worth_mock.assert_called_once_with(self.user_id,)
        add_wallet_transactions_mock.assert_called_once_with(
            self.credit_transaction_id, self.system_wallet_transaction_id, self.user_wallet_transaction_id,
        )
        create_credit_transaction_mock.assert_called_once_with(
            plan=_plan, currency=self.currency, tp=CreditTransaction.TYPES.lend, amount=self.amount,
        )
        create_and_commit_transaction_mock.assert_has_calls(calls=(call(
            user_id=_credit_system_user_id,
            currency=self.currency,
            amount=-self.amount,
            ref_module=RefMod.credit_system_lend,
            ref_id=self.credit_transaction_id,
            description=f'اعطای اعتبار به کاربر #666',
        ), call(
            user_id=666,
            currency=self.currency,
            amount=self.amount,
            ref_module=RefMod.credit_lend,
            ref_id=self.credit_transaction_id,
            description='اعطای 10.000000 بیت‌کوین اعتبار.',
        ),), any_order=True)

    @_patch_lend
    def test_user_with_low_assets(
        self,
        get_usdt_worth_mock: MagicMock,
        get_user_net_worth_mock: MagicMock,
        get_user_debt_worth_mock: MagicMock,
        create_credit_transaction_mock: MagicMock,
        add_wallet_transactions_mock: MagicMock,
        create_and_commit_transaction_mock: MagicMock,
    ):
        get_user_net_worth_mock.return_value = Decimal('100')
        self.default_mocks(
            get_usdt_worth_mock,
            None,
            get_user_debt_worth_mock,
            create_credit_transaction_mock,
            create_and_commit_transaction_mock,
        )
        with pytest.raises(errors.NotEnoughCollateral):
            CreditPlan.lend(self.user_id, self.currency, self.amount,)

    @_patch_lend
    def test_user_credit_limit(
        self,
        get_usdt_worth_mock: MagicMock,
        get_user_net_worth_mock: MagicMock,
        get_user_debt_worth_mock: MagicMock,
        create_credit_transaction_mock: MagicMock,
        add_wallet_transactions_mock: MagicMock,
        create_and_commit_transaction_mock: MagicMock,
    ):
        _plan.credit_limit_in_usdt = Decimal('25')
        self.default_mocks(
            get_usdt_worth_mock,
            get_user_net_worth_mock,
            get_user_debt_worth_mock,
            create_credit_transaction_mock,
            create_and_commit_transaction_mock,
        )
        with pytest.raises(errors.CreditLimit):
            CreditPlan.lend(self.user_id, self.currency, self.amount,)

    @_patch_lend
    def test_low_system_user_balance(
        self,
        get_usdt_worth_mock: MagicMock,
        get_user_net_worth_mock: MagicMock,
        get_user_debt_worth_mock: MagicMock,
        create_credit_transaction_mock: MagicMock,
        add_wallet_transactions_mock: MagicMock,
        create_and_commit_transaction_mock: MagicMock,
    ):
        create_and_commit_transaction_mock.side_effect = ValueError
        self.default_mocks(
            get_usdt_worth_mock,
            get_user_net_worth_mock,
            get_user_debt_worth_mock,
            create_credit_transaction_mock,
            None,
        )
        with pytest.raises(errors.CreditLimit):
            CreditPlan.lend(self.user_id, self.currency, self.amount,)

    @_patch_lend
    def test_user_with_deactivated_wallet(
        self,
        get_usdt_worth_mock: MagicMock,
        get_user_net_worth_mock: MagicMock,
        get_user_debt_worth_mock: MagicMock,
        create_credit_transaction_mock: MagicMock,
        add_wallet_transactions_mock: MagicMock,
        create_and_commit_transaction_mock: MagicMock,
    ):
        self.default_mocks(
            get_usdt_worth_mock,
            get_user_net_worth_mock,
            get_user_debt_worth_mock,
            create_credit_transaction_mock,
            None,
        )
        create_and_commit_transaction_mock.side_effect = (
            self.transaction_class(self.system_wallet_transaction_id,),
            ValueError,
        )
        with pytest.raises(errors.CantTransferAsset):
            CreditPlan.lend(self.user_id, self.currency, self.amount,)


def _patch_repay(test,):
    patch_prefix = 'exchange.credit.models'

    @wraps(test)
    @patch(patch_prefix + '.helpers.get_system_user_id', lambda *_: _credit_system_user_id,)
    @patch(patch_prefix + '.CreditPlan.get_last_plan', lambda _: _plan,)
    @patch(patch_prefix + '.create_and_commit_transaction',)
    @patch(patch_prefix + '.CreditTransaction.add_wallet_transactions',)
    @patch(patch_prefix + '.CreditTransaction.objects.create',)
    @patch(patch_prefix + '.CreditPlan._get_debt_amount',)
    def decorated(*args, **kwargs,):
        return test(*args, **kwargs,)
    return decorated


class RepayTest(TestCase):

    @classmethod
    def setUpTestData(cls) -> None:
        class DummyTransaction:
            def __init__(self, id,) -> None:
                self.id = id
        cls.user_id = 666
        cls.currency = 10
        cls.credit_transaction_id = 546
        cls.user_wallet_transaction_id = 54
        cls.system_wallet_transaction_id = 696
        cls.amount = Decimal('10')
        cls.transaction_class = DummyTransaction

    def setUp(self) -> None:
        for key, value in _plan_kwargs.items():
            _plan.__setattr__(key, value)

    def default_mocks(
        self,
        _get_debt_amount_mock: Optional[MagicMock],
        create_credit_transaction_mock: Optional[MagicMock],
        create_and_commit_transaction_mock: Optional[MagicMock],
    ):
        if _get_debt_amount_mock is not None:
            _get_debt_amount_mock.return_value = Decimal('20')

        if create_credit_transaction_mock is not None:
            create_credit_transaction_mock.return_value = self.transaction_class(self.credit_transaction_id)

        if create_and_commit_transaction_mock is not None:
            create_and_commit_transaction_mock.side_effect = (
                self.transaction_class(self.user_wallet_transaction_id,),
                self.transaction_class(self.system_wallet_transaction_id,),
            )

    @_patch_repay
    def test_a_successful_call(
        self,
        _get_debt_amount_mock: MagicMock,
        create_credit_transaction_mock: MagicMock,
        add_wallet_transactions_mock: MagicMock,
        create_and_commit_transaction_mock: MagicMock,
    ):
        add_wallet_transactions_mock.return_value = None
        self.default_mocks(
            _get_debt_amount_mock,
            create_credit_transaction_mock,
            create_and_commit_transaction_mock,
        )
        CreditPlan.repay(self.user_id, self.currency, self.amount,)
        add_wallet_transactions_mock.assert_called_once_with(
            self.credit_transaction_id, self.system_wallet_transaction_id, self.user_wallet_transaction_id,
        )
        create_credit_transaction_mock.assert_called_once_with(
            plan=_plan, currency=self.currency, tp=CreditTransaction.TYPES.repay, amount=self.amount,
        )
        create_and_commit_transaction_mock.assert_has_calls(calls=(call(
            user_id=_credit_system_user_id,
            currency=self.currency,
            amount=self.amount,
            ref_module=RefMod.credit_system_repay,
            ref_id=self.credit_transaction_id,
            description=f'تسویه‌ی اعتبار کاربر #666',
        ), call(
            user_id=self.user_id,
            currency=self.currency,
            amount=-self.amount,
            ref_module=RefMod.credit_repay,
            ref_id=self.credit_transaction_id,
            description='تسویه‌ی 10.000000 بیت‌کوین.',
        ),), any_order=True)

    @_patch_repay
    def test_over_repaying(
        self,
        _get_debt_amount_mock: MagicMock,
        create_credit_transaction_mock: MagicMock,
        add_wallet_transactions_mock: MagicMock,
        create_and_commit_transaction_mock: MagicMock,
    ):
        self.default_mocks(
            None,
            create_credit_transaction_mock,
            create_and_commit_transaction_mock,
        )
        _get_debt_amount_mock.return_value = Decimal('5')
        with pytest.raises(errors.InvalidAmount):
            CreditPlan.repay(self.user_id, self.currency, self.amount,)

    @_patch_repay
    def test_no_fund_to_repay(
        self,
        _get_debt_amount_mock: MagicMock,
        create_credit_transaction_mock: MagicMock,
        add_wallet_transactions_mock: MagicMock,
        create_and_commit_transaction_mock: MagicMock,
    ):
        self.default_mocks(
            _get_debt_amount_mock,
            create_credit_transaction_mock,
            create_and_commit_transaction_mock,
        )
        create_and_commit_transaction_mock.side_effect = ValueError
        with pytest.raises(errors.CantTransferAsset):
            CreditPlan.repay(self.user_id, self.currency, self.amount,)
