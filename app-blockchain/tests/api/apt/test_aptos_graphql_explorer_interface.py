from exchange.blockchain.api.apt.aptos_explorer_interface import AptosExplorerInterface
from exchange.blockchain.api.apt.aptoslabs_graphql import GraphQlAptosApi

api = GraphQlAptosApi
api.back_off_time = 300
symbol = 'APT'
explorerInterface = AptosExplorerInterface()
explorerInterface.block_txs_apis = [api]
explorerInterface.block_head_apis = [api]

import pytest
from unittest.mock import patch, Mock
from datetime import datetime
from exchange.blockchain.utils import RateLimitError
from rest_framework import status


def test__graphql_apt_explorer_interface__get_blockhead__with_backoff__successful():
    instance = api.get_instance()

    with patch('requests.post') as mock_post:
        # Mock response with 429 to trigger process_error_response()
        mock_response_429 = Mock()
        mock_response_429.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        mock_response_429.text = 'Too Many Requests'

        # Make .post return the 429 response
        mock_post.return_value = mock_response_429

        # First call: should raise RateLimitError and set backoff
        with pytest.raises(RateLimitError, match="Too Many Requests"):
            api.get_block_head()

        # Confirm that backoff is set in future
        assert instance.backoff > datetime.now()
        api.backoff = instance.backoff

        # Second call: should short-circuit (without hitting .post again)
        with patch('requests.post') as mock_post_2:
            with pytest.raises(RateLimitError, match="Remaining"):
                api.get_block_head()

            # Ensure second request did NOT go to HTTP layer
            mock_post_2.assert_not_called()
