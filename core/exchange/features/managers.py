from django.db import models


class QueueItemManager(models.Manager):
    def dequeue(self, feature, count=10):
        return super().get_queryset().filter(
            feature=feature,
            status__in=[0, 2],
        ).order_by('created_at')[:count]
