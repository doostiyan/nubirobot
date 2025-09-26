from django_cron import CronJobBase, Schedule
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import sleep
import os

from exchange.blockchain.apis_conf import APIS_CLASSES
from exchange.blockchain.service_based.logging import logger
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.explorer.networkproviders.models import Operation, Provider, NetworkDefaultProvider
from exchange.explorer.networkproviders.services import NetworkService
from exchange.explorer.networkproviders.services.provider_status_service import ProviderStatusService
from exchange.blockchain.metrics import block_head_health_check_provider_empty_response, \
    block_head_health_check_provider_last_status, block_head_health_check_difference_with_default, \
    block_head_health_check_provider_retries_count_for_success
from exchange.explorer.networkproviders.utils import get_providers_and_default_providers_by_network_and_operation
from exchange.explorer.utils.telegram_bot import send_telegram_alert
from exchange.explorer.utils.exception.custom_exceptions import NetworkNotFoundException, ProviderNotFoundException


class NetworkProviderBlockHeadHealthCheck(CronJobBase):
    RUN_EVERY_X_MINUTES = 360
    network = None
    schedule = Schedule(run_every_mins=RUN_EVERY_X_MINUTES)
    provider_status_service = ProviderStatusService
    MAX_RETRIES = 3

    @classmethod
    def fetch_block_head(cls, provider, network, is_default_provider):
        """Fetch block head for a given provider with retries."""
        explorer_interface = APIS_CLASSES.get(provider.explorer_interface)
        last_exception = False

        for attempt in range(0, cls.MAX_RETRIES + 1):  # +1 for the initial attempt
            try:
                block_head = explorer_interface().sample_get_block_head(provider.name)
                if block_head:
                    # Success case: Update success metrics
                    block_head_health_check_provider_last_status.labels(network, provider.name).set(200)
                    block_head_health_check_provider_empty_response.labels(network, provider.name).set(0)

                    # If this was a retry, log the retry count
                    if attempt > 0:
                        block_head_health_check_provider_retries_count_for_success.labels(network, provider.name).set(
                            attempt)

                    return provider.name, block_head, None  # Successful response

                # Failed (empty response), try again
                sleep(5)  # Optional: Add delay before retrying
            except Exception as e:
                if attempt < cls.MAX_RETRIES:
                    sleep(5)  # Optional delay
                else:
                    error_message = str(e)
                    last_exception = True

        # If all retries failed:
        block_head_health_check_provider_last_status.labels(network, provider.name).set(400)
        if is_default_provider:
            provider_message = "Default provider"
        else:
            provider_message = "Alternative provider"
        if not last_exception:
            message = (f"{network}:\n{provider_message} {provider.name} returned empty response after max retries!\n"
                       f"Request: get_block_head")
            send_telegram_alert(message)
            block_head_health_check_provider_empty_response.labels(network, provider.name).set(1)
        else:
            message = (f"{network}:\n{provider_message} {provider.name} faced an exception after max retries!\n"
                       f"Request: get_block_head\n"
                       f"Exception: {error_message}")
            send_telegram_alert(message)
        return provider.name, None, "failed after retries"

    def do(self):
        network = self.network
        network_id = NetworkService.get_network_by_name(network).id
        logger.info(msg='start-alternative-provider-validator', extra={
            'network': network,
            'operation': Operation.BLOCK_HEAD,
            'process_id': os.getpid()
        })
        if not network_id:
            raise NetworkNotFoundException
        providers, default_provider = get_providers_and_default_providers_by_network_and_operation(network_id,
                                                                                                   Operation.BLOCK_HEAD)

        if not default_provider:
            raise ProviderNotFoundException

        # Parallel execution using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(providers)) as executor:  # Adjust max_workers as needed
            futures = {}

            # Submit the default provider task first
            default_future = executor.submit(self.fetch_block_head, default_provider, network, is_default_provider=True)
            futures[default_future] = "default"

            # Ensure Default Provider Completes First
            default_provider_block_head = None
            for future in as_completed([default_future]):  # Wait only for the default provider first
                provider_name, block_head, error = future.result()
                default_provider_block_head = block_head

                if not default_provider_block_head:
                    self.provider_status_service.update_provider_status(default_provider.id, network_id,
                                                                        Operation.BLOCK_HEAD, "unhealthy")
                else:
                    self.provider_status_service.update_provider_status(default_provider.id, network_id,
                                                                    Operation.BLOCK_HEAD, "healthy")
                break

            # Submit the other providers
            for provider in providers:
                futures[
                    executor.submit(self.fetch_block_head, provider, network, is_default_provider=False)] = provider

            # Process Other Providers After Default Completes
            for future in as_completed(futures):
                if future == default_future:
                    continue  # Already processed default provider

                provider = futures[future]
                provider_name, block_head, error = future.result()
                if block_head and default_provider_block_head:
                    # Compare with default provider's block head
                    difference = block_head - default_provider_block_head
                    block_head_health_check_difference_with_default.labels(network, provider_name).set(difference)
                    message = (f"Network: {network}:\n"
                               f"Operation: {Operation.BLOCK_HEAD}\n"
                               f"Default provider: {default_provider.name}\n"
                               f"Alternative provider: {provider_name}\n"
                               f"Block head difference with default provider: {difference}\n"
                               f"Request: get_block_head")
                    logger.info(msg='alternative-provider-validator-details', extra={
                        'network': network,
                        'operation': Operation.BLOCK_HEAD,
                        'process_id': os.getpid(),
                        'details': message
                    })
                    self.provider_status_service.update_provider_status(provider.id, network_id, Operation.BLOCK_HEAD,
                                                                        "healthy")
                else:
                    if not block_head:
                        self.provider_status_service.update_provider_status(provider.id, network_id, Operation.BLOCK_HEAD,
                                                                        "unhealthy")
        logger.info(msg='finish-alternative-provider-validator', extra={
            'network': network,
            'operation': Operation.BLOCK_HEAD,
            'process_id': os.getpid()
        })


class CardanoProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.ADA


class AlgorandProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.ALGO


class AtomProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.ATOM


class AptosProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.APT


class ArbitrumProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.ARB


class AvalancheProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.AVAX


class BitcoinCashProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.BCH


class BinanceSmartChainProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.BSC


class BitcoinProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.BTC


class DogeCoinProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.DOGE


class PolkadotProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.DOT


class ElrondProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.EGLD


class EnjinCoinProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.ENJ


class EosProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.EOS


class EthereumClassicProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.ETC


class EthereumProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.ETH


class FilecoinProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.FIL


class FlowProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.FLOW


class FantomProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.FTM


class HederaProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.HBAR


class LiteCoinProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.LTC


class PolygonProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.MATIC


class NearProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.NEAR


class HarmonyProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.ONE


class SolanaProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.SOL


class SonicProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.SONIC


class TezosProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.XTZ


class TronProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.TRX


class MoneroProvidersBlockHeadHealthCheck(NetworkProviderBlockHeadHealthCheck):
    network = CurrenciesNetworkName.XMR
