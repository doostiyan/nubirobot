from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import ACTIVE_CURRENCIES, Currencies, get_currency_codename
from exchange.base.serializers import serialize
from exchange.features.models import QueueItem
from exchange.socialtrade.models import Leader, SocialTradeSubscription
from exchange.wallet.models import Wallet
from tests.socialtrade.helpers import SocialTradeTestDataMixin

currencies_real_value = {
    Currencies.rls: (1, 1),
    Currencies.usdt: (50_000_0, 49_000_0),
}


def get_price_range(currency: int, *_, db_fallback=False, **__) -> tuple:
    return currencies_real_value.get(currency, (0, 0))


class LeaderProfileAPITest(SocialTradeTestDataMixin, APITestCase):
    def setUp(self) -> None:
        Leader.objects.all().delete()
        self.create_test_data()
        super().setUp()
        self.url = '/social-trade/leaders/{leader_id}/profile'

        SocialTradeSubscription.objects.create(
            leader=self.leader_three,
            subscriber=self.leader.user,
            starts_at=ir_now(),
            expires_at=ir_now() + timedelta(days=2),
            is_trial=True,
        )
        SocialTradeSubscription.objects.create(
            leader=self.leader_two,
            subscriber=self.leader.user,
            starts_at=ir_now() - timedelta(days=2),
            expires_at=ir_now() - timedelta(days=1),
            is_trial=True,
        )
        Wallet.get_user_wallet(self.leader.user, Currencies.rls).create_transaction(
            tp='social_trade',
            amount=Decimal('1_000_0'),
            description=f'تست',
        ).commit()
        Wallet.get_user_wallet(self.leader_two.user, Currencies.usdt).create_transaction(
            tp='social_trade',
            amount=Decimal('10.0'),
            description=f'تست',
        ).commit()
        self.create_user_wallets(self.leader.user)
        self.create_user_wallets(self.leader_two.user)
        self.create_user_wallets(self.leader_three.user)

    def test_failed_get_private_leader_profile(self):
        response = self.client.get(self.url.format(leader_id=0))
        self._assert_unauthorized_user_response(api_response=response)

        self._set_user_token(self.leader.user)
        response = self.client.get(self.url.format(leader_id=0))
        self._assert_404_failure_response(api_response=response)

    @patch('exchange.wallet.estimator.PriceEstimator.get_price_range', new_callable=MagicMock)
    def test_successful_get_private_leader_profile(self, mock_price_estimator):
        mock_price_estimator.side_effect = get_price_range
        self._create_leader_portfolios_with_withdraw_and_deposit(self.leader, self.leader_two)

        self._set_user_token(self.leader.user)
        response = self.client.get(self.url.format(leader_id=self.leader.id))
        self._assert_success_private_response(api_response=response, leader=self.leader)

        self._set_user_token(self.leader_three.user)
        response = self.client.get(self.url.format(leader_id=self.leader_three.id))
        self._assert_success_private_response(api_response=response, leader=self.leader_three)

    @patch('exchange.wallet.estimator.PriceEstimator.get_price_range', new_callable=MagicMock)
    def test_successful_get_public_leader_profile(self, mock_price_estimator):
        mock_price_estimator.side_effect = get_price_range
        self._create_leader_portfolios_with_withdraw_and_deposit(self.leader, self.leader_two)

        self._set_user_token(self.subscribers[0])
        response = self.client.get(self.url.format(leader_id=self.leader.id))
        self._assert_success_public_response(api_response=response, leader=self.leader)
        self._assert_no_private_info_in_public_profile(api_response=response)

        response = self.client.get(self.url.format(leader_id=self.leader_two.id))
        self._assert_success_public_response(api_response=response, leader=self.leader_two)

        response = self.client.get(self.url.format(leader_id=self.leader_three.id))
        self._assert_success_public_response(api_response=response, leader=self.leader_three)

    def test_get_profile_of_inactive_leader(self):
        self.leader_two.activates_at = ir_now() + timedelta(minutes=1)
        self.leader_two.save()
        self._set_user_token(self.leader.user)
        response = self.client.get(self.url.format(leader_id=self.leader_two.pk))
        self._assert_404_failure_response(api_response=response)

        self._set_user_token(self.leader_two_subscriptions[0].subscriber)
        response = self.client.get(self.url.format(leader_id=self.leader_two.pk))
        self._assert_404_failure_response(api_response=response)

    @patch('exchange.wallet.estimator.PriceEstimator.get_price_range', new_callable=MagicMock)
    def test_get_profile_of_deleted_leader(self, mock_price_estimator):
        mock_price_estimator.side_effect = get_price_range
        self._create_leader_portfolios_with_withdraw_and_deposit(self.leader, self.leader_two)

        self.leader_two.deleted_at = ir_now() - timedelta(minutes=1)
        self.leader_two.save()
        self._set_user_token(self.leader.user)
        response = self.client.get(self.url.format(leader_id=self.leader_two.pk))
        self._assert_404_failure_response(api_response=response)

        self._set_user_token(self.leader_two_subscriptions[0].subscriber)
        response = self.client.get(self.url.format(leader_id=self.leader_two.pk))
        self._assert_success_public_response(api_response=response, leader=self.leader_two)

    def _set_user_token(self, user: User):
        if not hasattr(user, 'auth_token'):
            token = Token.objects.create(key=f'{user.username}Token', user=user)
            user.auth_token = token
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {user.auth_token.key}')

    def _assert_success_private_response(self, api_response, leader: Leader):
        assert api_response.status_code == status.HTTP_200_OK
        json_response = api_response.json()
        assert 'status' in json_response
        assert json_response['status'] == 'ok'
        assert 'data' in json_response
        assert 'leader' in json_response['data']
        self._assert_leader_private_profile(json_response['data']['leader'], leader)

    def _assert_leader_private_profile(self, response_data: dict, leader: Leader):
        self._assert_leader_public_profile(response_data, leader, public=False)
        assert 'numberOfUnsubscribes' in response_data
        assert response_data['numberOfUnsubscribes'] == (0 if leader.id == self.leader_three.id else 4)
        assert 'gainedSubscriptionFees' in response_data
        assert Decimal(response_data['gainedSubscriptionFees']) == Decimal(
            0 if leader.id == self.leader_three.id else 27
        )

    def _assert_leader_public_profile(self, response_data: dict, leader: Leader, public: bool = True):
        serialized_leader = serialize(leader, None)
        serialized_leader['subscriptionFee'] = Decimal(serialized_leader['subscriptionFee'])
        response_data['subscriptionFee'] = Decimal(response_data['subscriptionFee'])
        for key in serialized_leader:
            assert key in response_data
            assert serialized_leader[key] == response_data[key], key

        assert 'lastMonthProfitPercentage' in response_data
        assert 'numberOfSubscribers' in response_data
        assert response_data['numberOfSubscribers'] == (1 if leader.id == self.leader_three.id else 2)
        self._assert_leader_wallets_info(response_data, leader)
        self._assert_leader_daily_portfo(response_data, leader)

        if public:
            assert 'isTrialAvailable' in response_data
            assert response_data['isTrialAvailable'] == (True if leader.id == self.leader_three.id else False)
            assert 'isSubscribed' in response_data
            assert response_data['isSubscribed'] == (False if leader.id == self.leader_three.id else True)

    def _assert_success_public_response(self, api_response, leader: Leader):
        assert api_response.status_code == status.HTTP_200_OK
        json_response = api_response.json()
        assert 'status' in json_response
        assert json_response['status'] == 'ok'
        assert 'data' in json_response
        assert 'leader' in json_response['data']
        self._assert_leader_public_profile(json_response['data']['leader'], leader)

    def _assert_leader_wallets_info(self, response_data: dict, leader: Leader):
        assert 'assetRatios' in response_data
        wallet_info = response_data['assetRatios']
        for currency in ACTIVE_CURRENCIES:
            currency_codename = get_currency_codename(currency)
            assert currency_codename in wallet_info
            if leader.id == self.leader.id and currency == Currencies.rls:
                assert wallet_info[currency_codename] == '0.00074'
            elif leader.id == self.leader.id and currency == Currencies.usdt:
                assert wallet_info[currency_codename] == '0.99926'
            elif leader.id == self.leader_two.id and currency == Currencies.usdt:
                assert wallet_info[currency_codename] == '1'
            else:
                assert wallet_info[currency_codename] == '0'

    def _assert_leader_daily_portfo(self, response_data: dict, leader: Leader):
        assert 'dailyProfits' in response_data
        if leader.id == self.leader.id:
            assert len(response_data['dailyProfits']) == 4
        elif leader.id == self.leader_two.id:
            assert len(response_data['dailyProfits']) == 2

        profit_percentages = ['0.000', '40.00', '20.00', '-14.29']
        cumulative_profit_percentages = ['0.000', '33.33', '43.75', '33.33']
        response_data['dailyProfits'].sort(key=lambda portfo: portfo['reportDate'])
        for i, daily_portfo in enumerate(response_data['dailyProfits']):
            assert 'reportDate' in daily_portfo
            assert 'profitPercentage' in daily_portfo
            assert 'cumulativeProfitPercentage' in daily_portfo
            if leader.id == self.leader.id:
                assert daily_portfo['reportDate'] == self.report_dates[i].isoformat()
                assert Decimal(daily_portfo['profitPercentage']) == Decimal(profit_percentages[i])
                assert Decimal(daily_portfo['cumulativeProfitPercentage']) == Decimal(cumulative_profit_percentages[i])
            elif leader.id == self.leader_two.id:
                assert daily_portfo['reportDate'] == self.report_dates[i + 2].isoformat()
                assert Decimal(daily_portfo['profitPercentage']) == Decimal(profit_percentages[i])
                assert Decimal(daily_portfo['cumulativeProfitPercentage']) == Decimal(cumulative_profit_percentages[i])

    def _assert_no_private_info_in_public_profile(self, api_response: dict):
        response_data = api_response.json().get('data').get('leader')
        assert 'numberOfUnsubscribes' not in response_data
        assert 'gainedSubscriptionFees' not in response_data

    def _assert_unauthorized_user_response(self, api_response):
        assert api_response.status_code == status.HTTP_401_UNAUTHORIZED
        assert api_response.json() == {'detail': 'اطلاعات برای اعتبارسنجی ارسال نشده است.'}

    def _assert_404_failure_response(self, api_response):
        assert api_response.status_code == status.HTTP_404_NOT_FOUND
        assert api_response.json() == {'status': 'failed', 'code': 'NotFound', 'message': 'Leader does not exist'}
