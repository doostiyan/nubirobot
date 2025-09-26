from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from exchange.staking.tasks import creating_an_instant_cancellation_request_task


class CreateInstantCancellationRequestTests(TestCase):
    @patch('exchange.staking.tasks.add_and_apply_instant_end_request')
    def test_create_instant_cancellation_request_successfully_calls_create_instant_end_service(
        self, mock_instant_end_service
    ):
        creating_an_instant_cancellation_request_task(
            user_id=123,
            plan_id=321,
            amount='12.12',
        )

        mock_instant_end_service.assert_called_once_with(
            user_id=123,
            plan_id=321,
            amount=Decimal('12.12'),
            created_by_admin=True,
        )
