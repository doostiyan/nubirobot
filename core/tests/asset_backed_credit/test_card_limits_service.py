from decimal import Decimal
from unittest import TestCase

import pytest
from jdatetime import timedelta

from exchange.asset_backed_credit.exceptions import CardTransactionLimitExceedError, CardUnknownLevelError
from exchange.asset_backed_credit.models import Card, CardSetting, CardTransactionLimit
from exchange.asset_backed_credit.services.debit.limits import check_card_transaction_limits
from exchange.base.calendar import ir_today
from tests.asset_backed_credit.helper import ABCMixins


class CardTransactionLimitCheckServiceTest(TestCase, ABCMixins):
    def setUp(self):
        self.card_level_per_trx_limit = 100_000_000
        self.card_level_daily_limit = 200_000_000
        self.card_level_monthly_limit = 1_000_000_000

        self.card_level = self._create_card_level(
            1,
            self.card_level_per_trx_limit,
            self.card_level_daily_limit,
            self.card_level_monthly_limit,
            0.0,
        )
        self.card = self.create_card(
            '6037731012345666', user_service=self.create_user_service(), setting=self.card_level
        )

        self.new_transaction_amount = 1_000_000

    def test_when_amount_exceeds_per_transaction_max_allowed_amount_then_exception_is_raised(self):
        with pytest.raises(CardTransactionLimitExceedError):
            check_card_transaction_limits(self.card, self.card_level_daily_limit + 1)

    def test_when_new_transaction_amount_exceeds_allowed_daily_transactions_total_amount_then_exception_is_raised(self):
        self._create_daily_limit(self.card, self.card_level_daily_limit - self.new_transaction_amount)

        with pytest.raises(CardTransactionLimitExceedError):
            check_card_transaction_limits(self.card, self.new_transaction_amount + 1)

    def test_when_new_transaction_amount_exceeds_allowed_monthly_transactions_total_amount_then_exception_is_raised(
        self,
    ):
        self._create_daily_limit(self.card, self.card_level_daily_limit - self.new_transaction_amount * 2)
        self._create_monthly_limit(self.card, self.card_level_monthly_limit - self.new_transaction_amount)

        with pytest.raises(CardTransactionLimitExceedError) as e:
            check_card_transaction_limits(self.card, self.new_transaction_amount + 1)

    def test_when_card_has_no_levels_then_card_unknown_level_error_is_raised(self):
        card = self.create_card('6037731012345444', user_service=self.create_user_service())

        with pytest.raises(CardUnknownLevelError):
            check_card_transaction_limits(card, self.new_transaction_amount)

    def test_new_transaction_success_that_does_not_exceed_limits_when_card_had_some_transactions_today_and_this_month(
        self,
    ):
        self._create_daily_limit(self.card, self.card_level_daily_limit - self.new_transaction_amount * 2)
        self._create_monthly_limit(self.card, self.card_level_monthly_limit - self.new_transaction_amount * 5)

        check_card_transaction_limits(self.card, self.new_transaction_amount)

    def test_success_new_transaction_when_it_is_first_transaction_of_today_and_this_month(self):
        CardTransactionLimit.objects.filter(card=self.card).delete()
        check_card_transaction_limits(self.card, self.new_transaction_amount)

    def test_when_card_has_old_daily_limit_record_and_new_transaction_is_first_transaction_of_today_then_no_error_is_raised(
        self,
    ):
        CardTransactionLimit.objects.filter(card=self.card).delete()
        CardTransactionLimit._create(
            card=self.card,
            tp=CardTransactionLimit.DurationChoices.DAILY,
            start_at=ir_today() - timedelta(days=50),
            total=self.new_transaction_amount,
        )

    def test_when_card_has_old_monthly_limit_record_and_new_transaction_is_first_transaction_of_current_month_then_no_error_is_raised(
        self,
    ):
        CardTransactionLimit.objects.filter(card=self.card).delete()
        CardTransactionLimit._create(
            card=self.card,
            tp=CardTransactionLimit.DurationChoices.DAILY,
            start_at=ir_today() - timedelta(days=100),
            total=self.new_transaction_amount,
        )

        check_card_transaction_limits(self.card, self.new_transaction_amount)

    def _create_card_level(
        self, level: int, per_trx_limit: int, daily_limit: int, monthly_limit: int, cashback_percentage: Decimal
    ) -> CardSetting:
        return CardSetting.objects.create(
            level=level,
            per_transaction_amount_limit=per_trx_limit,
            daily_transaction_amount_limit=daily_limit,
            monthly_transaction_amount_limit=monthly_limit,
            cashback_percentage=cashback_percentage,
        )

    def _create_monthly_limit(self, card: Card, total_amount: int):
        CardTransactionLimit._add_monthly_transaction(card, total_amount)

    def _create_daily_limit(self, card: Card, total_amount: int):
        CardTransactionLimit._add_daily_transaction(card, total_amount)
