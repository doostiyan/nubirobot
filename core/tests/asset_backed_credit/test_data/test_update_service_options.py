from decimal import Decimal
from unittest.mock import patch

import responses
from django.core.cache import cache
from django.test import TestCase

from exchange.asset_backed_credit.externals.providers.azki import AZKI
from exchange.asset_backed_credit.models import Service, UserFinancialServiceLimit
from exchange.asset_backed_credit.services.loan.options import set_all_services_options
from exchange.base.models import Settings
from tests.asset_backed_credit.helper import MockCacheValue, sign_mock


class TestUpdateServiceOptions(TestCase):
    def setUp(self):
        cache.clear()
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()
        Settings.set_cached_json('scrubber_sensitive_fields', [])

    def tearDown(self):
        cache.clear()

    @responses.activate
    @patch.object(AZKI, 'username', 'test-username')
    @patch.object(AZKI, 'password', 'test-password')
    @patch('exchange.asset_backed_credit.externals.providers.base.ProviderAPI.sign', side_effect=sign_mock)
    def test_update_azki_service_options(self, _):
        responses.post(
            url='https://service.azkiloan.com/auth/login',
            json={
                'rsCode': 0,
                'result': {'token': 'test-access-token'},
            },
            status=200,
            match=[
                responses.matchers.json_params_matcher(
                    {
                        'username': 'test-username',
                        'password': 'test-password',
                    }
                ),
            ],
        )

        responses.get(
            url='https://service.azkiloan.com/crypto-exchange/summary',
            status=200,
            json={
                'rsCode': 0,
                'result': {
                    'minimumFinance': 100000000.000,
                    'maximumFinance': 750000000.000,
                    'periods': [12, 18],
                },
            },
        )

        service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.azki, tp=Service.TYPES.loan, is_active=True
        )

        assert service.options == {}

        set_all_services_options()

        service.refresh_from_db()
        assert service.options == {
            'min_principal_limit': 100_000_000,
            'max_principal_limit': 750_000_000,
            'periods': [12, 18],
        }

        service_limits = UserFinancialServiceLimit.get_limits_per_service()[service.id]
        assert service_limits.min_limit == 100_000_000
        assert service_limits.max_limit == Decimal('1.7') * 750_000_000

    def test_get_service_options_returns_none(self):
        service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.vency,
            tp=Service.TYPES.loan,
            is_active=True,
            options={'min_principal_limit': 1000, 'max_principal_limit': 2000, 'periods': [1, 2]},
        )

        set_all_services_options()

        service.refresh_from_db()
        assert service.options == {'min_principal_limit': 1000, 'max_principal_limit': 2000, 'periods': [1, 2]}

        services_limits = UserFinancialServiceLimit.get_limits_per_service()
        assert service.id not in services_limits

    @patch('exchange.asset_backed_credit.services.loan.options.set_service_options')
    def test_set_all_services_options_does_only_filters_loan_services(self, mock_set_service_options):
        service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.azki,
            tp=Service.TYPES.loan,
            is_active=True,
        )
        service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.vency,
            tp=Service.TYPES.loan,
            is_active=True,
        )
        service, _ = Service.objects.get_or_create(
            provider=Service.PROVIDERS.tara,
            tp=Service.TYPES.credit,
            is_active=True,
        )

        set_all_services_options()

        assert mock_set_service_options.call_count == 2
