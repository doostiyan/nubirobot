from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from tests.socialtrade.helpers import SocialTradeBaseAPITest


class ChangeisNotifEnabledTest(SocialTradeBaseAPITest):
    URl = '/social-trade/subscriptions/{subscription_id}/change-notif-enabled'

    def setUp(self) -> None:
        self.user = User.objects.get(id=201)
        self.user_2 = User.objects.get(id=202)
        leader = User.objects.get(id=203)
        self.leader = self.create_leader(leader)
        self.subscription_1 = self.create_subscription(self.user, self.leader)
        self.subscription_1.is_notif_enabled = True
        self.subscription_1.save()
        self.subscription_2 = self.create_subscription(self.user_2, self.leader)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')

    def test_set_false_successfully(self):
        data = {'isNotifEnabled': False}
        assert self.subscription_1.is_notif_enabled
        response = self.client.post(self.URl.format(subscription_id=self.subscription_1.id), data=data)
        self.subscription_1.refresh_from_db()
        assert response.status_code == 200
        assert not self.subscription_1.is_notif_enabled

    def test_set_true_successfully(self):
        self.subscription_1.is_notif_enabled = False
        self.subscription_1.save()
        data = {'isNotifEnabled': True}
        assert not self.subscription_1.is_notif_enabled
        response = self.client.post(self.URl.format(subscription_id=self.subscription_1.id), data=data)
        self.subscription_1.refresh_from_db()
        assert response.status_code == 200
        assert self.subscription_1.is_notif_enabled

    def test_change_auto_renewal_for_other_user_fail(self):
        data = {'isNotifEnabled': False}
        response = self.client.post(self.URl.format(subscription_id=self.subscription_2.id), data=data)
        assert response.status_code == 404
        assert self.subscription_1.is_notif_enabled
        output = response.json()
        assert output == {'status': 'failed', 'code': 'NotFound', 'message': 'Subscription does not exist'}

    def test_change_auto_renewal_expired_subscription_fail(self):
        self.subscription_1.expires_at = ir_now()
        self.subscription_1.save()
        data = {'isNotifEnabled': False}
        response = self.client.post(self.URl.format(subscription_id=self.subscription_1.id), data=data)
        assert response.status_code == 404
        assert self.subscription_1.is_notif_enabled
        output = response.json()
        assert output == {'status': 'failed', 'code': 'NotFound', 'message': 'Subscription does not exist'}
