from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import JSONField
from model_utils import Choices


class APICallLog(models.Model):
    STATUS = Choices(
        (0, 'success', 'success'),
        (1, 'failure', 'failure')
    )
    PROVIDER = Choices(
        (0, 'alpha', 'alpha'),
        (1, 'toman', 'toman'),
        (2, 'jibit', 'jibit'),
    )
    SERVICE = Choices((0, 'liveness', 'liveness'), (1, 'cobank_statements', 'cobank_statements'))

    created_at = models.DateTimeField(verbose_name='زمان ایجاد', auto_now_add=True, db_index=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
    object_id = models.PositiveIntegerField(null=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    retry = models.SmallIntegerField(verbose_name='تکرار فراخوانی', default=0)
    api_url = models.CharField(verbose_name='آدرس فراخوانی سرویس خارجی', max_length=100)
    request_details = JSONField(verbose_name='جزئیات درخواست')
    response_details = JSONField(verbose_name='جزئیات پاسخ')
    status = models.SmallIntegerField(verbose_name='وضعیت', choices=STATUS)
    status_code = models.SmallIntegerField(verbose_name='کد وضعیت')
    provider = models.SmallIntegerField(verbose_name='ارائه دهنده', choices=PROVIDER)
    service = models.SmallIntegerField(verbose_name='سرویس', choices=SERVICE)

    class Meta:
        verbose_name = 'لاگ نتایج صدا زدن سرویس‌های خارجی'
        indexes = [models.Index(fields=['content_type', 'object_id'])]
