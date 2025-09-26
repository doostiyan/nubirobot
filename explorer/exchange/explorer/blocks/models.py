from django.db import models


class GetBlockStats(models.Model):
    network = models.ForeignKey('networkproviders.Network', on_delete=models.SET_NULL, null=True)
    latest_processed_block = models.BigIntegerField(null=True)
    latest_fetched_block = models.BigIntegerField(null=True)
    min_available_block = models.BigIntegerField(null=True)
    latest_rechecked_block_processed = models.BigIntegerField(null=True)

    def __str__(self):
        return f"{self.network.name}"

    @classmethod
    def get_block_stats_by_network_name(cls, network_name):
        return cls.objects.get(network__name__iexact=network_name)
