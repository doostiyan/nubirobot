import functools
import json

from django.utils import text

from exchange.base.api import get_data, handle_ratelimit
from exchange.base.serializers import serialize


def standardise_oauth2_provider_api(view):
    """Adapt oauth2_provider API to project standards

    It converts input parameter cases from camelCase to snake_case.
    Also converts output dict keys to camelCase, adds `status` key to results and
    `code`-`message` pair on Error with PascalCase-Sentence case format.
    Args:
        view: oauth2_provider JSON APIView

    Returns:
        Standard API View
    """
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if getattr(request, 'limited', False):
            return handle_ratelimit()
        data_attr_name = 'POST' if request.method in ('POST', 'PUT', 'PATCH') else 'GET'
        data = get_data(request)[0].copy()
        for key in tuple(data):
            value = data.pop(key)
            snake_case_key = text.camel_case_to_spaces(key).replace(' ', '_')
            data[snake_case_key] = value[0] if isinstance(value, list) else value
        setattr(request, data_attr_name, data)
        response = view(request, *args, **kwargs)
        content_dict = json.loads(response.content)
        if 'error' in content_dict:
            code = content_dict['error'].title().replace('_', '')
            message = content_dict.get('error_description') or content_dict['error'].capitalize().replace('_', ' ')
            content_dict = {'status': 'failed', 'code': code, 'message': message}
        else:
            content_dict = {'status': 'ok', **serialize(content_dict, convert_to_camelcase=True)}
        response.content = json.dumps(content_dict)
        return response

    return wrapper