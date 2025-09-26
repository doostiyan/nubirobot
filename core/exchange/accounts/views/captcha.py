from django.http import JsonResponse
from django_ratelimit.decorators import ratelimit

from exchange.accounts.captcha import CaptchaHandler, DjangoCaptcha
from exchange.base.api import public_post_api
from exchange.base.decorators import measure_api_execution
from exchange.base.http import get_client_country


@ratelimit(key='ip', rate='60/m', block=True)
@public_post_api
def captcha_select_view(request):
    """View to determine which captcha types can be shown for the user.

    POST /captcha/select
    """
    country = get_client_country(request)
    usage = request.g('usage')
    captcha_types = CaptchaHandler.get_acceptable_types(country=country, usage=usage)
    return JsonResponse({
        'status': 'ok',
        'acceptableTypes': captcha_types,
    })


@ratelimit(key='ip', rate='30/m', block=True)
@measure_api_execution(api_label='authGetCaptchaKey')
def get_captcha_key(request):
    key, image_url = DjangoCaptcha.generate()
    return JsonResponse({
        'status': 'ok',
        'captcha': {
            'key': key,
            'image_url': image_url
        }
    })
