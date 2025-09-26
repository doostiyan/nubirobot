from django.db import models

from exchange.asset_backed_credit.models import Service
from exchange.base.calendar import ir_now


class Store(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE)

    title = models.CharField(max_length=255)
    url = models.URLField(max_length=500)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
