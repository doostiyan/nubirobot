from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from . import Network, Operation
from .url import URL


class Provider(models.Model):
    name = models.CharField(max_length=100, unique=True)
    network = models.ForeignKey(Network, on_delete=models.CASCADE)
    support_batch = models.BooleanField(default=False)
    batch_block_limit = models.PositiveSmallIntegerField(default=1)
    supported_operations = ArrayField(models.CharField(max_length=32, choices=Operation.choices))
    default_url = models.ForeignKey('URL', on_delete=models.CASCADE, null=True)
    urls = models.ManyToManyField('URL', related_name='providers')
    explorer_interface = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.support_batch and self.batch_block_limit > 1:
            raise ValidationError({'batch_block_limit': _('can not be more than 1')})
        super().save(*args, **kwargs)
