from django.core.exceptions import ValidationError
from django.db import models

from exchange.accounts.models import User

from .permission import Permission


class Key(models.Model):
    key = models.CharField(max_length=1024, primary_key=True)
    owner = models.ForeignKey(to=User, on_delete=models.CASCADE)
    expiration_date = models.DateTimeField(blank=True, null=True)
    name = models.CharField(max_length=1024)
    description = models.TextField(blank=True, max_length=1000)
    ip_addresses_whitelist = models.JSONField(default=list)
    permission_bits = models.IntegerField(default=Permission.NONE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    MAX_KEYS_PER_USER = 20
    MAX_IPS_PER_KEY = 10

    def save(self, *args, **kwargs):
        if self.created_at is None and len(Key.objects.filter(owner=self.owner)) >= self.MAX_KEYS_PER_USER:
            raise ValidationError(f'users can only have {self.MAX_KEYS_PER_USER} keys')
        if len(self.ip_addresses_whitelist) > self.MAX_IPS_PER_KEY:
            raise ValidationError(f'each key can have at most {self.MAX_IPS_PER_KEY} ip whitelist')

        super().save(*args, **kwargs)

    @property
    def permissions(self) -> Permission:
        return Permission(self.permission_bits)

    @permissions.setter
    def permissions(self, value: Permission):
        if not isinstance(value, Permission):
            raise ValueError('Value must be an instance of Permission enum')
        self.permission_bits = int(value)
