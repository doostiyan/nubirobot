from django.core.exceptions import ValidationError
from django.db import models

from . import Network, Operation, Provider


class NetworkDefaultProvider(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    operation = models.CharField(max_length=32, choices=Operation.choices)
    network = models.ForeignKey(Network, on_delete=models.CASCADE)
    set_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['operation', 'network']

    def __str__(self):
        return f"{self.provider.name}-{self.operation}-{self.network.name}"

    def save(self, *args, **kwargs):
        # Check if the provider supports the specified operation
        if self.operation not in self.provider.supported_operations:
            raise ValidationError(
                {"operation": f"The selected provider does not support the operation: {self.operation}"})
        super().save(*args, **kwargs)
