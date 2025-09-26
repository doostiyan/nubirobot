from decimal import Decimal

from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient

from exchange.accounts.models import User
from exchange.asset_backed_credit.api.serializers import serialize_service
from exchange.asset_backed_credit.models import Service, UserFinancialServiceLimit, Wallet
from exchange.asset_backed_credit.services.price import get_ratios
from exchange.asset_backed_credit.types import LoanServiceOptions, UserServiceLimit
from exchange.base.models import CREDIT_CURRENCIES, DEBIT_CURRENCIES, Settings, get_currency_codename
from tests.asset_backed_credit.helper import ABCMixins, APIHelper


class OptionsAPITest(APIHelper, ABCMixins):
    URL = '/asset-backed-credit/options'

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self._set_client_credentials(self.user.auth_token.key)
        abc_currencies = {
            currency: {'order': index, 'is_active': True} for index, currency in enumerate(CREDIT_CURRENCIES)
        }
        Settings.set_cached_json('abc_currencies', abc_currencies)
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.credit, min_limit=500)
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.debit, min_limit=500)
        UserFinancialServiceLimit.set_service_type_limit(service_type=Service.TYPES.loan, min_limit=800)

    def tearDown(self):
        cache.clear()

    def test_currencies_successful(self):
        response = self._get_request()
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        assert 'currencies' in res
        assert all(bool(get_currency_codename(c) in res['currencies']) for c in CREDIT_CURRENCIES)
        assert 'activeCurrencies' in res
        assert all(bool(get_currency_codename(c) in res['activeCurrencies']) for c in CREDIT_CURRENCIES), res[
            'activeCurrencies'
        ]
        assert 'debitCurrencies' in res
        assert all(bool(get_currency_codename(c) in res['debitCurrencies']) for c in DEBIT_CURRENCIES)
        assert 'debitActiveCurrencies' in res
        assert all(bool(get_currency_codename(c) in res['debitActiveCurrencies']) for c in DEBIT_CURRENCIES), res[
            'debitActiveCurrencies'
        ]

    def test_currencies_successful_after_change_cache(self):
        abc_currencies = {
            currency: {'order': index, 'is_active': False} for index, currency in enumerate(CREDIT_CURRENCIES)
        }
        Settings.set_cached_json('abc_currencies', abc_currencies)
        abc_debit_currencies = {
            currency: {'order': index, 'is_active': False} for index, currency in enumerate(DEBIT_CURRENCIES)
        }
        Settings.set_cached_json('abc_debit_currencies', abc_debit_currencies)

        response = self._get_request()
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        assert 'currencies' in res
        assert all(bool(get_currency_codename(c) in res['currencies']) for c in CREDIT_CURRENCIES)
        assert 'activeCurrencies' in res
        assert not res['activeCurrencies']
        assert 'debitCurrencies' in res
        assert all(bool(get_currency_codename(c) in res['debitCurrencies']) for c in DEBIT_CURRENCIES)
        assert 'debitActiveCurrencies' in res
        assert not res['debitActiveCurrencies']

    def test_services(self):
        services = [
            self.create_service(tp=Service.TYPES.debit, is_available=False),
            self.create_service(tp=Service.TYPES.credit),
            self.create_service(
                tp=Service.TYPES.loan,
                options={
                    'provider_fee': '12.34',
                    'periods': [1, 3, 6, 9],
                    'punishment_rate': '1.2',
                    'no_punishment_period': 2,
                    'forced_liquidation_period': 4,
                    'min_principal_limit': 5_000_000_0,
                    'max_principal_limit': 100_000_000_0,
                },
            ),
        ]
        UserFinancialServiceLimit.set_service_limit(services[0], max_limit=100000)
        UserFinancialServiceLimit.set_service_limit(services[1], max_limit=1000)
        UserFinancialServiceLimit.set_service_limit(services[2], max_limit=9000)

        UserFinancialServiceLimit.set_user_type_service_limit(
            user_type=self.user.user_type, service=services[0], max_limit=2000
        )

        limits = {
            services[0].pk: UserServiceLimit(min_limit=500, max_limit=2000),
            services[1].pk: UserServiceLimit(min_limit=500, max_limit=1000),
            services[2].pk: UserServiceLimit(min_limit=800, max_limit=9000),
        }
        services_data = {
            'debit': [serialize_service(services[0], {'limits': limits})],
            'credit': [serialize_service(services[1], {'limits': limits})],
            'loan': [serialize_service(services[2], {'limits': limits})],
        }

        response = self._get_request()
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')

        assert 'services' in res
        for service_type, value in res['services'].items():
            for index, service in enumerate(value):
                assert service['id'] == services_data[service_type][index]['id']
                assert service['provider'] == services_data[service_type][index]['provider']
                assert service['type'] == services_data[service_type][index]['type']
                assert service['isAvailable'] == services_data[service_type][index]['isAvailable']
                assert Decimal(service['minimumDebt']) == services_data[service_type][index]['minimumDebt']
                assert Decimal(service['maximumDebt']) == services_data[service_type][index]['maximumDebt']
                if service_type == 'loan':
                    assert service['periods'] == services_data[service_type][index]['periods']
                    assert service['providerFee'] == services_data[service_type][index]['providerFee']
                    assert service['punishmentRate'] == services_data[service_type][index]['punishmentRate']
                    assert (
                        service['forcedLiquidationPeriod']
                        == services_data[service_type][index]['forcedLiquidationPeriod']
                    )
                    assert service['noPunishmentPeriod'] == services_data[service_type][index]['noPunishmentPeriod']
                    assert service['minPrincipalLimit'] == services_data[service_type][index]['minPrincipalLimit']
                    assert service['maxPrincipalLimit'] == services_data[service_type][index]['maxPrincipalLimit']

    def test_services_order_by_id_reversed(self):
        services = [
            self.create_service(tp=Service.TYPES.debit, is_available=False),
            self.create_service(tp=Service.TYPES.credit),
            self.create_service(tp=Service.TYPES.credit, provider=Service.PROVIDERS.digipay),
        ]
        UserFinancialServiceLimit.set_service_limit(services[0], max_limit=100000)
        UserFinancialServiceLimit.set_service_limit(services[1], max_limit=1000)
        UserFinancialServiceLimit.set_service_limit(services[2], max_limit=9000)

        response = self._get_request()
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        assert services[2].id > services[1].id
        assert res['services']['credit'] == [
            {
                "fee": "0",
                "id": services[2].id,
                "interest": "0",
                "isAvailable": True,
                "maximumDebt": 9000,
                "minimumDebt": 500,
                "provider": "digipay",
                "providerFa": "دیجی‌پی",
                "type": "credit",
                "typeFa": "اعتبار",
            },
            {
                "fee": "0",
                "id": services[1].id,
                "interest": "0",
                "isAvailable": True,
                "maximumDebt": 1000,
                "minimumDebt": 500,
                "provider": "tara",
                "providerFa": "تارا",
                "type": "credit",
                "typeFa": "اعتبار",
            },
        ]

    def test_ratios(self):
        response = self._get_request()
        res = self._check_response(response=response, status_code=status.HTTP_200_OK, status_data='ok')
        assert 'ratios' in res
        assert Decimal(res['ratios']['collateral']) == get_ratios().get('collateral')
        assert Decimal(res['ratios']['margin_call']) == get_ratios().get('margin_call')
        assert Decimal(res['ratios']['liquidation']) == get_ratios().get('liquidation')
        assert 'debitRatios' in res
        assert Decimal(res['debitRatios']['collateral']) == get_ratios(Wallet.WalletType.DEBIT).get('collateral')
        assert Decimal(res['debitRatios']['margin_call']) == get_ratios(Wallet.WalletType.DEBIT).get('margin_call')
        assert Decimal(res['debitRatios']['liquidation']) == get_ratios(Wallet.WalletType.DEBIT).get('liquidation')

    def test_limit_authenticated_and_anonymous_user(self):
        credit_service_1 = self._create_service_with_limit(
            provider=Service.PROVIDERS.tara, tp=Service.TYPES.credit, interest=Decimal(0), limit=Decimal(1000_000)
        )
        UserFinancialServiceLimit.set_user_service_limit(
            user=self.user,
            service=credit_service_1,
            max_limit=600_000,
        )

        credit_service_2 = self._create_service_with_limit(
            provider=Service.PROVIDERS.digipay, tp=Service.TYPES.credit, interest=Decimal(5), limit=Decimal(2000_000)
        )

        loan_service_1 = self._create_service_with_limit(
            provider=Service.PROVIDERS.vency,
            tp=Service.TYPES.loan,
            interest=Decimal('23.45'),
            limit=Decimal(100_000_000),
            options=dict(
                LoanServiceOptions(
                    min_principal_limit=5_000_000,
                    max_principal_limit=50_000_000,
                    periods=[1, 3, 6, 9],
                    provider_fee=Decimal('23.45'),
                    debt_to_grant_ratio=Decimal('1.07'),
                )
            ),
        )

        loan_service_2 = self._create_service_with_limit(
            provider=Service.PROVIDERS.maani,
            tp=Service.TYPES.loan,
            interest=Decimal('17.35'),
            limit=Decimal(200_000_000),
            options=dict(
                LoanServiceOptions(
                    min_principal_limit=10_000_000,
                    max_principal_limit=80_000_000,
                    periods=[1, 3, 6, 9, 12],
                    provider_fee=Decimal('7.8'),
                )
            ),
        )
        UserFinancialServiceLimit.set_user_service_limit(
            user=self.user,
            service=loan_service_2,
            max_limit=67_000_000,
        )

        debit_service = self._create_service_with_limit(
            provider=Service.PROVIDERS.parsian, tp=Service.TYPES.debit, interest=Decimal(0), limit=Decimal(1000_000)
        )

        resp = self._get_request()

        anonymous_client = APIClient()
        a_resp = anonymous_client.get(path=self.URL)

        assert resp.status_code == a_resp.status_code == status.HTTP_200_OK

        services = self._list_to_dict_services(options_data=resp.json())
        a_services = self._list_to_dict_services(options_data=a_resp.json())

        assert len(services['credit']) == len(a_services['credit']) == 2
        assert len(services['loan']) == len(a_services['loan']) == 2
        assert len(services['debit']) == len(a_services['debit']) == 1

        _service = services['credit'][credit_service_1.pk]
        _a_service = a_services['credit'][credit_service_1.pk]
        assert _service['provider'] == _a_service['provider'] == 'tara'
        assert _service['type'] == _a_service['type'] == 'credit'
        assert _service['interest'] == _a_service['interest'] == '0'
        assert _service['minimumDebt'] == _a_service['minimumDebt'] == 500
        assert _service['maximumDebt'] == 600_000
        assert _a_service['maximumDebt'] == 1000_000

        _service = services['credit'][credit_service_2.pk]
        _a_service = a_services['credit'][credit_service_2.pk]
        assert _service['provider'] == _a_service['provider'] == 'digipay'
        assert _service['type'] == _a_service['type'] == 'credit'
        assert _service['interest'] == _a_service['interest'] == '5'
        assert _service['minimumDebt'] == _a_service['minimumDebt'] == 500
        assert _service['maximumDebt'] == _a_service['maximumDebt'] == 2000_000

        _service = services['loan'][loan_service_1.pk]
        _a_service = a_services['loan'][loan_service_1.pk]
        assert _service['provider'] == _a_service['provider'] == 'vency'
        assert _service['type'] == _a_service['type'] == 'loan'
        assert _service['interest'] == _a_service['interest'] == '23.45'
        assert _service['minimumDebt'] == _a_service['minimumDebt'] == 800
        assert _service['maximumDebt'] == _a_service['maximumDebt'] == 100_000_000
        assert _service['minPrincipalLimit'] == _a_service['minPrincipalLimit'] == 5_000_000
        assert _service['maxPrincipalLimit'] == _a_service['maxPrincipalLimit'] == 50_000_000
        assert _service['periods'] == _a_service['periods'] == [1, 3, 6, 9]
        assert _service['providerFee'] == _a_service['providerFee'] == '23.45'
        assert _service['punishmentRate'] is _a_service['punishmentRate'] is None
        assert _service['forcedLiquidationPeriod'] is _a_service['forcedLiquidationPeriod'] is None
        assert _service['noPunishmentPeriod'] is _a_service['noPunishmentPeriod'] is None
        assert _service['debtToGrantRatio'] == _a_service['debtToGrantRatio'] == '1.07'

        _service = services['loan'][loan_service_2.pk]
        _a_service = a_services['loan'][loan_service_2.pk]
        assert _service['provider'] == _a_service['provider'] == 'maani'
        assert _service['type'] == _a_service['type'] == 'loan'
        assert _service['interest'] == _a_service['interest'] == '17.35'
        assert _service['minimumDebt'] == _a_service['minimumDebt'] == 800
        assert _service['maximumDebt'] == 67_000_000
        assert _a_service['maximumDebt'] == 200_000_000
        assert _service['minPrincipalLimit'] == _a_service['minPrincipalLimit'] == 10_000_000
        assert _service['maxPrincipalLimit'] == _a_service['maxPrincipalLimit'] == 80_000_000
        assert _service['periods'] == _a_service['periods'] == [1, 3, 6, 9, 12]
        assert _service['providerFee'] == _a_service['providerFee'] == '7.8'
        assert _service['punishmentRate'] is _a_service['punishmentRate'] is None
        assert _service['forcedLiquidationPeriod'] is _a_service['forcedLiquidationPeriod'] is None
        assert _service['noPunishmentPeriod'] is _a_service['noPunishmentPeriod'] is None
        assert _service['debtToGrantRatio'] is _a_service['debtToGrantRatio'] is None

        _service = services['debit'][debit_service.pk]
        _a_service = a_services['debit'][debit_service.pk]
        assert _service['provider'] == _a_service['provider'] == 'parsian'
        assert _service['type'] == _a_service['type'] == 'debit'
        assert _service['interest'] == _a_service['interest'] == '0'
        assert _service['minimumDebt'] == _a_service['minimumDebt'] == 500
        assert _service['maximumDebt'] == 1000_000
        assert _a_service['maximumDebt'] == 1000_000

    @staticmethod
    def _create_service_with_limit(provider, tp, interest, limit, options=None):
        service = Service.objects.create(
            provider=provider,
            tp=tp,
            is_active=True,
            interest=interest,
            options=options or {},
        )
        UserFinancialServiceLimit.set_service_limit(service=service, max_limit=limit)
        return service

    @staticmethod
    def _list_to_dict_services(options_data):
        services = options_data['services']
        for service_type, service_info_list in services.items():
            services[service_type] = {service_info['id']: service_info for service_info in service_info_list}
        return services
