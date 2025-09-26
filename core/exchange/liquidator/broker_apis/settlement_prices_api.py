from .base import BrokerBaseAPI


class SettlementPrices(BrokerBaseAPI):
    url = '/liquidation/prices'
    method = 'get'
    metric_name = 'brokerPrices'
    retry: int

    def request(self):
        return self._request()
