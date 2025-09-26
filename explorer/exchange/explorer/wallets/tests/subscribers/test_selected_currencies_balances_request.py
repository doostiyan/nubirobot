import pytest
from unittest.mock import Mock, patch
from exchange.explorer.basis.tests.fixtures.message_broker_fixture import message_broker
from exchange.explorer.wallets.subscribers.dto.get_selected_currencies_balances_request import GetSelectedCurrenciesBalancesRequest
from exchange.explorer.wallets.subscribers.dto.get_balances_response import GetBalancesResponse
from exchange.blockchain.api.general.dtos.dtos import NewBalancesV2
from exchange.explorer.wallets.tests.fixtures.selected_currencies_balances_subscriber_fixture import (
    subscriber, batch_request_data, batch_balances_result
)

def test__get_topic__returns_correct_queue(subscriber):
    from exchange.explorer.wallets.subscribers.topics import GET_SELECTED_CURRENCIES_BALANCES_REQUEST_QUEUE
    assert subscriber.topic() == GET_SELECTED_CURRENCIES_BALANCES_REQUEST_QUEUE

def test__callback__publishes_balances(subscriber, batch_request_data, batch_balances_result):
    # Mock the necessary dependencies
    with patch('exchange.explorer.wallets.utils.provider_api.ProviderApiUtils.load_provider_api') as mock_load_api, \
         patch('exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_selected_tokens_balances_standalone') as mock_get_balances:
        
        # Setup mocks
        mock_load_api.return_value = Mock()
        mock_get_balances.return_value = batch_balances_result
        
        # Create request message
        request = GetSelectedCurrenciesBalancesRequest(**batch_request_data)
        message = request.model_dump_json()
        
        # Execute callback
        subscriber.callback(message)
        
        # Verify message broker was called with correct response
        subscriber._message_broker.publish.assert_called_once()
        call_args = subscriber._message_broker.publish.call_args[0]
        
        # Verify routing key
        from exchange.explorer.wallets.subscribers.topics import GET_SELECTED_CURRENCIES_BALANCE_RESPONSE_ROUTING_KEY
        assert call_args[0] == GET_SELECTED_CURRENCIES_BALANCE_RESPONSE_ROUTING_KEY
        
        # Verify response content
        response = GetBalancesResponse.model_validate_json(call_args[1])
        assert len(response.address_balances) == 2
        assert response.address_balances == batch_balances_result

def test__callback__when_invalid_json__raises_exception(subscriber):
    with pytest.raises(Exception):
        subscriber.callback("invalid json")

def test__callback__when_empty_balance_result__does_not_publish(subscriber, batch_request_data):
    with patch('exchange.explorer.wallets.utils.provider_api.ProviderApiUtils.load_provider_api') as mock_load_api, \
         patch('exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_selected_tokens_balances_standalone') as mock_get_balances:
        
        mock_load_api.return_value = Mock()
        mock_get_balances.return_value = []
        
        request = GetSelectedCurrenciesBalancesRequest(**batch_request_data)
        message = request.model_dump_json()
        
        subscriber.callback(message)
        
        # Verify message broker was not called when no balances are returned
        subscriber._message_broker.publish.assert_not_called()

def test__callback__when_mismatched_addresses__raises_value_error(subscriber, batch_request_data):
    with patch('exchange.explorer.wallets.utils.provider_api.ProviderApiUtils.load_provider_api') as mock_load_api, \
         patch('exchange.blockchain.api.general.explorer_interface.ExplorerInterface.get_selected_tokens_balances_standalone') as mock_get_balances:
        
        mock_load_api.return_value = Mock()
        # Return only one address when two were requested
        mock_get_balances.return_value = [
            NewBalancesV2(
                address="0x123",
                balance="1.0",
                contract_address="0x0000000000000000000000000000000000000000",
                symbol="ETH",
                network="ethereum",
                block_number=16027518,
                block_timestamp="2025-03-26T05:56:30+00:00"
            )
        ]
        
        request = GetSelectedCurrenciesBalancesRequest(**batch_request_data)
        message = request.model_dump_json()
        
        with pytest.raises(ValueError) as exc_info:
            subscriber.callback(message)
        
        assert "Selected Currencies: Addresses in input but not in results" in str(exc_info.value)
        subscriber._message_broker.publish.assert_not_called() 