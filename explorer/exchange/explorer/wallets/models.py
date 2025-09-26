from django.db import models


# Create your models here.

class Clients(models.TextChoices):
    PUBLIC = 'public'
    CORE = 'core'
    HOT_COLD = 'hot_cold'
    ADMIN = 'admin'
    WALLET_MONITORING = 'wallet_monitoring'


class DepositAddress(models.Model):
    network = models.ForeignKey('networkproviders.Network', on_delete=models.SET_NULL, null=True)
    address = models.CharField(max_length=255, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('network', 'address')

    def __str__(self):
        return f"{self.address} ({self.network.symbol})"
