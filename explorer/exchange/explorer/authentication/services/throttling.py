import time

from django.core.cache import caches
from rest_framework.throttling import BaseThrottle


class APIKeyRateThrottle(BaseThrottle):
    cache = caches['redis__throttling']
    cache_format = 'throttle_%(ident)s'
    timer = time.time

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'ident': self.get_ident(request)
        }

    def get_ident(self, request):
        return request.api_key.prefix

    def get_rate(self, request):
        return request.api_key.rate

    def parse_rate(self, rate):
        """
        Given the request rate string, return a two tuple of:
        <allowed number of requests>, <period of time in seconds>
        """
        if rate is None:
            return None, None
        num, period = rate.split('/')
        num_requests = int(num)
        duration = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[period[0]]
        return num_requests, duration

    def allow_request(self, request, view):
        """
        Implement the check to see if the request should be throttled.

        On success calls `throttle_success`.
        On failure calls `throttle_failure`.
        """
        if hasattr(request, 'api_key'):
            rate = self.get_rate(request)
            self.num_requests, self.duration = self.parse_rate(rate)

            self.key = self.get_cache_key(request, view)
            if self.key is None:
                return True

            self.history = self.cache.get(self.key, [])
            self.now = self.timer()

            # Drop any requests from the history which have now passed the
            # throttle duration
            while self.history and self.history[-1] <= self.now - self.duration:
                self.history.pop()
            if len(self.history) >= self.num_requests:
                return self.throttle_failure()
            return self.throttle_success()
        return True

    def throttle_success(self):
        """
        Inserts the current request's timestamp along with the key
        into the cache.
        """
        self.history.insert(0, self.now)
        self.cache.set(self.key, self.history, self.duration)
        return True

    def throttle_failure(self):
        """
        Called when a request to the API has failed due to throttling.
        """
        return False

    def wait(self):
        """
        Returns the recommended next request time in seconds.
        """
        if self.history:
            remaining_duration = self.duration - (self.now - self.history[-1])
        else:
            remaining_duration = self.duration

        available_requests = self.num_requests - len(self.history) + 1
        if available_requests <= 0:
            return None

        return remaining_duration / float(available_requests)
