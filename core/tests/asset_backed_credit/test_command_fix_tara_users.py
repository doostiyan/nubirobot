from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from exchange.asset_backed_credit.management.commands.abc_fix_tara_discharged_user_services import Command
from exchange.asset_backed_credit.models import OutgoingAPICallLog, UserService
from tests.asset_backed_credit.helper import ABCMixins


class TestFixTaraUsersCommand(ABCMixins, TestCase):
    def setUp(self):
        service = self.create_service()
        self.us1 = self.create_user_service(service=service, initial_debt=1000, current_debt=1000)
        self.user1 = self.us1.user
        self.us2 = self.create_user_service(service=service, initial_debt=2000, current_debt=2000)

        OutgoingAPICallLog.objects.create(
            status=OutgoingAPICallLog.STATUS.success,
            api_url='https://stage.tara-club.ir/club/api/v1/limited/account/transaction/discharge/to/774',
            request_body={
                'amount': '1000',
            },
            response_code=200,
            user_service=self.us1,
        )

    @patch(
        'exchange.asset_backed_credit.services.providers.dispatcher.TaraCreditAPIs.get_available_balance', lambda _: 0
    )
    def testCommand(self):
        with patch.object(Command, "USER_SERVICE_IDS", [self.us1.id]):
            call_command('abc_fix_tara_discharged_user_services')

        us1 = UserService.objects.get(id=self.us1.id)
        assert us1.status == UserService.STATUS.closed
        assert us1.current_debt == 0

        us2 = UserService.objects.get(id=self.us2.id)
        assert us2.status == UserService.STATUS.initiated
        assert us2.current_debt == 2000
