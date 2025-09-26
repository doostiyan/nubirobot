from urllib.parse import urlencode

import requests

from exchange.corporate_banking.exceptions import ThirdPartyClientUnavailable
from exchange.corporate_banking.integrations.dto import AccountData
from exchange.corporate_banking.integrations.toman.base import BaseTomanAPIClient
from exchange.corporate_banking.integrations.toman.dto import PaginationDTO


class CobankTomanAccountsList(BaseTomanAPIClient):
    request_method = 'GET'
    metric_name = 'cobanking_thirdparty_services__Toman_getAccounts_'

    def get_bank_accounts(self, page: int = 1, page_size: int = 50) -> PaginationDTO[AccountData]:
        query_string = self._prepare_query(page, page_size)
        self.api_url = f'/account/?{query_string}'

        try:
            headers = self._prepare_headers()
            response = self._send_request(headers, payload={}, retry=1)
            accounts = []
            for account in response.get('results', []):
                accounts.append(AccountData.from_toman(account))

            return PaginationDTO[AccountData](
                count=response.get('count', 0),
                next=response.get('next'),
                previous=response.get('previous'),
                results=accounts,
            )

        except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as e:
            raise ThirdPartyClientUnavailable(
                code=e.__class__.__name__,
                message=f'Client Currently Unavailable: {e}',
                status_code=e.response.status_code if e.response is not None and e.response.status_code else -1,
            ) from e

    def _prepare_query(self, page: int, page_size: int) -> str:
        query_params = {
            'page': page,
            'page_size': page_size,
        }
        return urlencode(query_params)
