from unittest.mock import patch

import responses
from django.test import TestCase
from responses import matchers

from exchange.asset_backed_credit.externals.providers import DIGIPAY
from exchange.asset_backed_credit.externals.providers.digipay.api import DigipayAPI
from exchange.asset_backed_credit.models import Service
from exchange.asset_backed_credit.models.store import Store
from exchange.asset_backed_credit.services.store import fetch_stores
from tests.asset_backed_credit.helper import ABCMixins, MockCacheValue


class StoreServiceTestCase(TestCase, ABCMixins):
    def setUp(self):
        self.service = self.create_service(provider=Service.PROVIDERS.digipay)
        mock_cache = MockCacheValue()
        patch(
            'exchange.asset_backed_credit.externals.providers.base.get_redis_connection', side_effect=mock_cache
        ).start()
        patch('exchange.asset_backed_credit.services.logging.get_redis_connection', side_effect=mock_cache).start()

    @responses.activate
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    def test_fetch_provider_stores_creates_updates_and_deactivates(self):
        Store.objects.create(
            service=self.service,
            url='old.com',
            title='Old Store Title',
            active=True,
        )
        Store.objects.create(
            service=self.service,
            url='inactive.com',
            title='Inactive Store Title',
            active=True,
        )
        Store.objects.create(
            service=self.service,
            url='reactivated.com',
            title='Reactivated Store Title',
            active=False,
        )

        url = f'{DigipayAPI.BASE_URL}/oauth/token'
        responses.post(
            url=url,
            json={
                'access_token': 'ACCESS_TOKEN',
                'refresh_token': 'REFRESH_TOKEN',
                'token_type': 'Bearer',
                'expires_in': 599,
            },
            status=200,
            match=[
                responses.matchers.header_matcher(
                    {'Authorization': 'Basic ZGlnaXBheS1jbGllbnQtaWQ6ZGlnaXBheS1jbGllbnQtc2VjcmV0'}
                ),
                responses.matchers.urlencoded_params_matcher(
                    {
                        'username': 'digipay-username',
                        'password': 'digipay-password',
                        'grant_type': 'password',
                    }
                ),
            ],
        )
        url = f'{DigipayAPI.BASE_URL}/dpx/stores/search?page=0&size=250'
        responses.add(
            responses.POST,
            url,
            json={
                'result': {
                    'title': 'SUCCESS',
                    'status': 0,
                    'message': '',
                    'level': 'INFO',
                },
                'stores': [
                    {'title': 'New Store', 'url': 'new.com'},
                    {'title': 'Old Store Updated', 'url': 'old.com'},
                    {'title': 'Reactivated Store Title', 'url': 'reactivated.com'},
                ],
                'totalElements': 3,
                'totalPages': 1,
            },
            status=200,
            match=[
                matchers.json_params_matcher(
                    {
                        'restrictions': [
                            {'type': 'simple', 'field': 'state.disabled', 'operation': 'eq', 'value': False},
                            {'type': 'collection', 'field': 'types', 'operation': 'eq', 'values': [0]},
                        ],
                        'orders': [{'order': 'asc', 'field': 'priority'}],
                    }
                )
            ],
        )

        fetch_stores()

        assert Store.objects.filter(service=self.service, url='new.com').exists()
        new = Store.objects.get(service=self.service, url='new.com')
        assert new.title == 'New Store'
        assert new.active is True

        old = Store.objects.get(service=self.service, url='old.com')
        assert old.title == 'Old Store Updated'
        assert old.active is True

        inactive = Store.objects.get(service=self.service, url='inactive.com')
        assert inactive.title == 'Inactive Store Title'
        assert inactive.active is False

        reactivated = Store.objects.get(service=self.service, url='reactivated.com')
        assert reactivated.title == 'Reactivated Store Title'
        assert reactivated.active is True

    @responses.activate
    @patch.object(DIGIPAY, 'username', 'digipay-username')
    @patch.object(DIGIPAY, 'password', 'digipay-password')
    @patch.object(DIGIPAY, 'client_id', 'digipay-client-id')
    @patch.object(DIGIPAY, 'client_secret', 'digipay-client-secret')
    def test_fetch_stores_reports_exception(self):
        Store.objects.create(
            service=self.service,
            url='old.com',
            title='Old Store Title',
            active=True,
        )
        Store.objects.create(
            service=self.service,
            url='inactive.com',
            title='Inactive Store Title',
            active=True,
        )
        Store.objects.create(
            service=self.service,
            url='reactivated.com',
            title='Reactivated Store Title',
            active=False,
        )

        url = f'{DigipayAPI.BASE_URL}/oauth/token'
        responses.post(
            url=url,
            json={
                'access_token': 'ACCESS_TOKEN',
                'refresh_token': 'REFRESH_TOKEN',
                'token_type': 'Bearer',
                'expires_in': 599,
            },
            status=200,
            match=[
                responses.matchers.header_matcher(
                    {'Authorization': 'Basic ZGlnaXBheS1jbGllbnQtaWQ6ZGlnaXBheS1jbGllbnQtc2VjcmV0'}
                ),
                responses.matchers.urlencoded_params_matcher(
                    {
                        'username': 'digipay-username',
                        'password': 'digipay-password',
                        'grant_type': 'password',
                    }
                ),
            ],
        )
        url = f'{DigipayAPI.BASE_URL}/dpx/stores/search?page=0&size=250'
        responses.add(
            responses.POST,
            url,
            json={
                'result': {
                    'title': 'FAILURE',
                    'status': 0,
                    'message': '',
                    'level': 'INFO',
                },
            },
            status=422,
            match=[
                matchers.json_params_matcher(
                    {
                        'restrictions': [
                            {'type': 'simple', 'field': 'state.disabled', 'operation': 'eq', 'value': False},
                            {'type': 'collection', 'field': 'types', 'operation': 'eq', 'values': [0]},
                        ],
                        'orders': [{'order': 'asc', 'field': 'priority'}],
                    }
                )
            ],
        )

        with patch('exchange.asset_backed_credit.services.store.report_exception') as mock_report:
            fetch_stores()

        assert mock_report.call_count == 1

        assert not Store.objects.filter(service=self.service, url='new.com').exists()

        old = Store.objects.get(service=self.service, url='old.com')
        assert old.title == 'Old Store Title'
        assert old.active is True

        inactive = Store.objects.get(service=self.service, url='inactive.com')
        assert inactive.title == 'Inactive Store Title'
        assert inactive.active is True

        inactive = Store.objects.get(service=self.service, url='reactivated.com')
        assert inactive.title == 'Reactivated Store Title'
        assert inactive.active is False
