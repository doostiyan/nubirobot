from exchange.explorer.networkproviders.models import Provider, NetworkDefaultProvider
from exchange.explorer.transactions.models import Transfer
from exchange.blockchain.api.general.dtos.dtos import TransferTx


def get_providers_and_default_providers_by_network_and_operation(network_id, operation):
    providers = Provider.objects.filter(network=network_id, supported_operations__contains=[operation])

    # Get default provider
    default_provider = Provider.objects.filter(
        id__in=NetworkDefaultProvider.objects.filter(
            network=network_id, operation=operation
        ).values_list('provider', flat=True)
    ).first()

    if not default_provider:
        return  None, None # No default provider found

    if not default_provider.explorer_interface:
        return  None, None # Default provider is from old-structure

    # Drop providers that are equal to default_provider, or they are from old-structure
    providers = [provider for provider in providers if (provider.name != default_provider.name and provider.explorer_interface)]

    return providers, default_provider

def get_latest_transfer_by_network_and_symbol(network_id, symbol):
    return Transfer.objects.filter(
        network_id=network_id,
        symbol=symbol,
        to_address_str__isnull=False  # Ensure `to_address_str` exists
    ).order_by('-created_at').first()

def check_transfers_completeness(default_transfer: TransferTx, alternative_transfer: TransferTx):
    if not default_transfer.from_address == alternative_transfer.from_address:
        return False
    if not default_transfer.to_address == alternative_transfer.to_address:
        return False
    if not default_transfer.value == alternative_transfer.value:
        return False
    if not default_transfer.memo == alternative_transfer.memo:
        return False
    if not default_transfer.token == alternative_transfer.token:
        return False
    return True
