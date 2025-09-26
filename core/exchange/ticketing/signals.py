from django.db.models.signals import post_save
from django.dispatch import receiver

from exchange.celery import app as celery_app

from .models import Activity, Ticket


@receiver(post_save, sender=Ticket)
def create_task_for_new_ticket(sender, instance, created, **kwargs):
    if created:
        # Create a new employee task to consider the new ticket.
        celery_app.send_task(
            'admin.create_new_task',
            kwargs={
                'tp': Ticket.TASK_TYPE_CHOICES.ticketing,
                'object_id': instance.pk,
                'queue': instance.topic_id,
                'related_user_id': instance.related_user_id,
            }
        )


@receiver(post_save, sender=Activity)
def create_task_for_new_comment(sender, instance, created, **kwargs):
    if created and instance.type == Activity.TYPES.comment:
        ticket = instance.ticket
        if ticket.state != Ticket.STATE_CHOICES.sent:
            ticket.state = Ticket.STATE_CHOICES.sent
            ticket.save(update_fields=['state'])
            # Create a new employee task to consider the new comment from the user.
            celery_app.send_task(
                'admin.create_new_task',
                kwargs={
                    'tp': Ticket.TASK_TYPE_CHOICES.ticketing,
                    'object_id': ticket.pk,
                    'queue': ticket.topic_id,
                    'related_user_id': ticket.related_user_id,
                }
            )
