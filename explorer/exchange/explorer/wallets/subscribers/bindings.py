from exchange.explorer.basis.message_broker.adapters.rabbitmq_binding_config import RabbitmqBindingConfig
from exchange.explorer.wallets.subscribers.topics import GET_SELECTED_CURRENCIES_BALANCES_REQUEST_QUEUE, GET_ALL_CURRENCIES_BALANCES_REQUEST_QUEUE, GET_SELECTED_CURRENCIES_BALANCES_REQUEST_ROUTING_KEY, \
    GET_ALL_CURRENCIES_BALANCES_REQUEST_ROUTING_KEY


class SelectedCurrenciesNewBalanceBinding(RabbitmqBindingConfig):
    def routing_key(self) -> str:
        return GET_SELECTED_CURRENCIES_BALANCES_REQUEST_ROUTING_KEY

    def queue(self) -> str:
        return GET_SELECTED_CURRENCIES_BALANCES_REQUEST_QUEUE


class AllCurrenciesNewBalanceBinding(RabbitmqBindingConfig):
    def routing_key(self) -> str:
        return GET_ALL_CURRENCIES_BALANCES_REQUEST_ROUTING_KEY

    def queue(self) -> str:
        return GET_ALL_CURRENCIES_BALANCES_REQUEST_QUEUE