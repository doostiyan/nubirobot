from exchange.base.serializers import register_serializer
from exchange.crm.models import News, NewsTag


@register_serializer(model=News)
def serialize_news(news: News, opts=None):
    data = {
        'id': news.pk,
        'title': news.title,
        'subtitle': news.subtitle,
        'context': news.context,
        'createdAt': news.created_at,
        'image': news.image_serve_url,
        'link': news.link,
        'publishAt': news.publish_at,
        'tags': news.tags.all(),
    }
    return data


@register_serializer(model=NewsTag)
def serialize_tags(tag: NewsTag, opts=None):
    data = {
        'name': tag.name,
        'slug': tag.slug,
        'color': tag.color,
    }
    return data
