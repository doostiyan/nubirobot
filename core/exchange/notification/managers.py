from django.db import models
from django.db.models.signals import post_save, pre_save


class BulkCreateWithSignalManager(models.Manager):
    """
    Since pre-save and post-save signals are not called during bulk_create,
    we make this Manager instead to handle calling pre-save and post-save signals
    before and after creating the objects.
    Examples of usage: exchange/socialtrade/tasks.py where we need to bulk_create UserSms and Notification objects
    """

    def bulk_create(self, items, **kwargs):
        for item in items:
            pre_save.send(type(item), instance=item)
        super().bulk_create(items, **kwargs)
        for item in items:
            post_save.send(type(item), instance=item, created=True)
