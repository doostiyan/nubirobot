import os
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http.response import HttpResponse
from django.test import Client, TestCase, override_settings

from exchange.accounts.models import User, UploadedFile
from exchange.ticketing.models import Topic, Ticket, Activity


class TicketingViewsTest(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.other_user = User.objects.get(pk=202)
        self.client = Client()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'

    def tearDown(self) -> None:
        for file in UploadedFile.objects.all():
            os.remove(file.disk_path)
        Ticket.objects.all().delete()

    @patch('exchange.ticketing.signals.celery_app.send_task')
    def test_create_ticket(self, send_task):
        self.topic = Topic.objects.create(title='تستی', show_to_users=True)
        response = self.client.post(path='/ticketing/tickets/create', data={
            'topic': self.topic.pk,
        }).json()
        assert response['status'] == 'failed'
        assert response['message']['content'] == ["این مقدار لازم است."]

        response = self.client.post(path='/ticketing/tickets/create', data={
            'content': 'test content for create ticket with api',
        }).json()
        assert response['status'] == 'failed'
        assert response['message']['topic'] == ["این مقدار لازم است."]

        hidden_topic = Topic.objects.create(title='hidden', show_to_users=False)
        response = self.client.post(path='/ticketing/tickets/create', data={
            'content': 'test content for create ticket with api',
            'topic': hidden_topic.pk,
        }).json()
        assert response['status'] == 'failed'
        assert response['message']['topic'] == ["یک گزینهٔ معتبر انتخاب کنید. آن گزینه از گزینه‌های موجود نیست."]

        response = self.client.post(path='/ticketing/tickets/create', data={
            'content': 'test content for create ticket with api',
            'topic': self.topic.pk,
        })
        response_json = response.json()
        assert response_json['status'] == 'ok'
        send_task.assert_called_with('admin.create_new_task',
                                     kwargs={
                                         'tp': Ticket.TASK_TYPE_CHOICES.ticketing,
                                         'object_id': response_json['data']['ticket']['id'],
                                         'queue': response_json['data']['ticket']['topic']['id'],
                                         'related_user_id': response.wsgi_request.user.id,
                                     })
        assert response_json['data']['ticket']['topic'] == {"id": self.topic.pk, "title": "تستی"}
        assert response_json['data']['ticket']['stateName'] == "ارسال‌شده"
        assert response_json['data']['ticket']['content'] == "test content for create ticket with api"
        assert len(response_json['data']['ticket']['filesUrls']) == 0

    @patch('exchange.ticketing.signals.celery_app.send_task')
    def test_create_ticket_with_attachment(self, _send_task):
        assert not UploadedFile.objects.filter().exists()
        self.topic = Topic.objects.create(title='تستی', show_to_users=True)
        # Ignore non-image file
        with open("tests/ticketing/invalid_file.png", 'rb') as file:
            response = self.client.post(path='/ticketing/tickets/create', data={
                'topic': self.topic.pk,
                'content': 'test content for create ticket with api',
                'files': [file]
            })
        result = response.json()
        assert result['status'] == 'failed'
        _send_task.assert_not_called()
        assert not UploadedFile.objects.filter().exists()
        assert not Ticket.objects.filter().exists()

        # Valid image file
        with open('tests/ticketing/img.png', 'rb') as image:
            response = self.client.post(path='/ticketing/tickets/create', data={
                'topic': self.topic.pk,
                'content': 'test content for create ticket with api',
                'files': [image]
            })
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert len(result['data']['ticket']['filesUrls']) == 1
        # download the attached files url
        response = self.client.get(path=result['data']['ticket']['filesUrls'][0])
        assert isinstance(response, HttpResponse)
        assert response.status_code == 200
        assert response.charset == 'utf-8'
        # check the db
        assert UploadedFile.objects.last() is not None

        # Check size
        with override_settings(MAX_TICKET_ATTACHMENT_UPLOAD_SIZE=100):
            with open('tests/ticketing/img.png', 'rb') as image:
                response = self.client.post(path='/ticketing/tickets/create', data={
                    'topic': self.topic.pk,
                    'content': 'test content for create ticket with api',
                    'files': [image]
                })
            assert response.status_code == 200
            result = response.json()
            assert result['status'] == 'failed'

    def test_get_ticket_details(self):
        response = self.client.get('/ticketing/tickets/0')
        assert response.status_code == 200
        response = response.json()
        assert response['status'] == 'failed'
        assert response['code'] == 'NotFound'
        self.topic = Topic.objects.create(title='تستی', show_to_users=True)
        self.ticket = Ticket.objects.create(
            content='test',
            created_by=self.user,
            related_user=self.user,
            topic=self.topic,
        )
        response = self.client.get(f'/ticketing/tickets/{self.ticket.pk}').json()
        assert response['status'] == 'ok'
        assert response['data']['ticket']['content'] == 'test'
        assert response['data']['ticket']['topic'] == {"id": self.topic.pk, "title": "تستی"}

    def test_comment_seen_by_related_user(self):
        user = User.objects.create_user(username='admin')
        topic = Topic.objects.create(title='تستی', show_to_users=True)
        ticket = Ticket.objects.create(
            content='test',
            created_by=self.user,
            related_user=self.user,
            topic=topic,
        )
        admin_comment = Activity.objects.create(ticket=ticket, type=Activity.TYPES.comment, actor=user)
        user_comment = Activity.objects.create(ticket=ticket, type=Activity.TYPES.comment, actor=self.user)
        assert admin_comment.seen_at is None
        assert user_comment.seen_at is None
        response = self.client.get(f'/ticketing/tickets/{ticket.pk}').json()
        assert response['status'] == 'ok'

        # the user has seen admin's comment now.
        admin_comment.refresh_from_db()
        assert admin_comment.seen_at is not None

        # the admin has not seen user's comment yet.
        user_comment.refresh_from_db()
        assert user_comment.seen_at is None

    @patch('exchange.ticketing.signals.celery_app.send_task')
    def test_create_comment(self, send_task):
        self.topic = Topic.objects.create(title='تستی', show_to_users=True)
        self.ticket = Ticket.objects.create(
            content='test',
            created_by=self.user,
            related_user=self.user,
            topic=self.topic,
        )
        response = self.client.post(path='/ticketing/comments/create', data={
            'ticket': self.ticket.pk,
        }).json()
        assert response['status'] == 'failed'
        assert response['message']['content'] == ["این مقدار لازم است."]

        response = self.client.post(path='/ticketing/comments/create', data={
            'content': 'test content for create comment with api',
        }).json()
        assert response['status'] == 'failed'
        assert response['message']['ticket'] == ["این مقدار لازم است."]

        response = self.client.post(path='/ticketing/comments/create', data={
            'content': 'test content for create comment with api',
            'ticket': 0,
        }).json()
        assert response['status'] == 'failed'
        assert response['message']['ticket'] == ["یک گزینهٔ معتبر انتخاب کنید. آن گزینه از گزینه‌های موجود نیست."]

        response = self.client.post(path='/ticketing/comments/create', data={
            'content': '<ul><li>i will not escape _ and *</li></ul>',
            'ticket': self.ticket.pk,
        })
        response_json = response.json()
        assert response_json['status'] == 'ok'
        send_task.assert_called_with('admin.create_new_task',
                                     kwargs={
                                         'tp': Ticket.TASK_TYPE_CHOICES.ticketing,
                                         'object_id': response_json['data']['ticket']['id'],
                                         'queue': response_json['data']['ticket']['topic']['id'],
                                         'related_user_id': response.wsgi_request.user.id,
                                     })
        assert response_json['data']['ticket']['topic'] == {"id": self.topic.pk, "title": "تستی"}
        assert response_json['data']['ticket']['stateName'] == "ارسال‌شده"
        assert response_json['data']['ticket']['content'] == "test"
        assert response_json['data']['ticket']['comments'][0]['actorName'] == self.user.get_full_name()
        assert response_json['data']['ticket']['comments'][0]['content'] == '&^lt;ul&^gt;&^lt;li&^gt;i will not escape _ and *&^lt;/li&^gt;&^lt;/ul&^gt;'
        assert len(response_json['data']['ticket']['comments'][0]['filesUrls']) == 0

        self.ticket.state = Ticket.STATE_CHOICES.closed
        self.ticket.save()
        response = self.client.post(path='/ticketing/comments/create', data={
            'content': 'test content for create comment with api',
            'ticket': self.ticket.pk,
        }).json()
        assert response['status'] == 'failed'

    @patch('exchange.ticketing.signals.celery_app.send_task')
    def test_content_sanitizations(self, send_task):
        self.topic = Topic.objects.create(title='تستی', show_to_users=True)
        self.ticket = Ticket.objects.create(
            content='test',
            created_by=self.user,
            related_user=self.user,
            topic=self.topic,
        )

        # 1
        response = self.client.post(path='/ticketing/comments/create', data={
            'content': '<script>js</script>',
            'ticket': self.ticket.pk,
        }).json()
        assert response['data']['ticket']['comments'][0]['content'] == '&^amp;lt;script&^amp;gt;js&^amp;lt;/script&^amp;gt;'

        # 2
        response = self.client.post(path='/ticketing/comments/create', data={
            'content': '<a href="https://yahoo.com/">yahoo</a>',
            'ticket': self.ticket.pk,
        }).json()
        assert response['data']['ticket']['comments'][1]['content'] == '&^lt;a href=&^quot;https://yahoo.com/&^quot;&^gt;yahoo&^lt;/a&^gt;'

        # 3
        response = self.client.post(path='/ticketing/comments/create', data={
            'content': '<a href="https://yahoo.com/">yahoo</script>',
            'ticket': self.ticket.pk,
        }).json()
        assert response['data']['ticket']['comments'][2]['content'] == '&^lt;a href=&^quot;https://yahoo.com/&^quot;&^gt;yahoo&^amp;lt;/script&^amp;gt;&^lt;/a&^gt;'

        # 4
        response = self.client.post(path='/ticketing/comments/create', data={
            'content': '&lt;script&gt;',
            'ticket': self.ticket.pk,
        }).json()
        assert response['data']['ticket']['comments'][3]['content'] == '&^amp;lt;script&^amp;gt;'

    @patch('exchange.ticketing.signals.celery_app.send_task')
    def test_create_comment_with_attachment(self, _send_task):
        self.topic = Topic.objects.create(title='تستی', show_to_users=True)
        self.ticket = Ticket.objects.create(
            content='test',
            created_by=self.user,
            related_user=self.user,
            topic=self.topic,
        )
        with open('tests/ticketing/invalid_file.png', 'rb') as file:
            response = self.client.post(path='/ticketing/comments/create', data={
                'content': 'test content for create comment with api',
                'ticket': self.ticket.pk,
                'files': [file]
            })
        result = response.json()
        assert result['status'] == 'failed'
        assert UploadedFile.objects.last() is None
        _send_task.assert_called()

        # Valid image file
        with open('tests/ticketing/img.png', 'rb') as image:
            response = self.client.post(path='/ticketing/comments/create', data={
                'content': 'test content for create comment with api',
                'ticket': self.ticket.pk,
                'files': [image]
            })
        result = response.json()
        assert result['status'] == 'ok'
        assert len(result['data']['ticket']['comments'][0]['filesUrls']) == 1
        # download the attached files url
        response = self.client.get(path=result['data']['ticket']['comments'][0]['filesUrls'][0])
        assert isinstance(response, HttpResponse)
        assert response.status_code == 200
        assert response.charset == 'utf-8'
        # check the db
        self.ticket.refresh_from_db()
        assert self.ticket.comments.count() == 1
        assert self.ticket.comments.first().files.count() == 1

        # Check size
        with override_settings(MAX_TICKET_ATTACHMENT_UPLOAD_SIZE=10):
            with open('tests/ticketing/img.png', 'rb') as image:
                response = self.client.post(path='/ticketing/comments/create', data={
                    'content': 'test content for create comment with api',
                    'ticket': self.ticket.pk,
                    'files': [image]
                })
            result = response.json()
            assert result['status'] == 'failed'

    def test_get_list_user_tickets(self):
        self.topic = Topic.objects.create(title='تستی', show_to_users=True)
        self.ticket = Ticket.objects.create(
            content='test',
            created_by=self.user,
            related_user=self.user,
            topic=self.topic,
        )
        response = self.client.get(path='/ticketing/tickets').json()
        assert response['status'] == 'ok'
        assert len(response['data']['tickets']) == 1

        self.ticket1 = Ticket.objects.create(
            content='test1',
            created_by=self.user,
            related_user=self.user,
            topic=self.topic,
        )
        response = self.client.get(path='/ticketing/tickets').json()
        assert response['status'] == 'ok'
        assert len(response['data']['tickets']) == 2

    def test_get_topics(self):
        topic1 = Topic.objects.create(
            title='topic1', show_to_users=True, priority=Topic.PRIORITY_CHOICES.very_low,
        )

        topic2 = Topic.objects.create(
            title='topic2', show_to_users=True, priority=Topic.PRIORITY_CHOICES.critical,
        )

        topic3 = Topic.objects.create(
            title='atopic3', show_to_users=True, priority=Topic.PRIORITY_CHOICES.critical,
        )


        Topic.objects.create(title='topic3', show_to_users=False)
        response = self.client.get(path='/ticketing/topics').json()
        assert response['status'] == 'ok'
        assert len(response['data']['topics']) == 3
        assert response['data']['topics'][0]['id'] == topic3.pk
        assert response['data']['topics'][1]['id'] == topic2.pk
        assert response['data']['topics'][2]['id'] == topic1.pk

    def test_close_ticket(self):
        topic = Topic.objects.create(title='تستی', show_to_users=True)
        ticket = Ticket.objects.create(
            content='test',
            created_by=self.user,
            related_user=self.user,
            topic=topic,
            state=Ticket.STATE_CHOICES.resolved
        )
        response = self.client.post(path=f'/ticketing/tickets/{ticket.pk}/close').json()
        assert response['status'] == 'ok'
        assert response['data']['ticket']['state'] == 'closed'

        # Check for log activity
        activity = Activity.objects.filter(
            ticket=ticket,
            type=Activity.TYPES.log,
            content='تیکت توسط کاربر بسته شده است'
        ).first()

        assert activity is not None

    def test_rate_ticket(self):
        topic = Topic.objects.create(title='تستی', show_to_users=True)
        ticket = Ticket.objects.create(
            content='test',
            created_by=self.user,
            related_user=self.user,
            topic=topic,
            state=Ticket.STATE_CHOICES.closed
        )

        # rating must be an integer in range 1 to 5.
        response = self.client.post(path=f'/ticketing/tickets/{ticket.pk}/rate', data={
            'rating': 6,
        }).json()
        assert response['status'] == 'failed'

        response = self.client.post(path=f'/ticketing/tickets/{ticket.pk}/rate', data={
            'rating': 0,
        }).json()
        assert response['status'] == 'failed'

        # ok. only rating field is required
        response = self.client.post(path=f'/ticketing/tickets/{ticket.pk}/rate', data={
            'rating': 5,
        }).json()
        assert response['status'] == 'ok'
        assert response['data']['ticket']['rating'] == 5

        # ok. with rating note
        ticket.rating = None
        ticket.save()
        response = self.client.post(path=f'/ticketing/tickets/{ticket.pk}/rate', data={
            'rating': 4,
            'ratingNote': 'rate is good'
        }).json()
        assert response['status'] == 'ok'
        assert response['data']['ticket']['rating'] == 4
        assert response['data']['ticket']['ratingNote'] == 'rate is good'

    def test_rate_unclosed_ticket(self):
        topic = Topic.objects.create(title='تستی', show_to_users=True)
        ticket = Ticket.objects.create(
            content='test',
            created_by=self.user,
            related_user=self.user,
            topic=topic,
            state=Ticket.STATE_CHOICES.sent
        )

        response = self.client.post(path=f'/ticketing/tickets/{ticket.pk}/rate', data={
            'rating': 5,
        }).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'UnclosedTicket'

    def test_twice_rate_ticket(self):
        topic = Topic.objects.create(title='تستی', show_to_users=True)
        ticket = Ticket.objects.create(
            content='test',
            created_by=self.user,
            related_user=self.user,
            topic=topic,
            state=Ticket.STATE_CHOICES.closed,
            rating=4
        )

        response = self.client.post(path=f'/ticketing/tickets/{ticket.pk}/rate', data={
            'rating': 5,
        }).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'AlreadyRated'

    def test_rate_non_existing_ticket(self):
        response = self.client.post(path=f'/ticketing/tickets/78678678686799/rate', data={
            'rating': 5,
        }).json()
        assert response['status'] == 'failed'

    def test_download_gif_attachment(self):
        image = SimpleUploadedFile(name='test_image.gif', content=open('tests/ticketing/img_1.gif', 'rb').read(),
                                   content_type='image/gif')
        uploaded_file = UploadedFile.objects.create(user=self.user, tp=UploadedFile.TYPES.ticketing_attachment)
        with open(uploaded_file.disk_path, 'wb+') as destination:
            for chunk in image.chunks():
                destination.write(chunk)
        response = self.client.get(path=f'/ticketing/attachments/{uploaded_file.filename}')
        assert isinstance(response, HttpResponse)
        assert response.status_code == 200
        assert response.charset == 'utf-8'

    def test_download_non_gif_attachment(self):
        image = SimpleUploadedFile(name='test_image.png', content=open('tests/ticketing/img.png', 'rb').read(),
                                   content_type='image/png')
        uploaded_file = UploadedFile.objects.create(user=self.user, tp=UploadedFile.TYPES.ticketing_attachment)
        with open(uploaded_file.disk_path, 'wb+') as destination:
            for chunk in image.chunks():
                destination.write(chunk)
        response = self.client.get(path=f'/ticketing/attachments/{uploaded_file.filename}')
        assert isinstance(response, HttpResponse)
        assert response.status_code == 200
        assert response.charset == 'utf-8'

    def test_download_non_existing_attachment(self):
        # File not found
        response = self.client.get(path=f'/ticketing/attachments/wrong_hash')
        assert response.status_code == 200
        response = response.json()
        assert response['status'] == 'failed'
        assert response['code'] == 'InvalidFilename'

    def test_download_non_image_attachment(self):
        # UnidentifiedImageError
        file = SimpleUploadedFile(name='test_image.jpg', content=b'test', content_type='application/pdf')
        uploaded_file = UploadedFile.objects.create(user=self.user, tp=UploadedFile.TYPES.ticketing_attachment)
        with open(uploaded_file.disk_path, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        response = self.client.get(path=f'/ticketing/attachments/{uploaded_file.filename}')
        assert response.status_code == 200
        response = response.json()
        assert response['status'] == 'failed'
        assert response['code'] == 'NotFound'

    def test_unauthorized_ticket_access(self):
        self.topic = Topic.objects.create(title='تستی', show_to_users=True)
        self.ticket = Ticket.objects.create(
            content='test',
            created_by=self.user,
            related_user=self.user,
            topic=self.topic,
        )
        self.ticket2 = Ticket.objects.create(
            content='test',
            created_by=self.other_user,
            related_user=self.other_user,
            topic=self.topic,
        )
        response = self.client.post(
            path='/ticketing/comments/create',
            data={
                'content': '<ul><li>i will not escape _ and *</li></ul>',
                'ticket': self.ticket.pk,
            },
        )
        response_json = response.json()
        assert response_json['status'] == 'ok'
        assert response_json['data']['ticket']['topic'] == {"id": self.topic.pk, "title": "تستی"}
        assert response_json['data']['ticket']['stateName'] == "ارسال‌شده"
        assert response_json['data']['ticket']['content'] == "test"
        assert response_json['data']['ticket']['comments'][0]['actorName'] == self.user.get_full_name()
        assert (
            response_json['data']['ticket']['comments'][0]['content']
            == '&^lt;ul&^gt;&^lt;li&^gt;i will not escape _ and *&^lt;/li&^gt;&^lt;/ul&^gt;'
        )
        assert len(response_json['data']['ticket']['comments'][0]['filesUrls']) == 0

        response = self.client.post(
            path='/ticketing/comments/create',
            data={
                'content': '<ul><li>i will not escape _ and *</li></ul>',
                'ticket': self.ticket2.pk,
            },
        )
        response_json = response.json()
        assert response_json['status'] == 'failed'
