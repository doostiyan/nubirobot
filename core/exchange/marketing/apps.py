from django.apps import AppConfig


class MarketingConfig(AppConfig):
    name = 'exchange.marketing'
    verbose_name = 'مارکتینگ'


    def ready(self):
        from exchange.marketing.api import serializers
