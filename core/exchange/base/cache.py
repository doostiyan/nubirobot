""" Caching Utilities """
from django.core.cache import cache
from django.db import transaction


class CacheManager:
    """ Main data cache manager """

    @classmethod
    def invalidate_user_wallets(cls, user_id):
        """ Invalidate cache for list of user wallet addresses """
        transaction.on_commit(lambda: cache.set('user_{}_wl_addr'.format(user_id), '', 100))
