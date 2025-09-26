from django.test import TestCase

from exchange.accounts.models import User
from exchange.tokens.auth import create_token, get_user_token_ttl


class TokenTest(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)

    def test_create_token(self):
        # Create a token
        token = create_token(self.user)
        assert token.created
        assert token.key is not None
        assert token.user == self.user

    def test_get_user_token_ttl(self):
        logout_threshold = 1
        self.user.logout_threshold = logout_threshold
        assert get_user_token_ttl(self.user) == logout_threshold * 60

        self.user.logout_threshold = None

        self.user.remembered_login = True
        assert get_user_token_ttl(self.user) == 2592000  # 30 days

        self.user.remembered_login = False
        assert get_user_token_ttl(self.user) == 14400  # 4h
