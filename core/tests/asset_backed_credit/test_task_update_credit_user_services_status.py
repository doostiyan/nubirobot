from unittest.mock import patch

from django.test import TestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.externals.providers.digipay import DigipayGetAccountAPI
from exchange.asset_backed_credit.externals.providers.digipay import ResponseSchema as DigipayAccountSchema
from exchange.asset_backed_credit.externals.providers.digipay.schema import ResultSchema as DigipayResultSchema
from exchange.asset_backed_credit.models import Service, UserService
from exchange.asset_backed_credit.services.user_service import update_credit_user_services_status
from tests.asset_backed_credit.helper import ABCMixins


def mock_get_request(self):
    account_number = self.url.rsplit('/', 1)[-1]
    if account_number == 'test-account-1':
        return DigipayAccountSchema(
            tracking_code='12345', status='ACTIVATED', allocated_amount=1000, result=DigipayResultSchema(status=0)
        )
    elif account_number == 'test-account-4':
        return DigipayAccountSchema(
            tracking_code='12345', status='CLOSED', allocated_amount=1000, result=DigipayResultSchema(status=0)
        )
    elif account_number == 'test-account-5':
        return DigipayAccountSchema(
            tracking_code='12345', status='CLOSED', allocated_amount=1000, result=DigipayResultSchema(status=0)
        )
    elif account_number == 'test-account-6':
        return DigipayAccountSchema(
            tracking_code='12345', status='ACTIVATED', allocated_amount=1000, result=DigipayResultSchema(status=0)
        )
    elif account_number == 'test-account-7':
        return DigipayAccountSchema(tracking_code='23456', status='FAILED', result=DigipayResultSchema(status=5363))
    elif account_number == 'test-account-8':
        return DigipayAccountSchema(tracking_code='34567', status='IN_CLOSURE', result=DigipayResultSchema(status=0))
    elif account_number == 'test-account-9':
        return DigipayAccountSchema(tracking_code='45678', status='CLOSED', result=DigipayResultSchema(status=0))


class TaskUpdateCreditUserServicesStatusTestCase(ABCMixins, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_1, _ = User.objects.get_or_create(username='test-user-1')
        cls.user_2, _ = User.objects.get_or_create(username='test-user-2')
        cls.user_3, _ = User.objects.get_or_create(username='test-user-3')
        cls.user_4, _ = User.objects.get_or_create(username='test-user-4')
        cls.user_5, _ = User.objects.get_or_create(username='test-user-5')
        cls.user_6, _ = User.objects.get_or_create(username='test-user-6')
        cls.user_7, _ = User.objects.get_or_create(username='test-user-7')

    @patch.object(DigipayGetAccountAPI, 'request', mock_get_request)
    def test_success(self):
        service_1 = self.create_service(Service.PROVIDERS.digipay, tp=Service.TYPES.credit)
        service_2 = self.create_service(Service.PROVIDERS.tara, tp=Service.TYPES.credit)
        service_3 = self.create_service(Service.PROVIDERS.vency, tp=Service.TYPES.loan)

        user_service_1 = self.create_user_service(
            self.user_1, service_1, status=UserService.STATUS.created, account_number='test-account-1'
        )
        user_service_2 = self.create_user_service(
            self.user_1, service_2, status=UserService.STATUS.created, account_number='test-account-2'
        )
        user_service_3 = self.create_user_service(
            self.user_1, service_3, status=UserService.STATUS.created, account_number='test-account-3'
        )
        user_service_4 = self.create_user_service(
            self.user_2, service_1, status=UserService.STATUS.initiated, account_number='test-account-4'
        )
        user_service_5 = self.create_user_service(
            self.user_3, service_1, status=UserService.STATUS.settled, account_number='test-account-5'
        )
        user_service_6 = self.create_user_service(
            self.user_4, service_1, status=UserService.STATUS.initiated, account_number='test-account-6'
        )
        user_service_7 = self.create_user_service(
            self.user_5, service_1, status=UserService.STATUS.created, account_number='test-account-7'
        )
        user_service_8 = self.create_user_service(
            self.user_6, service_1, status=UserService.STATUS.close_requested, account_number='test-account-8'
        )
        user_service_9 = self.create_user_service(
            self.user_7, service_1, status=UserService.STATUS.close_requested, account_number='test-account-9'
        )

        update_credit_user_services_status()

        user_service_1.refresh_from_db()
        user_service_2.refresh_from_db()
        user_service_3.refresh_from_db()
        user_service_4.refresh_from_db()
        user_service_5.refresh_from_db()
        user_service_6.refresh_from_db()
        user_service_7.refresh_from_db()
        user_service_8.refresh_from_db()
        user_service_9.refresh_from_db()

        assert user_service_1.status == UserService.STATUS.initiated
        assert user_service_2.status == UserService.STATUS.created
        assert user_service_3.status == UserService.STATUS.created
        assert user_service_4.status == UserService.STATUS.closed
        assert user_service_5.status == UserService.STATUS.settled
        assert user_service_6.status == UserService.STATUS.initiated
        assert user_service_7.status == UserService.STATUS.closed
        assert user_service_8.status == UserService.STATUS.close_requested
        assert user_service_9.status == UserService.STATUS.closed
