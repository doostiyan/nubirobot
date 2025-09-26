from django.core.management import BaseCommand

from exchange.explorer.utils.logging import logger
from exchange.explorer.utils.iterator import get_ordered_list_options
from ...models import Network
from ...models.operation import Operation
from ...services import ProviderService, NetworkDefaultProviderService


class Command(BaseCommand):
    help = "Set default provider for an operation of network"

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

        # get operation and provider from user
        operation = get_operation_from_user()
        provider_name2set = get_provider_from_user(network, operation)

        # set default provider with given inputs
        provider_id = ProviderService.get_provider_by_name(provider_name2set).id
        network_name = Network.objects.get(name=network).name

        try:
            ndp = NetworkDefaultProviderService.update_or_create_default_provider(provider_id, operation, network_name)
            if ndp:
                logger.info('Default provider successfully changed to %s', provider_name2set)
            else:
                logger.info('Default provider failed to change to %s', provider_name2set)
        except Exception as e:
            logger.exception('Exception occurred: %s', e)


def get_operation_from_user():
    operation_option_values, operation_options = get_ordered_list_options(Operation.values)
    operation_index = input('Enter operation\noptions:\n{}\n: '.format(operation_option_values))
    operation = operation_options[operation_index].split(')')[1].strip()
    return operation


def get_provider_from_user(network, operation):
    providers = list(ProviderService.get_providers_by_network_name_and_operation(network, [operation])
                     .values_list('name', flat=True))

    current_default_provider = NetworkDefaultProviderService.get_default_provider_by_network_name_and_operation(
        network, operation).provider.name
    providers.remove(current_default_provider)

    provider_option_values, provider_options = get_ordered_list_options(providers)
    provider_index = input(
        'Enter provider to set as default\n* current provider: {}\nother options:\n{}\n: '.format(
            current_default_provider, provider_option_values))
    provider_name2set = provider_options[provider_index].split(')')[1].strip()
    return provider_name2set



