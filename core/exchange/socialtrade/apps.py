from django.apps import AppConfig


class SocialTradeConfig(AppConfig):
    name = 'exchange.socialtrade'
    verbose_name = 'سوشال ترید'

    def ready(self):
        from . import serializers
        from . import signals
