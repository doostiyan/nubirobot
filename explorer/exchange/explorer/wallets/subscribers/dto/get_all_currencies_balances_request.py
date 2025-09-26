from typing import List

from pydantic import BaseModel

class GetAllCurrenciesBalancesRequest(BaseModel):
    network: str
    addresses: List[str]