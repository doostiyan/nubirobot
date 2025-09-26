import requests

from exchange.corporate_banking.exceptions import ThirdPartyDataParsingException
from exchange.corporate_banking.integrations.dto import AccountData
from exchange.corporate_banking.integrations.jibit.base import BaseJibitAPIClient
from exchange.corporate_banking.integrations.toman.dto import PaginationDTO


class CobankJibitAccountsList(BaseJibitAPIClient):
    request_method = 'GET'
    metric_name = 'cobanking_thirdparty_services__Jibit_getAccounts_'
    api_url = 'v1/accounts/'

    def get_bank_accounts(self, page=1) -> PaginationDTO[AccountData]:
        response = {}
        try:
            headers = self._prepare_headers()
            response = self._send_request(headers, payload={}, retry=1)
            return PaginationDTO[AccountData](
                count=len(response or []),
                next=None,
                previous=None,
                results=[AccountData.from_jibit(item) for item in response],
            )

        except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as e:
            # This will raise a ThirdPartyClientUnavailable exception
            self._extract_exception(e, response)

        except TypeError as e:
            raise ThirdPartyDataParsingException(
                message=f'Failed to parse Jibit account data: {e}',
                response=response,
            ) from e
