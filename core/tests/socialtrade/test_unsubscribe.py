from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.socialtrade.models import SocialTradeSubscription
from tests.socialtrade.helpers import SocialTradeBaseAPITest


class UnsubscribeAPITest(SocialTradeBaseAPITest):
    URL = '/social-trade/subscriptions/{subscription_id}/unsubscribe'

    def setUp(self) -> None:
        self.user = User.objects.get(id=201)
        self.user_leader = User.objects.get(id=203)
        self.leader = self.create_leader()
        self.subscription = SocialTradeSubscription.subscribe(self.leader, self.user, is_auto_renewal_enabled=True)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def test_unsubscribe_successfully(self):
        assert self.subscription.canceled_at is None
        response = self.client.post(path=self.URL.format(subscription_id=self.subscription.id))
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'
        self.subscription.refresh_from_db()
        assert self.subscription.canceled_at is not None

    def test_unsubscribe_when_subscription_not_exists_fail(self):
        user = User.objects.get(id=202)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {user.auth_token.key}')
        response = self.client.post(path=self.URL.format(subscription_id=self.subscription.id))
        assert response.status_code == 404
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'NotFound'

    def test_unsubscribe_when_subscription_expired(self):
        self.subscription.expires_at = ir_now()
        self.subscription.save()
        response = self.client.post(path=self.URL.format(subscription_id=self.subscription.id))
        assert response.status_code == 404
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'NotFound'

    def test_unsubscribe_with_invalid_subscription_id_fail(self):
        response = self.client.post(path=self.URL.format(subscription_id=10000))
        assert response.status_code == 404
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'NotFound'

    def test_unsubscribe_with_other_user_subscription_id_fail(self):
        user = User.objects.get(id=202)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {user.auth_token.key}')
        response = self.client.post(path=self.URL.format(subscription_id=self.subscription.id))
        assert response.status_code == 404
        assert response.json()['status'] == 'failed'
        assert response.json()['code'] == 'NotFound'
