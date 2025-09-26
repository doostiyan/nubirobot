import pytest
from django.urls import reverse
from rest_framework import status
from urllib.parse import urlencode
from exchange.explorer.accounts.models import User


@pytest.mark.django_db
@pytest.mark.service
def test_logout_view(client):
    username, password, email = 'test', 'testPassword', 'test@gmail.com'
    user = User.objects.create_user(username=username, email=email, password=password)
    user.is_staff = True
    user.save()
    login_url = reverse('authentication:token_obtain_pair')
    login_response = client.post(login_url, {'username': username, 'password': password})
    assert login_response.status_code == status.HTTP_200_OK
    data = login_response.json()
    valid_token = data.get('refresh')
    logout_url = reverse("authentication:token_blacklist")
    logout_response = client.post(logout_url, {'refresh': valid_token})
    assert logout_response.status_code == status.HTTP_205_RESET_CONTENT
    refresh_url = reverse('authentication:token_refresh')
    response = client.post(refresh_url, {'refresh': valid_token})
    assert response.status_code == status.HTTP_403_FORBIDDEN
