from django.apps import AppConfig


class FeaturesConfig(AppConfig):
    name = 'exchange.features'

    def ready(self):
        from . import signals
