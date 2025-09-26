import json
import requests

from django.conf import settings

from exchange.base.models import Settings


def get_padro_verification_token():
    return Settings.get('padro_verification_api_token')


def renew_padro_token():
    """ Renew padro verification API token. The previous token are read
        from Settings table and if renew process succeeds, saved token are updated.

        Sample return value:
        {
            "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiIsImp0aSI6IjQ4NTM2MjlkMGRkYWY4OGViYWI0NGEzYWRhYjcxZDg4Yjk3NTk2YmU2MzZjNWY5ZjUyMmMyZDYzNGU1ODdmYmFlZmUwZWRjNGM2ZjllYTdhIn0.eyJhdWQiOiIxIiwianRpIjoiNDg1MzYyOWQwZGRhZjg4ZWJhYjQ0YTNhZGFiNzFkODhiOTc1OTZiZTYzNmM1ZjlmNTIyYzJkNjM0ZTU4N2ZiYWVmZTBlZGM0YzZmOWVhN2EiLCJpYXQiOjE2MTc2OTg0NjgsIm5iZiI6MTYxNzY5ODQ2OCwiZXhwIjoxNjQ5MjM0NDY4LCJzdWIiOiIxIiwic2NvcGVzIjpbXX0.qbtsN3vk6yOW2u2EvUGCrJY6qEJj5gbxx10OyvtLOy5DKZvKfyyNQrqS_gpaSFgosSnBdtcQwfD8oKTG2p5qAMqA6ZQSFb3Lp2h-Om7keS675zuO6rfUYLEa5wYmIK0nM1a2s_suPWkwFLF3QTBw67CrGjIbdbQJHtJ2B0ZhD8FSDzbkJGRpM3wMTc80HtTTooRH0q9fEJTHqc5yxywFs-u83f8K3XzV6RUg1b-4wlqONSspxTmdICF82iO-SainmHUF55vtiKhpy-AA3jGGGmV0SsbRYFSZQVLSzD6GLKZkSQiPnNRnERJy6aZD7dRWMFv8yKKDFFwAxbAXOY9KIaEPCJyLunaKl1uTd1AVLDqBjrXRYASCCGnEzQximpdAnVclmWrHifylRuW2TefsxtX1vT9-ySd1Mxh0b50LPnbmQ3ZgOsFuPb_p9wBJxTyBgMEDqfmHsG58u-5q6UtyZu8OHsXrU1df2JN5kXKGCKHHiTGPrUC5GcNrCF1rviLTo_CjSxC5vSMPFF4JicQbdFH3BjgvqaUndc7sTGqF0ThLp6zIcEbI3_H3EiUWc8SLVGZQXV8p7CHkzZUTted_svg6k9VnpyosmtkVeUDl3S4LoISQ-jjXS_gLhav3lo9CagbtE0682H5baSwDU4J5MaSuJGbUnzif2GniTSITk9o",
            "token_type": "Bearer"
        }
    """
    padro_username = settings.PADRO_USERNAME
    padro_password = settings.PADRO_PASSWORD
    # Padro Login API Call
    login_api_url = 'https://staging.podro.com/api/v1/login'
    payload = json.dumps({
        "email": padro_username,
        "password": padro_password
    })
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    try:
        api_result = requests.request("POST", login_api_url, headers=headers, data=payload)
        api_result.raise_for_status()
    except requests.exceptions.RequestException:
        return {'result': False}
    access_token = api_result.json()['access_token']

    # Updates tokens in Settings
    if not access_token:
        return {'result': False}
    Settings.set('padro_verification_api_token', access_token)
    return {
        'result': True,
        'accesstoken': access_token,
    }


def get_padro_cities():
    cities = Settings.get_dict('padro_cities')
    if cities:
        return cities
    url = f"https://staging.podro.com/api/v1/cities"
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
    Settings.set_dict('padro_cities', response.json()['source_cities'])
    return response.json()['source_cities']
