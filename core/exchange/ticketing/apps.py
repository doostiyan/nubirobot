from django.apps import AppConfig


class TicketingConfig(AppConfig):
    name = 'exchange.ticketing'
    verbose_name = 'تیکتینگ'

    def ready(self):
        from . import signals
