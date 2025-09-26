from django_cron import CronJobBase, Schedule
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import sleep
import time
import os

from exchange.blockchain.apis_conf import APIS_CLASSES
from exchange.blockchain.service_based.logging import logger
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.explorer.networkproviders.models import Operation
from exchange.explorer.networkproviders.services import NetworkService
from exchange.explorer.networkproviders.services.provider_status_service import ProviderStatusService
from exchange.blockchain.metrics import (address_txs_health_check_provider_empty_response, \
                                         address_txs_health_check_provider_last_status,
                                         address_txs_health_check_provider_retries_count_for_success,
                                         address_txs_health_check_provider_response_time,
                                         address_txs_health_check_alternative_provider_accuracy,
                                         address_txs_health_check_alternative_provider_response_completeness)
from exchange.explorer.utils.telegram_bot import send_telegram_alert
from exchange.explorer.networkproviders.utils import get_providers_and_default_providers_by_network_and_operation, \
    get_latest_transfer_by_network_and_symbol, check_transfers_completeness
from exchange.explorer.utils.exception.custom_exceptions import ProviderNotFoundException, NetworkNotFoundException


class NetworkProviderAddressTxsHealthCheck(CronJobBase):
    RUN_EVERY_X_MINUTES = 360
    network = None
    schedule = Schedule(run_every_mins=RUN_EVERY_X_MINUTES)
    provider_status_service = ProviderStatusService
    MAX_RETRIES = 3
    is_token = False

    @classmethod
    def address_txs_health_check(cls, address, provider, network):
        """Get address-txs for a given provider with retries."""
        explorer_interface = APIS_CLASSES.get(provider.explorer_interface)
        last_exception = False

        for attempt in range(0, cls.MAX_RETRIES + 1):  # +1 for the initial attempt
            try:
                start_time = time.time()
                address_txs = explorer_interface().sample_get_txs(address, provider.name)
                if address_txs:
                    end_time = time.time()
                    response_time = (end_time - start_time)
                    # Success case: Update success metrics
                    address_txs_health_check_provider_last_status.labels(network, provider.name).set(200)
                    address_txs_health_check_provider_empty_response.labels(network, provider.name).set(0)
                    address_txs_health_check_provider_response_time.labels(network, provider.name).set(response_time)

                    # If this was a retry, log the retry count
                    if attempt > 0:
                        address_txs_health_check_provider_retries_count_for_success.labels(network, provider.name).set(
                            attempt)

                    return provider.name, address_txs, None  # Successful response

                # Failed (empty response), try again
                sleep(5)  # Optional: Add delay before retrying
            except Exception as e:
                if attempt < cls.MAX_RETRIES:
                    sleep(0)  # Optional delay
                else:
                    error_message = str(e)
                    last_exception = True

        # If all retries failed:
        address_txs_health_check_provider_last_status.labels(network, provider.name).set(400)
        if not last_exception:
            message = (f"Network: {network}\n"
                       f"Operation: {Operation.ADDRESS_TXS}\n"
                       f"Address: {address}\n"
                       f"Provider {provider.name} returned empty response after max retries")
            send_telegram_alert(message)
            address_txs_health_check_provider_empty_response.labels(network, provider.name).set(1)
        else:
            message = (f"Network: {network}\n"
                       f"Operation: {Operation.ADDRESS_TXS}\n"
                       f"Provider {provider.name} faced an exception after max retries!\n"
                       f"Exception: {error_message}")
            send_telegram_alert(message)
        return provider.name, None, "failed after retries"

    @classmethod
    def address_txs_response_checker_with_default_provider(cls, network, default_address_txs, alternative_address_txs,
                                                           alternative_provider_name):
        alternative_completeness_ratio = len(alternative_address_txs) / len(default_address_txs)
        address_txs_health_check_alternative_provider_response_completeness.labels(network, alternative_provider_name).set(
            alternative_completeness_ratio)
        default_txs_dict = dict()
        alternative_txs_dict = dict()
        default_accuracy = len(default_address_txs)
        alternative_accuracy = default_accuracy

        for default_address_tx in default_address_txs:
            default_txs_dict[default_address_tx.tx_hash] = default_address_tx

        for alternative_address_tx in alternative_address_txs:
            alternative_txs_dict[alternative_address_tx.tx_hash] = alternative_address_tx
        for tx_hash, transfer in default_txs_dict.items():
            if alternative_txs_dict.get(tx_hash):
                if not check_transfers_completeness(alternative_txs_dict[tx_hash], transfer):
                    alternative_accuracy -= 1
        alternative_provider_accuracy = alternative_accuracy / default_accuracy
        address_txs_health_check_alternative_provider_accuracy.labels(network,
                                                                                   alternative_provider_name).set(
            alternative_provider_accuracy)
        return alternative_provider_accuracy, alternative_completeness_ratio

    def do(self):
        network = self.network
        network_id = NetworkService.get_network_by_name(network).id
        logger.info(msg='start-alternative-provider-validator', extra={
            'network': network,
            'operation': Operation.ADDRESS_TXS,
            'process_id': os.getpid()
        })
        if not network_id:
            raise NetworkNotFoundException
        providers, default_provider = get_providers_and_default_providers_by_network_and_operation(network_id,
                                                                                                   Operation.ADDRESS_TXS)

        if not default_provider:
            raise ProviderNotFoundException

        latest_transfer = get_latest_transfer_by_network_and_symbol(network_id, network)
        if not latest_transfer:
            return
        address = latest_transfer.to_address_str
        # Parallel execution using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(providers)) as executor:  # Adjust max_workers as needed
            futures = {}

            # Submit the default provider task first
            default_future = executor.submit(self.address_txs_health_check, address, default_provider, network)
            futures[default_future] = "default"

            # Submit the other providers
            for provider in providers:
                futures[executor.submit(self.address_txs_health_check, address, provider, network)] = provider

            # Ensure Default Provider Completes First
            default_provider_address_txs = None
            for future in as_completed([default_future]):  # Wait only for the default provider first
                default_provider_name, address_txs, error = future.result()
                default_provider_address_txs = address_txs

                if not default_provider_address_txs:
                    self.provider_status_service.update_provider_status(default_provider.id, network_id,
                                                                        Operation.ADDRESS_TXS, "unhealthy")
                    return  # Exit early if the default provider failed
                self.provider_status_service.update_provider_status(default_provider.id, network_id,
                                                                    Operation.ADDRESS_TXS, "healthy")
                break

            # Process Other Providers After Default Completes
            for future in as_completed(futures):
                if future == default_future:
                    continue  # Already processed default provider

                provider = futures[future]
                alternative_provider_name, alternative_provider_address_txs, error = future.result()
                if alternative_provider_address_txs:
                    # Compare with default provider's address_txs
                    alternative_provider_accuracy, alternative_provider_response_completeness = self.address_txs_response_checker_with_default_provider(
                        network, default_provider_address_txs,
                        alternative_provider_address_txs,
                        alternative_provider_name)
                    self.provider_status_service.update_provider_status(provider.id, network_id, Operation.ADDRESS_TXS,
                                                                        "healthy")
                    if alternative_provider_accuracy != 1 or alternative_provider_response_completeness < 1:
                        message = (f"Network: {network}\n"
                                   f"Operation: {Operation.ADDRESS_TXS}\n"
                                   f"Address: {address}\n"
                                   f"Default provider name: {default_provider_name}\n"
                                   f"Alternative provider name: {alternative_provider_name}\n"
                                   f"Total default provider transfers: {len(default_provider_address_txs)}\n"
                                   f"Alternative provider accuracy ratio: {alternative_provider_accuracy}\n"
                                   f"Alternative provider completeness ratio: {alternative_provider_response_completeness}")
                        send_telegram_alert(message)
                        logger.info(msg='alternative-provider-validator-details', extra={
                            'network': network,
                            'operation': Operation.ADDRESS_TXS,
                            'process_id': os.getpid(),
                            'details': message
                        })

                else:
                    self.provider_status_service.update_provider_status(provider.id, network_id, Operation.ADDRESS_TXS,
                                                                        "unhealthy")
        logger.info(msg='finish-alternative-provider-validator', extra={
            'network': network,
            'operation': Operation.ADDRESS_TXS,
            'process_id': os.getpid()
        })


class CardanoProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.ADA


class AlgorandProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.ALGO


class AptosProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.APT


class ArbitrumProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.ARB


class AvalancheProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.AVAX


class BitcoinCashProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.BCH


class BinanceSmartChainProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.BSC


class BitcoinProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.BTC


class DogeCoinProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.DOGE


class PolkadotProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.DOT


class ElrondProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.EGLD


class EnjinCoinProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.ENJ


class EthereumClassicProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.ETC


class EthereumProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.ETH


class FilecoinProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.FIL


class FlowProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.FLOW


class FantomProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.FTM


class LiteCoinProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.LTC


class PolygonProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.MATIC


class NearProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.NEAR


class HarmonyProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.ONE


class SolanaProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.SOL


class SonicProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.SONIC


class TezosProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.XTZ


class TronProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.TRX


class MoneroProvidersAddressTxsHealthCheck(NetworkProviderAddressTxsHealthCheck):
    network = CurrenciesNetworkName.XMR
