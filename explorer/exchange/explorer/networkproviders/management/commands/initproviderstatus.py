from django.core.management.base import BaseCommand
from exchange.explorer.networkproviders.models import Provider, Network, Operation, ProviderServiceStatus


class Command(BaseCommand):
    help = "Initialize provider service statuses"

    def handle(self, *args, **kwargs):
        providers = Provider.objects.all()

        for provider in providers:
            network = provider.network
            for operation in provider.supported_operations:
                obj, created = ProviderServiceStatus.objects.get_or_create(
                    provider=provider,
                    network=network,
                    operation=operation,
                    defaults={
                        'is_active': True,
                        'last_status': 'healthy',
                    }
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Added status for {provider.name} - {operation}"))
                else:
                    self.stdout.write(self.style.WARNING(f"Status already exists for {provider.name} - {operation}"))
