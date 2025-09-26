import base64
from decimal import Decimal
from unittest.mock import patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import (
    Card,
    CardTransactionFeeSetting,
    DebitSettlementTransaction,
    IncomingAPICallLog,
    Service,
    UserFinancialServiceLimit,
    UserService,
)
from exchange.asset_backed_credit.models.debit import CardSetting, CardTransactionLimit
from exchange.asset_backed_credit.services.debit.bank_switch import get_service
from exchange.asset_backed_credit.services.providers.provider import BasicAuthenticationSupportProvider
from exchange.asset_backed_credit.services.providers.provider_manager import provider_manager
from exchange.asset_backed_credit.types import bank_switch_status_code_mapping
from exchange.base.calendar import ir_now
from exchange.base.constants import ZERO
from exchange.base.models import Currencies, Settings
from exchange.wallet.models import Wallet as ExchangeWallet
from tests.asset_backed_credit.helper import ABCMixins
from tests.base.utils import check_response


class TestTransactionAPI(APITestCase, ABCMixins):

    @classmethod
    def setUpTestData(cls) -> None:
        cls.url = '/asset-backed-credit/v1/debit/transaction'
        cls.provider = BasicAuthenticationSupportProvider('pnovin', ['127.0.0.1'], 1, 1, 'pnovin', 'passw0rd', '', '')
        cls.user = User.objects.get(pk=201)
        cls.user.national_code = '0921234567'
        cls.user.save()
        Settings.set('abc_debit_card_initiate_transaction_enabled', 'yes')
        Settings.set('abc_debit_wallet_enabled', 'yes')

    def setUp(self) -> None:
        provider_manager_patch = patch.object(
            provider_manager,
            'providers',
            new=[self.provider],
        )
        provider_manager_patch.start()
        self.service = self.create_service(contract_id='123456', provider=self.provider.id, tp=Service.TYPES.debit)
        self.service_limit = UserFinancialServiceLimit.set_service_limit(self.service, max_limit=10_000_000_0)
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.debit, min_limit=10_000)
        self.card_level_settings = CardSetting.objects.create(
            level=1,
            per_transaction_amount_limit=20_000_000,
            daily_transaction_amount_limit=100_000_000,
            monthly_transaction_amount_limit=1_000_000_000,
            cashback_percentage=0,
        )
        CardTransactionFeeSetting.objects.create(
            level=self.card_level_settings,
            min_amount=100_0,
            max_amount=1_000_000_0,
            fee_percentage=1,
        )
        get_service.cache_clear()

    def tearDown(self) -> None:
        DebitSettlementTransaction.objects.all().delete()
        Card.objects.all().delete()
        UserService.objects.all().delete()
        IncomingAPICallLog.objects.all().delete()
        CardTransactionLimit.objects.all().delete()
        CardTransactionFeeSetting.objects.all().delete()

    def test_basic_authentication_no_header_404(self):
        response = self.client.post(self.url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

        api_log = IncomingAPICallLog.objects.all().first()
        assert api_log is None

    def test_basic_authentication_wrong_username_404(self):
        username = 'test@nobitex.com'
        password = ''
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        response = self.client.post(
            self.url,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

        api_log = IncomingAPICallLog.objects.all().first()
        assert api_log is None

    def test_basic_authentication_wrong_password_404(self):
        username = 'pnovin'
        password = 'wrong'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        response = self.client.post(
            self.url,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

        api_log = IncomingAPICallLog.objects.all().first()
        assert api_log is None

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_basic_authentication_correct_credentials_success(self, get_provider_mock):
        get_provider_mock.return_value = self.provider

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        response = self.client.post(
            self.url,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        data = response.json()
        assert data['RespCode'] == bank_switch_status_code_mapping['UNAUTHORIZED_TRANSACTION']

        api_log = IncomingAPICallLog.objects.all().first()
        assert api_log is not None
        assert api_log.api_url == '/asset-backed-credit/v1/debit/transaction'
        assert api_log.request_body == {}
        assert api_log.response_body == data
        assert api_log.response_code == status.HTTP_200_OK
        assert api_log.status == IncomingAPICallLog.STATUS.failure
        assert api_log.provider == self.provider.id
        assert api_log.service == Service.TYPES.debit
        assert api_log.user_service is None
        assert api_log.user is None

    @patch('django_ratelimit.decorators.is_ratelimited', return_value=True)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_provider_rate_limit_error(self, get_provider_mock, _):
        get_provider_mock.return_value = self.provider

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        response = self.client.post(
            self.url,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        check_response(
            response=response,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            status_data='failed',
            code='TooManyRequests',
            message='Too many requests',
        )

        api_log = IncomingAPICallLog.objects.all().first()
        assert api_log is not None
        assert api_log.api_url == '/asset-backed-credit/v1/debit/transaction'
        assert api_log.request_body == {}
        assert api_log.response_body == response.json()
        assert api_log.response_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert api_log.status == IncomingAPICallLog.STATUS.failure
        assert api_log.provider == self.provider.id
        assert api_log.service == Service.TYPES.debit
        assert api_log.user_service is None
        assert api_log.user is None

    @override_settings(RATELIMIT_ENABLE=True)
    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_user_rate_limit_error(self, get_provider_mock):
        get_provider_mock.return_value = self.provider

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1403/04/31',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': 1000,
            'RID': 'rid-123456',
        }

        responses = [
            self.client.post(self.url, data=request_data, HTTP_AUTHORIZATION=f'Basic {credentials}') for _ in range(10)
        ]

        assert any([response.status_code == status.HTTP_429_TOO_MANY_REQUESTS for response in responses])

        api_log = IncomingAPICallLog.objects.all().last()
        assert api_log is not None
        assert api_log.api_url == '/asset-backed-credit/v1/debit/transaction'
        api_log.request_body['Price'] = int(api_log.request_body['Price'])
        assert api_log.request_body == request_data
        assert api_log.response_body == responses[-1].json()
        assert api_log.response_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert api_log.status == IncomingAPICallLog.STATUS.failure
        assert api_log.provider == self.provider.id
        assert api_log.service == Service.TYPES.debit
        assert api_log.user_service is not None
        assert api_log.user is not None

    def test_transaction_invalid_ip_404(self):
        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        data = {
            'MTI': '0200',
            'PAN': '6063909010102323',
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': 1000,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

        api_log = IncomingAPICallLog.objects.all().first()
        assert api_log is None

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_service_not_found_404(self, get_provider_mock):
        self.provider.id = -1
        get_provider_mock.return_value = self.provider

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': 1000,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

        api_log = IncomingAPICallLog.objects.all().first()
        assert api_log is None

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_wrong_field_name(self, get_provider_mock):
        get_provider_mock.return_value = self.provider

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MIT': '0200',
            'PAN': pan,
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': 1000,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['UNAUTHORIZED_TRANSACTION']

        self.assert_incoming_api_log(request_data, response_data)

    def test_transaction_wrong_field_name_with_invalid_ip(self):
        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MIT': '0200',
            'PAN': pan,
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': 1000,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['UNAUTHORIZED_TRANSACTION']

        api_log = IncomingAPICallLog.objects.all().first()

        assert api_log is not None
        assert api_log.api_url == '/asset-backed-credit/v1/debit/transaction'
        api_log.request_body['Price'] = int(api_log.request_body['Price'])
        assert api_log.request_body == request_data
        assert api_log.response_body == response_data
        assert api_log.response_code == status.HTTP_200_OK
        assert api_log.status == IncomingAPICallLog.STATUS.failure
        assert api_log.provider is None
        assert api_log.service is None
        assert api_log.user_service is None
        assert api_log.user is None

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_missing_pan_field(self, get_provider_mock):
        get_provider_mock.return_value = self.provider

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': 1000,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['UNAUTHORIZED_TRANSACTION']

        api_log = IncomingAPICallLog.objects.all().first()

        assert api_log is not None
        assert api_log.api_url == '/asset-backed-credit/v1/debit/transaction'
        api_log.request_body['Price'] = int(api_log.request_body['Price'])
        assert api_log.request_body == request_data
        assert api_log.response_body == response_data
        assert api_log.response_code == status.HTTP_200_OK
        assert api_log.status == IncomingAPICallLog.STATUS.failure
        assert api_log.provider == self.provider.id
        assert api_log.service == Service.TYPES.debit
        assert api_log.user_service is None
        assert api_log.user is None

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_wrong_date_and_time(self, get_provider_mock):
        get_provider_mock.return_value = self.provider

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '14021117',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': 1000,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['UNAUTHORIZED_TRANSACTION']

        self.assert_incoming_api_log(request_data, response_data)
        IncomingAPICallLog.objects.all().delete()

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1402/11/17',
            'Time': '15:00',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': 1000,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['UNAUTHORIZED_TRANSACTION']

        self.assert_incoming_api_log(request_data, response_data)

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_card_inactive_error(self, get_provider_mock):
        get_provider_mock.return_value = self.provider

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        card = self.create_card(pan=pan, user_service=user_service, status=Card.STATUS.requested)

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': 1000,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['CARD_INACTIVE']

        self.assert_incoming_api_log(request_data, response_data)
        IncomingAPICallLog.objects.all().delete()

        card.status = Card.STATUS.registered

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['CARD_INACTIVE']

        self.assert_incoming_api_log(request_data, response_data)

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_card_expired_error(self, get_provider_mock):
        get_provider_mock.return_value = self.provider

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, status=Card.STATUS.expired)

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': 1000,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['CARD_EXPIRED']

        self.assert_incoming_api_log(request_data, response_data)

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_card_restricted_error(self, get_provider_mock):
        get_provider_mock.return_value = self.provider

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, status=Card.STATUS.restricted)

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': 1000,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['CARD_RESTRICTED']

        self.assert_incoming_api_log(request_data, response_data)

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_balance_not_enough(self, get_provider_mock):
        get_provider_mock.return_value = self.provider

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': 10000,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['BALANCE_NOT_ENOUGH']

        self.assert_incoming_api_log(request_data, response_data)

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_above_margin_ratio_success(self, get_provider_mock):
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            user=self.user, currency=Currencies.rls, amount=Decimal('1_050_0'), tp=ExchangeWallet.WALLET_TYPE.debit
        )

        # create credit user service just to make sure it's debt is excluded in check margin ratio logic
        credit_service = self.create_service()
        self.create_user_service(self.user, service=credit_service, initial_debt=100_000_0)

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': 10000,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        self.assert_incoming_api_log(request_data, response_data)

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_above_margin_ratio_on_credit_wallet_success(self, get_provider_mock):
        Settings.set('abc_debit_wallet_enabled', 'no')

        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            user=self.user, currency=Currencies.rls, amount=Decimal('1_300_0'), tp=ExchangeWallet.WALLET_TYPE.credit
        )

        # create credit user service just to make sure it's debt is excluded in check margin ratio logic
        credit_service = self.create_service()
        self.create_user_service(self.user, service=credit_service, initial_debt=100_000_0)

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': 10000,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        self.assert_incoming_api_log(request_data, response_data)

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_below_margin_ratio_failed(self, get_provider_mock):
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            user=self.user, currency=Currencies.rls, amount=Decimal('1_049_0'), tp=ExchangeWallet.WALLET_TYPE.debit
        )

        # create credit user service just to make sure it's debt is excluded in check margin ratio logic
        credit_service = self.create_service()
        self.create_user_service(self.user, service=credit_service, initial_debt=100_000_0)

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': 10000,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['BALANCE_NOT_ENOUGH']

        self.assert_incoming_api_log(request_data, response_data)

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_initiate_success_and_initiate_duplicate_transaction(self, get_provider_mock):
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            user=self.user, currency=Currencies.rls, amount=Decimal('13000'), tp=ExchangeWallet.WALLET_TYPE.debit
        )

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        DebitSettlementTransaction.objects.create(
            user_service=user_service,
            amount=1000,
            status=DebitSettlementTransaction.STATUS.unknown_rejected,
            trace_id='trace-rejected',
            terminal_id='terminal-id',
        )
        DebitSettlementTransaction.objects.create(
            user_service=user_service,
            amount=1000,
            status=DebitSettlementTransaction.STATUS.confirmed,
            transaction_datetime=ir_now(),
            trace_id='trace-confirmed',
            terminal_id='terminal-id',
        )

        trace_id = 'TRACE-abcd'
        terminal_id = 'terminal-id'
        rrn = 'RRN-123456'
        amount = 10000
        fee_amount = amount / 100
        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': rrn,
            'Trace': trace_id,
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': terminal_id,
            'TerminalOwner': 'terminal-owner',
            'Price': amount,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        settlement = DebitSettlementTransaction.objects.filter(rrn=rrn).first()
        assert settlement is not None
        assert settlement.amount == amount
        assert settlement.fee_amount == fee_amount
        assert settlement.status == DebitSettlementTransaction.STATUS.initiated
        assert settlement.pan == pan
        assert settlement.trace_id == trace_id
        assert settlement.terminal_id == terminal_id
        assert settlement.rid == request_data['RID']

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount + fee_amount
        assert user_service.current_debt == amount + fee_amount

        self.assert_incoming_api_log(request_data, response_data, success=True)

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['DUPLICATE_TRANSACTION']

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_initiate_and_confirm_success_and_confirm_duplicate_transaction(self, get_provider_mock):
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            user=self.user, currency=Currencies.rls, amount=Decimal('13000'), tp=ExchangeWallet.WALLET_TYPE.debit
        )

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        trace_id = 'TRACE-abcd'
        terminal_id = 'terminal-id'
        rrn = 'RRN-123456'
        amount = 10000
        fee_amount = amount / 100
        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': rrn,
            'Trace': trace_id,
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': terminal_id,
            'TerminalOwner': 'terminal-owner',
            'Price': amount,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        settlement = DebitSettlementTransaction.objects.filter(rrn=rrn).first()
        assert settlement is not None
        assert settlement.amount == amount
        assert settlement.fee_amount == fee_amount
        assert settlement.status == DebitSettlementTransaction.STATUS.initiated
        assert settlement.pan == pan
        assert settlement.trace_id == trace_id
        assert settlement.terminal_id == terminal_id
        assert settlement.rid == request_data['RID']

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount + fee_amount
        assert user_service.current_debt == amount + fee_amount

        self.assert_incoming_api_log(request_data, response_data, success=True)
        IncomingAPICallLog.objects.all().delete()

        request_data['MTI'] = '0220'

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        settlement.refresh_from_db()
        assert settlement is not None
        assert settlement.status == DebitSettlementTransaction.STATUS.confirmed

        user_service.refresh_from_db()
        assert user_service.closed_at is None
        assert user_service.status == UserService.STATUS.initiated

        self.assert_incoming_api_log(request_data, response_data, success=True)
        IncomingAPICallLog.objects.all().delete()

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['DUPLICATE_TRANSACTION']

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_initiate_and_confirm_success_and_initiate_unauthorized_transaction(self, get_provider_mock):
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            user=self.user, currency=Currencies.rls, amount=Decimal('26000'), tp=ExchangeWallet.WALLET_TYPE.debit
        )

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        trace_id = 'TRACE-abcd'
        terminal_id = 'terminal-id'
        rrn = 'RRN-123456'
        amount = 10000
        fee_amount = amount / 100
        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': rrn,
            'Trace': trace_id,
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': terminal_id,
            'TerminalOwner': 'terminal-owner',
            'Price': amount,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        settlement = DebitSettlementTransaction.objects.filter(rrn=rrn).first()
        assert settlement is not None
        assert settlement.amount == amount
        assert settlement.fee_amount == fee_amount
        assert settlement.status == DebitSettlementTransaction.STATUS.initiated
        assert settlement.pan == pan
        assert settlement.trace_id == trace_id
        assert settlement.terminal_id == terminal_id
        assert settlement.rid == request_data['RID']

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount + fee_amount
        assert user_service.current_debt == amount + fee_amount

        self.assert_incoming_api_log(request_data, response_data, success=True)
        IncomingAPICallLog.objects.all().delete()

        request_data['MTI'] = '0220'

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        settlement.refresh_from_db()
        assert settlement is not None
        assert settlement.status == DebitSettlementTransaction.STATUS.confirmed

        self.assert_incoming_api_log(request_data, response_data, success=True)
        IncomingAPICallLog.objects.all().delete()

        request_data['MTI'] = '0200'

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['UNAUTHORIZED_TRANSACTION']

        self.assert_incoming_api_log(request_data, response_data, success=False)

        settlement.refresh_from_db()
        assert settlement is not None
        assert settlement.status == DebitSettlementTransaction.STATUS.confirmed

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount + fee_amount
        assert user_service.current_debt == amount + fee_amount

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_initiate_and_confirm_success_and_reject_unauthorized_transaction(self, get_provider_mock):
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            user=self.user, currency=Currencies.rls, amount=Decimal('13000'), tp=ExchangeWallet.WALLET_TYPE.debit
        )

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        trace_id = 'TRACE-abcd'
        terminal_id = 'terminal-id'
        rrn = 'RRN-123456'
        amount = 10000
        fee_amount = amount / 100
        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': rrn,
            'Trace': trace_id,
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': terminal_id,
            'TerminalOwner': 'terminal-owner',
            'Price': amount,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        settlement = DebitSettlementTransaction.objects.filter(rrn=rrn).first()
        assert settlement is not None
        assert settlement.amount == amount
        assert settlement.fee_amount == fee_amount
        assert settlement.status == DebitSettlementTransaction.STATUS.initiated
        assert settlement.pan == pan
        assert settlement.trace_id == trace_id
        assert settlement.terminal_id == terminal_id
        assert settlement.rid == request_data['RID']

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount + fee_amount
        assert user_service.current_debt == amount + fee_amount

        self.assert_incoming_api_log(request_data, response_data, success=True)
        IncomingAPICallLog.objects.all().delete()

        request_data['MTI'] = '0220'

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        settlement.refresh_from_db()
        assert settlement is not None
        assert settlement.status == DebitSettlementTransaction.STATUS.confirmed

        self.assert_incoming_api_log(request_data, response_data, success=True)
        IncomingAPICallLog.objects.all().delete()

        request_data['MTI'] = '0400'

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['UNAUTHORIZED_TRANSACTION']

        self.assert_incoming_api_log(request_data, response_data, success=False)

        settlement.refresh_from_db()
        assert settlement is not None
        assert settlement.status == DebitSettlementTransaction.STATUS.confirmed

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount + fee_amount
        assert user_service.current_debt == amount + fee_amount

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_initiate_and_reject_success_and_reject_duplicate_transaction(self, get_provider_mock):
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            user=self.user, currency=Currencies.rls, amount=Decimal('13000'), tp=ExchangeWallet.WALLET_TYPE.debit
        )

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        trace_id = 'TRACE-abcd'
        terminal_id = 'terminal-id'
        rrn = 'RRN-123456'
        amount = 10000
        fee_amount = amount / 100
        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': rrn,
            'Trace': trace_id,
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': terminal_id,
            'TerminalOwner': 'terminal-owner',
            'Price': amount,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        settlement = DebitSettlementTransaction.objects.filter(rrn=rrn).first()
        assert settlement is not None
        assert settlement.amount == amount
        assert settlement.fee_amount == fee_amount
        assert settlement.status == DebitSettlementTransaction.STATUS.initiated
        assert settlement.pan == pan
        assert settlement.trace_id == trace_id
        assert settlement.terminal_id == terminal_id
        assert settlement.rid == request_data['RID']

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount + fee_amount
        assert user_service.current_debt == amount + fee_amount

        self.assert_incoming_api_log(request_data, response_data, success=True)
        IncomingAPICallLog.objects.all().delete()

        request_data['MTI'] = '0400'

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        settlement.refresh_from_db()
        assert settlement is not None
        assert settlement.status == DebitSettlementTransaction.STATUS.unknown_rejected

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount + fee_amount
        assert user_service.current_debt == 0

        self.assert_incoming_api_log(request_data, response_data, success=True)

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['DUPLICATE_TRANSACTION']

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_initiate_and_reject_success_and_initiate_unauthorized_transaction(self, get_provider_mock):
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            user=self.user, currency=Currencies.rls, amount=Decimal('13000'), tp=ExchangeWallet.WALLET_TYPE.debit
        )

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        trace_id = 'TRACE-abcd'
        terminal_id = 'terminal-id'
        rrn = 'RRN-123456'
        amount = 10000
        fee_amount = amount / 100
        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': rrn,
            'Trace': trace_id,
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': terminal_id,
            'TerminalOwner': 'terminal-owner',
            'Price': amount,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        settlement = DebitSettlementTransaction.objects.filter(rrn=rrn).first()
        assert settlement is not None
        assert settlement.amount == amount
        assert settlement.fee_amount == fee_amount
        assert settlement.status == DebitSettlementTransaction.STATUS.initiated
        assert settlement.pan == pan
        assert settlement.trace_id == trace_id
        assert settlement.terminal_id == terminal_id
        assert settlement.rid == request_data['RID']

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount + fee_amount
        assert user_service.current_debt == amount + fee_amount

        self.assert_incoming_api_log(request_data, response_data, success=True)
        IncomingAPICallLog.objects.all().delete()

        request_data['MTI'] = '0400'

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        settlement.refresh_from_db()
        assert settlement is not None
        assert settlement.status == DebitSettlementTransaction.STATUS.unknown_rejected

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount + fee_amount
        assert user_service.current_debt == 0

        self.assert_incoming_api_log(request_data, response_data, success=True)
        IncomingAPICallLog.objects.all().delete()

        request_data['MTI'] = '0200'

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['UNAUTHORIZED_TRANSACTION']

        self.assert_incoming_api_log(request_data, response_data, success=False)

        settlement.refresh_from_db()
        assert settlement is not None
        assert settlement.status == DebitSettlementTransaction.STATUS.unknown_rejected

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount + fee_amount
        assert user_service.current_debt == 0

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_initiate_and_reject_success_and_confirm_unauthorized_transaction(self, get_provider_mock):
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            user=self.user, currency=Currencies.rls, amount=Decimal('13000'), tp=ExchangeWallet.WALLET_TYPE.debit
        )

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        trace_id = 'TRACE-abcd'
        terminal_id = 'terminal-id'
        rrn = 'RRN-123456'
        amount = 10000
        fee_amount = amount / 100
        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': rrn,
            'Trace': trace_id,
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': terminal_id,
            'TerminalOwner': 'terminal-owner',
            'Price': amount,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        settlement = DebitSettlementTransaction.objects.filter(rrn=rrn).first()
        assert settlement is not None
        assert settlement.amount == amount
        assert settlement.fee_amount == fee_amount
        assert settlement.status == DebitSettlementTransaction.STATUS.initiated
        assert settlement.pan == pan
        assert settlement.trace_id == trace_id
        assert settlement.terminal_id == terminal_id
        assert settlement.rid == request_data['RID']

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount + fee_amount
        assert user_service.current_debt == amount + fee_amount

        self.assert_incoming_api_log(request_data, response_data, success=True)
        IncomingAPICallLog.objects.all().delete()

        request_data['MTI'] = '0400'

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        settlement.refresh_from_db()
        assert settlement is not None
        assert settlement.status == DebitSettlementTransaction.STATUS.unknown_rejected

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount + fee_amount
        assert user_service.current_debt == 0

        self.assert_incoming_api_log(request_data, response_data, success=True)
        IncomingAPICallLog.objects.all().delete()

        request_data['MTI'] = '0220'

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['UNAUTHORIZED_TRANSACTION']

        self.assert_incoming_api_log(request_data, response_data, success=False)

        settlement.refresh_from_db()
        assert settlement is not None
        assert settlement.status == DebitSettlementTransaction.STATUS.unknown_rejected

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount + fee_amount
        assert user_service.current_debt == 0

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_unknown_confirmed_and_confirm_duplicate_transaction(self, get_provider_mock):
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            user=self.user, currency=Currencies.rls, amount=Decimal('13000'), tp=ExchangeWallet.WALLET_TYPE.debit
        )

        amount = 10000
        pan = '6063909010102323'
        user_service = self.create_user_service(
            self.user, service=self.service, initial_debt=amount, current_debt=amount
        )
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        trace_id = 'TRACE-abcd'
        terminal_id = 'terminal-id'
        rrn = 'RRN-123456'
        rid = 'rid-123456'

        settlement = DebitSettlementTransaction()
        settlement.amount = amount
        settlement.status = DebitSettlementTransaction.STATUS.unknown_confirmed
        settlement.user_service = user_service
        settlement.pan = pan
        settlement.rrn = rrn
        settlement.trace_id = trace_id
        settlement.terminal_id = terminal_id
        settlement.rid = rid
        settlement.save()

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0220',
            'PAN': pan,
            'RRN': rrn,
            'Trace': trace_id,
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': terminal_id,
            'TerminalOwner': 'terminal-owner',
            'Price': amount,
            'RID': rid,
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['DUPLICATE_TRANSACTION']

        self.assert_incoming_api_log(request_data, response_data, success=False)

        settlement.refresh_from_db()
        assert settlement is not None
        assert settlement.status == DebitSettlementTransaction.STATUS.unknown_confirmed

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_unknown_confirmed_and_reject_unauthorized_transaction(self, get_provider_mock):
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            user=self.user, currency=Currencies.rls, amount=Decimal('13000'), tp=ExchangeWallet.WALLET_TYPE.debit
        )

        amount = 10000
        pan = '6063909010102323'
        user_service = self.create_user_service(
            self.user, service=self.service, initial_debt=amount, current_debt=amount
        )
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        trace_id = 'TRACE-abcd'
        terminal_id = 'terminal-id'
        rrn = 'RRN-123456'
        rid = 'rid-123456'

        settlement = DebitSettlementTransaction()
        settlement.amount = amount
        settlement.status = DebitSettlementTransaction.STATUS.unknown_confirmed
        settlement.user_service = user_service
        settlement.pan = pan
        settlement.rrn = rrn
        settlement.trace_id = trace_id
        settlement.terminal_id = terminal_id
        settlement.rid = rid
        settlement.save()

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0400',
            'PAN': pan,
            'RRN': rrn,
            'Trace': trace_id,
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': terminal_id,
            'TerminalOwner': 'terminal-owner',
            'Price': amount,
            'RID': rid,
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['UNAUTHORIZED_TRANSACTION']

        self.assert_incoming_api_log(request_data, response_data, success=False)

        settlement.refresh_from_db()
        assert settlement is not None
        assert settlement.status == DebitSettlementTransaction.STATUS.unknown_confirmed

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_initiate_and_confirm_success_multiple_times(self, get_provider_mock):
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            user=self.user, currency=Currencies.rls, amount=Decimal('43000'), tp=ExchangeWallet.WALLET_TYPE.debit
        )

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        total_amount = 0
        # ----- first transaction -----
        trace_id = 'TRACE-abcd1'
        terminal_id = 'terminal-id'
        rrn = 'RRN-123456-1'
        amount = Decimal(10000).quantize(Decimal('0.0001'))
        fee_amount_1 = Decimal(amount / 100).quantize(Decimal('0.0001'))
        total_amount += amount
        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': rrn,
            'Trace': trace_id,
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': terminal_id,
            'TerminalOwner': 'terminal-owner',
            'Price': amount,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        settlement = DebitSettlementTransaction.objects.filter(rrn=rrn).first()
        assert settlement is not None
        assert settlement.amount == amount
        assert settlement.fee_amount == fee_amount_1
        assert settlement.status == DebitSettlementTransaction.STATUS.initiated

        user_service.refresh_from_db()
        assert user_service.initial_debt == amount + fee_amount_1
        assert user_service.current_debt == amount + fee_amount_1

        request_data['MTI'] = '0220'

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        # make settlement final (manually!)
        settlement.create_transactions()

        settlement.refresh_from_db()
        assert settlement is not None
        assert settlement.status == DebitSettlementTransaction.STATUS.confirmed

        user_service.refresh_from_db()
        assert user_service.closed_at is None
        assert user_service.status == UserService.STATUS.initiated
        assert user_service.initial_debt == amount + fee_amount_1
        assert user_service.current_debt == 0

        # ----- second transaction -----
        trace_id = 'TRACE-abcd2'
        rrn = 'RRN-123456-2'
        amount = Decimal(15000.25).quantize(Decimal('0.0001'))
        fee_amount_2 = Decimal(amount / 100).quantize(Decimal('0.0001'))
        total_amount += amount
        request_data['MTI'] = "0200"
        request_data['Trace'] = trace_id
        request_data['RRN'] = rrn
        request_data['Price'] = amount
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        settlement = DebitSettlementTransaction.objects.filter(rrn=rrn).first()
        assert settlement is not None
        assert settlement.amount == amount
        assert settlement.fee_amount == fee_amount_2
        assert settlement.status == DebitSettlementTransaction.STATUS.initiated

        user_service.refresh_from_db()
        assert user_service.initial_debt == total_amount + fee_amount_1 + fee_amount_2
        assert user_service.current_debt == amount + fee_amount_2

        request_data['MTI'] = '0220'

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        # make settlement final (manually!)
        settlement.create_transactions()

        settlement.refresh_from_db()
        assert settlement is not None
        assert settlement.status == DebitSettlementTransaction.STATUS.confirmed

        user_service.refresh_from_db()
        assert user_service.closed_at is None
        assert user_service.status == UserService.STATUS.initiated
        assert user_service.current_debt == 0

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_initiate_success_multiple_times_failed_after_initiated_settlements_count_exceeded(
        self, get_provider_mock
    ):
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            user=self.user, currency=Currencies.rls, amount=Decimal('4300000'), tp=ExchangeWallet.WALLET_TYPE.debit
        )

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        total_amount = Decimal(0)
        for i in range(5):
            trace_id = 'TRACE-abcd-' + str(i)
            terminal_id = 'terminal-id'
            rrn = 'RRN-123456-' + str(i)
            amount = Decimal(10000)
            fee_amount = amount / 100
            total_amount += amount + fee_amount
            username = 'pnovin'
            password = 'passw0rd'
            credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

            request_data = {
                'MTI': '0200',
                'PAN': pan,
                'RRN': rrn,
                'Trace': trace_id,
                'Date': '1402/11/17',
                'Time': '15:00:11',
                'PRCode': '111',
                'TerminalID': terminal_id,
                'TerminalOwner': 'terminal-owner',
                'Price': amount,
                'RID': 'rid-123456',
            }
            response = self.client.post(
                self.url,
                data=request_data,
                HTTP_AUTHORIZATION=f'Basic {credentials}',
            )

            response_data = response.json()
            assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

            settlement = DebitSettlementTransaction.objects.filter(rrn=rrn).first()
            assert settlement is not None
            assert settlement.amount == amount
            assert settlement.fee_amount == fee_amount
            assert settlement.status == DebitSettlementTransaction.STATUS.initiated

            user_service.refresh_from_db()
            assert user_service.initial_debt == total_amount
            assert user_service.current_debt == total_amount

        # ----- sixth transaction -----
        trace_id = 'TRACE-abcd-5'
        rrn = 'RRN-123456-5'
        amount = Decimal(15000.25)
        total_amount += amount
        request_data['MTI'] = "0200"
        request_data['Trace'] = trace_id
        request_data['RRN'] = rrn
        request_data['Price'] = amount
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['UNAUTHORIZED_TRANSACTION']

        assert not DebitSettlementTransaction.objects.filter(rrn=rrn).exists()

        user_service.refresh_from_db()
        assert user_service.initial_debt == total_amount - amount
        assert user_service.current_debt == total_amount - amount

    def assert_incoming_api_log(self, request_data, response_data, success=False):
        api_log = IncomingAPICallLog.objects.all().first()

        assert api_log is not None
        assert api_log.api_url == '/asset-backed-credit/v1/debit/transaction'
        api_log.request_body['Price'] = int(api_log.request_body['Price'])
        assert api_log.request_body == request_data
        assert api_log.response_body == response_data
        assert api_log.response_code == status.HTTP_200_OK
        assert api_log.status == IncomingAPICallLog.STATUS.success if success else IncomingAPICallLog.STATUS.failure
        assert api_log.provider == self.provider.id
        assert api_log.service == Service.TYPES.debit
        assert api_log.user_service is not None
        assert api_log.user is not None

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_initiate_fails_when_card_transaction_meets_per_transaction_max_amount_limit(
        self, get_provider_mock
    ):
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            self.user, Currencies.rls, Decimal(self.card_level_settings.per_transaction_amount_limit * 2)
        )

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': self.card_level_settings.per_transaction_amount_limit + 1,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['AMOUNT_LIMIT_EXCEEDED']

        self.assert_incoming_api_log(request_data, response_data)

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_initiate_fails_when_card_transaction_meets_total_daily_allowed_amount_limit(
        self, get_provider_mock
    ):
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            self.user, Currencies.rls, Decimal(self.card_level_settings.per_transaction_amount_limit * 2)
        )

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        card = self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        today_remaining = 1_000_0000
        CardTransactionLimit._add_daily_transaction(
            card, self.card_level_settings.daily_transaction_amount_limit - today_remaining
        )

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': today_remaining + 1,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['AMOUNT_LIMIT_EXCEEDED']

        self.assert_incoming_api_log(request_data, response_data)

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_initial_fails_when_card_transaction_meets_total_monthly_allowed_amount_limit(
        self, get_provider_mock
    ):
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            self.user, Currencies.rls, Decimal(self.card_level_settings.per_transaction_amount_limit * 2)
        )

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        card = self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        this_month_remaining = 1_000_0000
        CardTransactionLimit._add_monthly_transaction(
            card, self.card_level_settings.monthly_transaction_amount_limit - this_month_remaining
        )

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': this_month_remaining + 1,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['AMOUNT_LIMIT_EXCEEDED']

        self.assert_incoming_api_log(request_data, response_data)

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_transaction_initial_fails_when_card_has_no_level_settings(self, get_provider_mock):
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            self.user, Currencies.rls, Decimal(self.card_level_settings.per_transaction_amount_limit * 2)
        )

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service)

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': self.card_level_settings.per_transaction_amount_limit + 1,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['UNAUTHORIZED_TRANSACTION']

        self.assert_incoming_api_log(request_data, response_data)

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_initiate_transaction_success_adds_one_daily_and_one_monthly_debit_transaction_limit_record_for_first_transaction_and_then_confirms_successfully(
        self, get_provider_mock
    ):
        previous_limit_count = CardTransactionLimit.objects.count()
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            self.user,
            Currencies.rls,
            Decimal(self.card_level_settings.per_transaction_amount_limit * 2),
            tp=ExchangeWallet.WALLET_TYPE.debit,
        )
        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        card = self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)
        trace_id = 'TRACE-abcd'
        terminal_id = 'terminal-id'
        rrn = 'RRN-123456'
        amount = 10000
        fee_amount = amount / 100
        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')
        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': rrn,
            'Trace': trace_id,
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': terminal_id,
            'TerminalOwner': 'terminal-owner',
            'Price': amount,
            'RID': 'rid-123456',
        }

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )
        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']
        settlement = DebitSettlementTransaction.objects.filter(rrn=rrn).first()
        assert settlement is not None
        assert settlement.amount == amount
        assert settlement.fee_amount == fee_amount
        assert settlement.status == DebitSettlementTransaction.STATUS.initiated
        assert settlement.pan == pan
        assert settlement.trace_id == trace_id
        assert settlement.terminal_id == terminal_id
        assert settlement.rid == request_data['RID']
        user_service.refresh_from_db()
        assert user_service.initial_debt == amount + fee_amount
        assert user_service.current_debt == amount + fee_amount
        self.assert_incoming_api_log(request_data, response_data, success=True)
        IncomingAPICallLog.objects.all().delete()

        assert previous_limit_count + 2 == CardTransactionLimit.objects.count()
        assert CardTransactionLimit.get_card_daily_total_amount(card) == amount
        assert CardTransactionLimit.get_card_monthly_total_amount(card) == amount

        request_data['MTI'] = '0220'
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )
        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']
        settlement.refresh_from_db()
        assert settlement is not None
        assert settlement.status == DebitSettlementTransaction.STATUS.confirmed
        user_service.refresh_from_db()
        assert user_service.closed_at is None
        assert user_service.status == UserService.STATUS.initiated
        self.assert_incoming_api_log(request_data, response_data, success=True)

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_initiate_transaction_success_multiple_times_adds_to_existing_daily_and_monthly_transaction_limit_records_and_then_transactions_confirm_successfully(
        self, get_provider_mock
    ):
        previous_limit_count = CardTransactionLimit.objects.count()
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            self.user,
            Currencies.rls,
            Decimal(self.card_level_settings.per_transaction_amount_limit * 2),
            tp=ExchangeWallet.WALLET_TYPE.debit,
        )
        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        card = self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)
        trace_id = 'TRACE-first'
        terminal_id = 'terminal-id-first'
        rrn = 'RRN-first'
        amount = 10000
        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')
        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': rrn,
            'Trace': trace_id,
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': terminal_id,
            'TerminalOwner': 'terminal-owner',
            'Price': amount,
            'RID': 'rid-123456',
        }

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )
        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        assert previous_limit_count + 2 == CardTransactionLimit.objects.count()
        assert CardTransactionLimit.get_card_daily_total_amount(card) == amount
        assert CardTransactionLimit.get_card_monthly_total_amount(card) == amount

        # confirm fist transaction
        request_data['MTI'] = '0220'
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )
        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']
        settlement = DebitSettlementTransaction.objects.filter(rrn=rrn).first()
        assert settlement is not None
        assert settlement.status == DebitSettlementTransaction.STATUS.confirmed

        trace_id = 'TRACE-second'
        terminal_id = 'terminal-id-second'
        rrn = 'RRN-second'
        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': rrn,
            'Trace': trace_id,
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': terminal_id,
            'TerminalOwner': 'terminal-owner',
            'Price': amount,
            'RID': 'rid-second',
        }

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )
        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

        assert previous_limit_count + 2 == CardTransactionLimit.objects.count()
        assert CardTransactionLimit.get_card_daily_total_amount(card) == amount * 2
        assert CardTransactionLimit.get_card_monthly_total_amount(card) == amount * 2

        # confirm second transaction
        request_data['MTI'] = '0220'
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )
        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_initiate_transaction_multiple_times_with_different_terminal_id_adds_card_daily_and_monthly_limits_history(
        self, get_provider_mock
    ):
        previous_limit_count = CardTransactionLimit.objects.count()
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            self.user,
            Currencies.rls,
            Decimal(self.card_level_settings.per_transaction_amount_limit * 7),
            tp=ExchangeWallet.WALLET_TYPE.debit,
        )
        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        card = self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)
        amount = 10000
        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')
        for i in range(1, 6):
            request_data = {
                'MTI': '0200',
                'PAN': pan,
                'RRN': f'rrn-{i}',
                'Trace': f'trace_id-{i}',
                'Date': '1402/11/17',
                'Time': '15:00:11',
                'PRCode': '111',
                'TerminalID': f'terminal_id-{i}',
                'TerminalOwner': 'terminal-owner',
                'Price': amount,
                'RID': 'rid-123456',
            }

            response = self.client.post(
                self.url,
                data=request_data,
                HTTP_AUTHORIZATION=f'Basic {credentials}',
            )
            response_data = response.json()
            assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']
            settlement = DebitSettlementTransaction.objects.filter(rrn=f'rrn-{i}').first()
            assert settlement is not None
            assert settlement.status == DebitSettlementTransaction.STATUS.initiated

            assert previous_limit_count + 2 == CardTransactionLimit.objects.count()
            assert CardTransactionLimit.get_card_daily_total_amount(card) == amount * i
            assert CardTransactionLimit.get_card_monthly_total_amount(card) == amount * i

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_initiate_transaction_success_adds_one_daily_and_one_monthly_debit_transaction_limit_and_reject_transaction_subtracts_from_daily_and_monthly_limits(
        self, get_provider_mock
    ):
        previous_limit_count = CardTransactionLimit.objects.count()
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            self.user,
            Currencies.rls,
            Decimal(self.card_level_settings.per_transaction_amount_limit * 2),
            tp=ExchangeWallet.WALLET_TYPE.debit,
        )
        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        card = self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)
        amount = 10000
        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')
        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': 'rrn',
            'Trace': 'trace_id',
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal_id',
            'TerminalOwner': 'terminal-owner',
            'Price': amount,
            'RID': 'rid-123456',
        }

        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )
        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']
        settlement = DebitSettlementTransaction.objects.filter(rrn='rrn').first()
        assert settlement.status == DebitSettlementTransaction.STATUS.initiated
        user_service.refresh_from_db()
        self.assert_incoming_api_log(request_data, response_data, success=True)

        assert previous_limit_count + 2 == CardTransactionLimit.objects.count()
        assert CardTransactionLimit.get_card_daily_total_amount(card) == amount
        assert CardTransactionLimit.get_card_monthly_total_amount(card) == amount

        request_data['MTI'] = '0400'
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )
        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['SUCCESS']
        settlement.refresh_from_db()
        assert settlement.status == DebitSettlementTransaction.STATUS.unknown_rejected

        assert previous_limit_count + 2 == CardTransactionLimit.objects.count()
        assert CardTransactionLimit.get_card_daily_total_amount(card) == ZERO
        assert CardTransactionLimit.get_card_monthly_total_amount(card) == ZERO

    @patch('exchange.asset_backed_credit.services.providers.provider_manager.ProviderManager.get_provider_by_ip')
    def test_initiate_transaction_fails_with_unauthorized_transaction_code_when_card_transaction_flag_is_not_enabled(
        self, get_provider_mock
    ):
        Settings.set('abc_debit_card_initiate_transaction_enabled', 'no')
        get_provider_mock.return_value = self.provider
        self.charge_exchange_wallet(
            self.user, Currencies.rls, Decimal(self.card_level_settings.per_transaction_amount_limit * 2)
        )

        pan = '6063909010102323'
        user_service = self.create_user_service(self.user, service=self.service, initial_debt=0)
        self.create_card(pan=pan, user_service=user_service, setting=self.card_level_settings)

        username = 'pnovin'
        password = 'passw0rd'
        credentials = base64.b64encode(f'{username}:{password}'.encode('utf-8')).decode('utf-8')

        request_data = {
            'MTI': '0200',
            'PAN': pan,
            'RRN': 'RRN-123456',
            'Trace': 'TRACE-abcd',
            'Date': '1402/11/17',
            'Time': '15:00:11',
            'PRCode': '111',
            'TerminalID': 'terminal-id',
            'TerminalOwner': 'terminal-owner',
            'Price': 100_000,
            'RID': 'rid-123456',
        }
        response = self.client.post(
            self.url,
            data=request_data,
            HTTP_AUTHORIZATION=f'Basic {credentials}',
        )

        response_data = response.json()
        assert response_data['RespCode'] == bank_switch_status_code_mapping['UNAUTHORIZED_TRANSACTION']
        self.assert_incoming_api_log(request_data, response_data)
