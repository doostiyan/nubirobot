from django.test import TestCase

from exchange.accounts.models import User
from exchange.ticketing.models import Ticket, TicketingGroup, Topic


class TestTicket(TestCase):
    def test_set_group_by_topic_if_group_is_none(self):
        user = User.objects.get(pk=201)
        group = TicketingGroup.objects.create(name='group')
        another_group = TicketingGroup.objects.create(name='another-group')
        topic = Topic.objects.create(title='test', group_in_charge=group)
        ticket1 = Ticket.objects.create(created_by=user, related_user=user, content='test-content', topic=topic)
        ticket2 = Ticket.objects.create(
            created_by=user, related_user=user, content='test-content', topic=topic, group=another_group
        )

        ticket1.refresh_from_db()
        ticket2.refresh_from_db()

        assert ticket1.group is not None
        assert ticket2.group is not None
        assert ticket1.group == group
        assert ticket2.group == another_group

        ticket3 = Ticket.objects.create(created_by=user, related_user=user, content='test-content')
        assert ticket3.topic is None
        assert ticket3.group is None

        ticket3.topic = topic
        ticket3.save(update_fields=['topic'])

        ticket3.refresh_from_db()
        assert ticket3.group is not None
        assert ticket3.group == group
