from django.core.exceptions import ValidationError

from exchange.explorer.networkproviders.models import Provider
from exchange.explorer.networkproviders.models.url import URL
from exchange.explorer.utils.exception.custom_exceptions import URLNotFoundException


class UrlService:

    @classmethod
    def get_all_urls(cls):
        return URL.objects.all()

    @classmethod
    def get_url_by_id(cls, url_id):
        return URL.objects.get(id=url_id)

    @classmethod
    def get_or_create_url_by_url_address(cls, url_address):
        return URL.objects.get_or_create(url=url_address)[0]

    @classmethod
    def create_url(cls, url, use_proxy=False):
        return URL.objects.create(url=url, use_proxy=use_proxy)

    @classmethod
    def update_url(cls, url_id, new_url=None, new_use_proxy=None):
        url = cls.get_url_by_id(url_id)
        if new_url is not None:
            url.url = new_url
        if new_use_proxy is not None:
            url.use_proxy = new_use_proxy
        url.save()
        return url

    @classmethod
    def delete_url(cls, url_id):
        url_obj = URL.objects.get(id=url_id)
        if url_obj is None:
            raise URLNotFoundException
        providers_with_default_url = Provider.objects.filter(default_url=url_obj.url)
        if providers_with_default_url:
            raise ValidationError(f"URL cannot be deleted as it is the default URL for provider(s):"
                                  f" {', '.join(providers_with_default_url.values_list('name', flat=True))}")
        url_obj.delete()
