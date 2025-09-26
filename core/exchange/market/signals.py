from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from exchange.accounts.models import User
from exchange.market.models import UserTradeStatus


@receiver(post_save, sender=User, dispatch_uid='market_initialize_new_user')
def market_initialize_new_user(sender, instance, created, **kwargs):
    """ Create market-related models for new users """
    if not created:
        return
    UserTradeStatus.objects.get_or_create(user=instance)
