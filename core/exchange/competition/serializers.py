from exchange.base.serializers import register_serializer
from .models import Competition, CompetitionRegistration


@register_serializer(model=Competition)
def serialize_competition(competition, **kwargs):
    return {
        'id': competition.id,
        'name': competition.name,
        'isActive': competition.is_active,
        'initialBalance': competition.initial_balance,
    }


@register_serializer(model=CompetitionRegistration)
def serialize_competition_registration(competition_registration, **kwargs):
    return {
        'id': competition_registration.id,
        'user': competition_registration.user_display_name,
        'isActive': competition_registration.is_active,
        'currentBalance': competition_registration.current_balance,
    }
