import requests

from django.conf import settings

from .logging import log_event


def api_call(url, token=None, ignore_400=False, **kwargs):
    """ Call a API endpoint and return Json data
        This method provides some reasonable default options and
        handles errors.
    """
    kwargs.setdefault('timeout', 3)
    kwargs.setdefault('proxies', settings.DEFAULT_PROXY)
    if token:
        kwargs.setdefault('headers', {})
        kwargs['headers']['Authorization'] = 'Bearer ' + token
    r = requests.post(url, **kwargs)
    if r is None:
        log_event('NoAPIResponse', level='WARNING', category='notice', module='apicall',
            runner='apicall', details='NoResponse: url={}'.format(url))
        return None
    if r.status_code >= 400:
        error_type = 'Server' if r.status_code >= 500 else 'Client'
        if not ignore_400 or error_type == 'Server':
            log_event(
                'API{}Error'.format(error_type), level='WARNING',
                category='notice', module='apicall', runner='apicall',
                details='APIError: status={} url={} response={}'.format(r.status_code, url, r.text))
        return None
    try:
        return r.json()
    except:
        log_event('InvalidAPIResponse', level='WARNING', category='notice', module='apicall',
            runner='apicall', details='InvalidJSON: url={} response={}'.format(url, r.text))
        return None
