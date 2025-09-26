from django.test import Client, TestCase

from exchange.accounts.models import User, UserEvent


class UserPreferenceTest(TestCase):

    def setUp(self):
        self.user = User.objects.get(pk=201)
        self.client = Client()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'

    def test_is_beta_user(self):
        assert not self.user.is_beta_user
        self.user.set_beta_status(True)
        assert self.user.is_beta_user
        assert not User.objects.get(pk=202).is_beta_user
        self.user.set_beta_status(False)
        assert not self.user.is_beta_user

    def test_set_beta_status(self):
        beta = User.TRACK.beta
        assert self.user.track is None
        self.user.set_beta_status(False)
        assert self.user.track is None
        self.user.set_beta_status(True)
        assert self.user.track == beta
        self.user.set_beta_status(False)
        assert self.user.track == 0
        self.user.track = 5
        self.user.set_beta_status(True)
        assert self.user.track == beta + 5
        assert self.user.is_beta_user
        self.user.set_beta_status(False)
        assert self.user.track == 5
        assert not self.user.is_beta_user

    def test_set_preferences_view_beta(self):
        url = '/users/set-preference'
        user = User.objects.get(id=201)
        beta = User.TRACK.beta
        assert user.track is None
        # Enable beta
        r = self.client.post(url, {'preference': 'beta', 'value': True}).json()
        assert r['status'] == 'ok'
        user.refresh_from_db()
        assert user.track == beta
        # Set some flags
        user.track += 5
        user.save(update_fields=['track'])
        # Disable beta, flags must remain the same
        r = self.client.post(url, {'preference': 'beta', 'value': False}).json()
        assert r['status'] == 'ok'
        user.refresh_from_db()
        assert user.track == 5

    def test_set_preferences_user_add_event_user(self):
        url = '/users/set-preference'
        user = User.objects.get(id=201)
        beta = User.TRACK.beta
        assert user.track is None
        # Enable beta
        r = self.client.post(url, {'preference': 'beta', 'value': True}).json()
        assert r['status'] == 'ok'
        user.refresh_from_db()
        assert user.track == beta

        # Check User Event Added
        user_events = UserEvent.objects.filter(
            user = self.user,
            action = UserEvent.ACTION_CHOICES.change_user_track,
            action_type = UserEvent.CHANGE_USER_TRACK_ACTION_TYPE.active_beta
        )
        assert user_events.count() > 0

        r = self.client.post(
            url, {'preference': 'beta', 'value': False}).json()
        assert r['status'] == 'ok'
        user.refresh_from_db()
        assert user.track == 0

        # Check User Event Added
        user_events = UserEvent.objects.filter(
            user = self.user,
            action = UserEvent.ACTION_CHOICES.change_user_track,
            action_type = UserEvent.CHANGE_USER_TRACK_ACTION_TYPE.deactive_beta
        )
        assert user_events.count() > 0
