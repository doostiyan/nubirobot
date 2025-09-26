from exchange.base.serializers import register_serializer
from exchange.marketing.models import Suggestion, SuggestionCategory


@register_serializer(model=SuggestionCategory)
def serialize_suggestion_category(category, opts=None):
    return {
        'id': category.pk,
        'priority': category.get_priority_display(),
        'title': category.title,
    }


@register_serializer(model=Suggestion)
def serialize_suggestion(suggestion, opts=None):
    return {
        'id': suggestion.pk,
        'priority': suggestion.category.get_priority_display(),
        'title': suggestion.category.title,
        'description': suggestion.description,
        'name': suggestion.name,
        'mobile': suggestion.mobile,
        'email': suggestion.email,
    }
