from exchange.base.serializers import register_serializer
from .models import Topic, Ticket, Activity


@register_serializer(Topic)
def serialize_topic(topic):
    return {
        'id': topic.pk,
        'title': topic.title
    }


@register_serializer(Activity)
def serialize_comment(activity):
    return {
        'actorName': activity.actor_name,
        'content': activity.content,
        'filesUrls': activity.files_urls,
        'createdAt': activity.created_at,
        'seenAt': activity.seen_at,
    }


@register_serializer(Ticket)
def serialize_ticket(ticket, opts):
    level = opts.get('level', 1)
    data = {
        'id': ticket.pk,
        'topic': serialize_topic(ticket.topic) if ticket.topic else {},
        'state': Ticket.STATE_CHOICES._triples[ticket.state][1],
        'stateName': ticket.state_name,
        'createdAt': ticket.created_at,
        'content': ticket.content,
        'rating': ticket.rating,
    }

    if level >= 2:
        data['filesUrls'] = ticket.files_urls
        data['comments'] = [serialize_comment(_ticket) for _ticket in ticket.comments.order_by('created_at')]
        data['ratingNote'] = ticket.rating_note

    return data
