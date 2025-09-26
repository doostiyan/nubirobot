from typing import List

from pydantic import BaseModel

from exchange.blockchain.api.general.dtos.dtos import SelectedCurrenciesBalancesRequest

class GetSelectedCurrenciesBalancesRequest(BaseModel):
    addresses: List[SelectedCurrenciesBalancesRequest]
    network: str
