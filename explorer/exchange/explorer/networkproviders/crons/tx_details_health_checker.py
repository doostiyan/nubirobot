import concurrent.futures
import json
import os
from time import sleep
from django_cron import CronJobBase, Schedule

from exchange.blockchain.apis_conf import APIS_CLASSES
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.blockchain.service_based.logging import logger
from exchange.explorer.networkproviders.services import NetworkService, NetworkDefaultProviderService
from exchange.explorer.networkproviders.models import Operation, Provider
from exchange.explorer.networkproviders.services.provider_status_service import ProviderStatusService
from exchange.explorer.networkproviders.services.provider_health_checker_services import ProviderHealthCheckerService
from exchange.explorer.transactions.services import TransactionExplorerService
from exchange.explorer.transactions.utils.exceptions import TransactionNotFoundException
from exchange.explorer.utils.exception.custom_exceptions import ProviderNotFoundException, NotFoundException
from exchange.explorer.utils.telegram_bot import send_telegram_alert


class NetworkProviderTxDetailsValidator(CronJobBase):
    RUN_EVERY_X_MINUTES = 360
    schedule = Schedule(run_every_mins=RUN_EVERY_X_MINUTES)
    network = None

    def do(self):
        network = self.network
        network_id = NetworkService.get_network_by_name(network).id
        logger.info(msg='start-alternative-provider-validator', extra={
            'network': network,
            'operation': Operation.TX_DETAILS,
            'process_id': os.getpid()
        })
        providers = Provider.objects.filter(
            network=network_id,
            supported_operations__contains=[Operation.TX_DETAILS]
        )

        def_provider = NetworkDefaultProviderService.get_default_provider_by_network_name_and_operation(
            network_name=network,
            operation=Operation.TX_DETAILS
        )

        latest_tx = TransactionExplorerService.get_latest_transaction_from_db_by_network_id(network_id)

        if not def_provider or not providers:
            send_telegram_alert(f'{network}:failed to update tx details health checker. provider not found!')
            raise ProviderNotFoundException
        if not latest_tx:
            send_telegram_alert(f'{network}:failed to update tx details health checker. Transaction not found!')
            raise TransactionNotFoundException

        def_provider_data = self.get_tx_details_from_default_provider(def_provider, latest_tx)
        if not def_provider_data:
            send_telegram_alert(
                f'{network}:failed to update tx details health checker. default provider data not found!')
            raise NotFoundException

        # Using ThreadPoolExecutor for concurrent execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            for provider in providers:
                # drop default and old providers
                if provider.name == def_provider.provider.name or not provider.explorer_interface:
                    continue
                # Submit a separate thread to check the health of each provider
                futures.append(executor.submit(self.retry_tx_details_health_checker, def_provider_data, provider,
                                               latest_tx))

            # Wait for all threads to complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    provider, status, status_details = future.result()
                    status = 'healthy' if status else 'unhealthy'
                    ProviderStatusService.update_provider_status(
                        network=network_id,
                        provider=provider,
                        operation=Operation.TX_DETAILS,
                        status=status,
                    )
                except Exception as e:
                    send_telegram_alert(f'{network}:failed to update tx details health checker. exception:{str(e)}')

                message = {
                    'alert_name': 'alternative provider health checker',
                    'network': network,
                    'operation': Operation.TX_DETAILS,
                    'default_provider': def_provider.provider.name.replace('_', ''),
                    'alternative_provider': provider.name.replace('_', ''),
                    'status': status,
                    'status_details': status_details,
                    'hash': latest_tx.tx_hash,
                }
                message_str = json.dumps(message, indent=6)
                formatted_message = message_str.replace("{", "").replace("}", "").replace('"', '').replace(',', '')
                send_telegram_alert(formatted_message)
                logger.info(msg='alternative-provider-validator-details', extra={
                    'network': network,
                    'operation': Operation.TX_DETAILS,
                    'process_id': os.getpid(),
                    'details': message
                })
        logger.info(msg='finish-alternative-provider-validator', extra={
            'network': network,
            'operation': Operation.TX_DETAILS,
            'process_id': os.getpid()
        })

    @classmethod
    def get_tx_details_from_default_provider(cls, default_provider, latest_tx):
        explorer_interface = APIS_CLASSES.get(default_provider.provider.explorer_interface)
        max_retry = 3
        counter = 0
        def_transfers = []
        while counter < max_retry:
            try:
                if latest_tx.network.name.lower() == latest_tx.symbol.lower() or not explorer_interface.token_tx_details_apis:
                    def_transfers = explorer_interface().sample_get_tx_details(
                        provider=default_provider.provider.name,
                        tx_hash=latest_tx.tx_hash,
                    )
                else:
                    def_transfers = explorer_interface().sample_get_token_tx_details(
                        provider=default_provider.provider.name,
                        tx_hash=latest_tx.tx_hash,
                    )
                if def_transfers:
                    break
            except Exception:
                pass
            counter += 1
            sleep(5)
        return def_transfers

    @classmethod
    def retry_tx_details_health_checker(cls, data, provider, latest_tx):
        max_retries = 3
        attempt = 0
        while attempt < max_retries:
            result = ProviderHealthCheckerService.tx_details_alternative_provider_health_checker(
                data=data,
                provider=provider,
                latest_tx=latest_tx
            )
            is_healthy, status_details = result
            if is_healthy:
                return provider, is_healthy, status_details
            else:
                attempt += 1
                if attempt < max_retries:
                    pass
                    sleep(10)  # Wait for 10 seconds before retrying
                else:
                    # After 3 failed attempts, return the status provider as unhealthy
                    return provider, is_healthy, status_details


class CardanoProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.ADA


class AlgorandProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.ALGO


class AptosProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.APT


class ArbitrumProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.ARB


class AvalancheProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.AVAX


class BitcoinCashProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.BCH


class BinanceSmartChainProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.BSC


class BitcoinProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.BTC


class DogeCoinProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.DOGE


class PolkadotProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.DOT


class ElrondProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.EGLD


class EthereumProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.ETH


class FilecoinProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.FIL


class FlowProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.FLOW


class FantomProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.FTM


class LiteCoinProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.LTC


class PolygonProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.MATIC


class NearProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.NEAR


class HarmonyProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.ONE


class SolanaProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.SOL


class TezosProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.XTZ


class TronProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.TRX


class MoneroProvidersTxDetailsValidator(NetworkProviderTxDetailsValidator):
    network = CurrenciesNetworkName.XMR
