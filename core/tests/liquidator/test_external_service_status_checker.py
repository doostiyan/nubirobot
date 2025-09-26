import json

import responses
from django.core.cache import cache
from django.test import TestCase
from requests import RequestException

from exchange.liquidator.broker_apis import BrokerBaseAPI
from exchange.liquidator.tasks import task_check_external_broker_service_status


def service_up_but_unavailable(*args, **kwargs):
    json_data = {
        "result": {"status": "unavailable", "time": 1701003817123},
        "message": "successful message",
        "error": "success",
        "hasError": True,
    }
    return 200, {}, json.dumps(json_data)


def service_up_and_available(*args, **kwargs):
    json_data = {
        "result": {"status": "available", "time": 1701003817123},
        "message": "successful message",
        "error": "success",
        "hasError": False,
    }
    return 200, {}, json.dumps(json_data)


def service_unavailable(*args, **kwargs):
    return 500, {}, None


def exception_raised(*args, **kwargs):
    raise RequestException('some error')


class TestExternalServiceStatusChecker(TestCase):
    @responses.activate
    def test_status_set_to_disabled_on_unavailable_response(self):
        responses.add_callback(
            'GET', f'{BrokerBaseAPI.get_base_url()}/liquidation/status', callback=service_up_but_unavailable
        )
        BrokerBaseAPI.activate_broker()

        task_check_external_broker_service_status()

        assert BrokerBaseAPI.is_active() == False

    @responses.activate
    def test_status_set_to_disabled_on_unavailable_service(self):
        responses.add_callback(
            'GET', f'{BrokerBaseAPI.get_base_url()}/liquidation/status', callback=service_unavailable
        )
        BrokerBaseAPI.activate_broker()

        task_check_external_broker_service_status()

        assert BrokerBaseAPI.is_active() == False

    @responses.activate
    def test_status_set_to_disabled_on_exception(self):
        responses.add_callback('GET', f'{BrokerBaseAPI.get_base_url()}/liquidation/status', callback=exception_raised)
        BrokerBaseAPI.activate_broker()

        task_check_external_broker_service_status()

        assert BrokerBaseAPI.is_active() == False

    @responses.activate
    def test_status_set_to_available_on_success(self):
        responses.add_callback(
            'GET', f'{BrokerBaseAPI.get_base_url()}/liquidation/status', callback=service_up_and_available
        )
        BrokerBaseAPI.deactivate_broker()
        cache.delete(BrokerBaseAPI.failure_rate_cache_key)

        task_check_external_broker_service_status()

        assert BrokerBaseAPI.is_active() == True
