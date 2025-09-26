from django.utils.timezone import now
from ..models.provider_service_status import ProviderServiceStatus


class ProviderStatusService:

    @classmethod
    def create_provider_service_status(cls, provider, network, operation, is_active=True):
        provider_service_status = ProviderServiceStatus.objects.create(
            provider=provider,
            network=network,
            operation=operation,
            is_active=is_active
        )
        return provider_service_status

    @classmethod
    def get_provider_service_status(cls, provider, network, operation):
        try:
            return ProviderServiceStatus.objects.get(
                provider=provider,
                network=network,
                operation=operation
            )
        except ProviderServiceStatus.DoesNotExist:
            return None

    @classmethod
    def update_provider_service_status(cls, provider, network, operation, is_active):
        provider_service_status = ProviderServiceStatus.objects.get(
            provider=provider,
            network=network,
            operation=operation
        )
        provider_service_status.is_active = is_active
        provider_service_status.save()
        return provider_service_status

    @classmethod
    def deactivate_provider_service_status(cls, provider, network, operation):
        return cls.update_provider_service_status(provider, network, operation, is_active=False)

    @classmethod
    def get_all_active_provider_services(cls):
        return ProviderServiceStatus.objects.filter(is_active=True)

    @classmethod
    def get_all_provider_services(cls):
        return ProviderServiceStatus.objects.all()

    @classmethod
    def get_active_providers_by_operation(cls, network, operation):
        return ProviderServiceStatus.objects.filter(
            network=network,
            operation=operation,
            is_active=True
        ).select_related('provider')

    @staticmethod
    def update_provider_status(network, provider, operation, status):
        ProviderServiceStatus.objects.filter(
            network=network,
            provider=provider,
            operation=operation,
        ).update(last_status=status, updated_at=now())

    @staticmethod
    def get_provider_status(network, provider, operation):
        provider = ProviderServiceStatus.objects.get(
            network=network,
            provider=provider,
            operation=operation,
        )
        return provider.last_status

    @classmethod
    def get_healthy_providers_by_operation(cls, network, operation):
        return ProviderServiceStatus.objects.filter(
            network=network,
            operation=operation,
            last_status='healthy'
        ).select_related('provider')

    @classmethod
    def get_network_providers_by_operation(cls, network, operation):
        return ProviderServiceStatus.objects.filter(
            network=network,
            operation=operation,
        )
