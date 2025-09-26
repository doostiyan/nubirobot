from typing import Any, Dict, List, Optional

from django.utils.timezone import now
from rest_framework import status

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import Service, UserService
from exchange.base.serializers import serialize_choices, serialize_decimal
from tests.asset_backed_credit.helper import ABCMixins, APIHelper


class UserServiceListAPITest(APIHelper, ABCMixins):
    URL = '/asset-backed-credit/user-services/list'

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self._set_client_credentials(self.user.auth_token.key)
        self.active_services = [
            self.create_service(tp=tp)
            for tp in [
                Service.TYPES.credit,
                Service.TYPES.loan,
                Service.TYPES.debit,
            ]
        ]
        self.inactive_service = self.create_service(tp=Service.TYPES.credit, is_active=False)

    def _create_user_services(self, services: List[Service]):
        user_services = []
        for service in services:
            if service.tp == Service.TYPES.loan:
                user_services.append(self.create_loan_user_service(self.user, service=service))
                user_services.append(self.create_loan_user_service(self.user, service=service, closed_at=now()))
            else:
                user_services.append(self.create_user_service(self.user, service=service))
                user_services.append(self.create_user_service(self.user, service=service, closed_at=now()))
        return user_services

    def _check_api_result(self, response: Dict[str, Any], user_services: Optional[List[UserService]]):
        assert 'userServices' in response
        assert 'result' in response['userServices']
        assert len(response['userServices']['result']) == len(user_services)
        us1 = sorted(response['userServices']['result'], key=lambda x: x['id'])
        us2 = sorted(user_services, key=lambda x: x.id)
        for data, user_service in zip(us1, us2):
            assert data['id'] == user_service.id
            assert data['status'] == 'initiated'
            assert 'service' in data
            assert data['service']['provider'] == serialize_choices(Service.PROVIDERS, user_service.service.provider)
            assert data['service']['type'] == serialize_choices(Service.TYPES, user_service.service.tp)
            assert data['currentDebt'] == serialize_decimal(user_service.current_debt)
            assert data['initialDebt'] == serialize_decimal(user_service.initial_debt)
            assert data['service']['fee'] == serialize_decimal(user_service.service.fee)
            assert data['service']['interest'] == serialize_decimal(user_service.service.interest)
            if user_service.principal:
                assert data['principal'] == serialize_decimal(user_service.principal)
            else:
                assert data['principal'] is None
            if user_service.total_repayment:
                assert data['totalRepayment'] == serialize_decimal(user_service.total_repayment)
            else:
                assert data['totalRepayment'] is None
            if user_service.installment_amount:
                assert data['installmentAmount'] == serialize_decimal(user_service.installment_amount)
            else:
                assert data['installmentAmount'] is None
            if user_service.installment_period:
                assert data['installmentPeriod'] == user_service.installment_period
            else:
                assert data['installmentPeriod'] is None

    def test_empty_list(self):
        response = self._get_request()
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_api_result(res, [])

    def test_all_user_service(self):
        user_services = self._create_user_services(self.active_services)
        response = self._get_request()
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_api_result(res, user_services)

    def test_filter_by_provider(self):
        user_services = self._create_user_services(self.active_services)
        # failed
        response = self._get_request(url=self.URL + '?provider=not-tara')
        self._check_response(response=response, status_code=status.HTTP_400_BAD_REQUEST, status_data='failed')
        # success
        response = self._get_request(url=self.URL + '?provider=tara')
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_api_result(res, user_services)

    def test_filter_by_service_type(self):
        user_services = self._create_user_services(self.active_services[0:1])
        # failed
        response = self._get_request(url=self.URL + '?type=not-credit')
        self._check_response(response=response, status_code=status.HTTP_400_BAD_REQUEST, status_data='failed')
        # success
        response = self._get_request(url=self.URL + '?type=loan')
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_api_result(res, [])

        response = self._get_request(url=self.URL + '?type=credit')
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_api_result(res, user_services)

    def test_filter_by_status(self):
        user_services = self._create_user_services([self.active_services[1], self.inactive_service])
        # failed
        response = self._get_request(url=self.URL + '?status=not-closed')
        self._check_response(response=response, status_code=status.HTTP_400_BAD_REQUEST, status_data='failed')
        # success
        response = self._get_request(url=self.URL + '?status=inactive')
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_api_result(res, [user_services[1], user_services[3]])

    def test_pagination(self):
        user_services = self._create_user_services(self.active_services)
        # success
        response = self._get_request(url=self.URL + '?page=2&pageSize=2')
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        self._check_api_result(res, user_services[2:4])
        assert 'hasNext' in res['userServices']
        assert res['userServices']['hasNext']
