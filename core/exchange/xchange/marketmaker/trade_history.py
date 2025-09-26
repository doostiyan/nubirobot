import datetime
from typing import List

from exchange.xchange.marketmaker.client import Client
from exchange.xchange.types import MarketMakerTradeHistoryItem


class GetTradeHistory:
    def __init__(self, from_date: datetime.datetime, to_date: datetime.datetime, page_size: int = 1000):
        self.from_date = from_date
        self.to_date = to_date
        self.page_size = page_size

    def get_trades_history(
        self,
    ) -> (bool, List[MarketMakerTradeHistoryItem]):
        data = {
            'fromTimestamp': str(int(self.from_date.astimezone(tz=datetime.timezone.utc).timestamp() * 1000)),
            'toTimestamp': str(int(self.to_date.astimezone(tz=datetime.timezone.utc).timestamp() * 1000)),
            'pageSize': self.page_size,
        }
        response = Client().request(Client.Method.GET, '/xconvert/history', query_params=data)
        converts = response['result']['converts']
        converts_obj = [MarketMakerTradeHistoryItem(**convert, response=convert) for convert in converts]
        has_next = response['result']['hasNextPage']
        return has_next, converts_obj
