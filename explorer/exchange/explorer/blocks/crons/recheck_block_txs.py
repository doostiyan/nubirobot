import datetime
from functools import partial

import pytz
from django_cron import Schedule
from django.db import transaction

from exchange.blockchain.models import CurrenciesNetworkName, Currencies
from exchange.explorer.networkproviders.services import NetworkDefaultProviderService
from exchange.explorer.transactions.models import Transfer
from exchange.explorer.utils.dto import get_dto_data
from exchange.explorer.utils.cron import CronJob, set_cron_code
from exchange.explorer.blocks.services import BlockExplorerService
from exchange.explorer.blocks.models import GetBlockStats
from exchange.explorer.blocks.utils.metrics import missed_block_txs_in_recheck, latest_rechecked_block_height
from exchange.explorer.networkproviders.models import Network, Operation

from exchange.explorer.utils.logging import get_logger
from exchange.explorer.wallets.models import Address

code_fmt = 'get_{}_block_txs'

set_code = partial(set_cron_code, code_fmt=code_fmt)


RECHECK_NETWORKS = ['SOL', 'NEAR', 'FIL', 'FLOW', 'ADA']
RECHECK_OFFSETS = {
        'SOL': 4000,
        'FIL': 60,
        'FLOW': 1800,
        'NEAR': 1500,
        'ADA': 90
    }

class RecheckBlockTxsCron(CronJob):

    def run(self):
        logger = get_logger()
        logger.info('recheck cron started!')

        network, _ = Network.objects.get_or_create(name=self.network)
        # Check if the network is in the recheck list
        if network.name not in RECHECK_NETWORKS:
            logger.info(f'Network {network} is not in recheck list.')
            return
        provider = NetworkDefaultProviderService.get_default_provider_by_network_name_and_operation(
            network.name,
            Operation.BLOCK_TXS
        ).provider.name
        get_block_stats, _ = GetBlockStats.objects.get_or_create(network_id=network.id)
        if get_block_stats.latest_rechecked_block_processed is None:
            db_latest_block = get_block_stats.latest_processed_block
            offset = RECHECK_OFFSETS.get(network.name, 0)
            get_block_stats.latest_rechecked_block_processed = (
                    db_latest_block - offset
            )
            get_block_stats.save()
        db_latest_rechecked_block = get_block_stats.latest_rechecked_block_processed
        logger.info('db_latest_rechecked_block:{}'.format(db_latest_rechecked_block))

        block_info_dto = BlockExplorerService.get_latest_block_info_dto(
            network=self.network,
            after_block_number=get_block_stats.latest_rechecked_block_processed,
            to_block_number=None,
            include_info=True,
            include_inputs=True,
            use_db=False,
        )
        transactions = block_info_dto.transactions

        # Step 1: Filter transactions by those not already in the database
        existing_tx_hashes = set(
            Transfer.objects.filter(tx_hash__in=[tx.tx_hash for tx in transactions]).values_list('tx_hash', flat=True)
        )
        transactions_to_process = [tx for tx in transactions if tx.tx_hash not in existing_tx_hashes]
        if not transactions_to_process:
            logger.info('No new transactions to process for recheck.')
            return
        # Step 2: Process the filtered transactions (same as in GetBlockTxsCron)
        unique_addresses = set()
        for transaction_dto in transactions_to_process:
            data = get_dto_data(transaction_dto)
            from_address = data.get('from_address')
            to_address = data.get('to_address')
            if from_address:
                unique_addresses.add(from_address)
            if to_address:
                unique_addresses.add(to_address)

        # Fetch and create addresses as in the original GetBlockTxsCron
        existing_addresses = Address.objects.filter(blockchain_address__in=unique_addresses).values_list(
            'blockchain_address', flat=True)
        logger.info('after fetch existing addresses')
        new_addresses = list(unique_addresses - set(existing_addresses))

        batch_size = 30000
        for i in range(0, len(new_addresses), batch_size):
            batch = (Address(blockchain_address=address) for address in new_addresses[i:i + batch_size])
            Address.objects.bulk_create(batch, ignore_conflicts=True)

        all_addresses = Address.objects.filter(blockchain_address__in=unique_addresses).values_list(
            'blockchain_address', 'id')
        address_map = {address[0]: address[1] for address in all_addresses}

        # Prepare Transfer objects for bulk creation
        created_at = datetime.datetime.now(tz=pytz.UTC)
        transfers = []
        missed_blocks = []
        for transaction_dto in transactions_to_process:
            if transaction_dto.block_height not in missed_blocks:
                missed_blocks.append(transaction_dto.block_height)
                missed_block_txs_in_recheck.labels(network=network.name, provider=provider).inc()
            data = get_dto_data(transaction_dto)
            data.pop('confirmations')
            data['created_at'] = created_at
            data['network_id'] = network.id
            data['source_operation'] = Operation.BLOCK_TXS
            from_address = data.pop('from_address')
            to_address = data.pop('to_address')

            if from_address:
                data['from_address_id'] = address_map[from_address]
            if to_address:
                data['to_address_id'] = address_map[to_address]

            transfers.append(Transfer(**data))

        # Log and save processed transfers
        logger.info(f'Processing {len(transfers)} transfers for recheck.')
        with transaction.atomic():
            if transfers:
                Transfer.objects.bulk_create(transfers, ignore_conflicts=True, batch_size=batch_size)
                get_block_stats.latest_rechecked_block_processed = block_info_dto.latest_processed_block
                get_block_stats.save()
                logger.info('get_block_stats updated successfully: {}'.format(get_block_stats.latest_rechecked_block_processed))

        latest_rechecked_block_height.labels(network=network.name, provider=provider).set(
            get_block_stats.latest_rechecked_block_processed)

        logger.info('recheck cron finished')


@set_code
class GetFilecoinRecheckBlockTxsCron(RecheckBlockTxsCron):
    network = CurrenciesNetworkName.FIL
    currency = Currencies.fil
    schedule = Schedule(run_every_mins=1)

@set_code
class GetFlowRecheckBlockTxsCron(RecheckBlockTxsCron):
    network = CurrenciesNetworkName.FLOW
    currency = Currencies.flow
    schedule = Schedule(run_every_mins=1)

@set_code
class GetNearRecheckBlockTxsCron(RecheckBlockTxsCron):
    network = CurrenciesNetworkName.NEAR
    currency = Currencies.near
    schedule = Schedule(run_every_mins=1)

@set_code
class GetSolanaRecheckBlockTxsCron(RecheckBlockTxsCron):
    network = CurrenciesNetworkName.SOL
    currency = Currencies.sol
    schedule = Schedule(run_every_mins=1)

@set_code
class GetCardanoRecheckBlockTxsCron(RecheckBlockTxsCron):
    network = CurrenciesNetworkName.ADA
    currency = Currencies.ada
    schedule = Schedule(run_every_mins=2)
