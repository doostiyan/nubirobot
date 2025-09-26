import requests
from exchange.base.api import api
from exchange.gift.functions import get_padro_verification_token, renew_padro_token


@api
def get_padro_provinces(request):
    """
    Get Padro provinces
    """
    url = "https://staging.podro.com/api/v1/provinces"

    payload = {}
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {get_padro_verification_token()}'
    }

    response = requests.request("GET", url, headers=headers, data=payload)
    if response.status_code == 401:
        renew_padro_token()
        headers['Authorization'] = f'Bearer {get_padro_verification_token()}'
        response = requests.request("GET", url, headers=headers, data=payload)
    response.raise_for_status()
    return {
        'status': 'ok',
        'data': response.json()['data']
    }


@api
def get_padro_province_cities(request, province_code):
    """
    Get Padro cities of The Province
    """
    url = f"https://staging.podro.com/api/v1/provinces/{province_code}/cities"

    payload = {}
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {get_padro_verification_token()}'
    }

    response = requests.request("GET", url, headers=headers, data=payload)
    if response.status_code == 401:
        renew_padro_token()
        headers['Authorization'] = f'Bearer {get_padro_verification_token()}'
        response = requests.request("GET", url, headers=headers, data=payload)
    response.raise_for_status()
    return {
        'status': 'ok',
        'data': response.json()['data']
    }
