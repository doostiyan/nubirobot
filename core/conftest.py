import os
import re
import subprocess
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.management import call_command
from pytest_django.fixtures import _set_suffix_to_test_databases
from pytest_django.lazy_django import skip_if_no_django

from exchange.base.metrics import MetricHandler
from exchange.broker.broker.client.testing import (  # noqa: I001, RUF100, F401, W0611
    producer_write_event,
    producer_write_obj,
)


def pytest_addoption(parser):
    parser.addoption(
        '--runslow', action='store_true', default=False, help='run slow tests'
    )


def pytest_collection_modifyitems(config, items):
    skip_slow = pytest.mark.skipif(not config.getoption('--runslow'), reason='need --runslow option to run')
    skip_interactive = pytest.mark.skipif(config.getoption('--capture') != 'no', reason='need -s option to run')
    for item in items:
        if 'slow' in item.keywords:
            item.add_marker(skip_slow)
        if 'interactive' in item.keywords:
            item.add_marker(skip_interactive)


def pytest_configure(config):
    config.addinivalue_line('markers', 'slow: mark test as slow to run')
    config.addinivalue_line('markers', 'unit: mark test as unit to run')
    config.addinivalue_line('markers', 'matcher: mark test as matcher to run')
    config.addinivalue_line('markers', 'matcherFull: mark test as matcherFull to run')
    config.addinivalue_line('markers', 'interactive: mark test as interactive to run')


@pytest.fixture(scope='session', autouse=True)
def metric_handler_backend():
    with patch.object(MetricHandler, 'is_redis', return_value=True), patch.object(
        MetricHandler, 'is_kafka', return_value=False
    ):
        yield


@pytest.fixture(scope='session', autouse=True)
def session_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command('loaddata', 'system', 'test_data')


@pytest.fixture(scope='module', autouse=True)
def module_setup():
    cache.clear()


@pytest.fixture(autouse=True)
def cleanup():
    from exchange.wallet.estimator import PriceEstimator

    PriceEstimator.get_price_range.clear()


def _get_git_branch():
    """Returns the current Git branch name."""
    try:
        branch_name = subprocess.check_output(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD']
        ).strip().decode('utf-8')
        if not branch_name:
            raise ValueError
        return branch_name
    except subprocess.CalledProcessError:
        return 'master'


# Original code: https://github.com/pytest-dev/pytest-django/blob/bd2ae62968aaf97c6efc7e02ff77ba6160865435/pytest_django/fixtures.py#L46
@pytest.fixture(scope='session')
def django_db_modify_db_settings_xdist_suffix(request):
    skip_if_no_django()

    from django.conf import settings

    xdist_suffix = getattr(request.config, 'workerinput', {}).get('workerid')
    if xdist_suffix:
        # 'gw0' -> '1', 'gw1' -> '2', ...
        suffix = str(int(xdist_suffix.replace('gw', '')) + 1)
        _set_suffix_to_test_databases(suffix=suffix)

    branch_name = _get_git_branch()
    if not settings.IS_CI_RUNNER:
        if branch_name.startswith('release'):
            _set_suffix_to_test_databases(suffix='release')
    else:
        branch_name = os.environ.get('BRANCH_NAME', branch_name)
        _set_suffix_to_test_databases(suffix=sanitize_branch_name(branch_name))


def sanitize_branch_name(branch_name):
    # Convert to lowercase
    branch_name = branch_name.lower()
    # Remove non-alphanumeric characters
    sanitized_name = re.sub(r'[^a-z0-9]', '', branch_name)
    return sanitized_name
