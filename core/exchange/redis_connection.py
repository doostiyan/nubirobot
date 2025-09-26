from django_redis.client.default import DefaultClient


class RedisClient(DefaultClient):
    """
    Custom Redis Client class to override reading sequences from master/slave servers
    """

    def get(self, key, default=None, version=None, client=None):
        """
        Retrieve a value from the cache.

        Returns decoded value if key is found, the default if not.
        Use Master server if key is a master key
        """
        # Use master cache client for specific keys
        #  The condition is hardcoded to avoid extra checks and loops.
        #  If there are more than one pattern it should be modified.
        if str(key).endswith('_recent_order'):
            client = self.get_client(write=True)

        return super().get(key, default=default, version=version, client=client)
