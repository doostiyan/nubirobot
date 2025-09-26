import binascii
import os
from datetime import timedelta

from django.db import models
from django.utils.timezone import now


class FataAPICallLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ip = models.CharField(max_length=16)
    inquiry_type = models.CharField(null=True, blank=True, editable=False, max_length=40)
    inquiry_value = models.CharField(null=True, blank=True, editable=False, max_length=250)
    inquiry_result = models.BooleanField(null=True, blank=True)


def generate_key():
    return binascii.hexlify(os.urandom(30)).decode()


class FataLoginToken(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    key = models.CharField(max_length=60, primary_key=True, editable=False, default=generate_key)

    @classmethod
    def is_token_valid(cls, key) -> bool:
        return cls.objects.filter(key=key, is_used=False, created_at__lt=now() + timedelta(days=1)).exists()
