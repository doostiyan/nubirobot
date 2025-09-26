from tests.socialtrade.helpers import SocialTradeBaseAPITest


class LeaderboardAPITest(SocialTradeBaseAPITest):
    URL = '/social-trade/avatars'

    def setUp(self) -> None:
        self.avatar_1 = self.create_avatar()
        self.avatar_2 = self.create_avatar()
        self.disabled_avatar = self.create_avatar(is_active=False)

    def test_list_avatars(self):
        response = self.client.get(path=self.URL)
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert len(result['avatars']) == 2
        assert result['avatars'][0]['id'] == self.avatar_2.id
        assert result['avatars'][0]['image'] == self.avatar_2.image.url
        assert result['avatars'][1]['id'] == self.avatar_1.id
        assert result['avatars'][1]['image'] == self.avatar_1.image.url
