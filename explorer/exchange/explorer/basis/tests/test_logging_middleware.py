from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.test import override_settings

from exchange.explorer.basis.tests.fixtures.logging_middleware_fixtures import (
    dummy_view,
    factory,
    find_header_case_insensitive,
    urlpatterns,
)
from exchange.explorer.utils.logging_middleware import ELKLoggingMiddleware

PATCH_PATH = 'exchange.blockchain.service_based.logging.logger.info'


@pytest.fixture
def clear_ip_cache():
    # Only clear the specific cache keys used by the logging middleware
    cache.delete_pattern('ip_anonymization_*')
    yield
    # Clean up after the test
    cache.delete_pattern('ip_anonymization_*')


@pytest.mark.django_db
@patch(PATCH_PATH)
@override_settings(ROOT_URLCONF=__name__)
def test__process_response__when_new_ip_in_header__should_anonymize_to_client1(mock_logger, factory, clear_ip_cache):
    middleware = ELKLoggingMiddleware(dummy_view)
    request = factory.get('/test-path/', HTTP_X_REAL_IP='192.168.1.1')

    middleware(request)

    mock_logger.assert_called_once()
    logged_extra = mock_logger.call_args.kwargs['extra']

    anonymized_ip = find_header_case_insensitive(logged_extra['request_headers'], 'X-REAL-IP')
    assert anonymized_ip == 'client1'


@pytest.mark.django_db
@patch(PATCH_PATH)
@override_settings(ROOT_URLCONF=__name__)
def test__process_response__when_same_ip_in_subsequent_request__should_use_cached_client_id(mock_logger, factory, clear_ip_cache):
    middleware = ELKLoggingMiddleware(dummy_view)
    middleware(factory.get('/test-path/', HTTP_X_REAL_IP='192.168.1.1'))
    middleware(factory.get('/test-path/', HTTP_X_REAL_IP='192.168.1.1'))
    expected_call_count: int = 2

    assert mock_logger.call_count == expected_call_count
    logged_extra = mock_logger.call_args.kwargs['extra']
    anonymized_ip = find_header_case_insensitive(logged_extra['request_headers'], 'X-REAL-IP')
    assert anonymized_ip == 'client1'


@pytest.mark.django_db
@patch(PATCH_PATH)
def test__process_response__when_path_is_excluded__should_not_log(mock_logger, factory, clear_ip_cache):
    middleware = ELKLoggingMiddleware(dummy_view)
    middleware(factory.get('/metrics/'))

    mock_logger.assert_not_called()


@pytest.mark.django_db
@patch(PATCH_PATH)
@override_settings(ROOT_URLCONF=__name__)
def test__process_response__when_different_ips__should_get_different_anonymized_ids(mock_logger, factory, clear_ip_cache):
    middleware = ELKLoggingMiddleware(dummy_view)

    middleware(factory.get('/test-path/', HTTP_X_REAL_IP='192.168.1.1'))
    middleware(factory.get('/test-path/', HTTP_X_REAL_IP='192.168.1.2'))
    middleware(factory.get('/test-path/', HTTP_X_REAL_IP='192.168.1.3'))
    expected_call_count: int = 3

    assert mock_logger.call_count == expected_call_count

    calls = mock_logger.call_args_list

    anonymized_ips = [
        find_header_case_insensitive(call.kwargs['extra']['request_headers'], 'X-REAL-IP')
        for call in calls
    ]

    assert len(set(anonymized_ips)) == expected_call_count, 'Each IP should get a different anonymized ID'
    assert anonymized_ips == ['client1', 'client2', 'client3'], 'IPs should be anonymized in order'
