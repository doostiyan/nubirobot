from django.core.management.base import BaseCommand

from exchange.blockchain.apis_conf import APIS_CONF, APIS_CLASSES
from exchange.explorer.networkproviders.models import Operation
from exchange.explorer.networkproviders.services.provider_service import ProviderService
from exchange.explorer.networkproviders.services.url_service import UrlService


def set_all_base_urls(network_name):
    if network_name in ('all', 'ALL', '.'):
        network_names = APIS_CONF.keys()
    else:
        network_names = [network_name]

    for network_name in network_names:
        providers_info = APIS_CONF[network_name]
        for service, provider_name in providers_info.items():
            operation = {
                'get_balances': Operation.BALANCE,
                'get_balances_alternatives': Operation.BALANCE,
                'get_txs': Operation.ADDRESS_TXS,
                'get_txs_alternatives': Operation.ADDRESS_TXS,
                'txs_details': Operation.TX_DETAILS,
                'txs_details_alternatives': Operation.TX_DETAILS,
                'get_blocks_addresses': Operation.BLOCK_TXS,
                'get_blocks_addresses_alternatives': Operation.BLOCK_TXS,
                'block_head_apis': Operation.BLOCK_HEAD,
            }.get(service)
            if isinstance(provider_name, list):
                for provider_name_ in provider_name:
                    set_base_url(provider_name_, network_name=network_name, operation=operation)
            else:
                set_base_url(provider_name, network_name=network_name, operation=operation)


def set_base_url(provider_name, network_name, operation):
    if 'interface' in provider_name:
        set_base_url_for_interface_providers(provider_name, network_name, operation)
    else:
        set_base_url_for_single_provider(provider_name, network_name, operation)


def set_base_url_for_single_provider(provider_name, network_name, operation):
    if provider_name in APIS_CLASSES:
        api = APIS_CLASSES[provider_name]
        provider = ProviderService.get_provider_by_name(provider_name)
        base_url = api._base_url
        if base_url:
            url = UrlService.get_or_create_url_by_url_address(url_address=base_url)
            url.use_proxy = api.USE_PROXY
            url.save()
            ProviderService.add_url_to_provider(provider, url.id)
            ProviderService.set_url_as_default(provider, url.url, network=network_name, operation=operation)


def set_base_url_for_interface_providers(provider_name, network_name, operation):
    explorer_interface_instance = APIS_CLASSES[provider_name]
    api_name = {
        Operation.BALANCE: 'balance_apis',
        Operation.ADDRESS_TXS: 'address_txs_apis',
        Operation.TX_DETAILS: 'tx_details_apis',
        Operation.BLOCK_TXS: 'block_txs_apis',
        Operation.BLOCK_HEAD: 'block_head_apis'
    }.get(operation)
    apis = getattr(explorer_interface_instance, api_name, [])
    set_base_urls_for_apis(apis, network_name, operation)
    if operation == Operation.BALANCE:
        apis = getattr(explorer_interface_instance, 'token_balance_apis')
        set_base_urls_for_apis(apis, network_name, Operation.TOKEN_BALANCE)
    if operation == Operation.TX_DETAILS:
        apis = getattr(explorer_interface_instance, 'token_tx_details_apis')
        set_base_urls_for_apis(apis, network_name, Operation.TOKEN_TX_DETAILS)
    if operation == Operation.ADDRESS_TXS:
        apis = getattr(explorer_interface_instance, 'token_txs_apis')
        set_base_urls_for_apis(apis, network_name, Operation.TOKEN_TXS)


def set_base_urls_for_apis(apis, network_name, operation):
    for api in apis:
        api_instance = api.get_instance()
        api_name = api_instance.get_name()
        if api._base_url:
            base_url = api._base_url
            url = UrlService.get_or_create_url_by_url_address(url_address=base_url)
            url.use_proxy = api.USE_PROXY
            url.save()
            provider = ProviderService.get_provider_by_name(api_name)
            ProviderService.add_url_to_provider(provider, url.id)
            ProviderService.set_url_as_default(provider, base_url, network=network_name, operation=operation)


class Command(BaseCommand):
    help = "Load base URLs form APIs to database"

    def add_arguments(self, parser):
        parser.add_argument(
            'network',
            type=str,
            help='the network ',
        )

    def handle(self, *args, **kwargs):
        network = kwargs.get('network')
        if network:
            network = network.upper()

        set_all_base_urls(network_name=network)
