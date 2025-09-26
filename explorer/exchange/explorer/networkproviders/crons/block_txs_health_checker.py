import concurrent.futures
import json
import os
from time import sleep

from django_cron import CronJobBase, Schedule
from exchange.blockchain.service_based.logging import logger
from exchange.blockchain.apis_conf import APIS_CLASSES
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.explorer.networkproviders.services import NetworkService, NetworkDefaultProviderService
from exchange.explorer.networkproviders.models import Operation, Provider
from exchange.explorer.networkproviders.services.provider_status_service import ProviderStatusService
from exchange.explorer.networkproviders.services.provider_health_checker_services import ProviderHealthCheckerService
from exchange.explorer.transactions.services import TransactionExplorerService
from exchange.explorer.utils.exception.custom_exceptions import ProviderNotFoundException, NotFoundException
from exchange.explorer.utils.telegram_bot import send_telegram_alert


class NetworkProviderBlockTxsValidator(CronJobBase):
    RUN_EVERY_X_MINUTES = 360
    schedule = Schedule(run_every_mins=RUN_EVERY_X_MINUTES)
    network = None

    def do(self):
        network = self.network
        network_id = NetworkService.get_network_by_name(network).id
        logger.info(msg='start-alternative-provider-validator', extra={
            'network': network,
            'operation': Operation.BLOCK_TXS,
            'process_id': os.getpid()
        })
        providers = Provider.objects.filter(
            network=network_id,
            supported_operations__contains=[Operation.BLOCK_TXS]
        )

        def_provider = NetworkDefaultProviderService.get_default_provider_by_network_name_and_operation(
            network_name=network,
            operation=Operation.BLOCK_TXS
        )

        latest_tx = TransactionExplorerService.get_latest_transaction_from_db_by_network_id(network_id)
        block_head = latest_tx.block_height
        block_offset = NetworkService.get_number_of_blocks_given_time(network_name=network, time_s=3 * 60)  # 3 min
        if not def_provider or not providers:
            send_telegram_alert(f'{network}: failed to update block txs health checker. exception: provider not found!')
            raise ProviderNotFoundException
        if not block_head or not block_offset:
            send_telegram_alert(f'{network}: failed to update block txs health checker. exception: block not found!')
            raise NotFoundException

        min_block = block_head - block_offset
        max_block = block_head
        def_provider_data = self.get_block_txs_from_default_provider(def_provider, min_block, max_block)
        if not def_provider_data:
            send_telegram_alert(
                f'{network}: failed to update block txs health checker. exception: default provider data not found!')
            raise NotFoundException

        # Using ThreadPoolExecutor for concurrent execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for provider in providers:
                # drop default and old providers
                if provider.name == def_provider.provider.name or not provider.explorer_interface:
                    continue
                # Submit a separate thread to check the health of each provider
                futures.append(executor.submit(self.retry_block_txs_health_checker, def_provider_data,
                                               provider, min_block, max_block))

            # Wait for all threads to complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    provider, status, status_details = future.result()
                    status = 'healthy' if status else 'unhealthy'
                    ProviderStatusService.update_provider_status(
                        network=network_id,
                        provider=provider,
                        operation=Operation.BLOCK_TXS,
                        status=status,
                    )
                except Exception as e:
                    send_telegram_alert(f'{network}: failed to update block txs health checker. exception:{str(e)}')
                message = {
                    'alert_name': 'alternative provider health checker',
                    'network': network,
                    'operation': Operation.BLOCK_TXS,
                    'default_provider': def_provider.provider.name.replace('_', ''),
                    'alternative_provider': provider.name.replace('_', ''),
                    'status': status,
                    'status_details': status_details,
                    'block_range': f'{min_block} _ {max_block}',
                }
                message_str = json.dumps(message, indent=6)
                message_frmt = message_str.replace("{", "").replace("}", "").replace('"', '').replace(',', '')
                send_telegram_alert(message_frmt)
                logger.info(msg='alternative-provider-validator-details', extra={
                    'network': network,
                    'operation': Operation.BLOCK_TXS,
                    'process_id': os.getpid(),
                    'details': message
                })
        logger.info(msg='finish-alternative-provider-validator', extra={
            'network': network,
            'operation': Operation.BLOCK_TXS,
            'process_id': os.getpid()
        })

    @classmethod
    def get_block_txs_from_default_provider(cls, default_provider, min_block, max_block):
        explorer_interface = APIS_CLASSES.get(default_provider.provider.explorer_interface)
        max_retry = 3
        counter = 0
        def_transfers = []
        while counter < max_retry:
            try:
                def_transfers = explorer_interface().sample_get_blocks(
                    min_block=min_block,
                    max_block=max_block,
                    provider=default_provider.provider.name,
                )
                if def_transfers:
                    break
            except Exception:
                pass
            counter += 1
            sleep(5)
        return def_transfers

    @classmethod
    def retry_block_txs_health_checker(cls, data, provider, min_block, max_block):
        max_retries = 3
        attempt = 0
        while attempt < max_retries:
            result = ProviderHealthCheckerService.block_txs_alternative_health_checker(
                data=data,
                provider=provider,
                min_block=min_block,
                max_block=max_block
            )
            is_healthy, status_details = result
            if is_healthy:
                return provider, is_healthy, status_details
            else:
                attempt += 1
                if attempt < max_retries:
                    pass
                    sleep(5)  # Wait for 5 seconds before retrying
                else:
                    # After 3 failed attempts, return the status as unhealthy
                    return provider, is_healthy, status_details


class CardanoProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.ADA


class AlgorandProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.ALGO


class AptosProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.APT


class ArbitrumProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.ARB


class AvalancheProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.AVAX


class BitcoinCashProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.BCH


class BinanceSmartChainProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.BSC


class BitcoinProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.BTC


class DogeCoinProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.DOGE


class PolkadotProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.DOT


class ElrondProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.EGLD


class EthereumProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.ETH


class FilecoinProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.FIL


class FlowProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.FLOW


class FantomProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.FTM


class LiteCoinProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.LTC


class PolygonProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.MATIC


class NearProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.NEAR


class HarmonyProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.ONE


class SolanaProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.SOL


class TezosProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.XTZ


class TronProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.TRX


class MoneroProvidersBlockTxsValidator(NetworkProviderBlockTxsValidator):
    network = CurrenciesNetworkName.XMR
