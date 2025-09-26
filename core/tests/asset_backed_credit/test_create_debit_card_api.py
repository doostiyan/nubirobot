from decimal import Decimal
from unittest.mock import patch

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.asset_backed_credit.models import (
    Card,
    CardRequestSchema,
    Service,
    UserFinancialServiceLimit,
    UserService,
    UserServicePermission,
    Wallet,
)
from exchange.asset_backed_credit.types import DEBIT_FEATURE_FLAG
from exchange.base.models import Currencies, Settings
from exchange.wallet.models import Wallet as ExchangeWallet
from tests.asset_backed_credit.helper import ABCMixins
from tests.features.utils import BetaFeatureTestMixin

MOCKED_DEBIT_CURRENCIES = [Currencies.usdt, Currencies.ton, Currencies.btc]


def mocked_get_all_currencies(wallet_type):
    if wallet_type == Wallet.WalletType.DEBIT:
        return MOCKED_DEBIT_CURRENCIES
    return []


def get_price(self):
    if self.src_currency == self.dst_currency:
        return Decimal(1)
    if self.src_currency == Currencies.usdt:
        return Decimal(50_000)
    raise ValueError


class CreateDebitCardApiTestCase(BetaFeatureTestMixin, APITestCase, ABCMixins):
    URL = '/asset-backed-credit/debit/cards'

    feature = DEBIT_FEATURE_FLAG

    @classmethod
    def setUpTestData(cls):
        Settings.set('abc_debit_card_creation_enabled', 'yes')
        cls.user = User.objects.get(pk=201)
        cls.user.username = 'user'
        cls.user.save()

        service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit, is_available=True, is_active=True
        )
        UserFinancialServiceLimit.set_service_limit(service=service, min_limit=10_000, max_limit=10_000_000)

        cls.nobifi_service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.nobifi, tp=Service.TYPES.debit, is_active=True
        )

        cls.service = service

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def test_feature_is_not_activated(self):
        resp = self.client.post(path=self.URL)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == {
            'status': 'failed',
            'code': 'FeatureUnavailable',
            'message': 'abc_debit feature is not available for your user',
        }

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_success_without_address(self):
        self.request_feature(self.user, 'done')

        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=timezone.now())
        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        data = {
            'firstName': 'john',
            'lastName': 'doe',
            'birthCertNo': '100',
            'color': 1,
        }
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_200_OK

        card = Card.objects.order_by('pk').last()
        assert card.user_service.user == self.user
        assert card.user_service.internal_user.uid == self.user.uid
        assert card.user_service.service == self.service
        assert card.user_service.status == UserService.STATUS.created
        assert card.user == self.user
        assert card.internal_user.uid == self.user.uid
        assert card.status == Card.STATUS.requested
        assert card.extra_info == {
            'first_name': 'john',
            'last_name': 'doe',
            'birth_cert_no': '100',
            'color': 1,
            'delivery_address': None,
            'issue_data': None,
        }
        assert card.setting is None
        assert UserService.objects.filter(user=self.user, service=self.nobifi_service, closed_at=None).exists()

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    @patch('exchange.asset_backed_credit.currencies.ABCCurrencies.get_all_currencies', mocked_get_all_currencies)
    def test_failure_without_address_invalid_transfer_currency(self):
        self.service.options.update({'card_issue_cost': 200_000})
        self.service.save()

        self.request_feature(self.user, 'done')

        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=timezone.now())
        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        data = {
            'firstName': 'john',
            'lastName': 'doe',
            'birthCertNo': '100',
            'color': 1,
            'transferCurrency': Currencies.cake,
        }
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        resp = response.json()
        assert resp['status'] == 'failed'
        assert resp['code'] == 'ParseError'

        assert not Card.objects.filter(user=self.user).exists()

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    @patch('exchange.asset_backed_credit.currencies.ABCCurrencies.get_all_currencies', mocked_get_all_currencies)
    def test_success_with_address(self):
        self.request_feature(self.user, 'done')

        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=timezone.now())
        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.verified
        self.user.save()

        data = {
            'firstName': 'john',
            'lastName': 'doe',
            'birthCertNo': '100',
            'color': 3,
            'deliveryAddress': {
                'province': 'تهران',
                'city': 'تهران',
                'postalCode': '1234567890',
                'address': 'tehran, left, right, right, 10',
            },
            'transferCurrency': Currencies.btc,
        }
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_200_OK

        card = Card.objects.order_by('pk').last()
        assert card.user_service.user == self.user
        assert card.user_service.internal_user.uid == self.user.uid
        assert card.user_service.service == self.service
        assert card.user_service.status == UserService.STATUS.created
        assert card.user == self.user
        assert card.internal_user.uid == self.user.uid
        assert card.status == Card.STATUS.requested
        assert card.extra_info == {
            'first_name': 'john',
            'last_name': 'doe',
            'birth_cert_no': '100',
            'color': 3,
            'delivery_address': {
                'province': 'تهران',
                'city': 'تهران',
                'postal_code': '1234567890',
                'address': 'tehran, left, right, right, 10',
            },
            'issue_data': None,
        }
        assert card.setting is None
        assert UserService.objects.filter(user=self.user, service=self.nobifi_service, closed_at=None).exists()


    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_success_when_default_card_level_exists(self):
        self.request_feature(self.user, 'done')
        card_level1 = self.create_card_setting(level=1)
        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=timezone.now())
        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        data = {
            'firstName': 'john',
            'lastName': 'doe',
            'birthCertNo': '100',
            'color': 1,
        }
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_200_OK

        card = Card.objects.order_by('pk').last()
        assert card
        assert card.status == Card.STATUS.requested
        assert card.setting == card_level1
        assert UserService.objects.filter(user=self.user, service=self.nobifi_service, closed_at=None).exists()

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_service_unavailable(self):
        self.request_feature(self.user, 'done')

        self.service.is_available = False
        self.service.save(update_fields=['is_available'])

        data = {
            'firstName': 'john',
            'lastName': 'doe',
            'birthCertNo': '100',
            'color': 1,
            'deliveryAddress': None,
        }
        with patch.object(self.service, 'is_available', False):
            response = self.client.post(path=self.URL, data=data, format='json')
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
            assert response.json()['code'] == 'ServiceUnavailableError'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_parse_error(self):
        self.request_feature(self.user, 'done')

        data = {'first_name': 'john', 'last_name': 'doe', 'berth_cert_no': '1000', 'color': 1}
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['code'] == 'ParseError'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_invalid_color_error(self):
        self.request_feature(self.user, 'done')

        data = {'firstname': 'john', 'lastName': 'doe', 'color': 'test-color', 'birthCertNo': '1000'}
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['code'] == 'ParseError'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_service_permission(self):
        self.request_feature(self.user, 'done')

        data = {
            'firstName': 'john',
            'lastName': 'doe',
            'birthCertNo': '100',
            'color': 1,
        }
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['code'] == 'ServicePermissionNotFound'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_user_is_not_level2(self):
        self.request_feature(self.user, 'done')

        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=timezone.now())

        data = {
            'firstName': 'john',
            'lastName': 'doe',
            'birthCertNo': '100',
            'color': 1,
        }
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['code'] == 'UserLevelRestrictionError'
        assert response.json()['message'] == 'User is not level-2'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_failure_user_financial_limit_is_zero(self):
        self.request_feature(self.user, 'done')

        UserFinancialServiceLimit.set_user_service_limit(user=self.user, service=self.service, max_limit=0)
        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=timezone.now())
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        data = {
            'firstName': 'john',
            'lastName': 'doe',
            'birthCertNo': '100',
            'color': 1,
        }
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['code'] == 'UserLevelRestrictionError'
        assert response.json()['message'] == 'User is restricted to use this service'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    @patch('exchange.asset_backed_credit.currencies.ABCCurrencies.get_all_currencies', mocked_get_all_currencies)
    def test_success_without_address_when_its_not_first_card(self):
        self.request_feature(self.user, 'done')

        def create_dummy_card():
            user, _ = User.objects.get_or_create(username='dummy-user')
            permission = UserServicePermission.objects.create(user=user, service=self.service)
            user_service = UserService.objects.create(
                user=user,
                service=self.service,
                initial_debt=1000,
                current_debt=1000,
                user_service_permission=permission,
            )
            return Card.objects.create(user=user, user_service=user_service)

        dummy_card = create_dummy_card()
        assert dummy_card.pan is None

        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=timezone.now())
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        data = {
            'firstName': 'jane',
            'lastName': 'doe',
            'birthCertNo': '200',
            'color': 1,
            'transferCurrency': Currencies.btc,
        }

        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_200_OK

        card = Card.objects.order_by('pk').last()
        assert card != dummy_card
        assert card.user_service.user == self.user
        assert card.user_service.internal_user.uid == self.user.uid
        assert card.user_service.service == self.service
        assert card.user_service.status == UserService.STATUS.created
        assert card.user == self.user
        assert card.pan is None
        assert card.status == Card.STATUS.requested
        assert card.extra_info == {
            'first_name': 'jane',
            'last_name': 'doe',
            'birth_cert_no': '200',
            'color': 1,
            'delivery_address': None,
            'issue_data': None,
        }
        assert UserService.objects.filter(user=self.user, service=self.nobifi_service, closed_at=None).exists()

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_card_create_fails_when_card_creation_flag_is_not_enabled(self):
        Settings.set('abc_debit_card_creation_enabled', 'no')
        self.request_feature(self.user, 'done')

        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=timezone.now())
        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        data = {
            'firstName': 'john',
            'lastName': 'doe',
            'birthCertNo': '100',
            'color': 1,
        }
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['code'] == 'DebitCardCreationServiceTemporaryUnavailable'

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    def test_card_create_fails_nobifi_service_not_found(self):
        self.request_feature(self.user, 'done')

        Service.objects.filter(provider=Service.PROVIDERS.nobifi, tp=Service.TYPES.debit).delete()

        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=timezone.now())
        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        data = {
            'firstName': 'john',
            'lastName': 'doe',
            'birthCertNo': '100',
            'color': 1,
        }
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json()['code'] == 'ServiceNotFoundError'


class CreateDebitCardWithIssueCostApiTestCase(BetaFeatureTestMixin, APITestCase, ABCMixins):
    URL = '/asset-backed-credit/debit/cards'

    feature = DEBIT_FEATURE_FLAG

    @classmethod
    def setUpTestData(cls):
        Settings.set('abc_debit_card_creation_enabled', 'yes')
        cls.user = User.objects.get(pk=201)
        cls.user.username = 'user'
        cls.user.save()

        service, _ = Service.objects.update_or_create(
            provider=Service.PROVIDERS.parsian,
            tp=Service.TYPES.debit,
            defaults={'is_available': True, 'is_active': True, 'options': {'card_issue_cost': 250_000}},
        )
        UserFinancialServiceLimit.set_service_limit(service=service, min_limit=10_000, max_limit=10_000_000)

        cls.nobifi_service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.nobifi, tp=Service.TYPES.debit, is_active=True
        )

        cls.service = service
        Settings.set('abc_debit_wallet_enabled', 'yes')

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    @patch('exchange.asset_backed_credit.currencies.ABCCurrencies.get_all_currencies', mocked_get_all_currencies)
    @patch('exchange.asset_backed_credit.externals.price.PriceProvider.get_nobitex_price', get_price)
    @patch('exchange.asset_backed_credit.externals.price.PriceProvider.get_mark_price', get_price)
    def test_success_debit_balance_is_insufficient(self):

        self.request_feature(self.user, 'done')
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('1'), ExchangeWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('20'), ExchangeWallet.WALLET_TYPE.spot)

        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=timezone.now())
        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        data = {
            'firstName': 'john',
            'lastName': 'doe',
            'birthCertNo': '100',
            'color': 1,
            'transferCurrency': Currencies.usdt,
        }
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_200_OK

        card = Card.objects.order_by('pk').last()
        assert card.user_service.user == self.user
        assert card.user_service.internal_user.uid == self.user.uid
        assert card.user_service.service == self.service
        assert card.user_service.status == UserService.STATUS.created
        assert card.user == self.user
        assert card.internal_user.uid == self.user.uid
        assert card.status == Card.STATUS.requested

        extra_info = CardRequestSchema.model_validate(card.extra_info)
        assert extra_info.first_name == 'john'
        assert extra_info.last_name == 'doe'
        assert extra_info.birth_cert_no == '100'
        assert extra_info.color == 1
        assert extra_info.delivery_address is None
        assert extra_info.issue_data.cost == 250_000
        assert extra_info.issue_data.transfer_id is not None
        assert extra_info.issue_data.transfer_currency == Currencies.usdt
        assert extra_info.issue_data.transfer_amount == Decimal('4.5')
        assert extra_info.issue_data.settlement_id is None

        assert card.setting is None
        assert UserService.objects.filter(
            user=self.user,
            service=self.nobifi_service,
            closed_at=None,
            initial_debt=Decimal(250_000),
            current_debt=Decimal(250_000),
        ).exists()

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    @patch('exchange.asset_backed_credit.currencies.ABCCurrencies.get_all_currencies', mocked_get_all_currencies)
    @patch('exchange.asset_backed_credit.externals.price.PriceProvider.get_nobitex_price', get_price)
    @patch('exchange.asset_backed_credit.externals.price.PriceProvider.get_mark_price', get_price)
    def test_failure_debit_balance_is_insufficient_no_transfer_currency(self):
        self.request_feature(self.user, 'done')
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('1'), ExchangeWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('20'), ExchangeWallet.WALLET_TYPE.spot)

        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=timezone.now())
        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        data = {
            'firstName': 'john',
            'lastName': 'doe',
            'birthCertNo': '100',
            'color': 1,
        }
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {
            'status': 'failed',
            'code': 'TransferCurrencyRequiredError',
            'message': 'انتخاب رمزارز برای انتقال موجودی برای پرداخت هزینه صدور الزامی است.',
        }

        assert not Card.objects.exists()

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    @patch('exchange.asset_backed_credit.currencies.ABCCurrencies.get_all_currencies', mocked_get_all_currencies)
    @patch('exchange.asset_backed_credit.externals.price.PriceProvider.get_nobitex_price', get_price)
    @patch('exchange.asset_backed_credit.externals.price.PriceProvider.get_mark_price', get_price)
    def test_failure_debit_balance_is_insufficient(self):
        self.request_feature(self.user, 'done')
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('1'), ExchangeWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('4'), ExchangeWallet.WALLET_TYPE.spot)

        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=timezone.now())
        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        data = {
            'firstName': 'john',
            'lastName': 'doe',
            'birthCertNo': '100',
            'color': 1,
            'transferCurrency': Currencies.usdt,
        }
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {
            'status': 'failed',
            'code': 'InsufficientBalance',
            'message': 'Amount cannot exceed active balance',
        }

        assert not Card.objects.exists()

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    @patch('exchange.asset_backed_credit.currencies.ABCCurrencies.get_all_currencies', mocked_get_all_currencies)
    @patch('exchange.asset_backed_credit.externals.price.PriceProvider.get_nobitex_price', get_price)
    @patch('exchange.asset_backed_credit.externals.price.PriceProvider.get_mark_price', get_price)
    def test_success_debit_balance_is_sufficient(self):
        self.request_feature(self.user, 'done')
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('10'), ExchangeWallet.WALLET_TYPE.debit)
        self.charge_exchange_wallet(self.user, Currencies.usdt, Decimal('10'), ExchangeWallet.WALLET_TYPE.spot)

        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=timezone.now())
        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        data = {
            'firstName': 'john',
            'lastName': 'doe',
            'birthCertNo': '100',
            'color': 1,
            'transferCurrency': Currencies.usdt,
        }
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_200_OK

        card = Card.objects.order_by('pk').last()
        assert card.user_service.user == self.user
        assert card.user_service.internal_user.uid == self.user.uid
        assert card.user_service.service == self.service
        assert card.user_service.status == UserService.STATUS.created
        assert card.user == self.user
        assert card.internal_user.uid == self.user.uid
        assert card.status == Card.STATUS.requested

        extra_info = CardRequestSchema.model_validate(card.extra_info)
        assert extra_info.first_name == 'john'
        assert extra_info.last_name == 'doe'
        assert extra_info.birth_cert_no == '100'
        assert extra_info.color == 1
        assert extra_info.delivery_address is None
        assert extra_info.issue_data.cost == 250_000
        assert extra_info.issue_data.transfer_id is None
        assert extra_info.issue_data.transfer_currency == Currencies.usdt
        assert extra_info.issue_data.transfer_amount is None
        assert extra_info.issue_data.settlement_id is None

        assert card.setting is None
        assert UserService.objects.filter(
            user=self.user,
            service=self.nobifi_service,
            closed_at=None,
            initial_debt=Decimal(250_000),
            current_debt=Decimal(250_000),
        ).exists()

    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_verified_as_level_1', lambda user: True)
    @patch('exchange.accounts.userlevels.UserLevelManager.is_user_mobile_identity_confirmed', lambda user: True)
    @patch('exchange.asset_backed_credit.currencies.ABCCurrencies.get_all_currencies', mocked_get_all_currencies)
    def test_failure_invalid_transfer_currency(self):
        self.request_feature(self.user, 'done')

        UserServicePermission.objects.create(user=self.user, service=self.service, created_at=timezone.now())
        self.user.requires_2fa = True
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()

        data = {
            'firstName': 'john',
            'lastName': 'doe',
            'birthCertNo': '100',
            'color': 1,
            'transferCurrency': Currencies.cake,
        }
        response = self.client.post(path=self.URL, data=data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        resp = response.json()
        assert resp['status'] == 'failed'
        assert resp['code'] == 'ParseError'

        assert not Card.objects.filter(user=self.user).exists()
