from django.apps import AppConfig


class NotificationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'exchange.notification'
    verbose_name = 'Notification App'

    def ready(self):
        from . import consumers
        from .api import serializers
