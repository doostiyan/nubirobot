from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.test import TestCase

from exchange.asset_backed_credit.models import CardSetting, CardTransactionFeeSetting, CardTransactionLimit
from exchange.base.calendar import get_jalali_first_and_last_of_jalali_month, ir_now, ir_today
from tests.asset_backed_credit.helper import ABCMixins


class CardTransactionLimitTestCase(TestCase, ABCMixins):
    def setUp(self):
        self.card = self.create_card('6037731012345678', user_service=self.create_user_service())
        self.amount = 10_1200_11_009

    def test_create_limit_success(self):
        previous_limit_count = CardTransactionLimit.objects.count()

        limit = CardTransactionLimit._create(
            card=self.card,
            tp=CardTransactionLimit.DurationChoices.DAILY,
            total=self.amount,
            start_at=ir_today(),
        )

        assert limit
        assert previous_limit_count + 1 == CardTransactionLimit.objects.count()
        assert CardTransactionLimit.objects.get(
            card=self.card,
            tp=CardTransactionLimit.DurationChoices.DAILY,
            total=self.amount,
            start_at=ir_today(),
        )

    def test_create_limit_when_limit_with_exact_time_and_card_exists(self):
        previous_limit_count = CardTransactionLimit.objects.count()
        CardTransactionLimit._create(
            card=self.card,
            tp=CardTransactionLimit.DurationChoices.DAILY,
            total=self.amount,
            start_at=ir_today(),
        )

        with pytest.raises(IntegrityError):
            CardTransactionLimit._create(
                card=self.card,
                tp=CardTransactionLimit.DurationChoices.DAILY,
                total=self.amount,
                start_at=ir_today(),
            )

        assert previous_limit_count + 1 == CardTransactionLimit.objects.count()

    def test_add_daily_transaction_adds_limit_record_for_today_with_specified_amount(self):
        previous_limit_count = CardTransactionLimit.objects.count()

        CardTransactionLimit._add_daily_transaction(card=self.card, amount=self.amount)

        assert previous_limit_count + 1 == CardTransactionLimit.objects.count()
        limit = CardTransactionLimit.objects.filter(
            card=self.card,
            tp=CardTransactionLimit.DurationChoices.DAILY,
        ).first()
        assert limit
        assert limit.total == self.amount
        assert limit.start_at == ir_today()

    def test_call_add_daily_transaction_multiple_times_then_add_to_existing_daily_record_of_card(self):
        previous_limit_count = CardTransactionLimit.objects.count()

        CardTransactionLimit._add_daily_transaction(card=self.card, amount=self.amount)
        CardTransactionLimit._add_daily_transaction(card=self.card, amount=self.amount)
        CardTransactionLimit._add_daily_transaction(card=self.card, amount=self.amount)
        CardTransactionLimit._add_daily_transaction(card=self.card, amount=self.amount)
        CardTransactionLimit._add_daily_transaction(card=self.card, amount=self.amount)

        assert previous_limit_count + 1 == CardTransactionLimit.objects.count()

        limit = CardTransactionLimit.objects.get(
            card=self.card, tp=CardTransactionLimit.DurationChoices.DAILY, start_at=ir_today()
        )
        assert limit
        assert limit.total == self.amount * 5

    def test_add_monthly_transaction_adds_limit_in_current_jalali_month_with_specified_amount(self):
        previous_limit_count = CardTransactionLimit.objects.count()

        CardTransactionLimit._add_monthly_transaction(self.card, self.amount)

        assert previous_limit_count + 1 == CardTransactionLimit.objects.count()
        month_start, month_end = get_jalali_first_and_last_of_jalali_month(ir_now())
        month_start = month_start.togregorian()
        limit = CardTransactionLimit.objects.filter(
            card=self.card,
            tp=CardTransactionLimit.DurationChoices.MONTHLY,
        ).first()
        assert limit
        assert limit.start_at == month_start

    def test_call_add_monthly_transactions_multiple_times_adds_to_existing_monthly_record_of_card(self):
        previous_limit_count = CardTransactionLimit.objects.count()

        CardTransactionLimit._add_monthly_transaction(self.card, self.amount)
        CardTransactionLimit._add_monthly_transaction(self.card, self.amount)
        CardTransactionLimit._add_monthly_transaction(self.card, self.amount)
        CardTransactionLimit._add_monthly_transaction(self.card, self.amount)

        assert previous_limit_count + 1 == CardTransactionLimit.objects.count()
        month_start, _ = get_jalali_first_and_last_of_jalali_month(ir_now())
        limit = CardTransactionLimit.objects.filter(
            card=self.card,
            tp=CardTransactionLimit.DurationChoices.MONTHLY,
            start_at=month_start.togregorian(),
        ).first()
        assert limit
        assert limit.total == self.amount * 4

    def test_add_card_transaction_adds_both_daily_and_monthly_limit(self):
        previous_limit_count = CardTransactionLimit.objects.count()

        CardTransactionLimit.add_card_transaction(self.card, self.amount)

        assert previous_limit_count + 2 == CardTransactionLimit.objects.count()
        # assert daily
        daily_limit = CardTransactionLimit.objects.filter(
            card=self.card,
            tp=CardTransactionLimit.DurationChoices.DAILY,
        ).first()
        assert daily_limit
        assert daily_limit.total == self.amount
        assert daily_limit.start_at == ir_today()
        # assert monthly
        month_start, _ = get_jalali_first_and_last_of_jalali_month(ir_now())
        month_start = month_start.togregorian()
        monthly_limit = CardTransactionLimit.objects.filter(
            card=self.card,
            tp=CardTransactionLimit.DurationChoices.MONTHLY,
        ).first()
        assert monthly_limit
        assert monthly_limit.start_at == month_start

    def test_call_add_card_transaction_multiple_times_adds_one_daily_and_monthly_record_with_sum_of_all_calls(self):
        previous_limit_count = CardTransactionLimit.objects.count()

        CardTransactionLimit.add_card_transaction(self.card, self.amount)
        CardTransactionLimit.add_card_transaction(self.card, self.amount)
        CardTransactionLimit.add_card_transaction(self.card, self.amount)

        assert previous_limit_count + 2 == CardTransactionLimit.objects.count()
        daily_limit = CardTransactionLimit.objects.filter(
            card=self.card,
            tp=CardTransactionLimit.DurationChoices.DAILY,
        ).first()
        assert daily_limit
        assert daily_limit.total == self.amount * 3
        monthly_limit = CardTransactionLimit.objects.filter(
            card=self.card,
            tp=CardTransactionLimit.DurationChoices.MONTHLY,
        ).first()
        assert monthly_limit
        assert monthly_limit.total == self.amount * 3

    def test_add_daily_transaction_when_old_daily_limit_exists_then_existing_daily_limit_is_updated(self):
        CardTransactionLimit._add_daily_transaction(card=self.card, amount=self.amount)
        existing_old_daily_limit = CardTransactionLimit.objects.filter(
            tp=CardTransactionLimit.DurationChoices.DAILY, total=self.amount
        ).last()
        existing_old_daily_limit.start_at = ir_today() - timedelta(days=10)
        existing_old_daily_limit.save()
        previous_limit_count = CardTransactionLimit.objects.count()

        today_transaction_amount = self.amount - 10
        CardTransactionLimit._add_daily_transaction(self.card, today_transaction_amount)

        existing_old_daily_limit.refresh_from_db()
        assert previous_limit_count == CardTransactionLimit.objects.count()
        assert existing_old_daily_limit.total == today_transaction_amount
        assert existing_old_daily_limit.tp == CardTransactionLimit.DurationChoices.DAILY
        assert existing_old_daily_limit.start_at == ir_today()

    def test_add_monthly_transaction_when_old_monthly_transaction_exists_then_existing_monthly_limit_is_updated(self):
        CardTransactionLimit._add_monthly_transaction(card=self.card, amount=self.amount)
        existing_old_monthly_limit = CardTransactionLimit.objects.filter(
            tp=CardTransactionLimit.DurationChoices.MONTHLY, total=self.amount
        ).last()
        existing_old_monthly_limit.start_at = existing_old_monthly_limit.start_at - timedelta(days=60)
        existing_old_monthly_limit.save()
        previous_limit_count = CardTransactionLimit.objects.count()

        new_transaction_amount = self.amount - 10
        CardTransactionLimit._add_monthly_transaction(self.card, new_transaction_amount)

        existing_old_monthly_limit.refresh_from_db()
        assert previous_limit_count == CardTransactionLimit.objects.count()
        assert existing_old_monthly_limit.total == new_transaction_amount
        assert existing_old_monthly_limit.tp == CardTransactionLimit.DurationChoices.MONTHLY
        assert (
            existing_old_monthly_limit.start_at
            == get_jalali_first_and_last_of_jalali_month(ir_today())[0].togregorian()
        )

    def test_add_new_transaction_multiple_times_when_user_has_old_monthly_and_daily_records_then_both_records_are_updated(
        self,
    ):
        CardTransactionLimit._add_monthly_transaction(card=self.card, amount=self.amount)
        existing_old_monthly_limit = CardTransactionLimit.objects.filter(
            tp=CardTransactionLimit.DurationChoices.MONTHLY, total=self.amount
        ).last()
        existing_old_monthly_limit.start_at = existing_old_monthly_limit.start_at - timedelta(days=60)
        existing_old_monthly_limit.save()

        CardTransactionLimit._add_daily_transaction(card=self.card, amount=self.amount)
        existing_old_daily_limit = CardTransactionLimit.objects.filter(
            tp=CardTransactionLimit.DurationChoices.DAILY, total=self.amount
        ).last()
        existing_old_daily_limit.start_at = ir_today() - timedelta(days=10)
        existing_old_daily_limit.save()
        previous_limit_count = CardTransactionLimit.objects.count()

        new_transaction_amount = 11
        CardTransactionLimit.add_card_transaction(self.card, new_transaction_amount)
        CardTransactionLimit.add_card_transaction(self.card, new_transaction_amount)
        CardTransactionLimit.add_card_transaction(self.card, new_transaction_amount)
        CardTransactionLimit.add_card_transaction(self.card, new_transaction_amount)
        CardTransactionLimit.add_card_transaction(self.card, new_transaction_amount)

        existing_old_monthly_limit.refresh_from_db()
        assert previous_limit_count == CardTransactionLimit.objects.count()
        assert existing_old_monthly_limit.total == new_transaction_amount * 5
        assert existing_old_monthly_limit.tp == CardTransactionLimit.DurationChoices.MONTHLY
        assert (
            existing_old_monthly_limit.start_at
            == get_jalali_first_and_last_of_jalali_month(ir_today())[0].togregorian()
        )
        existing_old_daily_limit.refresh_from_db()
        assert previous_limit_count == CardTransactionLimit.objects.count()
        assert existing_old_daily_limit.total == new_transaction_amount * 5
        assert existing_old_daily_limit.tp == CardTransactionLimit.DurationChoices.DAILY
        assert existing_old_daily_limit.start_at == ir_today()


class CardTransactionFeeSettingTestCase(TestCase, ABCMixins):
    def setUp(self):
        self.card_level_setting = CardSetting.objects.create(
            level=1,
            per_transaction_amount_limit=20_000_000,
            daily_transaction_amount_limit=100_000_000,
            monthly_transaction_amount_limit=1_000_000_000,
            cashback_percentage=0,
        )
        self.card_fee_setting_1 = CardTransactionFeeSetting.objects.create(
            level=self.card_level_setting,
            min_amount=100_0,
            max_amount=1_000_000_0,
            fee_percentage=1,
        )
        self.card_fee_setting_2 = CardTransactionFeeSetting.objects.create(
            level=self.card_level_setting,
            min_amount=1_000_000_0,
            max_amount=10_000_000_0,
            fee_percentage=0.5,
        )
        self.card = self.create_card(
            '6037731012345678', user_service=self.create_user_service(), setting=self.card_level_setting
        )

    def test_get_by_level_success(self):
        with pytest.raises(CardTransactionFeeSetting.DoesNotExist):
            CardTransactionFeeSetting.get_by_level(level=self.card_level_setting, amount=Decimal(99_9))

        fee_setting = CardTransactionFeeSetting.get_by_level(level=self.card_level_setting, amount=Decimal(100_0))
        assert fee_setting == self.card_fee_setting_1

        fee_setting = CardTransactionFeeSetting.get_by_level(
            level=self.card_level_setting, amount=Decimal(1_000_000_0) - 1
        )
        assert fee_setting == self.card_fee_setting_1

        fee_setting = CardTransactionFeeSetting.get_by_level(level=self.card_level_setting, amount=Decimal(1_000_000_0))
        assert fee_setting == self.card_fee_setting_2

        fee_setting = CardTransactionFeeSetting.get_by_level(
            level=self.card_level_setting, amount=Decimal(10_000_000_0) - 1
        )
        assert fee_setting == self.card_fee_setting_2

        with pytest.raises(CardTransactionFeeSetting.DoesNotExist):
            CardTransactionFeeSetting.get_by_level(level=self.card_level_setting, amount=Decimal(10_000_000_0))

    def test_get_fee_amount_success(self):
        with pytest.raises(CardTransactionFeeSetting.DoesNotExist):
            CardTransactionFeeSetting.get_fee_amount(level=self.card_level_setting, amount=Decimal(99_9))

        fee_amount = CardTransactionFeeSetting.get_fee_amount(level=self.card_level_setting, amount=Decimal(100_0))
        assert fee_amount == 10

        fee_amount = CardTransactionFeeSetting.get_fee_amount(
            level=self.card_level_setting, amount=Decimal(1_000_000_0)
        )
        assert fee_amount == 5_000_0
