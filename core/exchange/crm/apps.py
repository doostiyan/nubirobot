from django.apps import AppConfig


class CrmConfig(AppConfig):
    name = 'exchange.crm'
    verbose_name = 'مدیریت ارتباط با مشتری'

    def ready(self):
        from . import serializers
        from . import signals
