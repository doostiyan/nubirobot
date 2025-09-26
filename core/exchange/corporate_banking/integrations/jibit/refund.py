from dataclasses import fields
from typing import Callable, Union

import requests

from exchange.base.logging import report_exception
from exchange.corporate_banking.exceptions import ThirdPartyClientUnavailable
from exchange.corporate_banking.integrations.jibit.base import BaseJibitAPIClient
from exchange.corporate_banking.integrations.jibit.dto import StatementItemDTO, TransferDTO
from exchange.corporate_banking.models import CoBankStatement


class RefundStatementJibitClient(BaseJibitAPIClient):
    """Client for handling Jibit refund operations on bank statements."""

    _base_api_url = '/v1/orders/aug-statement/{iban}/variz/{reference_number}/{action}'
    _base_metric_name = 'cobanking_thirdparty_services__Jibit_'

    def __init__(self, statement: CoBankStatement):
        super().__init__()
        self.statement = statement

    def refund_statement(self) -> StatementItemDTO:
        """
        Request a full refund for the statement.

        Returns:
            StatementItemDTO: The refund response data

        Raises:
            ThirdPartyClientUnavailable: If the API request fails
            ValueError: If statement validation fails
        """
        self.metric_name = f'{self._base_metric_name}requestRefund_'
        self.api_url = self._base_api_url.format(
            iban=self.statement.destination_account.iban,
            reference_number=self.statement.provider_statement_id,
            action='full-refund',
        )
        self.request_method = 'POST'

        return self._send_refund_request(self._parse_statement_response)

    def check_refund_status(self) -> TransferDTO:
        """
        Check the status of a refund request.

        Returns:
            TransferDTO: The refund status data

        Raises:
            ThirdPartyClientUnavailable: If the API request fails
            ValueError: If statement validation fails
        """
        self.metric_name = f'{self._base_metric_name}checkRefundStatus_'
        self.api_url = self._base_api_url.format(
            iban=self.statement.destination_account.iban,
            reference_number=self.statement.provider_statement_id,
            action='refund',
        )
        self.request_method = 'GET'

        return self._send_refund_request(self._parse_status_check_response)

    def make_statement_failed(self) -> StatementItemDTO:
        """
        Mark a statement as failed.

        Returns:
            StatementItemDTO: The failure response data

        Raises:
            ThirdPartyClientUnavailable: If the API request fails
            ValueError: If statement validation fails
        """
        self.metric_name = f'{self._base_metric_name}requestFail_'
        self.api_url = self._base_api_url.format(
            iban=self.statement.destination_account.iban,
            reference_number=self.statement.provider_statement_id,
            action='fail',
        )
        self.request_method = 'GET'

        return self._send_refund_request(self._parse_statement_response)

    def _send_refund_request(self, parser: Callable) -> Union[StatementItemDTO, TransferDTO]:
        """Send the refund request to Jibit API and parse as StatementItemDTO."""
        try:
            headers = self._prepare_headers()
            response = self._send_request(api_url=self.api_url, headers=headers, payload={}, retry=1)
            return parser(response)
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout, requests.RequestException) as e:
            raise self._build_client_unavailable_exception(e)
        except Exception as e:
            report_exception()
            raise self._build_client_unavailable_exception(e)

    def _parse_statement_response(self, response: dict) -> StatementItemDTO:
        """Parse the API response as StatementItemDTO"""

        valid_keys = {field.name for field in fields(StatementItemDTO)}
        filtered_response = {k: v for k, v in response.items() if k in valid_keys}
        filtered_response.update(
            {
                'destinationAccount': self.statement.destination_account.pk,
                'apiResponse': response,
            },
        )
        return StatementItemDTO(**filtered_response)

    def _parse_status_check_response(self, response: dict) -> TransferDTO:
        """Parse the API response as TransferDTO"""
        return TransferDTO.from_data(response)

    def _build_client_unavailable_exception(self, error: Exception) -> ThirdPartyClientUnavailable:
        """
        Build a ThirdPartyClientUnavailable exception from the original error.
        Sample api response on error state:
        {
            'fingerprint': '12345',
            'errors': [
                {
                    'code': 'Authentication.failed, Internal.error, Not.found, Bad.request',
                    'message': 'description of the error'
                }
            ]
        }
        """
        status_code = -1
        error_details = str(error)
        error_code = error.__class__.__name__

        if not hasattr(error, 'response') or error.response is None:
            return ThirdPartyClientUnavailable(
                code=error_code,
                message=f'Jibit API currently unavailable: {error_details}',
                status_code=status_code,
            )

        status_code = error.response.status_code

        if not hasattr(error.response, 'json'):
            return ThirdPartyClientUnavailable(
                code=error_code,
                message=f'Jibit API currently unavailable: {error_details}',
                status_code=status_code,
            )

        try:
            error_json = error.response.json()
            if not isinstance(error_json, dict):
                return ThirdPartyClientUnavailable(
                    code=error_code,
                    message=f'Jibit API currently unavailable: {error_details}',
                    status_code=status_code,
                )

            # Extract error details from Jibit API error format
            if 'errors' in error_json and isinstance(error_json['errors'], list) and error_json['errors']:
                the_error = error_json['errors'][0]
                if isinstance(the_error, dict):
                    error_code = the_error.get('code', error_code)
                    error_details = the_error.get('message', error_details)
            elif 'message' in error_json:
                error_details = error_json['message']

        except (ValueError, TypeError, KeyError):
            pass

        return ThirdPartyClientUnavailable(
            code=error_code,
            message=f'Jibit API currently unavailable: {error_details}',
            status_code=status_code,
        )
