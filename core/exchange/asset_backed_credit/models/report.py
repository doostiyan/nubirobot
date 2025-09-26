from django.db import models
from django.db.models import UniqueConstraint

from exchange.asset_backed_credit.models import Service
from exchange.base.storages import get_private_s3_storage


class CreditReport(models.Model):
    class Status(models.IntegerChoices):
        CREATED = 0
        COMPLETED = 2

    class Type(models.IntegerChoices):
        ALL = 0
        LOCK = 1
        UNLOCK = 2
        SETTLEMENT = 3
        SETTLEMENT_MISMATCH = 4

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.IntegerField(choices=Status.choices, default=Status.CREATED)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    type = models.IntegerField(choices=Type.choices, default=Type.ALL)


class ReportAttachment(models.Model):
    class AttachmentType(models.IntegerChoices):
        LOCK = 1
        UNLOCK = 2
        SETTLEMENT = 3
        SETTLEMENT_MISMATCH = 4

    report = models.ForeignKey(CreditReport, on_delete=models.CASCADE, related_name='attachments')
    attachment_type = models.IntegerField(choices=AttachmentType.choices)
    file = models.FileField(upload_to='abc_report', storage=get_private_s3_storage)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            UniqueConstraint(
                fields=('report', 'attachment_type'),
                name='unique_per_report_attachment_type',
            ),
        )
