from django.core.exceptions import ValidationError

from . import NetworkDefaultProviderService, NetworkService
from .url_service import UrlService
from ..dtos.provider import ProviderDataCreator
from ..models.url import URL
from ..models import Provider
from exchange.explorer.utils.exception.custom_exceptions import ProviderNotFoundException, URLNotFoundException
from ...utils.cache import CacheUtils


class ProviderService:

    @classmethod
    def get_all_urls(cls, provider_id):
        provider_object = Provider.objects.get(id=provider_id)
        urls =  list(provider_object.urls.all())
        urls.remove(provider_object.default_url)
        urls.insert(0, provider_object.default_url)
        return urls

    @classmethod
    def get_all_providers(cls):
        return Provider.objects.all()

    @classmethod
    def get_provider_by_id(cls, provider_id):
        try:
            return Provider.objects.get(id=provider_id)
        except Provider.DoesNotExist:
            raise ProviderNotFoundException

    @classmethod
    def get_provider_by_name(cls, provider_name):
        try:
            return Provider.objects.get(name__iexact=provider_name)
        except Provider.DoesNotExist:
            raise ProviderNotFoundException

    @classmethod
    def get_providers_by_network_name_and_operation(cls, network_name, operation_list):
        return Provider.objects.filter(network__name__iexact=network_name,
                                       supported_operations__contains=operation_list)

    @classmethod
    def get_default_url_for_provider_by_id(cls, provider_id):
        provider = cls.get_provider_by_id(provider_id)
        if provider:
            return provider.default_url

    @classmethod
    def get_default_url_for_provider_by_name(cls, provider_name):
        provider = cls.get_provider_by_name(provider_name)
        if provider:
            return provider.default_url

    @classmethod
    def create_provider(cls, name, network_id, support_batch, batch_block_limit,
                        supported_operations, default_url):
        provider = Provider.objects.create(
            name=name,
            network_id=network_id,
            support_batch=support_batch,
            batch_block_limit=batch_block_limit,
            supported_operations=supported_operations
        )
        url_object = UrlService.get_or_create_url_by_url_address(default_url)
        cls.add_url_to_provider(provider.id, url_object.id)
        return provider

    @classmethod
    def update_provider(cls, provider_id, new_name, new_network_id, new_support_batch, new_batch_block_limit,
                        new_supported_operations, default_url):
        provider = cls.get_provider_by_id(provider_id)
        provider.name = new_name
        provider.network_id = new_network_id
        provider.support_batch = new_support_batch
        provider.batch_block_limit = new_batch_block_limit
        provider.supported_operations = new_supported_operations
        provider.save()
        network_name = provider.network.name
        cls.set_url_as_default(provider, default_url, network=network_name)
        return provider

    @classmethod
    def delete_provider(cls, provider_id):
        try:
            provider = Provider.objects.filter(id=provider_id)
            provider.delete()
        except Provider.DoesNotExist:
            raise ProviderNotFoundException

    @classmethod
    def add_url_to_provider(cls, provider, url_id):
        try:
            url_object = UrlService.get_url_by_id(url_id)
            provider.urls.add(url_object)
            provider.save()
            return provider
        except Provider.DoesNotExist:
            raise ProviderNotFoundException
        except URL.DoesNotExist:
            raise URLNotFoundException

    @classmethod
    def get_check_provider_data(cls, network, operation, provider_name, url):
        cache_key = f'check_{network}_{operation}'
        provider_data = CacheUtils.read_from_external_cache(cache_key)

        if not (provider_data and provider_data.provider_name == provider_name):
            provider = ProviderService.get_provider_by_name(provider_name=provider_name)
            interface_name = provider.explorer_interface

            provider_data = ProviderDataCreator.get_dto(provider_name=provider_name, interface_name=interface_name)

        provider_data.base_url = url
        CacheUtils.write_to_external_cache(cache_key, provider_data)
        return provider_data

    @classmethod
    def set_url_as_default(cls, provider, url, network=None, operation=None):
        # Check if the URL exists in the provider's list
        if url not in provider.urls.all().values_list('url', flat=True):
            return None
        url_obj = URL.objects.get(url=url)
        if url_obj is None:
            raise URLNotFoundException(f'URL with url: {url} not found for provider {provider}.')
        provider.default_url = url_obj
        provider.save()
        operations = [operation] if operation else provider.supported_operations
        for operation in operations:
            NetworkDefaultProviderService.load_default_provider_data2redis(network=network, operation=operation)

    @classmethod
    def remove_url_from_provider(cls, provider_id, url_id):
        provider = Provider.objects.get(id=provider_id)
        # Check if the URL exists in the provider's list
        if url_id not in provider.urls.all().values_list('id', flat=True):
            return None
        url_obj = URL.objects.get(id=url_id)
        if url_obj is None:
            raise URLNotFoundException(f'URL with url id: {url_id} not found for provider {provider_id}.')
        if provider.default_url is not None:
            if url_obj.url == provider.default_url:
                raise ValidationError('Cannot remove the default URL for this provider.')
        provider.urls.remove(url_obj)
