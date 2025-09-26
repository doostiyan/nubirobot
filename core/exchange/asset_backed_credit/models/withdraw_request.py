import uuid

from django.db import models

from exchange.asset_backed_credit.models import Service


class ProviderWithdrawRequestLog(models.Model):
    STATUS_CREATED = 0
    STATUS_DONE = 1
    STATUS_CHOICES = (
        (STATUS_CREATED, 'Created'),
        (STATUS_DONE, 'Done'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    provider = models.SmallIntegerField(choices=Service.PROVIDERS)
    amount = models.BigIntegerField()
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=STATUS_CREATED)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True)
    external_id = models.IntegerField(null=True, blank=True)
