from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.oauth.constants import Scopes
from exchange.oauth.helpers import get_latest_tokens, get_unauthorized_scopes_of_app
from tests.oauth.helpers import create_access_token, create_application


class HelpersTest(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.client_user_one = User.objects.get(pk=201)
        cls.client_user_two = User.objects.get(pk=203)
        cls.application_one = create_application(user=cls.client_user_one, scope='profile-info user-info')
        cls.application_two = create_application(user=cls.client_user_two, scope='user-info')
        cls.user = User.objects.get(pk=202)
        cls.user_two = User.objects.get(pk=203)

    @patch('exchange.oauth.constants.Scopes.get_all', return_value={**Scopes.get_all(), 'new_scope': 'Some new scope'})
    def test_get_unauthorized_scopes_of_app(self, _):
        assert get_unauthorized_scopes_of_app(self.user, self.application_one, []) == []
        assert get_unauthorized_scopes_of_app(self.user, self.application_one, ['profile-info']) == ['profile-info']
        assert get_unauthorized_scopes_of_app(self.user, self.application_one, ['profile-info', 'user-info']) == [
            'profile-info',
            'user-info',
        ]
        assert get_unauthorized_scopes_of_app(self.user, self.application_one, ['profile-info', 'wrong-scope']) == [
            'profile-info'
        ]
        assert get_unauthorized_scopes_of_app(self.user, self.application_one, ['profile-info', 'new-scope']) == [
            'profile-info'
        ]

        token = create_access_token(user=self.user, application=self.application_one, scope='read')
        assert get_unauthorized_scopes_of_app(self.user, self.application_one, ['profile-info', 'read']) == [
            'profile-info'
        ]
        token.scope = 'read profile-info'
        token.save()
        assert get_unauthorized_scopes_of_app(self.user, self.application_one, ['profile-info', 'user-info']) == [
            'user-info'
        ]
        user_info_access_token = create_access_token(
            user=self.user, application=self.application_one, scope='user-info'
        )
        assert get_unauthorized_scopes_of_app(self.user, self.application_one, ['profile-info', 'user-info']) == []
        user_info_access_token.expires = ir_now() - timedelta(seconds=10)
        user_info_access_token.save()
        assert get_unauthorized_scopes_of_app(self.user, self.application_one, ['profile-info', 'user-info']) == [
            'user-info'
        ]

    def test_get_latest_tokens(self):
        # We have 3 different tokens, each with a different pair of (application, scope),
        # so each of them will be the latest one in their group of (application, scope)
        app_one_profile_token = create_access_token(self.application_one, self.user, scope='profile-info')
        app_one_user_token = create_access_token(
            self.application_one, self.user, scope='user-info', expires=ir_now() - timedelta(days=2)
        )
        app_two_user_token = create_access_token(
            self.application_two, self.user, scope='user-info', expires=ir_now() - timedelta(days=2)
        )
        granted_accesses = list(get_latest_tokens(user=self.user))
        assert sorted(granted_accesses, key=lambda p: p.id) == sorted(
            [app_one_user_token, app_one_profile_token, app_two_user_token], key=lambda token: token.id
        )

        # We have 5 different tokens, with 2 pairs of them having the same pair of (application, scope),
        # so in total we have 3 tokens with distinct pairs of (application, scope) which work as the latest
        app_one_profile_token = create_access_token(self.application_one, self.user, scope='profile-info')
        app_two_user_token = create_access_token(self.application_two, self.user, scope='user-info')
        granted_accesses = list(get_latest_tokens(user=self.user))
        assert sorted(granted_accesses, key=lambda p: p.id) == sorted(
            [app_one_user_token, app_one_profile_token, app_two_user_token], key=lambda token: token.id
        )

        # Adding tokens for another user
        user_two_profile_token = create_access_token(self.application_two, self.user_two, scope='profile-info')
        user_two_user_token = create_access_token(self.application_two, self.user_two, scope='user-info')
        granted_accesses = list(get_latest_tokens(user=self.user))
        assert sorted(granted_accesses, key=lambda p: p.id) == sorted(
            [app_one_user_token, app_one_profile_token, app_two_user_token], key=lambda token: token.id
        )
        user_two_granted_accesses = list(get_latest_tokens(user=self.user_two))
        assert sorted(user_two_granted_accesses, key=lambda p: p.id) == sorted(
            [user_two_profile_token, user_two_user_token], key=lambda token: token.id
        )
