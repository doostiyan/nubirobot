from exchange.explorer.utils.telegram_bot import send_telegram_alert
from exchange.explorer.networkproviders.services import NetworkDefaultProviderService, NetworkService
from exchange.explorer.networkproviders.services.check_network_provider_service import CheckNetworkProviderService
from exchange.explorer.networkproviders.services.provider_status_service import ProviderStatusService


class AutoSwitchProviderService:

    @classmethod
    def update_default_provider(cls, network, operation):
        current_provider = NetworkDefaultProviderService.get_default_provider_by_network_name_and_operation(
            network_name=network,
            operation=operation)

        check_provider_result = CheckNetworkProviderService.check_provider(
            provider_id=current_provider.provider_id,
            base_url=current_provider.provider.default_url,
            operation=operation,
        )
        network_obj = NetworkService.get_network_by_name(network)
        if not check_provider_result.is_healthy:
            alternative_providers = ProviderStatusService.get_active_providers_by_operation(
                network=network_obj.id,
                operation=operation
            )
            for alternative_provider in alternative_providers:
                if alternative_provider.provider.explorer_interface:  # drop old providers
                    check_alternative_result = CheckNetworkProviderService.check_provider(
                        provider_id=alternative_provider.provider_id,
                        base_url=alternative_provider.provider.urls.first(),
                        operation=operation,
                    )
                    if check_alternative_result.is_healthy:
                        # set new provider as default...
                        NetworkDefaultProviderService.update_or_create_default_provider(
                            provider_id=alternative_provider.provider.id,
                            operation=operation,
                            network_name=alternative_provider.network.name,
                        )
                        break
