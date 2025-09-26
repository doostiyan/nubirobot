from typing import List

import pytest
from _pytest.config import Config, Parser
from _pytest.nodes import Item
from django.core.cache import cache as _cache
from django.core.management import call_command
from pytest_django import DjangoDbBlocker
from rest_framework.test import APIClient


@pytest.fixture
def django_cache() -> _cache:
    """Safe alias for Django's cache object, avoiding conflict with pytest's built-in 'cache'."""
    return _cache


def pytest_addoption(parser: Parser) -> None:
    parser.addoption(
        '--runslow', action='store_true', default=False, help='run slow tests'
    )


def pytest_collection_modifyitems(config: Config, items: List[Item]) -> None:
    if config.getoption('--runslow'):
        return
    skip_slow = pytest.mark.skip(reason='need --runslow option to run')
    for item in items:
        if 'slow' in item.keywords:
            item.add_marker(skip_slow)


def pytest_configure(config: Config) -> None:
    config.addinivalue_line('markers', 'slow: mark test as slow to run')
    config.addinivalue_line('markers', 'unit: mark test as unit to run')


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup: object, django_db_blocker: DjangoDbBlocker) -> None:
    _ = django_db_setup
    with django_db_blocker.unblock():
        call_command('loadproviders', 'all')
        call_command('loadbaseurls', 'all')
        call_command('setnetworkstype')


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()
