from django.conf import settings
from django.test import Client
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from django.core.cache import cache


class TestTelegram(APITestCase):

    def setUp(self):
        self.client = Client()
        self.auth_headers = {'HTTP_AUTHORIZATION': 'Token user201token'}

    def test_telegram_bot_apis(self):
        # Get token
        r = self.client.post('/users/telegram/generate-url', **self.auth_headers).json()
        assert r.get('status') == 'ok'
        start_url = r.get('telegramActivationUrl') or ''
        assert start_url.startswith('https://telegram.me/testnobitexbot?start=')
        token = start_url[41:]
        assert len(token) == 8
        assert cache.get(f'telegram_activation_token_{token}') == 201
        # Set ID
        chat_id = '-267453237'
        r = self.client.post('/users/telegram/set-chat-id', data={
            'token': token,
            'chat_id': chat_id,
            'bot_key': settings.TELEGRAM_BOT_KEY,
        }).json()
        assert r['status'] == 'ok'
        user = User.objects.get(id=201)
        assert user.telegram_conversation_id == chat_id
        assert User.objects.filter(telegram_conversation_id=chat_id).count() == 1
        assert r['email'] == user.email
        # Check token reuse
        r = self.client.post('/users/telegram/set-chat-id', data={
            'token': token,
            'chat_id': '-1000000',
            'bot_key': settings.TELEGRAM_BOT_KEY,
        }).json()
        assert r['status'] == 'failed'
        assert r['code'] == 'InvalidToken'
        user.refresh_from_db()
        assert user.telegram_conversation_id == chat_id
        # Clear ID
        r = self.client.post('/users/telegram/generate-url', **self.auth_headers).json()
        token = r['telegramActivationUrl'][41:]
        r = self.client.post('/users/telegram/set-chat-id', data={
            'token': token,
            'chat_id': '@unsubscribe',
            'bot_key': settings.TELEGRAM_BOT_KEY,
        }).json()
        assert r['status'] == 'ok'
        user.refresh_from_db()
        assert user.telegram_conversation_id is None
        assert User.objects.filter(telegram_conversation_id=chat_id).count() == 0
        assert r['email'] == user.email

    def test_telegram_bot_unsubscribe_from_inside_bot(self):
        user = User.objects.get(id=201)
        chat_id = '-267453237'
        user.telegram_conversation_id = chat_id
        user.save(update_fields=('telegram_conversation_id',))
        r = self.client.post('/users/telegram/reset-chat-id', data={
            'chat_id': '-1000000',
            'bot_key': settings.TELEGRAM_BOT_KEY,
        }).json()
        assert r['error'] == 'NotFound'
        user.refresh_from_db()
        assert user.telegram_conversation_id == chat_id

        r = self.client.post('/users/telegram/reset-chat-id', data={
            'chat_id': chat_id,
            'bot_key': settings.TELEGRAM_BOT_KEY,
        }).json()
        assert r['status'] == 'ok'
        user.refresh_from_db()
        assert user.telegram_conversation_id is None
        assert User.objects.filter(telegram_conversation_id=chat_id).count() == 0
