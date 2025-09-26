""" Price Alert App """
from django.apps import AppConfig


class PriceAlertConfig(AppConfig):
    name = 'exchange.pricealert'
    verbose_name = 'اعلان قیمت'

    def ready(self):
        from . import serializers
