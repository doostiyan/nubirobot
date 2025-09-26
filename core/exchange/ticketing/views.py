import uuid

import bleach
import magic
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django_ratelimit.decorators import ratelimit
from PIL import UnidentifiedImageError

from exchange.accounts.models import UploadedFile
from exchange.base.api import api, get_api, post_api
from exchange.base.calendar import ir_now
from exchange.base.functions import serve, watermark_gif, watermark_image

from ..base.parsers import parse_int, parse_str
from .forms import CommentActivityForm, TicketForm
from .models import Activity, Ticket, Topic
from .serializers import serialize_ticket, serialize_topic
from .utils import escape


@ratelimit(key='user_or_ip', rate='30/1m', block=True)
@get_api
def get_topics(request):
    """ API for getting defined ticketing topics

        GET /ticketing/topics

        Sample result - Success
        {
            "status": "ok",
            "data": {
                "topics": [
                    {
                        "id": 1,
                        "title": "پشتیبانی"
                    },
                    {
                        "id": 2,
                        "title": "مالی"
                    }
                ]
            }
        }
    """

    topics_query = Topic.objects.filter(show_to_users=True).order_by('-priority', 'title')
    topics = [serialize_topic(topic) for topic in topics_query]

    return {
        'status': 'ok',
        'data': {
            'topics': topics
        }
    }


@ratelimit(key='user_or_ip', rate='30/1m', block=True)
@get_api
def get_list_of_user_tickets(request):
    """API for getting list of user tickets

    GET /ticketing/tickets

    Sample result - success
    {
        "status": "ok",
        "data": {
            "tickets": [
                {
                    "id": 1000003,
                    "topic": {
                        "id": 1,
                        "title": "پشتیبانی"
                    },
                    "state_name": "ارسال‌شده",
                    "created_at": "2022-04-06T18:37:50.848675+00:00",
                    "content": "<p>متن تیکت برای پشتیبانی</p>"
                },
            ]
        }
    }

    """
    user = request.user
    tickets = [serialize_ticket(ticket, opts={'level': 1}) for ticket in
               Ticket.objects.filter(related_user=user, is_private=False).order_by('-created_at')]

    return {
        'status': 'ok',
        'data': {
            'tickets': tickets
        }
    }


@ratelimit(key='user_or_ip', rate='60/1m', block=True)
@api
def get_details_of_ticket(request, pk):
    """API for getting details of ticket

    POST /ticketing/tickets/<ticket_id>

    Sample result - success
    {
        "status": "ok",
        "data": {
            "ticket": {
                "id": 1000003,
                "topic": {
                    "id": 1,
                    "title": "پشتیبانی"
                },
                "state_name": "ارسال‌شده",
                "created_at": "2022-04-06T18:37:50.848675+00:00",
                "content": "<p>متن تیکت برای پشتیبانی</p>",
                "files_urls": [],
                "comments": []
            }
        }
    }

    """
    user = request.user
    tickets = Ticket.objects.filter(related_user=user, is_private=False)
    try:
        ticket = tickets.get(pk=pk)
        comments_to_be_seen = ticket.comments.filter(seen_at=None).exclude(actor=user)
        comments_to_be_seen.update(seen_at=ir_now())

        obj = serialize_ticket(ticket, opts={'level': 2})
        return {
            'status': 'ok',
            'data': {
                'ticket': obj
            }
        }
    except Ticket.DoesNotExist:
        return {
            'status': 'failed',
            'code': 'NotFound',
            'message': 'ticket does not exist.'
        }


@ratelimit(key='user_or_ip', rate='10/1m', block=True)
@post_api
def post_ticket(request):
    """API for create a new ticket

    POST /ticketing/tickets/create

    Initial status of created ticket is : sent (ارسال شده)
    In success status as result you get details of the created ticket
    """
    user = request.user

    form = TicketForm(data=request.data)
    if form.is_valid():
        _files = request.FILES.getlist('files')
        if len(_files) > 10:
            return {
                'status': 'failed',
                'code': 'TooManyFiles',
                'message': 'A maximum of 10 files is allowed.',
            }

        for f in _files:
            if f.size > settings.MAX_TICKET_ATTACHMENT_UPLOAD_SIZE:
                return {
                    'status': 'failed',
                    'code': 'TooLargeFile',
                    'message': 'Some uploaded files are too large.',
                }

            file_format = magic.from_buffer(f.file.read(2048), mime=True)
            f.file.seek(0)
            if not file_format.startswith('image/'):
                return {
                    'status': 'failed',
                    'code': 'InvalidMimeType',
                    'message': 'Incorrect mime type.'
                }
            f.file_format = file_format
        ticket = form.save(commit=False)
        ticket.created_by = user
        ticket.related_user = user
        ticket.save()

        for f in _files:
            uploaded_file = UploadedFile(filename=uuid.uuid4(), user=user, tp=UploadedFile.TYPES.ticketing_attachment)

            with open(uploaded_file.disk_path, 'wb+') as destination:
                if f.file_format == 'image/gif':
                    watermark_gif(f.file, destination)
                else:
                    try:
                        watermark_image(f.file, destination)
                    except UnidentifiedImageError:
                        continue
            uploaded_file.save()
            ticket.files.add(uploaded_file)

        return {
            'status': 'ok',
            'data': {
                'ticket': serialize_ticket(ticket, opts={'level': 2})
            }
        }
    else:
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': form.errors
        }


@ratelimit(key='user_or_ip', rate='30/1m', block=True)
@post_api
def post_comment(request):
    """API for create a new comment for specified ticket

    POST /ticketing/comments/create

    In success status as result you get details of the ticket with comments
    """
    user = request.user
    form = CommentActivityForm(user, request.POST)
    if form.is_valid():
        _files = request.FILES.getlist('files')
        if len(_files) > 10:
            return {
                'status': 'failed',
                'code': 'TooManyFiles',
                'message': 'A maximum of 10 files is allowed.',
            }
        # Check sizes
        for f in _files:
            if f.size > settings.MAX_TICKET_ATTACHMENT_UPLOAD_SIZE:
                return {
                    'status': 'failed',
                    'code': 'TooLargeFile',
                    'message': 'Some uploaded files are too large.',
                }
            file_format = magic.from_buffer(f.file.read(2048), mime=True)
            f.file.seek(0)
            if not file_format.startswith('image/'):
                return {
                    'status': 'failed',
                    'code': 'InvalidMimeType',
                    'message': 'Incorrect mime type.'
                }
            f.file_format = file_format
        comment = form.save(commit=False)
        comment.actor = user
        comment.type = Activity.TYPES.comment
        comment.save()
        ticket = comment.ticket
        ticket.state = Ticket.STATE_CHOICES.sent if not ticket.assigned_to else Ticket.STATE_CHOICES.pending
        ticket.save(update_fields=['state'])

        for f in _files:
            uploaded_file = UploadedFile(filename=uuid.uuid4(), user=user, tp=UploadedFile.TYPES.ticketing_attachment)
            with open(uploaded_file.disk_path, 'wb+') as destination:
                if f.file_format == 'image/gif':
                    watermark_gif(f.file, destination)
                else:
                    try:
                        watermark_image(f.file, destination)
                    except UnidentifiedImageError:
                        continue
            uploaded_file.save()
            comment.files.add(uploaded_file)

        return {
            'status': 'ok',
            'data': {
                'ticket': serialize_ticket(ticket, opts={'level': 2})
            }
        }
    else:
        return {
            'status': 'failed',
            'code': 'ValidationError',
            'message': form.errors
        }


@ratelimit(key='user_or_ip', rate='10/1m', block=True)
@get_api
def download_ticket_attachment(request, file_hash):
    try:
        file = UploadedFile.objects.get(filename=file_hash, user=request.user)
    except ValidationError:
        return {
            'status': 'failed',
            'code': 'InvalidFilename',
            'message': 'Invalid ticket attachment filename.'
        }
    except UploadedFile.DoesNotExist:
        return {
            'status': 'failed',
            'code': 'NotFound',
            'message': 'Ticket attachment does not exist.'
        }

    if file.tp != UploadedFile.TYPES.ticketing_attachment:
        return {
            'status': 'failed',
            'code': 'InvalidFileType',
            'message': 'The file type is not a ticket attachment.'
        }

    return serve(file.relative_path, document_root=settings.MEDIA_ROOT)


@ratelimit(key='user_or_ip', rate='20/1m', block=True)
@post_api
def close_ticket(request, pk):
    """API for closing a resolved ticket

    POST /ticketing/tickets/<ticket_id>/close

    """

    user = request.user
    try:
        with transaction.atomic():
            ticket = Ticket.objects.filter(related_user=user, is_private=False, pk=pk).exclude(
                state=Ticket.STATE_CHOICES.closed,
            ).select_for_update().get()

            Activity.objects.create(
                actor=user,
                ticket=ticket,
                type=Activity.TYPES.log,
                content='تیکت توسط کاربر بسته شده است',
            )
            ticket.close()
            return {
                'status': 'ok',
                'data': {
                    'ticket': serialize_ticket(ticket, opts={'level': 2})
                }
            }
    except Ticket.DoesNotExist:
        return {
            'status': 'failed',
            'code': 'NotFound',
            'message': 'Ticket does not exist.'
        }


@ratelimit(key='user_or_ip', rate='20/1m', block=True)
@post_api
def rate_ticket(request, pk):
    """API for rating a closed ticket

    POST /ticketing/tickets/<ticket_id>/rate

    """

    user = request.user
    try:
        with transaction.atomic():
            ticket = Ticket.objects.filter(related_user=user, is_private=False, pk=pk).select_for_update().get()
            if ticket.rating:
                return {
                    'status': 'failed',
                    'code': 'AlreadyRated',
                    'message': 'Ticket is already rated.'
                }
            if ticket.state != Ticket.STATE_CHOICES.closed:
                return {
                    'status': 'failed',
                    'code': 'UnclosedTicket',
                    'message': 'Ticket is not closed yet.'
                }
            ticket_rating = parse_int(request.g('rating'), required=True)
            if not 0 < ticket_rating < 6:
                return {
                    'status': 'failed',
                    'code': 'ValidationError',
                    'message': {'rating': ['must be an integer in range 1 to 5.']}
                }
            ticket_rating_note = escape(bleach.clean(parse_str(request.g('ratingNote'), required=False)))
            ticket.rating = ticket_rating
            ticket.rating_note = ticket_rating_note
            ticket.save(update_fields=('rating_note', 'rating'))
            return {
                'status': 'ok',
                'data': {
                    'ticket': serialize_ticket(ticket, opts={'level': 2})
                }
            }

    except Ticket.DoesNotExist:
        return {
            'status': 'failed',
            'code': 'NotFound',
            'message': 'Ticket does not exist.'
        }
