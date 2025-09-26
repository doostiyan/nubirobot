from django.apps import AppConfig


class CompetitionConfig(AppConfig):
    name = 'exchange.competition'
    verbose_name = 'مسابقات'

    def ready(self):
        from . import serializers
        from . import signals
