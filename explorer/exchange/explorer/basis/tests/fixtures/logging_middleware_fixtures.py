from typing import Any, Optional

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import path
from rest_framework.request import Request


def dummy_view(_request: Request) -> HttpResponse:
    return HttpResponse('{"message": "Success"}', status=200, content_type='application/json')


urlpatterns = [
    path('test-path/', dummy_view, name='test_view'),
    path('metrics/', dummy_view, name='metrics_view'),
]


@pytest.fixture
def factory() -> RequestFactory:
    return RequestFactory()


def find_header_case_insensitive(headers: dict, key: str) -> Optional[Any]:
    key_lower = key.lower()
    for h_key, h_value in headers.items():
        if h_key.lower() == key_lower:
            return h_value
    return None
