from exchange.explorer.utils.logging import get_logger
from exchange.blockchain.api.general.explorer_interface import ExplorerInterface
from exchange.explorer.basis.message_broker.ports.message_broker_interface import MessageBrokerInterface
from exchange.explorer.basis.message_broker.ports.subscriber_interface import SubscriberInterface
from exchange.explorer.networkproviders.models import Operation
from exchange.explorer.wallets.subscribers.dto.get_balances_response import GetBalancesResponse
from exchange.explorer.wallets.subscribers.dto.get_selected_currencies_balances_request import \
    GetSelectedCurrenciesBalancesRequest
from exchange.explorer.wallets.subscribers.topics import GET_SELECTED_CURRENCIES_BALANCES_REQUEST_QUEUE, \
    GET_SELECTED_CURRENCIES_BALANCE_RESPONSE_ROUTING_KEY
from exchange.explorer.wallets.utils.provider_api import ProviderApiUtils


class SelectedCurrenciesBalancesRequestSubscriber(SubscriberInterface):

    def __init__(self, message_broker: MessageBrokerInterface) -> None:
        self._message_broker = message_broker
        self.logger = get_logger()

    def threads(self) -> int:
        return 5

    def callback(self, message: str) -> None:
        self.logger.info(f"Selected Currencies: Received message: {message}")
        try:
            # Validate and parse the incoming message
            get_selected_currencies_balances_request = GetSelectedCurrenciesBalancesRequest.model_validate_json(message)

            # Load the API for the specified network
            api = ProviderApiUtils.load_provider_api(
                get_selected_currencies_balances_request.network,
                Operation.BALANCE
            )

            # Fetch balances for the requested addresses and tokens
            balance_updated_addresses = ExplorerInterface.get_selected_tokens_balances_standalone(
                api,
                get_selected_currencies_balances_request.addresses
            )
            if not balance_updated_addresses or len(balance_updated_addresses) == 0:
                self.logger.info("Selected Currencies: No balances updated. Skipping further processing")
                return

            # Compare the input addresses with the result addresses
            input_addresses = {addr.address.lower() for addr in get_selected_currencies_balances_request.addresses}
            result_addresses = {addr.address.lower() for addr in balance_updated_addresses}

            # Identify unmatched addresses
            unmatched_input_addresses = input_addresses - result_addresses

            # Log and raise error the differences
            if unmatched_input_addresses:
                error_message = (
                    f"Selected Currencies: Addresses in input but not in results: {unmatched_input_addresses}"
                )
                self.logger.error(error_message)
                self.logger.error(f"Input addresses: {input_addresses}")
                self.logger.error(f"Result addresses: {result_addresses}")
                raise ValueError(error_message)

            # Publish the balances to the response routing key
            self._message_broker.publish(
                GET_SELECTED_CURRENCIES_BALANCE_RESPONSE_ROUTING_KEY,
                GetBalancesResponse(
                    address_balances=balance_updated_addresses,
                ).model_dump_json()
            )
            self.logger.info(
                f"Selected Currencies: Published balance updates to routing key: {GET_SELECTED_CURRENCIES_BALANCE_RESPONSE_ROUTING_KEY}")

        except Exception as e:
            self.logger.error(f"Selected Currencies: An error occurred while processing the message: {str(e)}",
                              exc_info=True)
            raise e

    def topic(self) -> str:
        return GET_SELECTED_CURRENCIES_BALANCES_REQUEST_QUEUE
