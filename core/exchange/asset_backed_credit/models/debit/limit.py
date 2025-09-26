from datetime import datetime
from decimal import Decimal

from cachetools.func import ttl_cache
from django.db import models, transaction
from django.db.models import F

from exchange.base.calendar import get_jalali_first_and_last_of_jalali_month, ir_now, ir_today


class CardTransactionLimit(models.Model):
    class DurationChoices(models.IntegerChoices):
        DAILY = 1, 'daily'
        MONTHLY = 2, 'monthly'

    card = models.ForeignKey(to='Card', on_delete=models.CASCADE, db_index=True)

    tp = models.PositiveSmallIntegerField(choices=DurationChoices.choices)
    total = models.BigIntegerField(help_text='مجموع ریالی')
    start_at = models.DateField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'tp',
                    'card',
                ],
                name='abc_%(class)s_transaction_card_and_type_unique_constraint',
            )
        ]

    @classmethod
    def get_card_daily_total_amount(cls, card: 'Card') -> int:
        try:
            limit = cls.objects.get(card=card, tp=cls.DurationChoices.DAILY)
            if limit.start_at == ir_today():
                return limit.total
            return 0
        except cls.DoesNotExist:
            return 0

    @classmethod
    def get_card_monthly_total_amount(cls, card: 'Card') -> int:
        try:
            current_month_start = get_jalali_first_and_last_of_jalali_month(ir_now())[0].togregorian()
            limit = cls.objects.get(
                card=card,
                tp=cls.DurationChoices.MONTHLY,
            )
            if limit.start_at == current_month_start:
                return limit.total

            return 0
        except cls.DoesNotExist:
            return 0

    @classmethod
    @transaction.atomic
    def add_card_transaction(cls, card: 'Card', amount: int):
        cls._add_monthly_transaction(card, amount)
        cls._add_daily_transaction(card, amount)

    @classmethod
    def _add_monthly_transaction(cls, card: 'Card', amount: int):
        current_month_start = get_jalali_first_and_last_of_jalali_month(ir_now())[0].togregorian()
        try:
            monthly_limit = cls.objects.select_for_update(no_key=True).get(card=card, tp=cls.DurationChoices.MONTHLY)
            if monthly_limit.start_at != current_month_start:
                monthly_limit.start_at = current_month_start
                monthly_limit.total = amount

            else:
                monthly_limit.total = F('total') + amount

            monthly_limit.save()
        except cls.DoesNotExist:
            cls._create(
                card=card,
                tp=cls.DurationChoices.MONTHLY,
                start_at=current_month_start,
                total=amount,
            )

    @classmethod
    def _add_daily_transaction(cls, card: 'Card', amount: int):
        try:
            daily_limit = cls.objects.select_for_update(no_key=True).get(card=card, tp=cls.DurationChoices.DAILY)
            if daily_limit.start_at != ir_today():
                daily_limit.start_at = ir_today()
                daily_limit.total = amount
            else:
                daily_limit.total = F('total') + amount

            daily_limit.save()
        except cls.DoesNotExist:
            cls._create(
                card=card,
                tp=cls.DurationChoices.DAILY,
                start_at=ir_today(),
                total=amount,
            )

    @classmethod
    @transaction.atomic
    def _create(cls, card: 'Card', tp: int, total: int, start_at: datetime) -> 'CardTransactionLimit':
        return cls.objects.create(
            card=card,
            tp=tp,
            total=total,
            start_at=start_at,
        )


class CardSetting(models.Model):
    DEFAULT_CARD_LEVEL = 1

    level = models.PositiveSmallIntegerField(unique=True, help_text='سطح کارت')
    label = models.CharField(blank=True, null=True, max_length=200)

    colors = models.JSONField(blank=True, null=True)
    per_transaction_amount_limit = models.BigIntegerField(help_text='محدودیت هر تراکنش')
    daily_transaction_amount_limit = models.BigIntegerField(help_text='محدودیت مجموع تراکنش های روزانه')
    monthly_transaction_amount_limit = models.BigIntegerField(help_text='محدودیت مجموع تراکنش های ماهانه')
    cashback_percentage = models.DecimalField(decimal_places=5, max_digits=10, help_text='درصد کش بک')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CardTransactionFeeSetting(models.Model):
    level = models.ForeignKey(to=CardSetting, related_name='+', on_delete=models.CASCADE, db_index=True)

    min_amount = models.BigIntegerField(help_text='شروع بازه مبلغ تراکنش')
    max_amount = models.BigIntegerField(help_text='پایان بازه مبلغ تراکنش')
    fee_percentage = models.DecimalField(decimal_places=5, max_digits=10, help_text='درصد کارمزد مبلغ تراکنش')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'level',
                    'min_amount',
                    'max_amount',
                ],
                name='abc_%(class)s_level_and_amount_range_unique_constraint',
            )
        ]

    @classmethod
    @ttl_cache(ttl=1 * 60 * 60)
    def get_by_level(cls, level: CardSetting, amount: Decimal) -> 'CardTransactionFeeSetting':
        return cls.objects.get(level=level, min_amount__lte=amount, max_amount__gt=amount)

    @classmethod
    def get_fee_amount(cls, level: CardSetting, amount: Decimal) -> Decimal:
        fee_setting = cls.get_by_level(level=level, amount=amount)
        return (fee_setting.fee_percentage * amount) / 100
