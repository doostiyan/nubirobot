from django.utils import translation
from django.utils.deprecation import MiddlewareMixin


class LanguageMiddleware(MiddlewareMixin):
    """
    Middleware that sets 'Language' attribute to request object.
    """

    def process_request(self, request):
        lang_code = request.GET.get('lang', None)
        if lang_code:
            translation.activate(lang_code)
            request.LANGUAGE_CODE = translation.get_language()
