from json import JSONDecodeError

import requests

from exchange.corporate_banking.exceptions import ThirdPartyClientUnavailable
from exchange.corporate_banking.integrations.toman.base import BaseTomanAPIClient
from exchange.corporate_banking.integrations.toman.dto import RefundData
from exchange.corporate_banking.models import CoBankRefund


class RefundStatementTomanClient(BaseTomanAPIClient):
    payload = {}
    api_url = '/revert'
    metric_name = 'cobanking_thirdparty_services__Toman_'

    def refund_statement(self, refund_request: CoBankRefund) -> RefundData:
        """
        scope: digital_banking.revert.create
        The response should be like this:
        https://docs.tomanpay.net/corporate_banking/?python#4-reverts
        {
            "id": 1,
            "transfer": {
                "uuid": "a524ffb9-34c3-4903-be9b-e82ec922b45f",
                "bank_id": 15,
                "account": 84,
                "account_number_source": "826-810-4704696-2",
                "iban_source": "IR300560082681004704696002",
                "transfer_type": 0,
                "status": 14,
                "amount": 1100,
                "iban_destination": "IR300560082681004704696002",
                "account_number_destination": "826-810-4704696-2",
                "card_number_destination": null,
                "description": null,
                "first_name": null,
                "last_name": null,
                "reason": 6,
                "tracker_id": "c1c995ef-fc23-4656-aa13-e25996326f9b",
                "created_at": "2025-03-12T10:54:54.231888Z",
                "created_by": 60,
                "creation_type": 20,
                "bank_id_destination": 15,
                "follow_up_code": null,
                "payment_id": null,
                "receipt_link": "https://settlement.toman.ir/receipt/cb/a524ffb9-34c3-4903-be9b-e82ec922b45f:9ead9200dcfc2e0701be67b5cfd7b3d489c1fb6fd59f8ae29f073d3ee7c29a35",
                "attachment_count": 0,
                "attachments": []
            },
            "statement_id": 941,
            "created_at": "2025-04-26T01:24:56.801425Z",
            "updated_at": "2025-04-26T01:24:56.801442Z",
            "status": 1,
            "account": 1,
            "created_by": 60,
            "partner": 1
        }
        """
        self.metric_name = 'cobanking_thirdparty_services__Toman_requestRefund_'
        self.api_url = f'{self.api_url}/'
        self.payload = {
            'account': refund_request.statement.destination_account.provider_bank_id,
            'statement_id': refund_request.statement.provider_statement_id,
        }
        self.request_method = 'POST'
        return self._send_refund_request()

    def check_refund_status(self, refund_request: CoBankRefund) -> RefundData:
        """
        scope: digital_banking.revert.read
        The response should be like this:
        https://docs.tomanpay.net/corporate_banking/?python#4-2-get-revert-by-account-and-statement-id
        """
        self.metric_name = 'cobanking_thirdparty_services__Toman_checkRefundStatus_'

        account_id = refund_request.statement.destination_account.provider_bank_id
        statement_id = refund_request.statement.provider_statement_id
        self.api_url = f'{self.api_url}/{account_id}/{statement_id}/'

        self.request_method = 'GET'
        return self._send_refund_request()

    def _send_refund_request(self) -> RefundData:
        try:
            headers = self._prepare_headers()
            response = self._send_request(
                api_url=self.api_url,
                headers=headers,
                payload=self.payload,
                retry=1,
                is_json=True,
            )
            return RefundData.from_data(response)
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as e:
            error_message = f'Client Currently Unavailable: {e}'
            status_code = -1

            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                try:
                    response_body = e.response.json()
                    error_message += f' | Response body (JSON): {response_body}'
                except (JSONDecodeError, requests.exceptions.JSONDecodeError):
                    response_body = e.response.text
                    error_message += f' | Response body (Text): {response_body}'

            raise ThirdPartyClientUnavailable(
                code=e.__class__.__name__,
                message=error_message,
                status_code=status_code,
            ) from e
