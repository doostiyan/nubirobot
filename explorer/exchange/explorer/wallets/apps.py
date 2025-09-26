import sys

from django.apps import AppConfig

from exchange.explorer.basis.message_broker.factory import MessageBrokerFactory
from exchange.explorer.wallets.subscribers.bindings import SelectedCurrenciesNewBalanceBinding, \
    AllCurrenciesNewBalanceBinding


class WalletsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'exchange.explorer.wallets'

    def ready(self):
        if len(sys.argv) > 1 and sys.argv[1] == "start_subscribers":
            message_broker = MessageBrokerFactory.get_instance()

            from exchange.explorer.wallets.subscribers.all_currencies_balances_request_subscriber import \
                AllCurrenciesBalancesRequestSubscriber

            from exchange.explorer.wallets.subscribers.selected_currencies_balances_request_subscriber import \
                SelectedCurrenciesBalancesRequestSubscriber

            message_broker.register_subscriber(AllCurrenciesBalancesRequestSubscriber(message_broker))
            message_broker.register_subscriber(SelectedCurrenciesBalancesRequestSubscriber(message_broker))

            message_broker.add_custom_config(
                SelectedCurrenciesNewBalanceBinding(),
                AllCurrenciesNewBalanceBinding()
            )
