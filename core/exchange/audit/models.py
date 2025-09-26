from decimal import Decimal

from django.db import models
from django.utils.timezone import now
from model_utils import Choices

from exchange.base.models import Currencies, Exchange
from exchange.wallet.models import WithdrawRequest


class ExternalWallet(models.Model):
    TYPES = Choices(
        (0, 'unknown', 'Unknown'),
        (1, 'binance', 'Binance'),
        (2, 'hot', 'Hot Wallet'),
        (3, 'cold', 'Cold Wallet'),
    )

    name = models.CharField(max_length=100, blank=True, unique=True)
    currency = models.IntegerField(choices=Currencies, verbose_name='رمزارز')
    tp = models.IntegerField(choices=TYPES, default=TYPES.unknown, verbose_name='نوع')
    address = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = 'External Wallet'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class ExternalWithdraw(models.Model):
    TYPES = Choices(
        (0, 'new', 'New'),
        (1, 'user_withdraw', 'UserWithdraw'),
        (2, 'unknown', 'Unknown'),
    )

    created_at = models.DateTimeField(default=now)
    tp = models.IntegerField(choices=TYPES, default=TYPES.new, verbose_name='نوع برداشت')
    user_withdraw = models.ForeignKey(WithdrawRequest, null=True, blank=True, on_delete=models.SET_NULL)

    source = models.ForeignKey(ExternalWallet, related_name='withdraws', on_delete=models.CASCADE)
    destination = models.CharField(max_length=100, blank=True, default='')
    tx_hash = models.CharField(max_length=100, blank=True, default='')
    tag = models.CharField(max_length=100, blank=True, null=True, verbose_name='تگ')
    currency = models.IntegerField(choices=Currencies, default=0, verbose_name='رمزارز')
    amount = models.DecimalField(max_digits=20, decimal_places=10, default=Decimal('0'), verbose_name='مقدار برداشت')

    class Meta:
        verbose_name = 'رکورد برداشت'
        verbose_name_plural = verbose_name
        unique_together = ['tx_hash', 'destination']
