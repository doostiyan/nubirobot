""" Redeem App """
from django.apps import AppConfig


class RedeemConfig(AppConfig):
    name = 'exchange.redeem'
    verbose_name = 'بازخرید'

    def ready(self):
        from exchange.redeem import serializers
