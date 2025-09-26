from dataclasses import fields
from typing import List

import requests

from exchange.corporate_banking.exceptions import ThirdPartyDataParsingException
from exchange.corporate_banking.integrations.jibit.base import BaseJibitAPIClient
from exchange.corporate_banking.integrations.jibit.dto import CardDTO
from exchange.corporate_banking.models import CoBankAccount


class CobankJibitCardsList(BaseJibitAPIClient):
    request_method = 'GET'
    metric_name = 'cobanking_thirdparty_services__Jibit_getCards_'
    api_url = 'v1/accounts/{iban}/cards'

    def __init__(self, bank_account: CoBankAccount):
        super().__init__()
        self.bank_account = bank_account
        self.api_url = self.api_url.format(iban=self.bank_account.iban)

    def get_cards(self) -> List[CardDTO]:
        response = {}
        try:
            headers = self._prepare_headers()
            response = self._send_request(headers, payload={}, retry=1)
            valid_keys = [field.name for field in fields(CardDTO)]
            cards = [
                CardDTO(
                    **{k: v for k, v in item.items() if k in valid_keys},
                )
                for item in response
            ]
            return cards

        except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as e:
            # This will raise a ThirdPartyClientUnavailable exception
            self._extract_exception(e, response)

        except TypeError as e:
            raise ThirdPartyDataParsingException(
                message=f'Failed to parse Jibit cards data: {e}',
                response=response,
            ) from e
