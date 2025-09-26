from unittest.mock import MagicMock, patch

import pytest

from exchange.blockchain.api.general import explorer_interface
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface


@pytest.mark.skip
def test__set_metric_of_block_txs_service_delay__successful():
    with patch.object(explorer_interface.settings, 'USE_PROMETHEUS_CLIENT', True):  # noqa: FBT003, SIM117
        with patch('exchange.blockchain.api.general.explorer_interface.datetime') as mock_datetime:
            with patch('exchange.blockchain.api.general.explorer_interface.cache') as mock_cache:
                with patch('exchange.blockchain.metrics.block_txs_service_delay_seconds') as mock_metric:
                    fake_now = MagicMock()
                    fake_now.now.return_value = fake_now
                    fake_now.__sub__.return_value.total_seconds.return_value = 123
                    mock_datetime.now.return_value = fake_now
                    mock_datetime.timezone.utc = None

                    mock_cache.get.return_value = 99

                    instance = ExplorerInterface()
                    instance.network = 'BTC'

                    dummy_provider = MagicMock()
                    dummy_provider.cache_key = 'dummy'
                    dummy_provider.get_name.return_value = 'dummy_provider'
                    instance.get_provider = MagicMock(return_value=dummy_provider)

                    instance.calculate_unprocessed_block_range = MagicMock(return_value=(101, 100))
                    dummy_transfer = MagicMock(block_height=100, date=fake_now)
                    instance.fetch_latest_block = MagicMock(return_value=([dummy_transfer], 101))
                    instance.convert_transfers2txs_addresses_dict = MagicMock(return_value={})
                    instance.convert_transfers2txs_info_dict = MagicMock(return_value={})

                    instance.get_latest_block()

                    mock_metric.labels.assert_called_with(network='BTC')
                    mock_metric.labels().set.assert_called_with(123)
