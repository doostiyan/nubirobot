import random

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
from exchange.blockchain.metrics import (token_txs_health_check_provider_empty_response, \
                                         token_txs_health_check_provider_last_status,
                                         token_txs_health_check_provider_retries_count_for_success,
                                         token_txs_health_check_provider_response_time,
                                         token_txs_health_check_alternative_provider_accuracy,
                                         token_txs_health_check_alternative_provider_response_completeness)
from exchange.explorer.utils.telegram_bot import send_telegram_alert
from exchange.explorer.networkproviders.utils import get_providers_and_default_providers_by_network_and_operation, \
    get_latest_transfer_by_network_and_symbol, check_transfers_completeness
from exchange.explorer.utils.exception.custom_exceptions import ProviderNotFoundException, NetworkNotFoundException
from exchange.blockchain.contracts_conf import CONTRACT_INFO


def choose_contract_info(network_contracts):
    contracts_info = network_contracts['mainnet']

    random_token_code = random.choice(list(contracts_info.keys()))
    # Randomly choose one of the token codes
    return contracts_info[random_token_code]


class NetworkProviderTokenTxsHealthCheck(CronJobBase):
    RUN_EVERY_X_MINUTES = 360
    network = None
    schedule = Schedule(run_every_mins=RUN_EVERY_X_MINUTES)
    provider_status_service = ProviderStatusService
    MAX_RETRIES = 3

    @classmethod
    def token_txs_health_check(cls, address, provider, network, contract_info, token_symbol):
        """Get address-txs for a given provider with retries."""
        explorer_interface = APIS_CLASSES.get(provider.explorer_interface)
        last_exception = False

        for attempt in range(0, cls.MAX_RETRIES + 1):  # +1 for the initial attempt
            try:
                start_time = time.time()
                token_txs = explorer_interface().sample_get_token_txs(address, contract_info, provider.name)
                if token_txs:
                    end_time = time.time()
                    response_time = (end_time - start_time)
                    # Success case: Update success metrics
                    token_txs_health_check_provider_last_status.labels(network, token_symbol, provider.name).set(200)
                    token_txs_health_check_provider_empty_response.labels(network, token_symbol, provider.name).set(0)
                    token_txs_health_check_provider_response_time.labels(network, token_symbol, provider.name).set(
                        response_time)

                    # If this was a retry, log the retry count
                    if attempt > 0:
                        token_txs_health_check_provider_retries_count_for_success.labels(network, token_symbol,
                                                                                         provider.name).set(
                            attempt)

                    return provider.name, token_txs, None  # Successful response

                # Failed (empty response), try again
                sleep(5)  # Optional: Add delay before retrying
            except Exception as e:
                if attempt < cls.MAX_RETRIES:
                    sleep(0)  # Optional delay
                else:
                    error_message = str(e)
                    last_exception = True

        # If all retries failed:
        token_txs_health_check_provider_last_status.labels(network, token_symbol, provider.name).set(400)
        if not last_exception:
            message = (f"Network: {network}\n"
                       f"Token: {token_symbol}\n"
                       f"Operation: {Operation.TOKEN_TXS}\n"
                       f"Provider {provider.name} returned empty response after max retries\n"
                       f"Address: {address}")
            send_telegram_alert(message)
            token_txs_health_check_provider_empty_response.labels(network, token_symbol, provider.name).set(1)
        else:
            message = (f"Network: {network}\n"
                       f"Token: {token_symbol}\n"
                       f"Operation: {Operation.TOKEN_TXS}\n"
                       f"Provider {provider.name} faced an exception after max retries!\n"
                       f"Exception: {error_message}")
            send_telegram_alert(message)
        return provider.name, None, "failed after retries"

    @classmethod
    def token_txs_response_checker_with_default_provider(cls, network, token_symbol, default_token_txs,
                                                         alternative_token_txs,
                                                         alternative_provider_name):
        alternative_provider_completeness = len(alternative_token_txs) / len(default_token_txs)
        token_txs_health_check_alternative_provider_response_completeness.labels(network, token_symbol,
                                                                    alternative_provider_name).set(
            alternative_provider_completeness)
        default__token_txs_dict = dict()
        alternative_token_txs_dict = dict()
        default_accuracy = len(default_token_txs)
        alternative_accuracy = default_accuracy

        for default_token_tx in default_token_txs:
            default__token_txs_dict[default_token_txs.tx_hash] = default_token_tx

        for alternative_address_tx in default_token_txs:
            alternative_token_txs_dict[alternative_address_tx.tx_hash] = alternative_address_tx
        for tx_hash, transfer in default__token_txs_dict.items():
            if alternative_token_txs_dict.get(tx_hash):
                if not check_transfers_completeness(alternative_token_txs_dict[tx_hash], transfer):
                    alternative_accuracy -= 1
        alternative_provider_accuracy = alternative_accuracy / default_accuracy
        token_txs_health_check_alternative_provider_accuracy.labels(network, token_symbol,
                                                                                 alternative_provider_name).set(
            alternative_provider_accuracy)
        return alternative_provider_accuracy, alternative_provider_completeness

    def do(self):
        network = self.network
        network_id = NetworkService.get_network_by_name(network).id
        logger.info(msg='start-alternative-provider-validator', extra={
            'network': network,
            'operation': Operation.TOKEN_TXS,
            'process_id': os.getpid()
        })
        if not network_id:
            raise NetworkNotFoundException
        providers, default_provider = get_providers_and_default_providers_by_network_and_operation(network_id,
                                                                                                   Operation.TOKEN_TXS)

        if not default_provider:
            raise ProviderNotFoundException

        latest_transfer = None
        contract_info = None
        token_symbol = None
        while not latest_transfer:
            contract_info = choose_contract_info(CONTRACT_INFO.get(network))
            token_symbol = contract_info.get('symbol')
            latest_transfer = get_latest_transfer_by_network_and_symbol(network_id, token_symbol)

        address = latest_transfer.to_address_str
        # Parallel execution using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(providers)) as executor:  # Adjust max_workers as needed
            futures = {}

            # Submit the default provider task first
            default_future = executor.submit(self.token_txs_health_check, address, default_provider, network,
                                             contract_info, token_symbol)
            futures[default_future] = "default"

            # Submit the other providers
            for provider in providers:
                futures[executor.submit(self.token_txs_health_check, address, provider, network, contract_info,
                                        token_symbol)] = provider

            # Ensure Default Provider Completes First
            default_provider_token_txs = None
            for future in as_completed([default_future]):  # Wait only for the default provider first
                default_provider_name, address_txs, error = future.result()
                default_provider_token_txs = address_txs

                if not default_provider_token_txs:
                    self.provider_status_service.update_provider_status(default_provider.id, network_id,
                                                                        Operation.TOKEN_TXS, "unhealthy")
                    return  # Exit early if the default provider failed
                self.provider_status_service.update_provider_status(default_provider.id, network_id,
                                                                    Operation.TOKEN_TXS, "healthy")
                break

            # Process Other Providers After Default Completes
            for future in as_completed(futures):
                if future == default_future:
                    continue  # Already processed default provider

                provider = futures[future]
                alternative_provider_name, alternative_provider_address_txs, error = future.result()
                if alternative_provider_address_txs:
                    # Compare with default provider's address_txs
                    alternative_provider_accuracy, alternative_provider_response_completeness = self.token_txs_response_checker_with_default_provider(
                        network, token_symbol, default_provider_token_txs,
                        alternative_provider_address_txs,
                        alternative_provider_name)
                    self.provider_status_service.update_provider_status(provider.id, network_id, Operation.TOKEN_TXS,
                                                                        "healthy")
                    if alternative_provider_accuracy != 1 or alternative_provider_response_completeness < 1:
                        message = (f"Network: {network}\n"
                                   f"Token: {token_symbol}\n"
                                   f"Operation: {Operation.TOKEN_TXS}\n"
                                   f"Address: {address}\n"
                                   f"Default provider name: {default_provider_name}\n"
                                   f"Alternative provider name: {alternative_provider_name}\n"
                                   f"Total default provider transfers: {len(default_provider_token_txs)}\n"
                                   f"Alternative provider accuracy ratio: {alternative_provider_accuracy}\n"
                                   f"Alternative provider completeness ratio: {alternative_provider_response_completeness}")
                        send_telegram_alert(message)
                        logger.info(msg='alternative-provider-validator-details', extra={
                            'network': network,
                            'operation': Operation.TOKEN_TXS,
                            'process_id': os.getpid(),
                            'details': message
                        })

                else:
                    self.provider_status_service.update_provider_status(provider.id, network_id, Operation.TOKEN_TXS,
                                                                        "unhealthy")
        logger.info(msg='finish-alternative-provider-validator', extra={
            'network': network,
            'operation': Operation.TOKEN_TXS,
            'process_id': os.getpid()
        })


class ArbitrumProvidersTokenTxsHealthCheck(NetworkProviderTokenTxsHealthCheck):
    network = CurrenciesNetworkName.ARB


class AvalancheProvidersTokenTxsHealthCheck(NetworkProviderTokenTxsHealthCheck):
    network = CurrenciesNetworkName.AVAX


class BinanceSmartChainTokenTxsHealthCheck(NetworkProviderTokenTxsHealthCheck):
    network = CurrenciesNetworkName.BSC


class EthereumClassicTokenTxsHealthCheck(NetworkProviderTokenTxsHealthCheck):
    network = CurrenciesNetworkName.ETC


class EthereumTokenTxsHealthCheck(NetworkProviderTokenTxsHealthCheck):
    network = CurrenciesNetworkName.ETH


class FantomTokenTxsHealthCheck(NetworkProviderTokenTxsHealthCheck):
    network = CurrenciesNetworkName.FTM


class PolygonTokenTxsHealthCheck(NetworkProviderTokenTxsHealthCheck):
    network = CurrenciesNetworkName.MATIC


class HarmonyTokenTxsHealthCheck(NetworkProviderTokenTxsHealthCheck):
    network = CurrenciesNetworkName.ONE


class SonicTokenTxsHealthCheck(NetworkProviderTokenTxsHealthCheck):
    network = CurrenciesNetworkName.SONIC


class TronTokenTxsHealthCheck(NetworkProviderTokenTxsHealthCheck):
    network = CurrenciesNetworkName.TRX
