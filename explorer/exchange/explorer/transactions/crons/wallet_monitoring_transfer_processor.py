import threading
import time
from datetime import datetime, timezone
from typing import List, Optional

from django.db import connection, models, transaction

from exchange.blockchain.metrics import get_prometheus_histogram, metric_incr, metric_set
from exchange.explorer.basis.message_broker.factory import MessageBrokerFactory
from exchange.explorer.transactions.models import Pointer, PointerProcessingRange, Transfer
from exchange.explorer.transactions.publisher.dto.wallet_monitoring_transfer_dto import (
    NewBlockchainTransactionsEvent,
    Transaction,
)
from exchange.explorer.transactions.publisher.topics import NEW_TRANSACTION_EVENT_ROUTING_KEY
from exchange.explorer.utils.logging import get_logger
from exchange.explorer.utils.string_helpers import string_size_in_mb


class WalletMonitoringTransferProcessor:
    TRANSFERS_LIMIT = 15000
    DELAY_SECONDS = 0.2  # Delay between iterations
    POINTER_PROCESSING_RANGE_NAME = 'wallet_monitoring_transfer_processors'
    THREADS_COUNT = 1

    def __init__(self) -> None:
        self._message_broker = MessageBrokerFactory.get_instance()
        self.logger = get_logger()
        # Initialize histogram metrics
        self.db_fetch_histogram = get_prometheus_histogram(
            'wallet_monitoring_db_fetch_latency_seconds',
            ['wallet_monitoring'],
        )
        self.queue_send_histogram = get_prometheus_histogram(
            'wallet_monitoring_queue_send_latency_seconds',
            ['wallet_monitoring'],
        )

    def _update_metrics(
            self,
            pointer_value: int,
            db_fetch_latency: float,
            queue_send_latency: float
    ) -> None:
        """Update Prometheus metrics for monitoring transfer processing state."""
        try:
            latest_transfer_id = Transfer.objects.aggregate(max_id=models.Max('id'))['max_id'] or 0

            metric_set('wallet_monitoring_pointer_position', ['wallet_monitoring'], pointer_value)
            metric_set('standalone_latest_transfer_id', ['wallet_monitoring'], latest_transfer_id)

            # Update health check metric with current timestamp
            metric_set(
                'wallet_monitoring_last_successful_run',
                ['wallet_monitoring'],
                int(datetime.now().timestamp())
            )

            # Update histogram metrics for latency
            self.db_fetch_histogram.observe(db_fetch_latency)
            if queue_send_latency and queue_send_latency != 0:
                self.queue_send_histogram.observe(queue_send_latency)

            self.logger.info(
                'Metrics updated - Pointer: %s, Latest Transfer: %s',
                pointer_value, latest_transfer_id
            )
        except Exception:
            # logger.exception automatically includes the stack trace
            self.logger.exception('Failed to update metrics')

    def _get_or_create_pointer(self) -> Pointer:
        """Get or create the pointer for tracking processed transfers."""
        pointer = Pointer.objects.select_for_update().filter(name='processed_transfer').first()
        if not pointer:
            pointer = Pointer.objects.create(
                name='processed_transfer',
                point=Transfer.objects.aggregate(min_id=models.Min('id'))['min_id'] or 0
            )
            self.logger.info('Created new pointer with initial value: %s', pointer.point)
            pointer = Pointer.objects.select_for_update().get(pk=pointer.pk)

        return pointer

    def _process_transfers(self, transfers: List[Transfer]) -> None:
        """Process a batch of transfers and publish them to the message broker."""
        transfer_dtos = [
            Transaction(
                tx_hash=transfer.tx_hash,
                success=transfer.success,
                value=str(transfer.value),
                symbol=transfer.symbol,
                block_height=transfer.block_height,
                date=transfer.date.isoformat() if transfer.date else None,
                created_at=transfer.created_at.isoformat(),
                network=transfer.network.name,
                from_address=transfer.from_address_str if transfer.from_address_str else None,
                to_address=transfer.to_address_str if transfer.to_address_str else None
            )
            for transfer in transfers
        ]

        event = NewBlockchainTransactionsEvent(transactions=transfer_dtos).model_dump_json()

        self._message_broker.publish(NEW_TRANSACTION_EVENT_ROUTING_KEY, event)

        self.logger.info('Event Sent to queue with size of: %s MegaByte', f'{string_size_in_mb(event)}')

    def first_transfer_id_after_limit(self, point: id) -> Optional[int]:
        transfer = Transfer.objects.filter(id__gte=int(point) + self.TRANSFERS_LIMIT).order_by('id').first()
        if transfer:
            return transfer.id
        return Transfer.objects.filter(id__lte=int(point) + self.TRANSFERS_LIMIT).order_by('-id').first().id

    def get_first_range(self) -> Optional[PointerProcessingRange]:
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT id FROM {PointerProcessingRange._meta.db_table}
                WHERE name = '{self.POINTER_PROCESSING_RANGE_NAME}'
                ORDER BY last_processed_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            """)  # noqa: SLF001, S608
            range_id = cursor.fetchone()

            if not range_id:
                return None

            return PointerProcessingRange.objects.filter(id=range_id[0]).get()

    def create_range(self) -> None:
        pointer = self._get_or_create_pointer()

        end_of_range = self.first_transfer_id_after_limit(pointer.point)

        if end_of_range < int(pointer.point):
            return

        PointerProcessingRange.objects.create(start_at=pointer.point,
                                              end_at=end_of_range,
                                              name=self.POINTER_PROCESSING_RANGE_NAME,
                                              last_processed_at=datetime.now(timezone.utc))

        pointer.point = end_of_range + 1
        pointer.save()

    def update_range(self, processing_range: PointerProcessingRange) -> int:
        pointer = self._get_or_create_pointer()

        end_of_range = self.first_transfer_id_after_limit(pointer.point)

        processing_range.start_at = pointer.point
        processing_range.end_at = end_of_range
        processing_range.last_processed_at = datetime.now(timezone.utc)
        processing_range.save(update_fields=['start_at', 'end_at', 'last_processed_at'])

        pointer.point = end_of_range + 1
        pointer.save()

        return pointer.point

    def transfer_processor(self) -> None:
        while True:
            transfers = None
            try:
                with transaction.atomic():
                    processing_range = self.get_first_range()

                    if not processing_range:
                        self.create_range()
                        continue

                    fetch_start_at = time.time()

                    transfers = (Transfer.objects
                                 .filter(id__gte=processing_range.start_at)
                                 .filter(id__lte=processing_range.end_at)
                                 .order_by('id'))

                    db_fetch_latency = time.time() - fetch_start_at

                    queue_send_latency = None

                    if len(transfers) == 0:
                        self.logger.info('No new transfers to process.')
                        self._update_metrics(int(processing_range.end_at), db_fetch_latency, 0.0)
                    else:
                        self.logger.info('Processing %d transfers', len(transfers))

                        send_start_at = time.time()
                        self._process_transfers(transfers)
                        queue_send_latency = time.time() - send_start_at
                        self.logger.info('Send to Queue latency: %s.', queue_send_latency)

                    new_point = self.update_range(processing_range)

                    self.logger.info('DB fetch latency: %s.', db_fetch_latency)

                    self._update_metrics(new_point, db_fetch_latency, queue_send_latency)

            except Exception:
                self.logger.exception('Error processing transfers')
                metric_incr('wallet_monitoring_processor_errors', ['wallet_monitoring'])

            finally:
                if not transfers:
                    time.sleep(self.DELAY_SECONDS)

    def run(self) -> None:
        """Main processing loop for wallet monitoring transfers."""
        for _ in range(self.THREADS_COUNT):
            threading.Thread(target=self.transfer_processor).start()

        threading.Event().wait()
