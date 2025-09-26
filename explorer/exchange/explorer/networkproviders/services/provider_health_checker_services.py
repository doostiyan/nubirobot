import time
from decimal import Decimal

from exchange.blockchain.apis_conf import APIS_CLASSES
from exchange.blockchain.metrics import block_txs_health_check_provider_accuracy, \
    block_txs_health_check_provider_response_time, block_txs_health_check_provider_speed, \
    block_txs_health_check_provider_last_status, block_txs_health_check_provider_empty_response, \
    tx_details_health_check_alternative_provider_accuracy, tx_details_health_check_provider_last_status, \
    tx_details_health_check_provider_empty_response, tx_details_health_check_provider_response_size, \
    tx_details_health_check_provider_response_time, block_txs_health_check_provider_response_size, \
    block_txs_health_check_provider_response_completeness, tx_details_health_check_database_match, \
    tx_details_health_check_alternative_provider_response_completeness
from exchange.explorer.networkproviders.services import ProviderService, NetworkService


class ProviderHealthCheckerService(ProviderService):

    @staticmethod
    def normalize_transaction(tx):
        # Extract only the important fields for comparison.
        return {
            "tx_hash": tx.tx_hash,
            "success": tx.success,
            "from_address": tx.from_address,
            "to_address": tx.to_address,
            "value": tx.value,
            "symbol": tx.symbol,
            "memo": tx.memo,
            "token": tx.token,
        }

    @classmethod
    def block_txs_alternative_health_checker(cls, data, provider, min_block, max_block):
        network = provider.network
        explorer_interface = APIS_CLASSES.get(provider.explorer_interface)
        block_time = NetworkService.get_block_time_of_network(network_name=network)

        is_healthy = True
        status_details = {
            'alt_provider_error': False,
        }

        try:
            start_time = time.time()
            alt_transfers = explorer_interface().sample_get_blocks(
                min_block=min_block,
                max_block=max_block,
                provider=provider.name,
            )
            end_time = time.time()
            elapsed_time = end_time - start_time

        except Exception:
            status_details["alt_provider_error"] = True
            is_healthy = False
            block_txs_health_check_provider_last_status.labels(network, provider).set(400)
            return is_healthy, status_details

        block_txs_health_check_provider_last_status.labels(network, provider).set(200)
        block_txs_health_check_provider_empty_response.labels(network, provider).set(1 if not alt_transfers else 0)
        if not alt_transfers:
            status_details['response_size'] = 'empty'
            is_healthy = False

        else:
            status_details['last_response_time'] = f"{round(elapsed_time, 3)}s"
            block_txs_health_check_provider_response_time.labels(network, provider).set(round(elapsed_time, 3))
            status_details['block_processing_status'] = 'normal'
            speed = elapsed_time / (max_block - min_block) > block_time
            block_txs_health_check_provider_speed.labels(network, provider).set(0 if speed else 1)
            if speed:
                is_healthy = False
                status_details['block_processing_status'] = 'slow'

            default_set = {frozenset(cls.normalize_transaction(tx).items()) for tx in data}
            alternate_set = {frozenset(cls.normalize_transaction(tx).items()) for tx in alt_transfers}

            # Transactions that exist in both providers
            common_transactions = default_set & alternate_set
            if len(common_transactions) == len(default_set):
                status_details['response_size'] = 'equal to default provider'
                block_txs_health_check_provider_response_size.labels(network, provider).set(0)

            # Transactions missing in alternate provider
            missing_in_alternate = default_set - alternate_set
            if len(missing_in_alternate) > 0:
                status_details['response_size'] = 'smaller than default provider'
                is_healthy = False
                block_txs_health_check_provider_response_size.labels(network, provider).set(-1)

            # Transactions missing in default provider
            missing_in_default = alternate_set - default_set
            if len(missing_in_default) > 0:
                status_details['response_size'] = 'larger than default provider'
                is_healthy = False
                block_txs_health_check_provider_response_size.labels(network, provider).set(1)

            alt_api_accuracy = round(len(alt_transfers) / len(data), 5)
            alt_api_completeness = round(len(common_transactions) / len(data), 5)
            block_txs_health_check_provider_accuracy.labels(network, provider).set(alt_api_accuracy)
            block_txs_health_check_provider_response_completeness.labels(network, provider).set(alt_api_completeness)
            status_details['completeness_ratio'] = alt_api_completeness
            status_details['accuracy_ratio'] = alt_api_accuracy

        return is_healthy, status_details

    @classmethod
    def tx_details_alternative_provider_health_checker(cls, data, provider, latest_tx):
        network = provider.network.name
        explorer_interface = APIS_CLASSES.get(provider.explorer_interface)
        is_healthy = True
        status_details = {
            'alt_provider_error': False,
        }

        try:
            start_time = time.time()
            if latest_tx.network.name.lower() == latest_tx.symbol.lower() or not explorer_interface.token_tx_details_apis:
                alt_transfers = explorer_interface().sample_get_tx_details(
                    provider=provider.name,
                    tx_hash=latest_tx.tx_hash,
                )
            else:
                alt_transfers = explorer_interface().sample_get_token_tx_details(
                    provider=provider.name,
                    tx_hash=latest_tx.tx_hash,
                )
            end_time = time.time()
            elapsed_time = end_time - start_time

        except Exception:
            status_details["alt_provider_error"] = True
            is_healthy = False
            tx_details_health_check_provider_last_status.labels(network, provider).set(400)
            return is_healthy, status_details

        tx_details_health_check_provider_last_status.labels(network, provider).set(200)
        tx_details_health_check_provider_empty_response.labels(network, provider).set(1 if not alt_transfers else 0)

        if not alt_transfers:
            status_details['response_size'] = 'empty'
            is_healthy = False

        else:
            status_details['last_response_time'] = f"{round(elapsed_time, 3)}s"
            tx_details_health_check_provider_response_time.labels(network, provider).set(round(elapsed_time, 3))
            default_set = {frozenset(cls.normalize_transaction(tx).items()) for tx in data}
            alternate_set = {frozenset(cls.normalize_transaction(tx).items()) for tx in alt_transfers}

            # Transactions that exist in both providers
            common_transactions = default_set & alternate_set
            if len(common_transactions) == len(default_set):
                status_details['response_size'] = 'equal to default provider'
                tx_details_health_check_provider_response_size.labels(network, provider).set(0)

            # Transactions missing in alternate provider
            missing_in_alternate = default_set - alternate_set
            if len(missing_in_alternate) > 0:
                status_details['response_size'] = 'smaller than default provider'
                is_healthy = False
                tx_details_health_check_provider_response_size.labels(network, provider).set(-1)

            # Transactions missing in default provider
            missing_in_default = alternate_set - default_set
            if len(missing_in_default) > 0:
                status_details['response_size'] = 'larger than default provider'
                is_healthy = False
                tx_details_health_check_provider_response_size.labels(network, provider).set(1)

            alternative_provider_completeness = len(common_transactions) / len(data)
            alternative_provider_accuracy = len(alt_transfers) / len(data)
            tx_details_health_check_alternative_provider_accuracy.labels(network, provider).set(
                alternative_provider_accuracy)
            tx_details_health_check_alternative_provider_response_completeness.labels(network, provider).set(
                alternative_provider_completeness)

            status_details['accuracy_ratio'] = alternative_provider_accuracy
            status_details['completeness_ratio'] = alternative_provider_completeness

            # Compare with latest transfer hash in DB
            status_details["database_match"] = True
            if latest_tx.tx_hash != alt_transfers[0].tx_hash:
                status_details["database_match"] = False
                is_healthy = False
                tx_details_health_check_database_match.labels(network, provider).set(0)

            # Compare with latest transfer address in DB
            elif not any((latest_tx.from_address_str or latest_tx.to_address_str)
                         in {transfer.from_address, transfer.to_address} for transfer in alt_transfers):
                status_details["database_match"] = False
                is_healthy = False
                tx_details_health_check_database_match.labels(network, provider).set(0)

            # Compare with latest transfer value in DB
            elif not any(Decimal(latest_tx.value) == Decimal(transfer.value) for transfer in alt_transfers):
                status_details["database_match"] = False
                is_healthy = False
                tx_details_health_check_database_match.labels(network, provider).set(0)

            # Compare with latest transfer value in DB
            elif not any(latest_tx.symbol == transfer.symbol for transfer in alt_transfers):
                status_details["database_match"] = False
                is_healthy = False
                tx_details_health_check_database_match.labels(network, provider).set(0)
            else:
                tx_details_health_check_database_match.labels(network, provider).set(1)

        return is_healthy, status_details
