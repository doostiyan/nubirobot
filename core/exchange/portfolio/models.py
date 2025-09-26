from django.db import models
from django.utils.timezone import now

from exchange.accounts.models import User
from exchange.base.constants import ZERO
from exchange.portfolio.constants import BALANCE_SUM_MAX_DIGITS


class UserTotalDailyProfit(models.Model):
    """
        represent total balance and daily profit of each user
    """

    # General Fields
    created_at = models.DateTimeField(default=now)
    report_date = models.DateField(null=False)

    user = models.ForeignKey(User, related_name='daily_profits', on_delete=models.CASCADE)

    # Daily balance field
    total_balance = models.DecimalField(max_digits=BALANCE_SUM_MAX_DIGITS, decimal_places=10)
    profit = models.DecimalField(max_digits=BALANCE_SUM_MAX_DIGITS, decimal_places=10)
    profit_percentage = models.DecimalField(max_digits=25, decimal_places=10)
    total_withdraw = models.DecimalField(max_digits=BALANCE_SUM_MAX_DIGITS, decimal_places=10, default=ZERO)
    total_deposit = models.DecimalField(max_digits=BALANCE_SUM_MAX_DIGITS, decimal_places=10, default=ZERO)

    class Meta:
        verbose_name = 'سود و زیان روزانه'
        verbose_name_plural = verbose_name
        unique_together = ['report_date', 'user']

    @classmethod
    def get_user_profits(cls, from_date, to_date, user=None):
        if user:
            user_profits = cls.objects.filter(user=user, report_date__gte=from_date, report_date__lte=to_date) \
                .order_by('created_at')
        else:
            user_profits = cls.objects.filter(report_date__gte=from_date, report_date__lte=to_date) \
                .order_by('created_at')
        return user_profits


class UserTotalMonthlyProfit(models.Model):
    """
        represent total balance of each user per month
    """

    # General Fields
    created_at = models.DateTimeField(default=now)
    report_date = models.DateField(null=False)

    user = models.ForeignKey(User, related_name="+", on_delete=models.CASCADE)

    # Monthly balance field
    total_balance = models.DecimalField(max_digits=BALANCE_SUM_MAX_DIGITS, decimal_places=10)
    first_day_total_balance = models.DecimalField(max_digits=BALANCE_SUM_MAX_DIGITS, decimal_places=10, default=ZERO)
    total_profit = models.DecimalField(max_digits=BALANCE_SUM_MAX_DIGITS, decimal_places=10)
    total_profit_percentage = models.DecimalField(max_digits=25, decimal_places=10)
    total_withdraw = models.DecimalField(max_digits=BALANCE_SUM_MAX_DIGITS, decimal_places=10, default=ZERO)
    total_deposit = models.DecimalField(max_digits=BALANCE_SUM_MAX_DIGITS, decimal_places=10, default=ZERO)

    class Meta:
        verbose_name = 'سود و زیان ماهانه'
        verbose_name_plural = verbose_name
        unique_together = ['report_date', 'user']

    @classmethod
    def get_user_profits(cls, year, month, user=None):
        if user:
            user_profits = cls.objects.filter(user=user, report_date__year=year, report_date__month=month) \
                .order_by('created_at')
        else:
            user_profits = cls.objects.filter(report_date__year=year, report_date__month=month) \
                .order_by('created_at')
        return user_profits
