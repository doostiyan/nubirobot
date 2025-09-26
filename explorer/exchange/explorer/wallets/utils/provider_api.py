from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.blockchain.apis_conf import APIS_CLASSES
from exchange.explorer.networkproviders.models import Operation
from exchange.explorer.networkproviders.services import NetworkDefaultProviderService


class ProviderApiUtils:
    @staticmethod
    def load_provider_api(network: str, operation: Operation) -> ExplorerInterface:
        """
        Load the appropriate provider API based on the network and operation.

        Args:
            network (str): The network to load the provider for.
            operation (Operation): The operation (e.g., BALANCE) to perform.

        Returns:
            object: An instance of the appropriate API class.
        """
        provider_data = NetworkDefaultProviderService.load_default_provider_data(network, operation)
        api_name = provider_data.interface_name or provider_data.provider_name
        return APIS_CLASSES[api_name].get_api()
