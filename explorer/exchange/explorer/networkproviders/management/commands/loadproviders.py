from django.core.management.base import BaseCommand

from exchange.blockchain.apis_conf import APIS_CONF, APIS_CLASSES
from exchange.explorer.networkproviders.models import Operation, NetworkDefaultProvider, Provider, Network
from exchange.explorer.networkproviders.services import NetworkDefaultProviderService


class Command(BaseCommand):
    help = "Load providers form APIs Conf to database"

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
        load_providers(network)


def load_providers(network):
    if network in ('all', 'ALL', '.'):
        network_names = APIS_CONF.keys()
    else:
        network_names = [network]
    for network_name in network_names:
        network, _ = Network.objects.get_or_create(
            name=network_name,
            defaults={'block_limit_per_req': 1, 'use_db': False},
        )
        services = APIS_CONF[network_name].keys()
        for service in services:
            provider_name = APIS_CONF[network_name][service]
            is_default_provider = True
            if isinstance(provider_name, list):
                for index, provider_name in enumerate(provider_name):
                    if provider_name:
                        if 'interface' in provider_name:
                            save_interface_in_db(service, network, provider_name)
                        else:
                            if index != 0 or service.endswith('alternatives'):
                                is_default_provider = False

                            save_in_db(service, network, provider_name, is_default_provider)
                            save_token_service_in_db(service, network, provider_name, is_default_provider)
            else:
                if provider_name:
                    if 'interface' in provider_name:
                        save_interface_in_db(service, network, provider_name)
                    else:
                        save_in_db(service, network, provider_name, is_default_provider)
                        save_token_service_in_db(service, network, provider_name, is_default_provider)


def save_interface_in_db(service, network, provider_name):
    explorer_interface_instance = APIS_CLASSES[provider_name]
    attr_name = {
        'get_balances': 'balance_apis',
        'get_balances_alternatives': 'balance_apis',
        'get_txs': 'address_txs_apis',
        'get_txs_alternatives': 'address_txs_apis',
        'txs_details': 'tx_details_apis',
        'txs_details_alternatives': 'tx_details_apis',
        'get_blocks_addresses': 'block_txs_apis',
        'get_blocks_addresses_alternatives': 'block_txs_apis',
        'block_head_apis': 'block_head_apis',
        'block_head_apis_alternatives': 'block_head_apis',
    }.get(service)
    apis = getattr(explorer_interface_instance, attr_name)
    save_apis_in_db(apis, network, service, provider_name)
    if service == 'txs_details':
        apis = getattr(explorer_interface_instance, 'token_tx_details_apis')
        save_apis_in_db(apis, network, Operation.TOKEN_TX_DETAILS, provider_name)
    if service == 'get_txs':
        apis = getattr(explorer_interface_instance, 'token_txs_apis')
        save_apis_in_db(apis, network, Operation.TOKEN_TXS, provider_name)
    elif service == 'get_balances':
        apis = getattr(explorer_interface_instance, 'token_balance_apis')
        save_apis_in_db(apis, network, Operation.TOKEN_BALANCE, provider_name)


def save_apis_in_db(apis, network, service, explorer_interface):
    if apis:
        for i, api in enumerate(apis):
            provider_name = api.get_instance().get_name()
            is_default_provider = True
            if i != 0 or service.endswith('alternatives'):
                is_default_provider = False
            save_in_db(service, network, provider_name, is_default_provider, explorer_interface=explorer_interface)


def save_token_service_in_db(service, network, provider_name, is_default_provider, explorer_interface=None):
    token_service = None
    if service == 'get_balances':
        token_service = 'token_balance'
    elif service == 'get_txs':
        token_service = 'token_txs'
    elif service == 'get_tx_details':
        token_service = 'token_tx_details'

    if token_service:
        save_in_db(token_service, network, provider_name, is_default_provider, explorer_interface=explorer_interface)


def save_in_db(service, network, provider_name, is_default_provider, explorer_interface=None):
    operation = {
        'get_balances': Operation.BALANCE,
        'get_balances_alternatives': Operation.BALANCE,
        'token_balance': Operation.TOKEN_BALANCE,
        'get_txs': Operation.ADDRESS_TXS,
        'get_txs_alternatives': Operation.ADDRESS_TXS,
        'token_txs': Operation.TOKEN_TXS,
        'txs_details': Operation.TX_DETAILS,
        'txs_details_alternatives': Operation.TX_DETAILS,
        'token_tx_details': Operation.TOKEN_TX_DETAILS,
        'get_blocks_addresses': Operation.BLOCK_TXS,
        'get_blocks_addresses_alternatives': Operation.BLOCK_TXS,
        'block_head_apis': Operation.BLOCK_HEAD,
    }.get(service)

    if operation:
        provider = Provider.objects.filter(name=provider_name).first()
        if provider:
            provider.supported_operations.append(operation)
            provider.supported_operations = list(set(provider.supported_operations))
            provider.explorer_interface = explorer_interface
            provider.save()
        else:
            provider, _ = Provider.objects.get_or_create(
                name=provider_name,
                network_id=network.id,
                supported_operations=[operation],
                explorer_interface=explorer_interface,
            )
        if is_default_provider:
            default_provider = NetworkDefaultProviderService.update_or_create_default_provider(
                network_name=network.name,
                operation=operation,
                provider_id=provider.id
            )
            default_provider.provider_id = provider.id
            default_provider.save()
