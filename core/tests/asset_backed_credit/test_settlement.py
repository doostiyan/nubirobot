import datetime
from decimal import Decimal
from typing import ClassVar, Optional
from unittest.mock import MagicMock, call, patch

import pytest
from django.core.management import call_command
from django.test import TestCase, override_settings

from exchange.accounts.models import Notification, UserSms
from exchange.asset_backed_credit.crons import ABCUnknownConfirmInitiatedUserSettlementCron, ABCUserSettlementCron
from exchange.asset_backed_credit.exceptions import (
    InsuranceFundAccountLowBalance,
    SettlementNeedsLiquidation,
    SettlementReverseError,
    UpdateClosedUserService,
)
from exchange.asset_backed_credit.models import ProviderWithdrawRequestLog, Service, SettlementTransaction, UserService
from exchange.asset_backed_credit.services.settlement import settle
from exchange.asset_backed_credit.tasks import task_settlement_liquidation, task_settlement_settle_user
from exchange.base.calendar import ir_now
from exchange.base.formatting import format_money
from exchange.base.models import RIAL, Currencies, Settings
from exchange.base.money import money_is_zero
from exchange.wallet.models import Transaction as ExchangeTransaction
from exchange.wallet.models import Wallet as ExchangeWallet
from exchange.wallet.models import WithdrawRequest as ExchangeWithdrawRequest
from tests.asset_backed_credit.helper import ABCMixins


class TestSettlement(ABCMixins, TestCase):
    fixtures: ClassVar = ['test_data']

    def setUp(self):
        self.settlement = self.create_settlement(
            Decimal(100_000_0), status=SettlementTransaction.STATUS.unknown_confirmed
        )
        self.user_service = self.settlement.user_service

    def assert_ok(
        self,
        user_amount: Decimal,
        insurance_amount: Decimal,
        user_wallet_balance_after: Decimal,
        insurance_wallet_balance_after: Decimal,
        liquidated_amount: Decimal,
        fee_amount: Decimal = 0,
        fee_wallet_balance_after: Optional[Decimal] = None,
        user_service_status: int = UserService.STATUS.settled,
        service_type: int = Service.TYPES.credit,
        is_reversed=False,
    ):
        self.user_service.refresh_from_db()
        if is_reversed:
            assert self.user_service.current_debt == self.user_service.initial_debt
        else:
            assert (
                self.user_service.current_debt
                == self.user_service.initial_debt - self.settlement.amount - self.settlement.fee_amount
            )

        if self.settlement.amount + self.settlement.fee_amount == self.user_service.initial_debt:
            assert self.settlement.user_service.status == user_service_status
            if user_service_status == UserService.STATUS.settled:
                assert self.settlement.user_service.closed_at is not None
            else:
                assert self.settlement.user_service.closed_at is None

            if is_reversed:
                assert self.settlement.user_service.current_debt == self.user_service.initial_debt
            else:
                assert money_is_zero(self.settlement.user_service.current_debt)

        user_wallet = self.settlement.user_rial_wallet
        user_wallet.refresh_from_db()

        assert user_wallet.balance == user_wallet_balance_after
        if not is_reversed:
            assert user_wallet.balance_blocked == user_wallet_balance_after

        assert self.settlement.liquidated_amount == liquidated_amount
        assert self.settlement.pending_liquidation_amount == 0
        assert self.settlement.should_use_insurance_fund is bool(insurance_amount)

        user_tx = self.settlement.user_withdraw_transaction
        assert user_tx.tp == ExchangeTransaction.TYPE.asset_backed_credit
        assert user_tx.ref_id == self.settlement.id
        assert user_tx.ref_module == ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlement']
        assert user_tx.amount == -user_amount
        assert user_tx.wallet.user_id == self.settlement.user_service.user_id
        if service_type == Service.TYPES.credit:
            assert (
                user_tx.description
                == f'تسویه اعتبار با {self.settlement.user_service.service.get_provider_display()} از کیف وثیقه'
            )
        else:
            assert (
                user_tx.description
                == f'تسویه دبیت با {self.settlement.user_service.service.get_provider_display()} از نوبی‌کارت'
            )

        user_reverse_tx = self.settlement.user_reverse_transaction
        if is_reversed:
            assert user_reverse_tx is not None
            assert user_reverse_tx.tp == ExchangeTransaction.TYPE.asset_backed_credit
            assert user_reverse_tx.ref_id == self.settlement.id
            assert (
                user_reverse_tx.ref_module == ExchangeTransaction.REF_MODULES['AssetBackedCreditUserSettlementReverse']
            )
            assert user_reverse_tx.amount == user_amount
            assert user_reverse_tx.wallet.user_id == self.settlement.user_service.user_id
            if service_type == Service.TYPES.credit:
                assert (
                    user_reverse_tx.description
                    == f'تراکنش اصلاحی اعتبار با {self.settlement.user_service.service.get_provider_display()} از کیف وثیقه'
                )
            else:
                assert (
                    user_reverse_tx.description
                    == f'تراکنش اصلاحی دبیت با {self.settlement.user_service.service.get_provider_display()} از نوبی‌کارت'
                )
        else:
            assert user_reverse_tx is None

        user_fee_tx = self.settlement.user_fee_withdraw_transaction
        if not money_is_zero(fee_amount):
            assert user_fee_tx.tp == ExchangeTransaction.TYPE.asset_backed_credit
            assert user_fee_tx.ref_id == self.settlement.id
            assert user_fee_tx.ref_module == ExchangeTransaction.REF_MODULES['AssetBackedCreditUserFeeSettlement']
            assert user_fee_tx.amount == -fee_amount
            assert user_fee_tx.wallet.user_id == self.settlement.user_service.user_id
            if service_type == Service.TYPES.credit:
                assert user_fee_tx.description == 'کسر کارمزد خرید از وثیقه'
            else:
                assert user_fee_tx.description == 'کسر کارمزد خرید از نوبی‌کارت'
        else:
            assert not user_fee_tx

        user_fee_reverse_tx = self.settlement.user_fee_reverse_transaction
        if is_reversed and not money_is_zero(fee_amount):
            assert user_fee_reverse_tx is not None
            assert user_fee_reverse_tx.tp == ExchangeTransaction.TYPE.asset_backed_credit
            assert user_fee_reverse_tx.ref_id == self.settlement.id
            assert (
                user_fee_reverse_tx.ref_module
                == ExchangeTransaction.REF_MODULES['AssetBackedCreditUserFeeSettlementReverse']
            )
            assert user_fee_reverse_tx.amount == fee_amount
            assert user_fee_reverse_tx.wallet.user_id == self.settlement.user_service.user_id
            if service_type == Service.TYPES.credit:
                assert user_fee_reverse_tx.description == 'اصلاح کسر کارمزد خرید از وثیقه'
            else:
                assert user_fee_reverse_tx.description == 'اصلاح کسر کارمزد خرید از نوبی‌کارت'
        else:
            assert user_fee_reverse_tx is None

        provider_tx = self.settlement.provider_deposit_transaction
        assert provider_tx.tp == ExchangeTransaction.TYPE.asset_backed_credit
        assert provider_tx.ref_id == self.settlement.id
        assert provider_tx.ref_module == ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlement']
        assert provider_tx.amount == self.settlement.amount
        assert provider_tx.description == f'واریز وجه تسویه طرح {self.settlement.user_service_id}'
        assert provider_tx.wallet.user_id == 910
        assert provider_tx.wallet.balance == self.settlement.amount

        provider_reverse_tx = self.settlement.provider_reverse_transaction
        if is_reversed:
            assert provider_reverse_tx is not None
            assert provider_reverse_tx.tp == ExchangeTransaction.TYPE.asset_backed_credit
            assert provider_reverse_tx.ref_id == self.settlement.id
            assert (
                provider_reverse_tx.ref_module
                == ExchangeTransaction.REF_MODULES['AssetBackedCreditProviderSettlementReverse']
            )
            assert provider_reverse_tx.amount == -self.settlement.amount
            assert provider_reverse_tx.description == f'تراکنش اصلاحی تسویه طرح {self.settlement.user_service_id}'
            assert provider_reverse_tx.wallet.user_id == 910
            assert provider_reverse_tx.wallet.balance == 0
        else:
            assert provider_reverse_tx is None

        insurance_tx = self.settlement.insurance_withdraw_transaction
        if bool(insurance_amount):
            assert insurance_tx is not None
            assert insurance_tx.tp == ExchangeTransaction.TYPE.asset_backed_credit
            assert insurance_tx.ref_id == self.settlement.id
            assert insurance_tx.ref_module == ExchangeTransaction.REF_MODULES['AssetBackedCreditInsuranceSettlement']
            assert insurance_tx.amount == -insurance_amount
            assert insurance_tx.description == f'برداشت وجه کسری مربوط به تسویه طرح {self.settlement.user_service_id}'
            assert insurance_tx.wallet.user_id == 990
        else:
            assert insurance_tx is None

        insurance_reverse_tx = self.settlement.insurance_reverse_transaction
        if is_reversed and bool(insurance_amount):
            assert insurance_reverse_tx is not None
            assert insurance_reverse_tx.tp == ExchangeTransaction.TYPE.asset_backed_credit
            assert insurance_reverse_tx.ref_id == self.settlement.id
            assert (
                insurance_reverse_tx.ref_module
                == ExchangeTransaction.REF_MODULES['AssetBackedCreditInsuranceSettlementReverse']
            )
            assert insurance_reverse_tx.amount == insurance_amount
            assert (
                insurance_reverse_tx.description
                == f'تراکنش اصلاحی کسری مربوط به تسویه طرح {self.settlement.user_service_id}'
            )
            assert insurance_reverse_tx.wallet.user_id == 990
        else:
            assert insurance_reverse_tx is None

        fee_tx = self.settlement.fee_deposit_transaction
        if not money_is_zero(fee_amount):
            assert fee_tx.tp == ExchangeTransaction.TYPE.asset_backed_credit
            assert fee_tx.ref_id == self.settlement.id
            assert fee_tx.ref_module == ExchangeTransaction.REF_MODULES['AssetBackedCreditFeeSettlement']
            assert fee_tx.amount == fee_amount
            assert fee_tx.wallet.user_id == 984
            if service_type == Service.TYPES.credit:
                assert fee_tx.description == 'انتقال کارمزد خرید از وثیقه'
            else:
                assert fee_tx.description == 'انتقال کارمزد خرید از نوبی‌کارت'
        else:
            assert not fee_tx

        fee_reverse_tx = self.settlement.fee_reverse_transaction
        if is_reversed and not money_is_zero(fee_amount):
            assert fee_reverse_tx is not None
            assert fee_reverse_tx.tp == ExchangeTransaction.TYPE.asset_backed_credit
            assert fee_reverse_tx.ref_id == self.settlement.id
            assert fee_reverse_tx.ref_module == ExchangeTransaction.REF_MODULES['AssetBackedCreditFeeSettlementReverse']
            assert fee_reverse_tx.amount == -fee_amount
            assert fee_reverse_tx.wallet.user_id == 984
            if service_type == Service.TYPES.credit:
                assert fee_reverse_tx.description == 'اصلاح انتقال کارمزد خرید از وثیقه'
            else:
                assert fee_reverse_tx.description == 'اصلاح انتقال کارمزد خرید از نوبی‌کارت'
        else:
            assert fee_reverse_tx is None

        insurance_wallet = self.settlement.get_insurance_fund_rial_wallet()
        insurance_wallet.refresh_from_db()
        assert insurance_wallet.balance == insurance_wallet_balance_after

        if fee_wallet_balance_after:
            fee_wallet = self.settlement.get_fee_rial_wallet()
            fee_wallet.refresh_from_db()
            assert fee_wallet.balance == fee_wallet_balance_after

    def test_create_user_transaction_when_already_settled(self):
        user_withdraw_transaction = self.settlement.user_rial_wallet.create_transaction(tp='manual', amount=100_000)
        user_withdraw_transaction.commit()
        self.settlement.user_withdraw_transaction = user_withdraw_transaction
        self.settlement.save()
        assert self.settlement.pending_liquidation_amount == 0
        assert self.settlement.create_user_transaction() == user_withdraw_transaction

    def test_create_user_reverse_transaction_when_already_settled(self):
        user_reverse_transaction = self.settlement.user_rial_wallet.create_transaction(tp='manual', amount=100_000)
        user_reverse_transaction.commit()
        self.settlement.user_reverse_transaction = user_reverse_transaction
        self.settlement.save()
        assert self.settlement.create_reverse_user_transaction() == user_reverse_transaction

    def test_create_user_fee_transaction_when_already_settled(self):
        user_fee_withdraw_transaction = self.settlement.user_rial_wallet.create_transaction(tp='manual', amount=1000)
        user_fee_withdraw_transaction.commit()
        self.settlement.user_fee_withdraw_transaction = user_fee_withdraw_transaction
        self.settlement.save()

        assert self.settlement.create_user_fee_transaction() == user_fee_withdraw_transaction

    def test_create_user_fee_reverse_transaction_when_already_settled(self):
        user_fee_reverse_transaction = self.settlement.user_rial_wallet.create_transaction(tp='manual', amount=1000)
        user_fee_reverse_transaction.commit()
        self.settlement.user_fee_reverse_transaction = user_fee_reverse_transaction
        self.settlement.save()

        assert self.settlement.create_reverse_user_fee_transaction() == user_fee_reverse_transaction

    def test_create_provider_transaction_when_already_settled(self):
        provider_deposit_transaction = self.settlement.provider.rial_wallet.create_transaction(
            tp='manual',
            amount=100_000,
        )
        provider_deposit_transaction.commit()
        self.settlement.provider_deposit_transaction = provider_deposit_transaction
        self.settlement.save()
        assert self.settlement.create_provider_transaction() == provider_deposit_transaction

    def test_create_provider_reverse_transaction_when_already_settled(self):
        provider_reverse_transaction = self.settlement.provider.rial_wallet.create_transaction(
            tp='manual',
            amount=100_000,
        )
        provider_reverse_transaction.commit()
        self.settlement.provider_reverse_transaction = provider_reverse_transaction
        self.settlement.save()
        assert self.settlement.create_reverse_provider_transaction() == provider_reverse_transaction

    def test_create_insurance_transaction_when_already_settled(self):
        insurance_withdraw_transaction = self.settlement.get_insurance_fund_rial_wallet().create_transaction(
            tp='manual',
            amount=100_000,
        )
        insurance_withdraw_transaction.commit()
        self.settlement.insurance_withdraw_transaction = insurance_withdraw_transaction
        self.settlement.save()
        assert self.settlement.create_insurance_fund_transaction() == insurance_withdraw_transaction

    def test_create_insurance_reverse_transaction_when_already_settled(self):
        insurance_reverse_transaction = self.settlement.get_insurance_fund_rial_wallet().create_transaction(
            tp='manual',
            amount=100_000,
        )
        insurance_reverse_transaction.commit()
        self.settlement.insurance_reverse_transaction = insurance_reverse_transaction
        self.settlement.save()
        assert self.settlement.create_reverse_insurance_fund_transaction() == insurance_reverse_transaction

    def test_create_fee_transaction_when_already_settled(self):
        fee_deposit_transaction = self.settlement.get_fee_rial_wallet().create_transaction(
            tp='manual',
            amount=100_000,
        )
        fee_deposit_transaction.commit()
        self.settlement.fee_deposit_transaction = fee_deposit_transaction
        self.settlement.save()
        assert self.settlement.create_fee_transaction() == fee_deposit_transaction

    def test_create_fee_reverse_transaction_when_already_settled(self):
        fee_reverse_transaction = self.settlement.get_fee_rial_wallet().create_transaction(
            tp='manual',
            amount=100_000,
        )
        fee_reverse_transaction.commit()
        self.settlement.fee_reverse_transaction = fee_reverse_transaction
        self.settlement.save()
        assert self.settlement.create_reverse_fee_transaction() == fee_reverse_transaction

    @patch('exchange.asset_backed_credit.services.wallet.wallet.WalletService.invalidate_user_wallets_cache')
    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_create_transactions_when_has_enough_balance_and_credit_service_type(
        self, mock_restriction_task, mock_wallet_cache_manager_invalidate: MagicMock
    ):
        assert self.settlement.pending_liquidation_amount == 100_000_0

        self.charge_exchange_wallet(self.settlement.user_service.user, RIAL, self.settlement.amount)

        assert self.settlement.liquidated_amount == 0

        self.settlement.orders.add(
            self.create_order(self.settlement.user_service.user, Decimal(30_000_0)),
            self.create_order(self.settlement.user_service.user, Decimal(10_000_0)),
        )

        self.settlement.user_service.initial_debt = self.settlement.amount
        self.settlement.user_service.current_debt = self.settlement.amount
        self.settlement.user_service.save()

        assert self.settlement.liquidated_amount == 40_000_0
        assert self.settlement.pending_liquidation_amount == 0
        assert self.settlement.user_service.current_debt == self.settlement.amount

        self.settlement.create_transactions()

        self.assert_ok(
            user_amount=Decimal(100_000_0),
            insurance_amount=Decimal(0),
            user_wallet_balance_after=Decimal(0),
            insurance_wallet_balance_after=Decimal(0),
            liquidated_amount=Decimal(40_000_0),
        )
        mock_restriction_task.assert_called_once()
        mock_wallet_cache_manager_invalidate.assert_called_once_with(user_id=self.settlement.user_service.user.uid)

    def test_create_transactions_when_has_enough_balance_and_debit_service_type(self):
        Settings.set('abc_debit_wallet_enabled', 'yes')

        self.settlement.user_service.service.tp = Service.TYPES.debit
        self.settlement.user_service.service.save()

        assert self.settlement.pending_liquidation_amount == 100_000_0

        self.charge_exchange_wallet(
            user=self.settlement.user_service.user,
            currency=RIAL,
            amount=self.settlement.amount,
            tp=ExchangeWallet.WALLET_TYPE.debit,
        )

        assert self.settlement.liquidated_amount == 0

        self.settlement.orders.add(
            self.create_order(self.settlement.user_service.user, Decimal(30_000_0)),
            self.create_order(self.settlement.user_service.user, Decimal(10_000_0)),
        )

        self.settlement.user_service.initial_debt = self.settlement.amount
        self.settlement.user_service.current_debt = self.settlement.amount
        self.settlement.user_service.save()

        assert self.settlement.liquidated_amount == 40_000_0
        assert self.settlement.pending_liquidation_amount == 0
        assert self.settlement.user_service.current_debt == self.settlement.amount

        self.settlement.create_transactions()

        self.assert_ok(
            user_amount=Decimal(100_000_0),
            insurance_amount=Decimal(0),
            user_wallet_balance_after=Decimal(0),
            insurance_wallet_balance_after=Decimal(0),
            liquidated_amount=Decimal(40_000_0),
            user_service_status=UserService.STATUS.initiated,
            service_type=Service.TYPES.debit,
        )

    def test_create_transactions_when_has_enough_balance_partial(self):
        self.settlement.amount = 10_000_0
        self.settlement.save()

        self.charge_exchange_wallet(self.settlement.user_service.user, RIAL, self.settlement.amount)

        self.settlement.user_service.initial_debt = self.settlement.amount * 2
        self.settlement.user_service.current_debt = self.settlement.amount * 2
        self.settlement.user_service.save()

        self.settlement.create_transactions()

        self.assert_ok(
            user_amount=Decimal(10_000_0),
            insurance_amount=Decimal(0),
            user_wallet_balance_after=Decimal(0),
            insurance_wallet_balance_after=Decimal(0),
            liquidated_amount=Decimal(0),
        )

    @patch('exchange.asset_backed_credit.services.wallet.wallet.WalletService.invalidate_user_wallets_cache')
    def test_create_transactions_and_reverse_transactions_success(
        self, mock_wallet_cache_manager_invalidate: MagicMock
    ):
        Settings.set('abc_debit_wallet_enabled', 'yes')

        self.settlement.user_service.service.tp = Service.TYPES.debit
        self.settlement.user_service.service.save()

        assert self.settlement.pending_liquidation_amount == 100_000_0

        self.charge_exchange_wallet(
            user=self.settlement.user_service.user,
            currency=RIAL,
            amount=self.settlement.amount,
            tp=ExchangeWallet.WALLET_TYPE.debit,
        )

        assert self.settlement.liquidated_amount == 0

        self.settlement.orders.add(
            self.create_order(self.settlement.user_service.user, Decimal(30_000_0)),
            self.create_order(self.settlement.user_service.user, Decimal(10_000_0)),
        )

        self.settlement.user_service.initial_debt = self.settlement.amount
        self.settlement.user_service.current_debt = self.settlement.amount
        self.settlement.user_service.save()

        assert self.settlement.liquidated_amount == 40_000_0
        assert self.settlement.pending_liquidation_amount == 0
        assert self.settlement.user_service.current_debt == self.settlement.amount

        self.settlement.create_transactions()

        self.assert_ok(
            user_amount=Decimal(100_000_0),
            insurance_amount=Decimal(0),
            user_wallet_balance_after=Decimal(0),
            insurance_wallet_balance_after=Decimal(0),
            liquidated_amount=Decimal(40_000_0),
            user_service_status=UserService.STATUS.initiated,
            service_type=Service.TYPES.debit,
        )

        self.settlement.create_reverse_transactions()

        self.assert_ok(
            user_amount=Decimal(100_000_0),
            insurance_amount=Decimal(0),
            user_wallet_balance_after=Decimal(100_000_0),
            insurance_wallet_balance_after=Decimal(0),
            liquidated_amount=Decimal(40_000_0),
            user_service_status=UserService.STATUS.initiated,
            service_type=Service.TYPES.debit,
            is_reversed=True,
        )

        assert mock_wallet_cache_manager_invalidate.call_count == 2
        mock_wallet_cache_manager_invalidate.assert_called_with(user_id=self.settlement.user_service.user.uid)

    def test_create_transactions_and_reverse_transactions_with_fee_amount_success(self):
        Settings.set('abc_debit_wallet_enabled', 'yes')

        self.settlement.user_service.service.tp = Service.TYPES.debit
        self.settlement.user_service.service.save()
        self.settlement.fee_amount = Decimal(100_0)

        assert self.settlement.pending_liquidation_amount == 100_100_0

        self.charge_exchange_wallet(
            user=self.settlement.user_service.user,
            currency=RIAL,
            amount=self.settlement.amount + self.settlement.fee_amount,
            tp=ExchangeWallet.WALLET_TYPE.debit,
        )

        assert self.settlement.liquidated_amount == 0

        self.settlement.orders.add(
            self.create_order(self.settlement.user_service.user, Decimal(30_000_0)),
            self.create_order(self.settlement.user_service.user, Decimal(10_000_0)),
        )

        self.settlement.user_service.initial_debt = self.settlement.amount + self.settlement.fee_amount
        self.settlement.user_service.current_debt = self.settlement.amount + self.settlement.fee_amount
        self.settlement.user_service.save()

        assert self.settlement.liquidated_amount == 40_000_0
        assert self.settlement.pending_liquidation_amount == 0
        assert self.settlement.user_service.current_debt == self.settlement.amount + self.settlement.fee_amount

        self.settlement.create_transactions()

        self.assert_ok(
            user_amount=Decimal(100_000_0),
            insurance_amount=Decimal(0),
            user_wallet_balance_after=Decimal(0),
            insurance_wallet_balance_after=Decimal(0),
            liquidated_amount=Decimal(40_000_0),
            fee_amount=Decimal(100_0),
            fee_wallet_balance_after=Decimal(100_0),
            user_service_status=UserService.STATUS.initiated,
            service_type=Service.TYPES.debit,
        )

        self.settlement.create_reverse_transactions()

        self.assert_ok(
            user_amount=Decimal(100_000_0),
            insurance_amount=Decimal(0),
            user_wallet_balance_after=Decimal(100_100_0),
            insurance_wallet_balance_after=Decimal(0),
            liquidated_amount=Decimal(40_000_0),
            fee_amount=Decimal(100_0),
            fee_wallet_balance_after=Decimal(0),
            user_service_status=UserService.STATUS.initiated,
            service_type=Service.TYPES.debit,
            is_reversed=True,
        )

    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_create_transactions_and_reverse_transactions_when_user_service_is_closed_reverse_failed(
        self, mock_restriction_task
    ):
        assert self.settlement.pending_liquidation_amount == 100_000_0

        self.charge_exchange_wallet(
            user=self.settlement.user_service.user, currency=RIAL, amount=self.settlement.amount
        )

        assert self.settlement.liquidated_amount == 0

        self.settlement.orders.add(
            self.create_order(self.settlement.user_service.user, Decimal(30_000_0)),
            self.create_order(self.settlement.user_service.user, Decimal(10_000_0)),
        )

        self.settlement.user_service.initial_debt = self.settlement.amount
        self.settlement.user_service.current_debt = self.settlement.amount
        self.settlement.user_service.save()

        assert self.settlement.liquidated_amount == 40_000_0
        assert self.settlement.pending_liquidation_amount == 0
        assert self.settlement.user_service.current_debt == self.settlement.amount

        self.settlement.create_transactions()

        self.assert_ok(
            user_amount=Decimal(100_000_0),
            insurance_amount=Decimal(0),
            user_wallet_balance_after=Decimal(0),
            insurance_wallet_balance_after=Decimal(0),
            liquidated_amount=Decimal(40_000_0),
        )
        mock_restriction_task.assert_called_once()

        with pytest.raises(UpdateClosedUserService):
            self.settlement.create_reverse_transactions()

        self.settlement.refresh_from_db()
        user_reverse_tx = self.settlement.user_reverse_transaction
        assert not user_reverse_tx
        provider_reverse_tx = self.settlement.provider_reverse_transaction
        assert not provider_reverse_tx
        insurance_reverse_tx = self.settlement.insurance_reverse_transaction
        assert not insurance_reverse_tx

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 100_000_000_0
    )
    @patch('exchange.wallet.estimator.PriceEstimator.get_price_range', lambda *_: (100_000_000_0, _))
    def test_create_user_transaction_when_needs_liquidation(self):
        assert self.settlement.pending_liquidation_amount == 100_000_0
        self.charge_exchange_wallet(self.settlement.user_service.user, Currencies.btc, 1)
        wallet = self.charge_exchange_wallet(self.settlement.user_service.user, RIAL, 20_000_0)
        wallet.refresh_from_db()

        assert self.settlement.liquidated_amount == 0

        self.settlement.orders.add(
            self.create_order(self.settlement.user_service.user, Decimal(10_000_0)),
        )

        assert self.settlement.liquidated_amount == 10_000_0
        assert self.settlement.pending_liquidation_amount == 80_000_0

        with pytest.raises(SettlementNeedsLiquidation):
            self.settlement.create_user_transaction()

    def test_create_reverse_transaction_success(self):
        self.charge_exchange_wallet(self.settlement.user_service.user, RIAL, 100_000)

        user_withdraw_transaction = self.settlement.user_rial_wallet.create_transaction(tp='manual', amount=-100_000)
        user_withdraw_transaction.commit()
        self.settlement.user_withdraw_transaction = user_withdraw_transaction
        self.settlement.save()

        user_reverse_transaction = self.settlement.create_reverse_user_transaction()

        assert user_reverse_transaction
        assert user_reverse_transaction.amount == -user_withdraw_transaction.amount
        self.settlement.user_rial_wallet.refresh_from_db()
        assert self.settlement.user_reverse_transaction
        assert self.settlement.user_reverse_transaction.amount == -user_withdraw_transaction.amount
        assert self.settlement.user_rial_wallet.balance == 100_000
        assert self.settlement.status == SettlementTransaction.STATUS.reversed

    def test_create_reverse_transaction_when_user_withdraw_transaction_not_found_error(self):
        with pytest.raises(SettlementReverseError):
            self.settlement.create_reverse_user_transaction()

    def test_create_reverse_transaction_when_provider_withdraw_transaction_found_error(self):
        user_withdraw_transaction = self.settlement.user_rial_wallet.create_transaction(tp='manual', amount=100_000)
        user_withdraw_transaction.commit()
        self.settlement.user_withdraw_transaction = user_withdraw_transaction
        withdraw_request = ExchangeWithdrawRequest.objects.create(
            amount=1_000_0,
            wallet=self.settlement.provider.rial_wallet,
            explanations='',
            target_account=None,
        )
        self.settlement.provider_withdraw_requests.add(withdraw_request)
        self.settlement.save()

        with pytest.raises(SettlementReverseError):
            self.settlement.create_reverse_user_transaction()

    def test_create_reverse_transaction_when_provider_withdraw_log_transaction_found_error(self):
        user_withdraw_transaction = self.settlement.user_rial_wallet.create_transaction(tp='manual', amount=100_000)
        user_withdraw_transaction.commit()
        provider_withdraw = ProviderWithdrawRequestLog(provider=self.settlement.provider.id, amount=1_000_0)
        provider_withdraw.save()
        self.settlement.user_withdraw_transaction = user_withdraw_transaction
        self.settlement.provider_withdraw_request_log = provider_withdraw
        self.settlement.save()

        with pytest.raises(SettlementReverseError):
            self.settlement.create_reverse_user_transaction()

    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_create_transactions_when_insurance_used(self, mock_restriction_task):
        assert self.settlement.pending_liquidation_amount == 100_000_0
        self.charge_exchange_wallet(
            self.settlement.get_insurance_fund_account(), RIAL, 100_000_0, tp=ExchangeWallet.WALLET_TYPE.spot
        )
        self.charge_exchange_wallet(self.settlement.user_service.user, RIAL, 20_000_0)

        assert self.settlement.liquidated_amount == 0

        self.settlement.orders.add(
            self.create_order(self.settlement.user_service.user, Decimal(10_000_0)),
        )

        assert self.settlement.liquidated_amount == 10_000_0
        assert self.settlement.pending_liquidation_amount == 80_000_0

        self.settlement.create_transactions()

        self.assert_ok(
            user_amount=Decimal(20_000_0),
            insurance_amount=Decimal(80_000_0),
            user_wallet_balance_after=Decimal(0),
            insurance_wallet_balance_after=Decimal(20_000_0),
            liquidated_amount=Decimal(10_000_0),
        )
        mock_restriction_task.assert_called_once()

    def test_create_transactions_and_reverse_transactions_when_insurance_used(self):
        Settings.set('abc_debit_wallet_enabled', 'yes')

        self.settlement.user_service.service.tp = Service.TYPES.debit
        self.settlement.user_service.service.save()

        assert self.settlement.pending_liquidation_amount == 100_000_0
        self.charge_exchange_wallet(
            self.settlement.get_insurance_fund_account(), RIAL, 100_000_0, tp=ExchangeWallet.WALLET_TYPE.spot
        )
        self.charge_exchange_wallet(
            user=self.settlement.user_service.user,
            currency=RIAL,
            amount=20_000_0,
            tp=ExchangeWallet.WALLET_TYPE.debit,
        )

        assert self.settlement.liquidated_amount == 0

        self.settlement.orders.add(
            self.create_order(self.settlement.user_service.user, Decimal(10_000_0)),
        )

        assert self.settlement.liquidated_amount == 10_000_0
        assert self.settlement.pending_liquidation_amount == 80_000_0

        self.settlement.create_transactions()

        self.assert_ok(
            user_amount=Decimal(20_000_0),
            insurance_amount=Decimal(80_000_0),
            user_wallet_balance_after=Decimal(0),
            insurance_wallet_balance_after=Decimal(20_000_0),
            liquidated_amount=Decimal(10_000_0),
            user_service_status=UserService.STATUS.initiated,
            service_type=Service.TYPES.debit,
        )

        self.settlement.create_reverse_transactions()

        self.assert_ok(
            user_amount=Decimal(20_000_0),
            insurance_amount=Decimal(80_000_0),
            user_wallet_balance_after=Decimal(20_000_0),
            insurance_wallet_balance_after=Decimal(100_000_0),
            liquidated_amount=Decimal(10_000_0),
            user_service_status=UserService.STATUS.initiated,
            service_type=Service.TYPES.debit,
            is_reversed=True,
        )

    def test_create_transactions_when_insurance_wallet_low_balance(self):
        insurance_wallet = self.charge_exchange_wallet(self.settlement.get_insurance_fund_account(), RIAL, 20_000_0)
        wallet = self.charge_exchange_wallet(self.settlement.user_service.user, RIAL, 20_000_0)
        wallet.refresh_from_db()

        assert self.settlement.liquidated_amount == 0

        self.settlement.orders.add(
            self.create_order(self.settlement.user_service.user, Decimal(10_000_0)),
        )

        assert self.settlement.liquidated_amount == 10_000_0
        assert self.settlement.pending_liquidation_amount == 80_000_0
        with pytest.raises(InsuranceFundAccountLowBalance):
            self.settlement.create_transactions()

        wallet.refresh_from_db()
        assert self.settlement.user_withdraw_transaction is None
        assert self.settlement.provider_deposit_transaction is None
        assert self.settlement.insurance_withdraw_transaction is None
        assert wallet.balance == 20_000_0
        assert wallet.balance_blocked == 0
        assert self.settlement.liquidated_amount == 10_000_0
        assert self.settlement.pending_liquidation_amount == 80_000_0
        assert self.settlement.user_service.current_debt == 100_000_0
        assert self.settlement.should_use_insurance_fund is True
        insurance_wallet.refresh_from_db()
        assert insurance_wallet.balance == 20_000_0

    def test_settlement_should_use_insurance_low_balance_1(self):
        assert self.settlement.should_use_insurance_fund is True

    def test_settlement_should_use_insurance_low_balance_2(self):
        self.charge_exchange_wallet(self.settlement.user_service.user, RIAL, 50_000_0)
        assert self.settlement.should_use_insurance_fund is True

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 10_000_0)
    @patch('exchange.wallet.estimator.PriceEstimator.get_price_range', lambda *_: (10_000_0, _))
    def test_settlement_should_use_insurance_low_balance_3(self):
        self.charge_exchange_wallet(self.settlement.user_service.user, Currencies.usdt, 1)

        assert self.settlement.should_use_insurance_fund is True

    @patch('exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 100_000_0)
    @patch('exchange.wallet.estimator.PriceEstimator.get_price_range', lambda *_: (100_000_0, _))
    def test_settlement_should_use_insurance_enough_balance(self):
        self.charge_exchange_wallet(self.settlement.user_service.user, Currencies.usdt, 1)

        assert self.settlement.should_use_insurance_fund is False

    @patch('exchange.asset_backed_credit.models.settlement.SettlementTransaction.create_user_transaction')
    @patch('exchange.asset_backed_credit.models.settlement.SettlementTransaction.create_insurance_fund_transaction')
    @patch('exchange.asset_backed_credit.models.settlement.SettlementTransaction.create_provider_transaction')
    @patch('exchange.asset_backed_credit.models.user_service.UserService.update_current_debt')
    def test_create_transactions_unit(
        self,
        mock_update_debt: MagicMock,
        mock_create_provider_transaction: MagicMock,
        mock_create_insurance_fund_transaction: MagicMock,
        mock_create_user_transaction: MagicMock,
    ):
        self.settlement.create_transactions()
        assert mock_create_user_transaction.call_count == 1
        assert mock_create_insurance_fund_transaction.call_count == 1
        assert mock_create_provider_transaction.call_count == 1
        mock_update_debt.assert_called_once_with(-self.settlement.amount)

    @patch('exchange.asset_backed_credit.tasks.task_settlement_liquidation.delay')
    @patch('exchange.asset_backed_credit.models.settlement.SettlementTransaction.create_user_transaction')
    def test_settle_user_when_already_settled(
        self,
        mock_create_user_transaction: MagicMock,
        mock_task_settlement_liquidation: MagicMock,
    ):
        user_wallet = ExchangeWallet.get_user_wallet(
            self.settlement.user_service.user_id, Currencies.btc, tp=ExchangeWallet.WALLET_TYPE.credit
        )
        user_withdraw_transaction = user_wallet.create_transaction(tp='manual', amount=100_000)
        user_withdraw_transaction.commit()
        self.settlement.user_withdraw_transaction = user_withdraw_transaction
        self.settlement.save()
        assert self.settlement.pending_liquidation_amount == 0

        settle(self.settlement.id)

        assert mock_create_user_transaction.call_count == 0
        assert mock_task_settlement_liquidation.call_count == 0
        self.settlement.refresh_from_db()
        assert self.settlement.remaining_rial_wallet_balance == None

    @patch('exchange.asset_backed_credit.tasks.task_settlement_liquidation.delay')
    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_settle_user_when_has_enough_balance(
        self,
        mock_restriction_task: MagicMock,
        mock_task_settlement_liquidation: MagicMock,
    ):
        self.charge_exchange_wallet(self.settlement.user_service.user, RIAL, self.settlement.amount)
        settle(self.settlement.id)

        assert mock_task_settlement_liquidation.call_count == 0
        mock_restriction_task.assert_called_once()
        self.settlement.refresh_from_db()
        assert self.settlement.remaining_rial_wallet_balance == 0

    @patch('exchange.asset_backed_credit.tasks.task_settlement_liquidation.delay')
    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_settle_user_when_has_more_balance(
        self,
        mock_restriction_task: MagicMock,
        mock_task_settlement_liquidation: MagicMock,
    ):
        self.charge_exchange_wallet(self.settlement.user_service.user, RIAL, self.settlement.amount + 100)
        settle(self.settlement.id)

        mock_restriction_task.assert_called_once()
        assert mock_task_settlement_liquidation.call_count == 0
        self.settlement.refresh_from_db()
        assert self.settlement.remaining_rial_wallet_balance == 100

    @patch(
        'exchange.asset_backed_credit.externals.price.MarkPriceCalculator.get_mark_price', lambda _, __: 100_000_000_0
    )
    @patch('exchange.wallet.estimator.PriceEstimator.get_price_range', lambda *_: (100_000_000_0, _))
    @patch('exchange.asset_backed_credit.tasks.task_settlement_liquidation.delay')
    def test_settle_user_when_needs_liquidation(
        self,
        mock_task_settlement_liquidation: MagicMock,
    ):
        self.charge_exchange_wallet(self.settlement.user_service.user, Currencies.btc, 1)
        settle(self.settlement.id)
        assert mock_task_settlement_liquidation.call_count == 1

    @patch('exchange.asset_backed_credit.tasks.task_settlement_liquidation.delay')
    @patch('exchange.asset_backed_credit.tasks.remove_user_restriction_task.delay')
    def test_settle_user_notifications(self, mock_restriction_task, *_):
        self.charge_exchange_wallet(self.settlement.user_service.user, RIAL, self.settlement.amount)
        self.settlement.transaction_datetime = ir_now()
        self.settlement.save()
        settle(self.settlement.id)

        sms = UserSms.objects.filter(user=self.user_service.user, tp=UserSms.TYPES.abc_liquidate_by_provider).first()
        assert sms
        assert (
            sms.text
            == format_money(money=self.settlement.amount, currency=Currencies.rls)
            + '\n'
            + self.user_service.service.get_tp_display()
            + '\n'
            + self.user_service.service.get_provider_display()
        )
        assert sms.to == self.user_service.user.mobile

        notif = Notification.objects.filter(user=self.user_service.user).first()
        assert notif
        mock_restriction_task.assert_called_once()
        self.settlement.refresh_from_db()
        assert self.settlement.remaining_rial_wallet_balance == 0

    @patch('exchange.asset_backed_credit.tasks.task_settlement_liquidation.delay')
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_settle_user_notifications_debit_service_type_exclude_email_notif(self, email_manager_mock: MagicMock, *_):
        Settings.set('abc_debit_wallet_enabled', 'yes')

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        self.user_service.service = service
        self.user_service.save()
        user = self.user_service.user
        vp = user.get_verification_profile()
        vp.email_confirmed = True
        vp.save()

        wallet_remaining_after_settle = 130_0000_000
        self.charge_exchange_wallet(
            user=self.settlement.user_service.user,
            currency=RIAL,
            amount=wallet_remaining_after_settle + self.settlement.amount,
            tp=ExchangeWallet.WALLET_TYPE.debit,
        )
        self.settlement.transaction_datetime = ir_now()
        self.settlement.save()

        settle(self.settlement.id)
        self.settlement.refresh_from_db()

        email_manager_mock.assert_not_called()

        sms = UserSms.objects.filter(user=self.user_service.user, tp=UserSms.TYPES.abc_debit_settlement).first()
        assert sms
        assert sms.to == self.user_service.user.mobile
        remaining_formatted_amount = format_money(
            money=Decimal(self.settlement.remaining_rial_wallet_balance), currency=Currencies.rls
        )
        assert remaining_formatted_amount in sms.sms_full_text
        assert remaining_formatted_amount in sms.text

        notif = Notification.objects.filter(user=self.user_service.user).first()
        assert notif
        self.settlement.refresh_from_db()
        assert self.settlement.remaining_rial_wallet_balance == wallet_remaining_after_settle

    @patch('exchange.asset_backed_credit.tasks.task_settlement_liquidation.delay')
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_settle_user_notifications_debit_service_type_exclude_email_notif_on_credit_wallet(
        self, email_manager_mock: MagicMock, *_
    ):
        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        self.user_service.service = service
        self.user_service.save()
        user = self.user_service.user
        vp = user.get_verification_profile()
        vp.email_confirmed = True
        vp.save()

        wallet_remaining_after_settle = 130_0000_000
        self.charge_exchange_wallet(
            user=self.settlement.user_service.user,
            currency=RIAL,
            amount=wallet_remaining_after_settle + self.settlement.amount,
            tp=ExchangeWallet.WALLET_TYPE.credit,
        )
        self.settlement.transaction_datetime = ir_now()
        self.settlement.save()

        settle(self.settlement.id)
        self.settlement.refresh_from_db()

        email_manager_mock.assert_not_called()

        sms = UserSms.objects.filter(user=self.user_service.user, tp=UserSms.TYPES.abc_debit_settlement).first()
        assert sms
        assert sms.to == self.user_service.user.mobile
        remaining_formatted_amount = format_money(
            money=Decimal(self.settlement.remaining_rial_wallet_balance), currency=Currencies.rls
        )
        assert remaining_formatted_amount in sms.sms_full_text
        assert remaining_formatted_amount in sms.text

        notif = Notification.objects.filter(user=self.user_service.user).first()
        assert notif
        self.settlement.refresh_from_db()
        assert self.settlement.remaining_rial_wallet_balance == wallet_remaining_after_settle

    @patch('exchange.asset_backed_credit.tasks.task_settlement_liquidation.delay')
    @patch('exchange.base.emailmanager.EmailManager.send_email')
    def test_settle_user_notifications_with_debit_service_type_and_empty_user_first_name(self, *_):
        Settings.set('abc_debit_wallet_enabled', 'yes')

        service = self.create_service(provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit)
        self.user_service.service = service
        self.user_service.save()
        user = self.user_service.user
        user.first_name = ''
        user.save()
        vp = user.get_verification_profile()
        vp.email_confirmed = True
        vp.save()

        self.charge_exchange_wallet(
            user=self.settlement.user_service.user,
            currency=RIAL,
            amount=self.settlement.amount,
            tp=ExchangeWallet.WALLET_TYPE.debit,
        )
        self.settlement.transaction_datetime = ir_now()
        self.settlement.save()
        settle(self.settlement.id)

        sms = UserSms.objects.filter(user=self.user_service.user, tp=UserSms.TYPES.abc_debit_settlement).first()
        assert sms
        assert 'کاربر' in sms.text
        assert sms.to == self.user_service.user.mobile

        notif = Notification.objects.filter(user=self.user_service.user).first()
        assert notif
        self.settlement.refresh_from_db()
        assert self.settlement.remaining_rial_wallet_balance == 0

    @pytest.mark.slow()
    @override_settings(POST_OFFICE={'BACKENDS': {'default': 'django.core.mail.backends.smtp.EmailBackend'}})
    @patch('exchange.asset_backed_credit.tasks.task_settlement_liquidation.delay')
    def test_settle_user_notifications_email(self, *_):
        user = self.user_service.user
        vp = user.get_verification_profile()
        vp.email_confirmed = True
        vp.save()

        Settings.set_dict('email_whitelist', [self.user_service.user.email])
        call_command('update_email_templates')

        self.charge_exchange_wallet(self.settlement.user_service.user, RIAL, self.settlement.amount)
        self.settlement.transaction_datetime = ir_now()
        self.settlement.save()
        settle(self.settlement.id)

        self.settlement.refresh_from_db()
        assert self.settlement.remaining_rial_wallet_balance == 0
        with patch('django.db.connection.close'):
            call_command('send_queued_mail')


@patch('exchange.asset_backed_credit.tasks.task_settlement_settle_user.delay')
class TestUserSettlementCron(ABCMixins, TestCase):
    def setUp(self):
        self.candid_settlement1 = self.create_settlement(Decimal(100_000_0))
        self.candid_settlement1.status = SettlementTransaction.STATUS.confirmed
        self.candid_settlement1.save()
        self.candid_settlement2 = self.create_settlement(Decimal(200_000_0))
        self.candid_settlement2.status = SettlementTransaction.STATUS.unknown_confirmed
        self.candid_settlement2.save()

        self.not_candid_settlement1 = self.create_settlement(Decimal(100_000_0))
        user_wallet = ExchangeWallet.get_user_wallet(
            self.not_candid_settlement1.user_service.user_id, Currencies.btc, tp=ExchangeWallet.WALLET_TYPE.credit
        )
        user_withdraw_transaction = user_wallet.create_transaction(tp='manual', amount=100_000)
        user_withdraw_transaction.commit()
        self.not_candid_settlement1.user_withdraw_transaction = user_withdraw_transaction
        self.not_candid_settlement1.save()

    def test_user_settlement_cron(self, mock_task_user_settlement: MagicMock):
        ABCUserSettlementCron().run()

        assert mock_task_user_settlement.call_count == 2
        mock_task_user_settlement.assert_has_calls(
            [call(self.candid_settlement1.id), call(self.candid_settlement2.id)], any_order=True
        )


class TestUnknownConfirmInitiatedUserSettlementCron(ABCMixins, TestCase):
    def setUp(self):
        self.amount = Decimal('100000')
        self.settlement1 = self.create_settlement(self.amount)
        self.settlement1.status = SettlementTransaction.STATUS.initiated
        self.settlement1.save()

        self.settlement2 = self.create_settlement(self.amount)
        self.settlement2.status = SettlementTransaction.STATUS.initiated
        self.settlement2.created_at = ir_now() - datetime.timedelta(minutes=6)
        self.settlement2.save()

        self.settlement3 = self.create_settlement(self.amount)
        self.settlement3.status = SettlementTransaction.STATUS.confirmed
        self.settlement3.save()

        self.debit_user_service = self.create_user_service(service=self.create_service(tp=Service.TYPES.debit))

    def test_liquidate_settlement_task(self):
        ABCUnknownConfirmInitiatedUserSettlementCron().run()

        self.settlement1.refresh_from_db()
        assert self.settlement1.status == SettlementTransaction.STATUS.initiated
        self.settlement2.refresh_from_db()
        assert self.settlement2.status == SettlementTransaction.STATUS.unknown_confirmed
        self.settlement3.refresh_from_db()
        assert self.settlement3.status == SettlementTransaction.STATUS.confirmed


@patch('exchange.asset_backed_credit.models.settlement.SettlementTransaction.create_transactions')
class TestUserSettlementTask(ABCMixins, TestCase):
    def setUp(self):
        self.settlement = self.create_settlement(Decimal(100_000_0))

    def test_user_settlement_task(self, create_transactions_mock: MagicMock):
        task_settlement_settle_user(self.settlement.id)

        assert create_transactions_mock.call_count == 1


@patch('exchange.asset_backed_credit.tasks.liquidate_settlement')
class TestLiquidateSettlementTask(ABCMixins, TestCase):
    def setUp(self):
        self.settlement = self.create_settlement(Decimal(100_000_0))

    def test_liquidate_settlement_task(self, liquidate_settlement_mock: MagicMock):
        task_settlement_liquidation(self.settlement.id)

        liquidate_settlement_mock.assert_called_once_with(
            settlement_id=self.settlement.id,
            wait_before_retry=datetime.timedelta(minutes=2),
        )
