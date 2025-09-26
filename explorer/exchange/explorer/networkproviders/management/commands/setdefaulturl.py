from django.core.management import BaseCommand

from exchange.explorer.utils.iterator import get_ordered_list_options
from ...services import ProviderService, NetworkDefaultProviderService
from ...services.url_service import UrlService
from .setdefaultprovider import get_operation_from_user


class Command(BaseCommand):
    help = "Set default url for a network default provider"

    def add_arguments(self, parser):
        parser.add_argument(
            'network',
            type=str,
            nargs='?',
            help='the network',
        )

    def handle(self, *args, **kwargs):
        network = kwargs.get('network')
        if not network:
            network = input('Enter network: ')

        network = network.upper()

        # get operation and url from user
        operation = get_operation_from_user()
        current_default_provider = NetworkDefaultProviderService.get_default_provider_by_network_name_and_operation(
            network, operation).provider

        url2set = get_url_from_user(current_default_provider)

        try:
            url = UrlService.get_or_create_url_by_url_address(url_address=url2set)
            ProviderService.add_url_to_provider(current_default_provider, url.id)
            ProviderService.set_url_as_default(current_default_provider, url.url, network, operation)
            print('Default url successfully changed to {}'.format(url2set))
        except Exception as e:
            print('Exception occurred {}'.format(e))


def get_url_from_user(current_default_provider):
    current_default_provider_name = current_default_provider.name
    current_default_provider_base_url = current_default_provider.default_url.url
    current_default_provider_other_urls = list(current_default_provider.urls.values_list('url', flat=True))
    current_default_provider_other_urls.remove(current_default_provider_base_url)

    url_option_values, url_options = get_ordered_list_options(current_default_provider_other_urls)

    url_index2set = input(
        '* current provider:{}\n* current base url:{}\nEnter url to set as default\nother options:\n{}\nor enter new url\n: '.format(
            current_default_provider_name, current_default_provider_base_url, url_option_values))

    if url_index2set.isnumeric():
        url2set = url_options[url_index2set].split(')')[1].strip()
    else:
        url2set = url_index2set
    return url2set
