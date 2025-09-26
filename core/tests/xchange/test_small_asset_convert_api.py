from unittest.mock import MagicMock, patch

from django.test import TestCase
from rest_framework import status
from rest_framework.authtoken.models import Token

from exchange.accounts.models import User, UserRestriction
from exchange.base.models import Currencies
from exchange.wallet.models import RIAL
from exchange.xchange import exceptions


class ConvertSmallAssetsAPITest(TestCase):
    def setUp(self):
        self.user = User.objects.create(
            username='xchange_small_asset_convert_api_test',
            user_type=User.USER_TYPE_LEVEL1,
        )
        token = Token.objects.create(key='XchangeSACTestToken', user=self.user)
        self.user.auth_token = token
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'
        self.url = '/exchange/convert-small-assets'

    @patch('exchange.xchange.small_asset_convertor.SmallAssetConvertor.convert')
    def test_convert_small_assets_success(self, mock_convert: MagicMock):
        source_currencies = [Currencies.btc, Currencies.eth]
        mock_convert.return_value = {
            Currencies.btc: exceptions.InvalidPair('srcCurrency should be in convert coins'),
            Currencies.eth: 'success',
        }

        response = self.client.post(
            self.url,
            data={'dstCurrency': 'rls', 'srcCurrencies': ['btc', 'eth']},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'status': 'ok',
            'result': {
                'btc': {
                    'status': 'failed',
                    'code': 'InvalidPair',
                    'message': 'srcCurrency should be in convert coins',
                },
                'eth': {
                    'status': 'ok',
                    'message': 'success',
                },
            },
        }
        mock_convert.assert_called_once_with(
            self.user,
            source_currencies,
            RIAL,
        )

    def test_convert_small_assets_restricted_user_convert(self):
        UserRestriction.add_restriction(self.user, UserRestriction.RESTRICTION.Convert)
        response = self.client.post(
            self.url,
            data={'dstCurrency': 'rls', 'srcCurrencies': ['btc', 'eth']},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {
            'code': 'ActionIsRestricted',
            'message': 'You can not convert small assets due to the restriction.',
            'status': 'failed',
        }

    def test_convert_small_assets_restricted_user_trade(self):
        UserRestriction.add_restriction(self.user, UserRestriction.RESTRICTION.Trading)
        response = self.client.post(
            self.url,
            data={'dstCurrency': 'rls', 'srcCurrencies': ['btc', 'eth']},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {
            'code': 'ActionIsRestricted',
            'message': 'You can not convert small assets due to the restriction.',
            'status': 'failed',
        }

    def test_convert_small_assets_missing_src_currency(self):
        response = self.client.post(
            self.url,
            data={'dstCurrency': 'rls'},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'RequiredParameter',
            'message': 'srcCurrencies parameter is required',
            'status': 'failed',
        }

    def test_convert_small_assets_invalid_src_currency(self):
        response = self.client.post(
            self.url,
            data={'dstCurrency': 'rls', 'srcCurrencies': ['invalid_coin']},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['code'] == 'ParseError'

    def test_convert_small_assets_missing_dst_currency(self):
        response = self.client.post(
            self.url,
            data={'srcCurrencies': ['btc', 'eth']},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['code'] == 'ParseError'

    def test_convert_small_assets_invalid_dst_currency(self):
        response = self.client.post(
            self.url,
            data={'dstCurrency': 'invalid_coin', 'srcCurrencies': ['btc', 'eth']},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json()['code'] == 'ParseError'

    @patch('exchange.xchange.small_asset_convertor.SmallAssetConvertor.convert')
    def test_convert_small_assets_invalid_pair(self, mock_convert: MagicMock):
        mock_convert.side_effect = exceptions.InvalidPair('Invalid currency pair')
        response = self.client.post(
            self.url,
            data={'dstCurrency': 'rls', 'srcCurrencies': ['btc', 'eth']},
            content_type='application/json',
        )
        mock_convert.assert_called_once()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'InvalidPair',
            'message': 'Invalid currency pair',
            'status': 'failed',
        }

    @patch('exchange.xchange.small_asset_convertor.SmallAssetConvertor.convert')
    def test_convert_small_assets_market_unavailable(self, mock_convert: MagicMock):
        mock_convert.side_effect = exceptions.MarketUnavailable('Market is unavailable')
        response = self.client.post(
            self.url,
            data={'dstCurrency': 'rls', 'srcCurrencies': ['btc', 'eth']},
            content_type='application/json',
        )
        mock_convert.assert_called_once()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'MarketUnavailable',
            'message': 'Market is unavailable',
            'status': 'failed',
        }

    @patch('exchange.xchange.small_asset_convertor.SmallAssetConvertor.convert')
    def test_convert_small_assets_all_converts_failed(self, mock_convert: MagicMock):
        source_currencies = [Currencies.btc, Currencies.eth]
        mock_convert.return_value = {
            Currencies.btc: exceptions.InvalidPair('srcCurrency should be in convert coins'),
            Currencies.eth: exceptions.MarketUnavailable('Market is not available.'),
        }

        response = self.client.post(
            self.url,
            data={'dstCurrency': 'rls', 'srcCurrencies': ['btc', 'eth']},
            content_type='application/json',
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'status': 'failed',
            'code': 'ConversionFailed',
            'message': 'All src conversion failed. Check result for more detail.',
            'result': {
                'btc': {
                    'status': 'failed',
                    'code': 'InvalidPair',
                    'message': 'srcCurrency should be in convert coins',
                },
                'eth': {
                    'status': 'failed',
                    'code': 'MarketUnavailable',
                    'message': 'Market is not available.',
                },
            },
        }
        mock_convert.assert_called_once_with(
            self.user,
            source_currencies,
            RIAL,
        )
