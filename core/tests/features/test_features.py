from django.test import TestCase, Client

from exchange.accounts.models import User, VerificationProfile
from exchange.base.models import TESTING_CURRENCIES, get_currency_codename
from exchange.base.coins_info import CURRENCY_INFO
from exchange.features.models import QueueItem
from exchange.features.utils import is_feature_enabled


class QueueItemTest(TestCase):

    def setUp(self):
        self.user1 = User.objects.get(pk=201)
        self.user2 = User.objects.get(pk=202)
        self.client = Client()
        self.client.defaults['HTTP_AUTHORIZATION'] = 'Token user201token'

    def test_get_position_in_queue(self):
        # First request
        req1x = QueueItem.objects.create(
            feature=QueueItem.FEATURES.xchange,
            user=self.user1,
        )
        assert req1x.status == QueueItem.STATUS.waiting
        assert req1x.get_position_in_queue() == 1
        # First request
        req1 = QueueItem.objects.create(
            feature=QueueItem.FEATURES.price_alert,
            user=self.user1,
        )
        assert req1.status == QueueItem.STATUS.waiting
        assert req1.get_position_in_queue() == 1
        # Second
        req2 = QueueItem.objects.create(
            feature=QueueItem.FEATURES.price_alert,
            user=self.user2,
        )
        assert req2.status == QueueItem.STATUS.waiting
        assert req2.get_position_in_queue() == 2
        # Enable
        req1.enable_feature()
        assert req1.status == QueueItem.STATUS.done
        assert req1.get_position_in_queue() == 0
        assert req2.get_position_in_queue() == 1
        req2.enable_feature()
        assert req2.status == QueueItem.STATUS.done
        assert req1.get_position_in_queue() == 0
        assert req2.get_position_in_queue() == 0
        # Recheck
        req1x.refresh_from_db()
        assert req1x.status == QueueItem.STATUS.waiting
        assert req1x.get_position_in_queue() == 1
        assert not req1.enable_feature()
        assert req1x.enable_feature()

    def test_enable_feature(self):
        req1 = QueueItem.objects.create(
            feature=QueueItem.FEATURES.portfolio,
            user=self.user1,
        )
        req2 = QueueItem.objects.create(
            feature=QueueItem.FEATURES.portfolio,
            user=self.user2,
        )
        assert not self.user1.is_beta_user
        assert not self.user2.is_beta_user
        req1.enable_feature()
        assert (self.user1.track or 0) & QueueItem.BIT_FLAG_PORTFOLIO
        assert not (self.user2.track or 0) & QueueItem.BIT_FLAG_PORTFOLIO
        req2.enable_feature()
        assert (self.user1.track or 0) & QueueItem.BIT_FLAG_PORTFOLIO
        assert (self.user2.track or 0) & QueueItem.BIT_FLAG_PORTFOLIO

    def test_new_coins_feature(self):
        """
            'new_coins' feature enabled to allow a very restricted bunch of users to have
            access to the new coins(those were not in the system before)
        """
        req1 = QueueItem.objects.create(
            feature=QueueItem.FEATURES.new_coins,
            user=self.user1,
        )
        assert not is_feature_enabled(self.user1, QueueItem.FEATURES.new_coins)
        self.user1.user_type = User.USER_TYPES.level1
        self.user1.save()
        VerificationProfile.objects.filter(id=self.user1.get_verification_profile().id).update(email_confirmed=True)
        for currency in TESTING_CURRENCIES:
            # address generation is not allowed without this feature enabled
            response = self.client.post('/users/wallets/generate-address', {'currency': get_currency_codename(currency)}).json()
            assert response.get('status') == 'failed'
            assert response.get('message') == 'Currency is not supported yet.'
        req1.enable_feature()
        assert is_feature_enabled(self.user1, QueueItem.FEATURES.new_coins)
        for currency in TESTING_CURRENCIES:
            if CURRENCY_INFO.get(currency).get('deposit_enable'):
                response = self.client.post('/users/wallets/generate-address', {'currency': get_currency_codename(currency)}).json()
                assert response.get('status') == 'ok'
        self.user1.user_type = User.USER_TYPES.level0
        self.user1.save()
