""" Xchange App """
from django.apps import AppConfig


class XchangeConfig(AppConfig):
    name = 'exchange.xchange'
    verbose_name = 'صرافی'

    def ready(self):
        from . import serializers, signals
