from exchange.liquidator.broker_apis import SettlementServiceStatus
from exchange.liquidator.errors import BrokerAPIError


class ExternalBrokerStatusChecker:
    @classmethod
    def run(cls):
        try:
            result = SettlementServiceStatus().request()
        except BrokerAPIError:
            result = False

        is_active_currently = SettlementServiceStatus.is_active()

        if is_active_currently and not result:
            # deactivate unlimitedly so that it only gets activated after available status is returned by service
            SettlementServiceStatus.deactivate_broker(for_limited_time=False)

        elif not is_active_currently and result and not SettlementServiceStatus.is_failure_limit_reached():
            # only activate if service is not deactivated because of too many failures.
            # Otherwise, it might be reactivated instantly after deactivated due to failures.
            SettlementServiceStatus.activate_broker()
