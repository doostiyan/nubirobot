from exchange.accounts.models import User
from exchange.base.models import Settings
from exchange.socialtrade.validators import FEE_BOUNDARY_KEY
from tests.socialtrade.helpers import SocialTradeBaseAPITest


class SocialTradeOptionsAPITest(SocialTradeBaseAPITest):
    URL = '/social-trade/options'

    def setUp(self) -> None:
        self.user = User.objects.get(id=201)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        Settings.set_dict(
            FEE_BOUNDARY_KEY,
            {
                'max': {'rls': '10000', 'usdt': '10.5'},
                'min': {'rls': '0', 'usdt': '0'},
            },
        )

    def test_get_options(self):
        response = self.client.get(path=self.URL)
        assert response.status_code == 200
        result = response.json()
        assert result['status'] == 'ok'
        assert result['feeBoundary']['min']['usdt'] == '0'
        assert result['feeBoundary']['max']['usdt'] == '10.5'
        assert result['minNicknameLength'] == 4
        assert result['maxNicknameLength'] == 12
        assert result['leaderId'] is None

        leader = self.create_leader(self.user)
        response = self.client.get(path=self.URL)
        result = response.json()
        assert result['leaderId'] == leader.id
