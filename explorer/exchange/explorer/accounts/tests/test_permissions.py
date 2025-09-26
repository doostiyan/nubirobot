import pytest
from django.urls import reverse

from ..models import User


@pytest.mark.permission
def test_get_dashboard_with_no_jwt_token_should_return_401(client):
    url = reverse('accounts:dashboard')
    response = client.get(url)
    assert response.status_code == 401
