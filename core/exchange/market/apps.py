from django.apps import AppConfig


class MarketConfig(AppConfig):
    name = 'exchange.market'
    verbose_name = 'Market App'

    def ready(self):
        from . import serializers
        from . import signals
