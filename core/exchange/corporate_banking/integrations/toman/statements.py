from dataclasses import fields
from datetime import datetime
from urllib.parse import urlencode

import requests

from exchange.corporate_banking.exceptions import ThirdPartyClientUnavailable
from exchange.corporate_banking.integrations.toman.base import BaseTomanAPIClient
from exchange.corporate_banking.integrations.toman.dto import StatementItemDTO
from exchange.corporate_banking.models import CoBankAccount


class TomanBankStatementClient(BaseTomanAPIClient):
    api_url = '/account/{bank_id}/statement/'
    request_method = 'GET'
    metric_name = 'cobanking_thirdparty_services__Toman_getStatements_'

    def __init__(self, bank_account: CoBankAccount, from_time: datetime, to_time: datetime):
        super().__init__()
        self.bank_account = bank_account
        self.from_time = from_time
        self.to_time = to_time
        self.api_url = self.api_url.format(bank_id=self.bank_account.provider_bank_id)

    def get_statements(self, page_size: int = 50):
        """
        Yields statements page by page along with the page number.
        :param page_size: How many results per page.
        """
        is_deposit = True
        page = 1
        while True:
            query_string = self._prepare_query(page, page_size, is_deposit, self.from_time, self.to_time)
            api_url = self.api_url + f'?{query_string}'

            try:
                headers = self._prepare_headers()
                response = self._send_request(api_url=api_url, headers=headers, payload={}, retry=1)
                result = response.get('results', [])

                valid_keys = [field.name for field in fields(StatementItemDTO)]
                statements = [
                    StatementItemDTO(
                        **{k: v for k, v in item.items() if k in valid_keys},
                        destination_account=self.bank_account.pk,
                        api_response=item,
                    )
                    for item in result
                ]

                yield statements, page

                if not response.get('next'):
                    break

                page += 1

            except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as e:
                raise ThirdPartyClientUnavailable(
                    code=e.__class__.__name__,
                    message=f'Toman Client Currently Unavailable: {e}',
                    status_code=e.response.status_code if e.response is not None and e.response.status_code else -1,
                ) from e

    def _prepare_query(
        self,
        page: int,
        page_size: int,
        is_deposit: bool,
        from_date: datetime,
        to_date: datetime,
    ) -> str:
        query_params = {
            'page': page,
            'page_size': page_size,
            'side': str(is_deposit).lower(),
            'created_at__gte': from_date.isoformat(),
            'created_at__lte': to_date.isoformat(),
        }
        return urlencode(query_params)
