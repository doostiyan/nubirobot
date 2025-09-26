from django.contrib.postgres.fields import ArrayField
from django.db import models

from exchange.base.calendar import ir_now
from exchange.corporate_banking.models import REFUND_STATUS


class CoBankRefund(models.Model):

    FINAL_STATUSES = {
        REFUND_STATUS.completed,
        REFUND_STATUS.invalid,
    }

    INQUIRABLE_STATUSES = {
        REFUND_STATUS.sent_to_provider,
        REFUND_STATUS.pending,
        REFUND_STATUS.unknown,
    }

    statement = models.OneToOneField(to='CoBankStatement', on_delete=models.DO_NOTHING, db_index=True)
    status = models.SmallIntegerField(choices=REFUND_STATUS, default=REFUND_STATUS.new)
    retry = models.SmallIntegerField(default=0)
    provider_response = ArrayField(models.JSONField(default=dict), null=True, blank=True, default=list)
    provider_refund_id = models.CharField(max_length=100, null=True, blank=True)

    updated_at = models.DateTimeField(default=ir_now)
    created_at = models.DateTimeField(default=ir_now)

    class Meta:
        verbose_name = 'درخواست‌های بازپرداخت'
        verbose_name_plural = verbose_name

        indexes = [
            models.Index(fields=['status', 'created_at'], name='refund_status_created_idx'),
        ]

    def save(self, *args, update_fields=None, force_insert=False, **kwargs):
        self.updated_at = ir_now()
        if not force_insert and self.pk is not None:
            update_fields = (*(update_fields if update_fields else []), 'updated_at')
        super().save(*args, update_fields=update_fields, force_insert=force_insert, **kwargs)
