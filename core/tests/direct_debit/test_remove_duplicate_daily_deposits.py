from django.db import IntegrityError
from django.test import TestCase, override_settings

from exchange.base.calendar import ir_now
from exchange.direct_debit.models import DailyDirectDeposit
from tests.direct_debit.helper import DirectDebitMixins


@override_settings(IS_PROD=True)
class RemoveDuplicateDailyDeposits(DirectDebitMixins, TestCase):
    fixtures = ('test_data',)

    def test_remove_command(self):
        trace_ids = [
            '010a016f-fa5b-4607-b9b2-0942728c3d53',
            '010a016f-fa5b-4607-b9b2-0942728c3d53',
        ]
        with self.assertRaises(IntegrityError):
            for trace_id in trace_ids:
                DailyDirectDeposit.objects.create(
                    trace_id=trace_id,
                    status=DailyDirectDeposit.STATUS.succeed,
                    server_date=ir_now(),
                    client_date=ir_now(),
                    transaction_amount=10000000,
                )
