from django.apps import AppConfig


class PromotionsConfig(AppConfig):
    name = 'exchange.promotions'
    verbose_name = 'بسته‌های تشویقی'

    def ready(self):
        from . import serializers
        from . import signals
