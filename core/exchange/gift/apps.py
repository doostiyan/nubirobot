from django.apps import AppConfig


class GiftConfig(AppConfig):
    name = 'exchange.gift'
    verbose_name = 'کارت هدیه'

    def ready(self):
        from . import serializers
