from django.db import models

from . import Network, Operation, Provider

healthy_status = [('healthy', 'Healthy'), ('unhealthy', 'Unhealthy')]


class ProviderServiceStatus(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    network = models.ForeignKey(Network, on_delete=models.CASCADE)
    operation = models.CharField(max_length=32, choices=Operation.choices)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_status = models.CharField(max_length=50, choices=healthy_status, blank=True, null=True)

    class Meta:
        unique_together = ('provider', 'network', 'operation')
