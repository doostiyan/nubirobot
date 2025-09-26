from django.core.management.base import BaseCommand

from exchange.asset_backed_credit.models import Service

DATA = {
    Service.TYPES.loan: {
        Service.PROVIDERS.vency: {'interest': 23, 'options': {'periods': [1, 3, 6, 9, 12], 'provider_fee': 23}}
    }
}


class Command(BaseCommand):
    help = "Set options field for service providers"

    def handle(self, *args, **options):
        for service_type, service_type_value in DATA.items():
            for provider, provider_data in service_type_value.items():
                service = Service.objects.filter(provider=provider, tp=service_type).first()
                if not service:
                    continue
                for field, value in provider_data.items():
                    if field == 'options':
                        service.options.update(value)
                    else:
                        setattr(service, field, value)
                service.save()
