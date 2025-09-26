from dataclasses import fields
from datetime import datetime, timezone
from urllib.parse import urlencode

import requests

from exchange.corporate_banking.exceptions import ThirdPartyClientUnavailable
from exchange.corporate_banking.integrations.jibit.base import BaseJibitAPIClient
from exchange.corporate_banking.integrations.jibit.dto import StatementItemDTO
from exchange.corporate_banking.models import CoBankAccount


class JibitBankStatementClient(BaseJibitAPIClient):
    api_url = 'v1/orders/aug-statement/{iban}/variz/waitingForVerify'
    request_method = 'GET'
    metric_name = 'cobanking_thirdparty_services__Jibit_getStatements_'

    def __init__(self, bank_account: CoBankAccount, from_time: datetime, to_time: datetime):
        super().__init__()
        self.bank_account = bank_account
        self.from_time = from_time
        self.to_time = to_time
        self.api_url = self.api_url.format(iban=self.bank_account.iban)

    def get_statements(self, page_size: int = 50):
        """
        Yields statements page by page along with the page number.
        :param page_size: Number of results per page.
        """
        page = 0
        while True:
            query_string = self._prepare_query(page, page_size, self.from_time, self.to_time)
            api_url = self.api_url + f'?{query_string}'

            try:
                headers = self._prepare_headers()
                response = self._send_request(api_url=api_url, headers=headers, payload={}, retry=1)
                elements = response.get('elements', [])

                valid_keys = [field.name for field in fields(StatementItemDTO)]
                statements = [
                    StatementItemDTO(
                        **{k: v for k, v in element.items() if k in valid_keys},
                        destinationAccount=self.bank_account.pk,
                        apiResponse=element,
                    )
                    for element in elements
                ]

                yield statements, page

                if not response.get('hasNext'):
                    break

                page += 1

            except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as e:
                raise ThirdPartyClientUnavailable(
                    code=e.__class__.__name__,
                    message=f'Jibit Client Currently Unavailable: {e}',
                    status_code=e.response.status_code if e.response is not None and e.response.status_code else -1,
                ) from e

    def _prepare_query(
        self,
        page: int,
        page_size: int,
        from_date: datetime,
        to_date: datetime,
    ) -> str:
        query_params = {
            'createdAtFrom': from_date.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
            'createdAtTo': to_date.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
            'pageNumber': page,
            'pageSize': page_size,
        }
        return urlencode(query_params)
