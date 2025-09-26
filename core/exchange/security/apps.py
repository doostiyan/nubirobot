from django.apps import AppConfig


class SecurityConfig(AppConfig):
    name = 'exchange.security'
    verbose_name = 'امنیت'

    def ready(self):
        from .serializers import address_book, security
        from . import signals
