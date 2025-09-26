from prometheus_client import Gauge, Counter

labelnames = ['network', 'provider']

latest_available_block_height = Gauge(
    'latest_available_block_height_by_{}'.format('_'.join(labelnames)),
    'Latest available block height',
    labelnames,
    multiprocess_mode='mostrecent',
)

min_available_block_height = Gauge(
    'min_available_block_height_by_{}'.format('_'.join(labelnames)),
    'min available block height',
    labelnames,
    multiprocess_mode='mostrecent',
)

provider_empty_response_counter = Counter(
    'empty_response_by_{}'.format('_'.join(labelnames)),
    'Total number of empty responses returned by providers',
    labelnames,
)

missed_block_txs_in_recheck = Counter(
    'missed_block_txs_by_network_provider_in_recheck',
    'Number of missed blocks by network and provider in recheck action',
    labelnames=labelnames,
)

latest_rechecked_block_height = Gauge(
    'latest_rechecked_block_height_by_{}'.format('_'.join(labelnames)),
    'Latest rechecked block height',
    labelnames,
    multiprocess_mode='mostrecent',
)
