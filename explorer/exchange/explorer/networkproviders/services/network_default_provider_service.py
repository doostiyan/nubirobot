from django.db.models import Q
from django.db import transaction

from exchange.blockchain.service_based.logging import logger
from . import NetworkService
from ..dtos.provider import ProviderDataCreator
from ..models import NetworkDefaultProvider, Operation
from ...utils.cache import CacheUtils, redis_lock

class NetworkDefaultProviderService:

    @classmethod
    def get_all_default_providers(cls):
        return NetworkDefaultProvider.objects.all()

    @classmethod
    def get_default_provider_by_network_name_and_operation(cls, network_name, operation):
        try:
            return NetworkDefaultProvider.objects.get(network__name__iexact=network_name, operation=operation)
        except NetworkDefaultProvider.DoesNotExist:
            return None

    @classmethod
    def get_default_providers_by_network_name_filter_operation(cls, network_name, operation):
        query = Q(network__name__iexact=network_name)
        if operation:
            query &= Q(operation=operation)
        return NetworkDefaultProvider.objects.filter(query)

    @classmethod
    def load_default_provider_data(cls, network, operation):
        cache_key = f'{network}_{operation}'
        provider_data = CacheUtils.read_from_external_cache(cache_key)
        if not provider_data:
            provider_data = cls.load_default_provider_data2redis(network, operation)
        return provider_data

    @classmethod
    def load_default_provider_data2redis(cls, network, operation):
        # If BLOCK_TXS depends on BLOCK_HEAD → handle both explicitly
        if operation == Operation.BLOCK_TXS:
            # First update BLOCK_HEAD under its own lock
            cls._load_provider_data_with_lock(network, Operation.BLOCK_HEAD)

        # Then handle the main operation
        cls._load_provider_data_with_lock(network, operation)

    @classmethod
    def _load_provider_data_with_lock(cls, network, operation):
        lock_key = f"lock:network_provider:{network}-{operation}"

        with redis_lock(lock_key, timeout=10):
            cache_key = f'{network}_{operation}'

            network_default_provider = NetworkDefaultProviderService.get_default_provider_by_network_name_and_operation(
                network, operation
            )

            if network_default_provider:
                provider = network_default_provider.provider

                provider_name = provider.name
                interface_name = provider.explorer_interface
                base_url = provider.default_url.url if provider.default_url else None

                provider_data = ProviderDataCreator.get_dto(
                    provider_name=provider_name,
                    interface_name=interface_name,
                    base_url=base_url
                )
                CacheUtils.write_to_external_cache(cache_key, provider_data)
                return provider_data

    @classmethod
    def update_or_create_default_provider(cls, provider_id, operation, network_name):
        try:
            with transaction.atomic():  # Ensure DB is atomic
                network = NetworkService.get_network_by_name(network_name)
                new_default_provider = NetworkDefaultProvider.objects.update_or_create(defaults={'provider_id': provider_id},
                                                                                       operation=operation,
                                                                                       network_id=network.id)[0]
                # To keep db and redis sync we use transaction.atomic and transaction.on_commit to ensure redis updated
                # only if db operation is successful and rolls back db in cause redis raise exception.
                transaction.on_commit(lambda: cls.load_default_provider_data2redis(
                    network=network_name,
                    operation=operation
                ))
                # The line above is required to update redis with new provider data
                return new_default_provider
        except Exception as e:
            logger.exception(e)
            return None
