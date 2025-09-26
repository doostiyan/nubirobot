from django.db import models
from django.db.models import IntegerChoices

from exchange.asset_backed_credit.models import Service, SettlementTransaction
from exchange.base.calendar import ir_now
from exchange.base.storages import get_private_s3_storage


class Recon(models.Model):
    class Status(IntegerChoices):
        INITIATED = 0
        FILE_TRANSFERRED = 10
        EVALUATED = 20
        PROCESSED = 30
        NO_FILE_EXISTED = 40
        RECON_ERROR = 50

    service = models.ForeignKey(Service, on_delete=models.CASCADE, verbose_name='سرویس‌دهنده')

    status = models.IntegerField(choices=Status.choices, default=Status.INITIATED, verbose_name='وضعیت')
    recon_date = models.DateTimeField(verbose_name='تاریخ مغایرت')
    created_at = models.DateTimeField(default=ir_now, verbose_name='تاریخ ایجاد')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='تاریخ بسته شدن')

    file = models.FileField(upload_to='debit_recon', storage=get_private_s3_storage)


class SettlementRecon(models.Model):
    class Status(IntegerChoices):
        NEW = 0
        SUCCESS = 1
        INVALID_AMOUNT = 2
        INVALID_STATUS = 3
        NOT_FOUND = 4

    recon = models.ForeignKey(Recon, on_delete=models.CASCADE, verbose_name='مغایرت‌گیری مربوطه', null=True, blank=True)
    settlement = models.OneToOneField(
        SettlementTransaction, on_delete=models.CASCADE, verbose_name='تراکنش تسویه', null=True, blank=True
    )
    status = models.IntegerField(choices=Status.choices, default=Status.NEW, verbose_name='وضعیت')
    description = models.CharField(max_length=255, blank=True, null=True, verbose_name='توضیحات')
    extra_info = models.JSONField(default=dict, null=True, blank=True)
