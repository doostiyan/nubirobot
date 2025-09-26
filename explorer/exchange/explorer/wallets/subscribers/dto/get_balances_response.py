from typing import List

from pydantic import BaseModel

from exchange.blockchain.api.general.dtos.dtos import NewBalancesV2


class GetBalancesResponse(BaseModel):
    address_balances: List[NewBalancesV2]