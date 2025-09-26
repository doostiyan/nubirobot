import time
from typing import List

from celery import shared_task
from django.db import transaction

from exchange.blockchain.api.general.dtos import TransferTx
from exchange.explorer.blocks.models import GetBlockStats
from exchange.explorer.blocks.services import BlockExplorerService
from exchange.explorer.blocks.utils.metrics import latest_available_block_height, provider_empty_response_counter
from exchange.explorer.networkproviders.models import Network, Operation
from exchange.explorer.networkproviders.services import NetworkDefaultProviderService
from exchange.explorer.transactions.models import Transfer
from exchange.explorer.utils.celery import get_task_count_by_queue
from exchange.explorer.utils.logging import get_logger
from exchange.explorer.wallets.tasks import chunked_bulk_create, transaction_data

networks_on_celery = ['AVAX', 'SOL', 'EGLD', 'ONE']

logger = get_logger()


# @shared_task
def run_get_block_txs_cron(network_name: str) -> None:
    insert_q_name = f'{network_name}-insert'
    if network_name in networks_on_celery and get_task_count_by_queue(insert_q_name) > 1:
        logger.info('%s-get-block-txs-cron-rejected', network_name)
        return

    network, _ = Network.objects.get_or_create(name=network_name)
    get_block_stats, _ = GetBlockStats.objects.get_or_create(network_id=network.id)
    latest_fetched_block = get_block_stats.latest_fetched_block or get_block_stats.latest_processed_block

    logger.info('%s-start-of-get-block-txs-cron: %s', network_name, latest_fetched_block)
    block_info_dto = BlockExplorerService.get_latest_block_info_dto(
        network=network_name,
        after_block_number=latest_fetched_block,
        to_block_number=None,
        include_info=True,
        include_inputs=True,
        use_db=False,
        serialize=False,
    )
    transactions = block_info_dto['transactions']
    latest_received_block = block_info_dto['latest_processed_block']
    logger.info(
        '%s-get-block-txs-cron-block-info-fetched - latest_fetched_block: %s - latest_received_block: %s - '
        'transfers_length: %s',
        network_name,
        latest_fetched_block,
        latest_received_block,
        len(transactions)
    )

    if not latest_fetched_block or latest_received_block > latest_fetched_block:
        GetBlockStats.objects.filter(network_id=network.id, ).update(latest_fetched_block=latest_received_block)

    provider = NetworkDefaultProviderService.get_default_provider_by_network_name_and_operation(
        network.name,
        Operation.BLOCK_TXS
    ).provider.name
    if not transactions:
        provider_empty_response_counter.labels(network=network.name, provider=provider).inc()

    if network.name in networks_on_celery:
        insert_txs2db.apply_async(
            kwargs={
                'transactions': transactions,
                'latest_processed_block': latest_received_block,
                'network_name': network.name,
                'network_id': network.id,
                'provider': provider,
            },
            queue=insert_q_name,
        )
    else:
        insert_txs2db(
            transactions=transactions,
            latest_processed_block=latest_received_block,
            network_name=network.name,
            network_id=network.id,
            provider=provider,
        )


@shared_task
def insert_txs2db(transactions: List[TransferTx], latest_processed_block: int, network_name: str, network_id: int,
                  provider: str) -> None:
    # Step 6: Prepare Transfer objects for bulk creation
    transfers = [transaction_data(tx, network_id, operation=Operation.BLOCK_TXS) for tx in transactions]

    batch_size = 1000
    start = time.time()
    with transaction.atomic():
        if transfers:
            chunked_bulk_create(Transfer, transfers, batch_size=batch_size, network=network_name, ignore_conflicts=True)

        get_block_stats, _ = GetBlockStats.objects.select_for_update().get_or_create(network_id=network_id)
        if not get_block_stats.min_available_block and transfers:
            get_block_stats.min_available_block = min([tx.block_height for tx in transfers])
        if (not get_block_stats.latest_processed_block
                or latest_processed_block > get_block_stats.latest_processed_block):
            get_block_stats.latest_processed_block = latest_processed_block
        get_block_stats.save(update_fields=['latest_processed_block', 'min_available_block'])
        end = time.time()
        duration = int(end - start)
        logger.info(
            '%s-get_block_stats updated successfully: %s in %s seconds for %s transfers',
            network_name,
            get_block_stats.latest_processed_block,
            duration,
            len(transfers)
        )

    latest_available_block_height.labels(network=network_name, provider=provider).set(
        get_block_stats.latest_processed_block)
