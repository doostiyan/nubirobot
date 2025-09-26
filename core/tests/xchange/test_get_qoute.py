import time
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, call, patch

import requests
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from exchange import settings
from exchange.accounts.models import User, UserRestriction
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.features.models import QueueItem
from exchange.xchange.marketmaker.quotes import Quote
from exchange.xchange.models import ExchangeTrade, MarketLimitation, MarketStatus
from tests.xchange.helpers import BaseMarketLimitationTest
from tests.xchange.mocks import quote_btcusdt_buy_sample, quote_btcusdt_sell_sample, quote_usdtrls_buy_sample


class GetEstimateAPITests(APITestCase):
    URL = '/exchange/get-quote'

    def setUp(self):
        self.user = User.objects.get(id=202)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'
        self.market = MarketStatus.objects.create(
            base_currency=Currencies.btc,
            quote_currency=Currencies.usdt,
            base_to_quote_price_buy=2.2,
            quote_to_base_price_buy=3.2,
            base_to_quote_price_sell=1.2,
            quote_to_base_price_sell=1.2,
            min_base_amount=0.001,
            max_base_amount=20,
            min_quote_amount=5,
            max_quote_amount=500,
            base_precision=Decimal('1e-4'),
            quote_precision=Decimal('1e-1'),
            status=MarketStatus.STATUS_CHOICES.available,
        )
        self.data = {
            'type': 'sell',
            'amount': '2',
            'baseCurrency': 'btc',
            'quoteCurrency': 'usdt',
            'refCurrency': 'btc',
        }
        self.quote = Quote(
            quote_id='btcusdt-sell-a7db70bd22424eb68ce2dc0e688ffeb5',
            base_currency=Currencies.btc,
            quote_currency=Currencies.usdt,
            reference_currency=Currencies.btc,
            reference_amount=Decimal('0.2'),
            destination_amount=Decimal('8800'),
            is_sell=True,
            client_order_id='abcd',
            expires_at=ir_now() + timedelta(minutes=5),
            user_id=202,
        )

    @patch('exchange.xchange.marketmaker.quotes.Client.request', MagicMock(return_value=quote_btcusdt_sell_sample))
    def test_get_quote(self):
        response = self.client.post(self.URL, self.data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'status': 'ok',
            'result': {
                'baseCurrency': 'btc',
                'quoteCurrency': 'usdt',
                'refCurrency': 'btc',
                'refAmount': '2',
                'destAmount': '100000',
                'quoteId': 'btcusdt-sell-a7db70bd22424eb68ce2dc0e688ffeb5',
                'isSell': True,
                'expiresAt': '1970-01-20T21:15:54.878000+03:30',
            },
        }

    @patch('exchange.xchange.marketmaker.quotes.Client.request', MagicMock(side_effect=requests.Timeout))
    def test_get_quote_error_timeout(self):
        response = self.client.post(self.URL, self.data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'UnavailableDestination',
            'message': 'Destination service is not available. please try again.',
            'status': 'failed',
        }

    @patch('exchange.xchange.marketmaker.quotes.Client.request', MagicMock(side_effect=requests.HTTPError))
    def test_get_quote_error_bad_request(self):
        response = self.client.post(self.URL, self.data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {'code': 'InvalidRequest', 'message': 'Invalid request.', 'status': 'failed'}

    def test_get_quote_unavailable_marker_error(self):
        self.market.base_currency = Currencies.eth
        self.market.save()
        response = self.client.post(self.URL, self.data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'MarketUnavailable',
            'message': 'Market is not available.',
            'status': 'failed',
        }

    @patch('exchange.xchange.marketmaker.quotes.Client.request', MagicMock(return_value=quote_btcusdt_sell_sample))
    def test_get_quote_with_both_side_admin_config_for_sell(self):
        self.data['type'] = 'sell'
        self.market.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.both_side
        self.market.save()

        response = self.client.post(self.URL, self.data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'status': 'ok',
            'result': {
                'baseCurrency': 'btc',
                'quoteCurrency': 'usdt',
                'refCurrency': 'btc',
                'refAmount': '2',
                'destAmount': '100000',
                'quoteId': 'btcusdt-sell-a7db70bd22424eb68ce2dc0e688ffeb5',
                'isSell': True,
                'expiresAt': '1970-01-20T21:15:54.878000+03:30',
            },
        }

    @patch('exchange.xchange.marketmaker.quotes.Client.request', MagicMock(return_value=quote_btcusdt_sell_sample))
    def test_get_quote_with_sell_only_admin_config_for_sell(self):
        self.data['type'] = 'sell'
        self.market.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.sell_only
        self.market.save()

        response = self.client.post(self.URL, self.data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'status': 'ok',
            'result': {
                'baseCurrency': 'btc',
                'quoteCurrency': 'usdt',
                'refCurrency': 'btc',
                'refAmount': '2',
                'destAmount': '100000',
                'quoteId': 'btcusdt-sell-a7db70bd22424eb68ce2dc0e688ffeb5',
                'isSell': True,
                'expiresAt': '1970-01-20T21:15:54.878000+03:30',
            },
        }

    @patch('exchange.xchange.marketmaker.quotes.Client.request', MagicMock(return_value=quote_btcusdt_sell_sample))
    def test_get_quote_with_buy_only_admin_config_for_sell(self):
        self.data['type'] = 'sell'
        self.market.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.buy_only
        self.market.save()

        response = self.client.post(self.URL, self.data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'MarketUnavailable',
            'message': 'Market is not available.',
            'status': 'failed',
        }

    @patch('exchange.xchange.marketmaker.quotes.Client.request', MagicMock(return_value=quote_btcusdt_sell_sample))
    def test_get_quote_with_closed_admin_config_for_sell(self):
        self.data['type'] = 'sell'
        self.market.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.closed
        self.market.save()

        response = self.client.post(self.URL, self.data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'MarketUnavailable',
            'message': 'Market is not available.',
            'status': 'failed',
        }

    @patch('exchange.xchange.marketmaker.quotes.Client.request', MagicMock(return_value=quote_btcusdt_buy_sample))
    def test_get_quote_with_both_side_admin_config_for_buy(self):
        self.data['type'] = 'buy'
        self.market.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.both_side
        self.market.save()

        response = self.client.post(self.URL, self.data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'status': 'ok',
            'result': {
                'baseCurrency': 'btc',
                'quoteCurrency': 'usdt',
                'refCurrency': 'btc',
                'refAmount': '2',
                'destAmount': '100000',
                'quoteId': 'btcusdt-buy-a7db70bd22424eb68ce2dc0e688ffeb5',
                'isSell': False,
                'expiresAt': '1970-01-20T21:15:54.878000+03:30',
            },
        }

    @patch('exchange.xchange.marketmaker.quotes.Client.request', MagicMock(return_value=quote_btcusdt_buy_sample))
    def test_get_quote_with_buy_only_admin_config_for_buy(self):
        self.data['type'] = 'buy'
        self.market.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.buy_only
        self.market.save()

        response = self.client.post(self.URL, self.data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'status': 'ok',
            'result': {
                'baseCurrency': 'btc',
                'quoteCurrency': 'usdt',
                'refCurrency': 'btc',
                'refAmount': '2',
                'destAmount': '100000',
                'quoteId': 'btcusdt-buy-a7db70bd22424eb68ce2dc0e688ffeb5',
                'isSell': False,
                'expiresAt': '1970-01-20T21:15:54.878000+03:30',
            },
        }

    @patch('exchange.xchange.marketmaker.quotes.Client.request', MagicMock(return_value=quote_btcusdt_buy_sample))
    def test_get_quote_with_sell_only_admin_config_for_buy(self):
        self.data['type'] = 'buy'
        self.market.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.sell_only
        self.market.save()

        response = self.client.post(self.URL, self.data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'MarketUnavailable',
            'message': 'Market is not available.',
            'status': 'failed',
        }

    @patch('exchange.xchange.marketmaker.quotes.Client.request', MagicMock(return_value=quote_btcusdt_buy_sample))
    def test_get_quote_with_closed_admin_config_for_buy(self):
        self.data['type'] = 'buy'
        self.market.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.closed
        self.market.save()

        response = self.client.post(self.URL, self.data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'MarketUnavailable',
            'message': 'Market is not available.',
            'status': 'failed',
        }

    @patch('exchange.xchange.trader.Estimator.estimate', new_callable=MagicMock)
    def test_adjusting_amount_with_market_status_precision(self, mock_estimate):
        mock_estimate.return_value = self.quote
        self.client.post(self.URL, data={**self.data, 'amount': '0.2233990099'})
        mock_estimate.assert_called_once_with(
            base_currency=Currencies.btc,
            quote_currency=Currencies.usdt,
            is_sell=True,
            amount=Decimal('0.2233'),
            user_id=202,
            reference_currency=Currencies.btc,
        )

        self.client.post(self.URL, data={**self.data, 'amount': '22', 'refCurrency': 'usdt'})
        mock_estimate.assert_called_with(
            base_currency=Currencies.btc,
            quote_currency=Currencies.usdt,
            is_sell=True,
            amount=Decimal('22'),
            user_id=202,
            reference_currency=Currencies.usdt,
        )

    @patch('exchange.xchange.trader.Estimator.estimate', new_callable=MagicMock)
    def test_adjusting_amount_with_market_status_max_amount(self, mock_estimate):
        mock_estimate.return_value = self.quote
        self.client.post(self.URL, data={**self.data, 'amount': '2020'})
        mock_estimate.assert_called_once_with(
            base_currency=Currencies.btc,
            quote_currency=Currencies.usdt,
            is_sell=True,
            amount=Decimal('20'),
            user_id=202,
            reference_currency=Currencies.btc,
        )

        self.client.post(self.URL, data={**self.data, 'amount': '500', 'refCurrency': 'usdt'})
        mock_estimate.assert_called_with(
            base_currency=Currencies.btc,
            quote_currency=Currencies.usdt,
            is_sell=True,
            amount=Decimal('500'),
            user_id=202,
            reference_currency=Currencies.usdt,
        )

    @patch('exchange.xchange.trader.Estimator.estimate', new_callable=MagicMock)
    def test_adjusting_amount_with_market_status_min_amount(self, mock_estimate):
        mock_estimate.return_value = self.quote
        self.client.post(self.URL, data={**self.data, 'amount': '0.1'})
        mock_estimate.assert_called_once_with(
            base_currency=Currencies.btc,
            quote_currency=Currencies.usdt,
            is_sell=True,
            amount=Decimal('0.1'),
            user_id=202,
            reference_currency=Currencies.btc,
        )

        response = self.client.post(self.URL, data={**self.data, 'amount': '0.5', 'refCurrency': 'usdt'})
        mock_estimate.assert_called_once()
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'InvalidQuoteAmount',
            'message': f'Amount should be more than 5.0',
            'status': 'failed',
        }

    def test_user_restrictions(self):
        """
        User should get error when its access restricted.
        Two restrictions will restrict get quote: Trading, Convert
        """
        convert_restriction = UserRestriction.add_restriction(self.user, UserRestriction.RESTRICTION.Convert)

        response = self.client.post(self.URL, self.data)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {
            'code': 'ActionIsRestricted',
            'message': 'You can not get the quote due to the restriction.',
            'status': 'failed',
        }

        convert_restriction.delete()

        trading_restriction = UserRestriction.add_restriction(self.user, UserRestriction.RESTRICTION.Trading)

        response = self.client.post(self.URL, self.data)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {
            'code': 'ActionIsRestricted',
            'message': 'You can not get the quote due to the restriction.',
            'status': 'failed',
        }

        trading_restriction.delete()

        UserRestriction.add_restriction(self.user, UserRestriction.RESTRICTION.Trading)
        UserRestriction.add_restriction(self.user, UserRestriction.RESTRICTION.Convert)

        response = self.client.post(self.URL, self.data)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {
            'code': 'ActionIsRestricted',
            'message': 'You can not get the quote due to the restriction.',
            'status': 'failed',
        }

    def test_get_quote_when_market_limitation_exceeded_in_sell(self):
        MarketLimitation.objects.create(
            interval=24,
            max_amount=Decimal('4'),
            market=self.market,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        BaseMarketLimitationTest.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('1'),
            dst_amount=Decimal('2.2'),
        )
        data = {
            'type': 'sell',
            'amount': '2',  # in here equals 2*1.2=2.4 usdt for selling
            'baseCurrency': 'btc',
            'quoteCurrency': 'usdt',
            'refCurrency': 'btc',
        }
        response = self.client.post(self.URL, data=data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {
            'code': 'MarketLimitationExceeded',
            'message': 'Market limitation exceeded.',
            'status': 'failed',
        }

    def test_get_quote_when_market_limitation_exceeded_in_buy(self):
        MarketLimitation.objects.create(
            interval=24,
            max_amount=Decimal('4'),
            market=self.market,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        BaseMarketLimitationTest.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('1'),
            dst_amount=Decimal('2.2'),
        )
        data = {
            'type': 'buy',
            'amount': '2',  # 2 usdt
            'baseCurrency': 'btc',
            'quoteCurrency': 'usdt',
            'refCurrency': 'usdt',
        }
        response = self.client.post(self.URL, data=data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {
            'code': 'MarketLimitationExceeded',
            'message': 'Market limitation exceeded.',
            'status': 'failed',
        }

    @patch('exchange.xchange.marketmaker.quotes.Client.request', MagicMock(return_value=quote_btcusdt_sell_sample))
    def test_get_quote_when_market_limit_not_exceeded_in_sell(self):
        MarketLimitation.objects.create(
            interval=24,
            max_amount=Decimal('8'),
            market=self.market,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        BaseMarketLimitationTest.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('1'),
            dst_amount=Decimal('2.2'),
        )
        data = {
            'type': 'sell',
            'amount': '5',  # 5 usdt
            'baseCurrency': 'btc',
            'quoteCurrency': 'usdt',
            'refCurrency': 'usdt',
        }
        response = self.client.post(self.URL, data=data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'result': {
                'baseCurrency': 'btc',
                'destAmount': '100000',
                'expiresAt': '1970-01-20T21:15:54.878000+03:30',
                'isSell': True,
                'quoteCurrency': 'usdt',
                'quoteId': 'btcusdt-sell-a7db70bd22424eb68ce2dc0e688ffeb5',
                'refAmount': '2',
                'refCurrency': 'btc',
            },
            'status': 'ok',
        }

    @patch('exchange.xchange.marketmaker.quotes.Client.request', MagicMock(return_value=quote_btcusdt_buy_sample))
    def test_get_quote_when_market_limit_not_exceeded_in_buy(self):
        MarketLimitation.objects.create(
            interval=24,
            max_amount=Decimal('8'),
            market=self.market,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        BaseMarketLimitationTest.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('1'),
            dst_amount=Decimal('2.2'),
        )
        data = {
            'type': 'buy',
            'amount': '2',  # 2*2.2=4.4 usdt
            'baseCurrency': 'btc',
            'quoteCurrency': 'usdt',
            'refCurrency': 'btc',
        }
        response = self.client.post(self.URL, data=data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'result': {
                'baseCurrency': 'btc',
                'destAmount': '100000',
                'expiresAt': '1970-01-20T21:15:54.878000+03:30',
                'isSell': False,
                'quoteCurrency': 'usdt',
                'quoteId': 'btcusdt-buy-a7db70bd22424eb68ce2dc0e688ffeb5',
                'refAmount': '2',
                'refCurrency': 'btc',
            },
            'status': 'ok',
        }

    def test_get_quote_when_user_market_limitation_exceeded_in_sell(self):
        MarketLimitation.objects.create(
            interval=24,
            max_amount=Decimal('4'),
            market=self.market,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.USER,
        )
        BaseMarketLimitationTest.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('1'),
            dst_amount=Decimal('2.2'),
        )
        data = {
            'type': 'sell',
            'amount': '2',  # in here equals 2*1.2=2.4 usdt for selling
            'baseCurrency': 'btc',
            'quoteCurrency': 'usdt',
            'refCurrency': 'btc',
        }
        response = self.client.post(self.URL, data=data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {
            'code': 'UserLimitationExceeded',
            'message': 'User limitation exceeded.',
            'status': 'failed',
        }

    def test_get_quote_when_user_market_limitation_exceeded_in_buy(self):
        MarketLimitation.objects.create(
            interval=24,
            max_amount=Decimal('4'),
            market=self.market,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.USER,
        )
        BaseMarketLimitationTest.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('1'),
            dst_amount=Decimal('2.2'),
        )
        data = {
            'type': 'buy',
            'amount': '2',  # 2 usdt
            'baseCurrency': 'btc',
            'quoteCurrency': 'usdt',
            'refCurrency': 'usdt',
        }
        response = self.client.post(self.URL, data=data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {
            'code': 'UserLimitationExceeded',
            'message': 'User limitation exceeded.',
            'status': 'failed',
        }

    @patch('exchange.xchange.marketmaker.quotes.Client.request', MagicMock(return_value=quote_btcusdt_sell_sample))
    def test_get_quote_when_user_market_limit_not_exceeded_in_sell(self):
        MarketLimitation.objects.create(
            interval=24,
            max_amount=Decimal('8'),
            market=self.market,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.USER,
        )
        BaseMarketLimitationTest.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('1'),
            dst_amount=Decimal('2.2'),
        )
        data = {
            'type': 'sell',
            'amount': '5',  # 5 usdt
            'baseCurrency': 'btc',
            'quoteCurrency': 'usdt',
            'refCurrency': 'usdt',
        }
        response = self.client.post(self.URL, data=data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'result': {
                'baseCurrency': 'btc',
                'destAmount': '100000',
                'expiresAt': '1970-01-20T21:15:54.878000+03:30',
                'isSell': True,
                'quoteCurrency': 'usdt',
                'quoteId': 'btcusdt-sell-a7db70bd22424eb68ce2dc0e688ffeb5',
                'refAmount': '2',
                'refCurrency': 'btc',
            },
            'status': 'ok',
        }

    @patch('exchange.xchange.marketmaker.quotes.Client.request', MagicMock(return_value=quote_btcusdt_buy_sample))
    def test_get_quote_when_user_market_limit_not_exceeded_in_buy(self):
        MarketLimitation.objects.create(
            interval=24,
            max_amount=Decimal('8'),
            market=self.market,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.USER,
        )
        BaseMarketLimitationTest.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=Decimal('1'),
            dst_amount=Decimal('2.2'),
        )
        data = {
            'type': 'buy',
            'amount': '5',  # 5 usdt
            'baseCurrency': 'btc',
            'quoteCurrency': 'usdt',
            'refCurrency': 'usdt',
        }
        response = self.client.post(self.URL, data=data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'result': {
                'baseCurrency': 'btc',
                'destAmount': '100000',
                'expiresAt': '1970-01-20T21:15:54.878000+03:30',
                'isSell': False,
                'quoteCurrency': 'usdt',
                'quoteId': 'btcusdt-buy-a7db70bd22424eb68ce2dc0e688ffeb5',
                'refAmount': '2',
                'refCurrency': 'btc',
            },
            'status': 'ok',
        }

    def test_get_quote_when_usdtrls_user_market_limitation_exceeded(self):
        usdtrls_market = BaseMarketLimitationTest.create_usdt_rls_market()
        MarketLimitation.objects.create(
            interval=24,
            max_amount=Decimal('4'),
            market=usdtrls_market,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.USER,
        )
        BaseMarketLimitationTest.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=Decimal('3'),
            dst_amount=Decimal('2100000'),
        )
        data = {
            'type': 'sell',
            'amount': '2',  # 2 usdt
            'baseCurrency': 'usdt',
            'quoteCurrency': 'rls',
            'refCurrency': 'usdt',
        }
        response = self.client.post(self.URL, data=data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {
            'code': 'UserLimitationExceeded',
            'message': 'User limitation exceeded.',
            'status': 'failed',
        }

    def test_get_quote_when_usdtrls_market_limitation_exceeded(self):
        usdtrls_market = BaseMarketLimitationTest.create_usdt_rls_market()
        MarketLimitation.objects.create(
            interval=24,
            max_amount=Decimal('4'),
            market=usdtrls_market,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        BaseMarketLimitationTest.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=Decimal('3'),
            dst_amount=Decimal('2100000'),
        )
        data = {
            'type': 'buy',
            'amount': '1400000',  # equals 2 usdt
            'baseCurrency': 'usdt',
            'quoteCurrency': 'rls',
            'refCurrency': 'rls',
        }
        response = self.client.post(self.URL, data=data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {
            'code': 'MarketLimitationExceeded',
            'message': 'Market limitation exceeded.',
            'status': 'failed',
        }

    @patch('exchange.xchange.marketmaker.quotes.Client.request', MagicMock(return_value=quote_usdtrls_buy_sample))
    def test_get_quote_when_sum_trade_of_users_exceeded_market_limitation(self):
        user_2 = User.objects.create_user(username='user2')
        Token.objects.create(user=user_2)
        user_3 = User.objects.create_user(username='user3')
        Token.objects.create(user=user_3)
        usdtrls_market = BaseMarketLimitationTest.create_usdt_rls_market()
        MarketLimitation.objects.create(
            interval=24,
            max_amount=Decimal('9'),
            market=usdtrls_market,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        MarketLimitation.objects.create(
            interval=24,
            max_amount=Decimal('7'),  # all user pass this limitation
            market=usdtrls_market,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.USER,
        )
        BaseMarketLimitationTest.create_trade(
            user=user_2,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=Decimal('3'),
            dst_amount=Decimal('2100000'),
        )
        BaseMarketLimitationTest.create_trade(
            user=user_3,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=Decimal('4'),
            dst_amount=Decimal('2800000'),
        )
        BaseMarketLimitationTest.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=Decimal('1'),
            dst_amount=Decimal('700000'),
        )
        data = {
            'type': 'buy',
            'amount': '2',
            'baseCurrency': 'usdt',
            'quoteCurrency': 'rls',
            'refCurrency': 'usdt',
        }
        market_limitation_error = {
            'code': 'MarketLimitationExceeded',
            'message': 'Market limitation exceeded.',
            'status': 'failed',
        }
        # user 1 requested for 2 usdt, but there are 3 + 4 + 1 = 8 usdt trades and limitation is 9
        response = self.client.post(self.URL, data=data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == market_limitation_error
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {user_2.auth_token.key}'
        # user 2 requested for 2 usdt, but there are 3 + 4 + 1 = 8 usdt trades and limitation is 9
        response = self.client.post(self.URL, data=data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == market_limitation_error
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {user_3.auth_token.key}'
        # user 3 requested for 2 usdt, but there are 3 + 4 + 1 = 8 usdt trades and limitation is 9
        response = self.client.post(self.URL, data=data)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == market_limitation_error
        data['amount'] = 1
        # 8 usdt are traded, limitation is 9 usdt. 9 - 8 = 1 usdt is available
        # user 3 requested 1 usdt and he can trades successfully
        response = self.client.post(self.URL, data=data)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'result': {
                'baseCurrency': 'usdt',
                'destAmount': '1400000',
                'expiresAt': '1970-01-20T21:15:54.878000+03:30',
                'isSell': False,
                'quoteCurrency': 'rls',
                'quoteId': 'usdtrls-buy-a7db70bd22424eb68ce2dc0e688feee5',
                'refAmount': '2',
                'refCurrency': 'usdt',
            },
            'status': 'ok',
        }

    def test_get_quote_ref_is_not_equal_base_or_quote(self):
        data = {
            'type': 'sell',
            'amount': '2',
            'baseCurrency': 'btc',
            'quoteCurrency': 'usdt',
            'refCurrency': 'eth',
        }
        response = self.client.post(self.URL, data=data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'InvalidRefCurrency',
            'message': 'refCurrency is invalid.',
            'status': 'failed',
        }

    @patch('exchange.base.decorators.time')
    @patch('exchange.base.decorators.metric_incr')
    def test_count_error_api(self, metric_mock, time_mock):
        UserRestriction.add_restriction(self.user, UserRestriction.RESTRICTION.Convert)
        flush_time = 30

        time_mock.return_value = time.time()
        response = self.client.post(self.URL, self.data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert metric_mock.call_count == 0  # Should not be called.

        time_mock.return_value = time.time() + flush_time
        response = self.client.post(self.URL, self.data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert metric_mock.call_count == 2

        time_mock.return_value = time.time() + flush_time + flush_time

        response = self.client.post(self.URL, self.data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert metric_mock.call_count == 4

        metric_mock.assert_has_calls(
            [
                call(
                    f'metric_api_process_result_count__xchangeGetQuote_{settings.SERVER_NAME}_ActionIsRestricted',
                    amount=2,
                ),
                call(f'metric_api_process_count__xchangeGetQuote_{settings.SERVER_NAME}_403', amount=2),
                call(
                    f'metric_api_process_result_count__xchangeGetQuote_{settings.SERVER_NAME}_ActionIsRestricted',
                    amount=1,
                ),
                call(f'metric_api_process_count__xchangeGetQuote_{settings.SERVER_NAME}_403', amount=1),
            ]
        )

    @patch('exchange.xchange.helpers.XCHANGE_TESTING_CURRENCIES', new=[Currencies.btc])
    def test_user_has_not_beta_markets_feature_flag(self):
        response = self.client.post(self.URL, self.data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            'code': 'MarketUnavailable',
            'message': 'Market is not available.',
            'status': 'failed',
        }

    @patch('exchange.xchange.helpers.XCHANGE_TESTING_CURRENCIES', new=[Currencies.btc])
    @patch('exchange.xchange.marketmaker.quotes.Client.request', MagicMock(return_value=quote_btcusdt_sell_sample))
    def test_user_has_beta_markets_feature_flag(self):
        QueueItem.objects.create(feature=QueueItem.FEATURES.new_coins, user=self.user, status=QueueItem.STATUS.done)
        response = self.client.post(self.URL, self.data)
        assert response.status_code == status.HTTP_200_OK
