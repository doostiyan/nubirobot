from exchange.liquidator.broker_apis.base import BrokerBaseAPI
from exchange.liquidator.errors import BrokerAPIError


class SettlementServiceStatus(BrokerBaseAPI):
    url = '/liquidation/status'
    method = 'get'
    metric_name = 'brokerServiceStatus'
    retry: int = 0

    def request(self):
        response = self._request()  # might raise exception
        return response.get('status') == 'available'
