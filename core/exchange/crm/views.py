from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django_ratelimit.decorators import ratelimit

from exchange.base.api import APIView
from exchange.base.api_v2_1 import paginate
from exchange.base.serializers import serialize

from .models import News, NewsTag


class NewsList(APIView):
    """GET /crm/news/list"""

    @method_decorator(ratelimit(key='user_or_ip', rate='30/m', method='GET', block=True))
    def get(self, request):
        tag_slug = request.GET.get('tag', None)
        news = cache.get(News.CACHE_KEY)
        if news is None:
            news_query = News.get_active_news()
            news = serialize(news_query)
            cache.set(News.CACHE_KEY, news, News.CACHE_TTL)

        if tag_slug:
            news = [n for n in news if any([tag for tag in n['tags'] if tag['slug'] == tag_slug])]

        result = paginate(news, self)
        return self.response(dict(status='ok', result=result['result'], hasNext=result['hasNext']))


class NewsTags(APIView):
    """GET /crm/news/tags/list"""

    @method_decorator(ratelimit(key='user_or_ip', rate='30/1m'), name='get')
    @method_decorator(cache_page(60, key_prefix='news_tags'), name='get')
    def get(self, request):
        return self.response({'status': 'ok', 'result': NewsTag.objects.all()})
