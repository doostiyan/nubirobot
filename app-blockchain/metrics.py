from threading import Lock
from typing import Optional

from django.conf import settings
from django.core.cache import cache

# Global lock for metric creation
metric_lock = Lock()

if settings.USE_PROMETHEUS_CLIENT:
    labelnames: list = ['network', 'provider']
    from prometheus_client import Counter, Gauge, Histogram

    address_txs_health_check_provider_last_status = Gauge(
        'address_txs_health_check_provider_last_status',
        'Last status of the address-txs provider which is 200 or 400',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    address_txs_health_check_provider_empty_response = Gauge(
        'address_txs_health_check_provider_empty_response',
        'Empty response returned from provider which is 1(for empty) and 0(for non-empty)',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    address_txs_health_check_provider_retries_count_for_success = Gauge(
        'address_txs_health_check_provider_retries_count_for_success',
        'Number of retries need for provider to have a successful response',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    address_txs_health_check_provider_response_time = Gauge(
        'address_txs_health_check_provider_response_time',
        'Response time of provider to return a successful response',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    address_txs_health_check_alternative_provider_accuracy = Gauge(
        'address_txs_health_check_alternative_provider_accuracy',
        'Accuracy of alternative provider based on default provider in length of transfers',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    address_txs_health_check_alternative_provider_response_completeness = Gauge(
        'address_txs_health_check_alternative_provider_response_completeness',
        'Completeness of alternative provider transfers based on default provider in transfer fields',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    token_txs_health_check_provider_last_status = Gauge(
        'token_txs_health_check_provider_last_status',
        'Last status of the address-txs provider which is 200 or 400',
        ['network', 'token_symbol', 'provider'],
        multiprocess_mode='mostrecent'
    )

    token_txs_health_check_provider_empty_response = Gauge(
        'token_txs_health_check_provider_empty_response',
        'Empty response returned from provider which is 1(for empty) and 0(for non-empty)',
        ['network', 'token_symbol', 'provider'],
        multiprocess_mode='mostrecent'
    )

    token_txs_health_check_provider_retries_count_for_success = Gauge(
        'token_txs_health_check_provider_retries_count_for_success',
        'Number of retries need for provider to have a successful response',
        ['network', 'token_symbol', 'provider'],
        multiprocess_mode='mostrecent'
    )

    token_txs_health_check_provider_response_time = Gauge(
        'token_txs_health_check_provider_response_time',
        'Response time of provider to return a successful response',
        ['network', 'token_symbol', 'provider'],
        multiprocess_mode='mostrecent'
    )

    token_txs_health_check_alternative_provider_accuracy = Gauge(
        'token_txs_health_check_alternative_provider_accuracy',
        'Accuracy of alternative provider based on default provider in length of transfers',
        ['network', 'token_symbol', 'provider'],
        multiprocess_mode='mostrecent'
    )

    token_txs_health_check_alternative_provider_response_completeness = Gauge(
        'token_txs_health_check_alternative_provider_response_completeness',
        'Completeness of alternative provider transfers based on default provider in transfer fields',
        ['network', 'token_symbol', 'provider'],
        multiprocess_mode='mostrecent'
    )

    block_head_health_check_difference_with_default = Gauge(
        'block_head_health_check_difference_with_default',
        'Difference of the block head of the provider with default provider',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    block_head_health_check_provider_last_status = Gauge(
        'block_head_health_check_provider_last_status',
        'Last status of the block head provider which is 200 or 400',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    block_head_health_check_provider_empty_response = Gauge(
        'block_head_health_check_provider_empty_response',
        'Empty response returned from provider which is 1(for empty) and 0(for non-empty)',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    block_head_health_check_provider_retries_count_for_success = Gauge(
        'block_head_health_check_provider_retries_count_for_success',
        'Number of retries need for provider to have a successful response',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    latest_block_height_processed = Gauge(
        'latest_block_height_processed_by_network_provider',
        'Latest block height processed by network and provider',
        labelnames=labelnames,
        multiprocess_mode='mostrecent',
    )

    latest_block_height_mined = Gauge(
        name='latest_block_height_mined_by_network_provider',
        documentation='Latest block height mined by network and provider',
        labelnames=labelnames,
        multiprocess_mode='mostrecent',
    )

    block_height_difference = Gauge(
        name='block_height_difference_by_network_provider',
        documentation='Difference between mined and processed block heights by network and provider',
        labelnames=labelnames,
        multiprocess_mode='mostrecent',
    )

    missed_block_txs = Counter(
        name='missed_block_txs_by_network_provider',
        documentation='Number of missed blocks by network and provider',
        labelnames=labelnames,
    )

    response_time_metric = Histogram(
        name='providers_response_time_seconds_by_network_provider',
        documentation='Histogram of providers response time',
        buckets=(0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 60, 120, 300, 600, 1800, float('inf'),),
        labelnames=labelnames,
    )

    # ----------------------BLOCK TXS HEALTH CHECKER METRICS------------------------

    block_txs_health_check_provider_last_status = Gauge(
        'block_txs_health_check_provider_last_status',
        'Last status of the block-txs provider which is 200 or 400',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    block_txs_health_check_provider_empty_response = Gauge(
        'block_txs_health_check_provider_empty_response',
        'Empty response returned from provider which is 1(for empty) and 0(for non-empty)',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    block_txs_health_check_provider_response_size = Gauge(
        'block_txs_health_check_provider_response_size',
        'Number of transactions returned by the provider compared to the default provider. '
        'Values can be: 0 (equal to default), 1 (greater than default), -1 (less than default)',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    block_txs_health_check_provider_response_time = Gauge(
        'block_txs_health_check_provider_response_time',
        'Response time of provider to return a successful response (in seconds)',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    block_txs_health_check_provider_accuracy = Gauge(
        'block_txs_health_check_alternative_provider_accuracy',
        'Accuracy of alternative provider based on default provider in length of transactions',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    block_txs_health_check_provider_response_completeness = Gauge(
        'block_txs_health_check_alternative_provider_response_completeness',
        'Completeness of alternative provider txs based on default provider in tx fields',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    block_txs_health_check_provider_speed = Gauge(
        'block_txs_health_check_provider_speed',
        'Indicates whether the response speed was acceptable (1: OK, 0: Slow)',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    # ----------------------TX DETAILS HEALTH CHECKER METRICS------------------------

    tx_details_health_check_provider_last_status = Gauge(
        'tx_details_health_check_provider_last_status',
        'Last status of the tx-details provider which is 200 or 400',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    tx_details_health_check_provider_empty_response = Gauge(
        'tx_details_health_check_provider_empty_response',
        'Empty response returned from provider which is 1(for empty) and 0(for non-empty)',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    tx_details_health_check_provider_retries_count_for_success = Gauge(
        'tx_details_health_check_provider_retries_count_for_success',
        'Number of retries needed for provider to have a successful response',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    tx_details_health_check_provider_response_time = Gauge(
        'tx_details_health_check_provider_response_time',
        'Response time of provider to return a successful response (in seconds)',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    tx_details_health_check_alternative_provider_accuracy = Gauge(
        'tx_details_health_check_alternative_provider_accuracy',
        'Accuracy of alternative provider based on default provider in length of transactions',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    tx_details_health_check_alternative_provider_response_completeness = Gauge(
        'tx_details_health_check_alternative_provider_response_completeness',
        'Completeness of alternative provider txs based on default provider in tx fields',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    tx_details_health_check_database_match = Gauge(
        'tx_details_health_check_database_match',
        'Whether the tx from DB matches with any returned from provider (1: match, 0: mismatch)',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    tx_details_health_check_provider_response_size = Gauge(
        'tx_details_health_check_provider_response_size',
        'Number of transactions returned by the provider compared to the default provider. '
        'Values can be: 0 (equal to default), 1 (greater than default), -1 (less than default)',
        ['network', 'provider'],
        multiprocess_mode='mostrecent'
    )

    block_txs_service_delay_seconds = Gauge(
        'block_txs_service_delay_seconds',
        'Time delay in seconds between the earliest transaction timestamp of a block (as seen on-chain) '
        'and the moment it is fetched and processed by our system.',
        ['network'],
        multiprocess_mode='mostrecent'
    )

# Contains metric names as keys, labels as values
metrics_conf = {
    'latest_block_processed': ['network'],
    'api_errors_count': ['network', 'api_name', 'error_type', 'method_name'],
    'api_unavailability': ['network', 'api_name'],
    'api_returned_bad_status': ['network', 'api_name'],
}
PROMETHEUS_COUNTERS = {}
PROMETHEUS_GAUGES = {}
PROMETHEUS_HISTOGRAMS = {}
label_needed_metrics = ['api_errors_count']


def get_prometheus_gauge(name: str, labels: str) -> None:
    if name in label_needed_metrics and isinstance(labels, dict):
        gauge_name = f'explorer_standalone_metric_{name}'
        labelnames = labels
    else:
        label_str = '__'.join(labels)
        gauge_name = f'explorer_standalone_metric_{name}__{label_str}'
        labelnames = ()

    if gauge_name not in PROMETHEUS_GAUGES:
        PROMETHEUS_GAUGES[gauge_name] = Gauge(gauge_name, 'Current value of the metric', labelnames=labelnames,
                                              multiprocess_mode='mostrecent')
    return PROMETHEUS_GAUGES[gauge_name]


def get_prometheus_counter(name: str, labels: str) -> None:
    with metric_lock:
        if name in label_needed_metrics and isinstance(labels, dict):
            counter_name = f'explorer_standalone_metric_{name}'
            labelnames = labels
        else:
            label_str = '__'.join(labels)
            counter_name = f'explorer_standalone_metric_{name}__{label_str}'
            labelnames = ()

        if counter_name not in PROMETHEUS_COUNTERS:
            PROMETHEUS_COUNTERS[counter_name] = Counter(counter_name, 'Total number of events', labelnames=labelnames)
    return PROMETHEUS_COUNTERS[counter_name]


def get_prometheus_histogram(name: str, labels: str) -> None:
    with metric_lock:
        if name in label_needed_metrics and isinstance(labels, dict):
            histogram_name = f'explorer_standalone_metric_{name}'
            labelnames = labels
        else:
            label_str = '__'.join(labels)
            histogram_name = f'explorer_standalone_metric_{name}__{label_str}'
            labelnames = ()

        if histogram_name not in PROMETHEUS_HISTOGRAMS:
            PROMETHEUS_HISTOGRAMS[histogram_name] = Histogram(
                name=histogram_name,
                documentation='Response time',
                labelnames=labelnames,
            )

    return PROMETHEUS_HISTOGRAMS[histogram_name]


def metric_incr(name: str, labels: str) -> None:
    if settings.USE_PROMETHEUS_CLIENT:
        metric = get_prometheus_counter(name, labels)
        if name in label_needed_metrics and isinstance(labels, dict):
            metric.labels(**labels).inc()
        else:
            metric.inc()
    else:
        metric = f'blockchain_metric_{name}__{"_".join(labels)}'
        try:
            cache.incr(metric)
        except ValueError:
            cache.set(metric, 1)


def metric_set(name: str, labels: str, amount: int) -> None:
    if settings.USE_PROMETHEUS_CLIENT:
        gauge = get_prometheus_gauge(name, labels)
        if name in label_needed_metrics and isinstance(labels, dict):
            gauge.labels(**labels).set(amount)
        else:
            gauge.set(amount)
    else:
        metric = f'blockchain_metric_{name}__{"_".join(labels)}'
        cache.set(metric, amount)


def metrics_get(name: str, labels: Optional[list] = None) -> dict:
    metric_pattern = f'blockchain_metric_{name}__{"_".join(labels)}' if labels else f'blockchain_metric_{name}__*'
    keys = sorted(cache.keys(metric_pattern))
    return dict(cache.get_many(keys))
