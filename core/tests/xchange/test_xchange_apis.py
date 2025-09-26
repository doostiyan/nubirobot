'''Xchange APIs Test'''
import decimal
from datetime import timedelta
from unittest.mock import MagicMock, patch

import requests
import responses
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token

from exchange.accounts.models import User, UserRestriction
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies
from exchange.wallet.models import Wallet
from exchange.xchange.marketmaker.client import Client
from exchange.xchange.marketmaker.quotes import Estimator, Quote
from exchange.xchange.models import ExchangeTrade, MarketLimitation, MarketStatus
from tests.xchange.helpers import BaseMarketLimitationTest


class CreateTradeTests(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:

        cls.quote_id = 'dc2566913fdb4148a1357141b11ea195'
        cls.user = User.objects.get(pk=201)
        cls.xchange_user = User.objects.get(username='system-convert')
        return super().setUpTestData()

    def setUp(self):
        self.quote = Quote(
            quote_id=self.quote_id,
            base_currency=Currencies.btc,
            quote_currency=Currencies.usdt,
            reference_currency=Currencies.usdt,
            reference_amount=decimal.Decimal('12.22'),
            destination_amount=decimal.Decimal('12.22'),
            is_sell=True,
            client_order_id='cliOid',
            expires_at=ir_now() + timedelta(days=1),
            user_id=self.user.id,
        )
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
            base_precision=decimal.Decimal('1e-4'),
            quote_precision=decimal.Decimal('1e-1'),
            status=MarketStatus.STATUS_CHOICES.available,
        )
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {self.user.auth_token.key}'
        return super().setUp()

    def _mock_market_maker_response(self, *, is_sell=True, quote=None):
        quote = quote or self.quote
        responses.post(
            url=Client.get_base_url()[1] + '/xconvert/convert',
            json={
                'result': {
                    'convertId': 1,
                    'destinationCurrencyAmount': str(quote.destination_amount),
                    'quoteId': quote.quote_id,
                    'clientId': quote.client_order_id,
                    'baseCurrency': quote.base_currency_code_name,
                    'quoteCurrency': quote.quote_currency_code_name,
                    'status': 'Filled',
                    'side': 'sell' if is_sell else 'buy',
                    'referenceCurrency': quote.reference_currency_code_name,
                    'referenceCurrencyAmount': str(quote.reference_amount),
                },
                'message': 'successful message',
                'error': 'success',
                'hasError': False,
            },
            status=200,
        )

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_a_successful_call(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        wallet.balance = 13
        wallet.save()
        wallet = Wallet.get_user_wallet(self.xchange_user, Currencies.usdt)
        wallet.balance = 1000
        wallet.save()
        Estimator.set_quote(self.quote, self.user.id)
        self._mock_market_maker_response()
        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
            HTTP_USER_AGENT='android/9',
            HTTP_X_APP_MODE='PRO',
        ).json()
        assert response['status'] == 'ok'
        result = response['result']
        result.pop('id')
        result.pop('createdAt')
        assert result == {
            'dstAmount': '12.22',
            'dstSymbol': 'usdt',
            'isSell': True,
            'srcAmount': '12.22',
            'srcSymbol': 'btc',
            'status': 'succeeded',
        }
        assert ExchangeTrade.objects.get(
            quote_id='dc2566913fdb4148a1357141b11ea195', user_agent=ExchangeTrade.USER_AGENT.android_pro
        )

    @responses.activate
    def test_failed_provider_api_call(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        wallet.balance = 13
        wallet.save()
        wallet = Wallet.get_user_wallet(self.xchange_user, Currencies.usdt)
        wallet.balance = 1000
        wallet.save()
        Estimator.set_quote(self.quote, self.user.id)
        responses.post(
            url=Client.get_base_url()[1] + '/xconvert/convert',
            json={'hasError': True},
            status=400,
        )
        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        ).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'FailedConversion'

    @responses.activate
    def test_invalid_quote_id(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        wallet.balance = 13
        wallet.save()
        wallet = Wallet.get_user_wallet(self.xchange_user, Currencies.usdt)
        wallet.balance = 1000
        wallet.save()
        Estimator.set_quote(self.quote, self.user.id)
        self._mock_market_maker_response()
        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': '000000000fdb4148a135714100000000'},
        ).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'QuoteIsNotAvailable'

    @responses.activate
    def test_invalid_quote_user(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        wallet.balance = 13
        wallet.save()
        wallet = Wallet.get_user_wallet(self.xchange_user, Currencies.usdt)
        wallet.balance = 1000
        wallet.save()
        self.quote.user_id = 5463564365
        Estimator.set_quote(self.quote, self.user.id)
        self._mock_market_maker_response()
        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        ).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'QuoteIsNotAvailable'

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_both_side_market_when_quote_is_sell(self):
        self.market.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.both_side
        self.market.save()
        self.quote.is_sell = True

        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        wallet.balance = 13
        wallet.save()
        wallet = Wallet.get_user_wallet(self.xchange_user, Currencies.usdt)
        wallet.balance = 1000
        wallet.save()

        Estimator.set_quote(self.quote, self.user.id)
        self._mock_market_maker_response(is_sell=True)

        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        ).json()
        assert response['status'] == 'ok'
        result = response['result']
        result.pop('id')
        result.pop('createdAt')
        assert result == {
            'dstAmount': '12.22',
            'dstSymbol': 'usdt',
            'isSell': True,
            'srcAmount': '12.22',
            'srcSymbol': 'btc',
            'status': 'succeeded',
        }

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_sell_only_market_when_quote_is_sell(self):
        self.market.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.sell_only
        self.market.save()
        self.quote.is_sell = True

        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        wallet.balance = 13
        wallet.save()
        wallet = Wallet.get_user_wallet(self.xchange_user, Currencies.usdt)
        wallet.balance = 1000
        wallet.save()

        Estimator.set_quote(self.quote, self.user.id)
        self._mock_market_maker_response(is_sell=True)

        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        ).json()
        assert response['status'] == 'ok'
        result = response['result']
        result.pop('id')
        result.pop('createdAt')
        assert result == {
            'dstAmount': '12.22',
            'dstSymbol': 'usdt',
            'isSell': True,
            'srcAmount': '12.22',
            'srcSymbol': 'btc',
            'status': 'succeeded',
        }

    @responses.activate
    def test_buy_only_market_when_quote_is_sell(self):
        self.market.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.buy_only
        self.market.save()
        self.quote.is_sell = True

        Estimator.set_quote(self.quote, self.user.id)
        self._mock_market_maker_response(is_sell=True)

        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        ).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'MarketUnavailable'

    @responses.activate
    def test_closed_market_when_quote_is_sell(self):
        self.market.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.closed
        self.market.save()
        self.quote.is_sell = True

        Estimator.set_quote(self.quote, self.user.id)
        self._mock_market_maker_response(is_sell=True)

        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        ).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'MarketUnavailable'

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_both_side_market_when_quote_is_buy(self):
        self.market.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.both_side
        self.market.save()
        self.quote.is_sell = False

        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        wallet.balance = 13
        wallet.save()
        wallet = Wallet.get_user_wallet(self.xchange_user, Currencies.btc)
        wallet.balance = 1000
        wallet.save()

        Estimator.set_quote(self.quote, self.user.id)
        self._mock_market_maker_response(is_sell=False)

        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        ).json()
        assert response['status'] == 'ok'
        result = response['result']
        result.pop('id')
        result.pop('createdAt')
        assert result == {
            'dstAmount': '12.22',
            'dstSymbol': 'usdt',
            'isSell': False,
            'srcAmount': '12.22',
            'srcSymbol': 'btc',
            'status': 'succeeded',
        }

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_buy_only_market_when_quote_is_buy(self):
        self.market.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.buy_only
        self.market.save()
        self.quote.is_sell = False

        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        wallet.balance = 13
        wallet.save()
        wallet = Wallet.get_user_wallet(self.xchange_user, Currencies.btc)
        wallet.balance = 1000
        wallet.save()

        Estimator.set_quote(self.quote, self.user.id)
        self._mock_market_maker_response(is_sell=False)

        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        ).json()
        assert response['status'] == 'ok'
        result = response['result']
        result.pop('id')
        result.pop('createdAt')
        assert result == {
            'dstAmount': '12.22',
            'dstSymbol': 'usdt',
            'isSell': False,
            'srcAmount': '12.22',
            'srcSymbol': 'btc',
            'status': 'succeeded',
        }

    @responses.activate
    def test_sell_only_market_when_quote_is_buy(self):
        self.market.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.sell_only
        self.market.save()
        self.quote.is_sell = False

        Estimator.set_quote(self.quote, self.user.id)
        self._mock_market_maker_response(is_sell=False)

        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        ).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'MarketUnavailable'

    @responses.activate
    def test_closed_market_when_quote_is_buy(self):
        self.market.exchange_side = MarketStatus.EXCHANGE_SIDE_CHOICES.closed
        self.market.save()
        self.quote.is_sell = False

        Estimator.set_quote(self.quote, self.user.id)
        self._mock_market_maker_response(is_sell=False)

        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        ).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'MarketUnavailable'

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_insufficient_user_assets(self):
        Estimator.set_quote(self.quote, self.user.id)
        self._mock_market_maker_response()
        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        ).json()
        assert response['status'] == 'failed'
        assert response['code'] == 'FailedAssetTransfer'

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_insufficient_system_assets(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        wallet.balance = 13
        wallet.save()
        Estimator.set_quote(self.quote, self.user.id)
        self._mock_market_maker_response()
        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        ).json()
        assert response['status'] == 'ok'
        result = response['result']
        result.pop('id')
        result.pop('createdAt')
        assert result == {
            'dstAmount': '12.22',
            'dstSymbol': 'usdt',
            'isSell': True,
            'srcAmount': '12.22',
            'srcSymbol': 'btc',
            'status': 'succeeded',
        }

    @patch.object(Client, 'request', MagicMock(side_effect=requests.Timeout))
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_a_provider_timeout(self):
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        wallet.balance = 13
        wallet.save()
        wallet = Wallet.get_user_wallet(self.xchange_user, Currencies.usdt)
        wallet.balance = 1000
        wallet.save()
        Estimator.set_quote(self.quote, self.user.id)
        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        ).json()
        assert response['status'] == 'ok'
        result = response['result']
        result.pop('id')
        result.pop('createdAt')
        assert result == {
            'dstAmount': '12.22',
            'dstSymbol': 'usdt',
            'isSell': True,
            'srcAmount': '12.22',
            'srcSymbol': 'btc',
            'status': 'unknown',
        }

    def test_user_restrictions(self):
        """
        User should get error when its access restricted.
        Two restrictions will restrict get quote: Trading, Convert
        """
        url = '/exchange/create-trade'
        data = {'quoteId': 'dc2566913fdb4148a1357141b11ea195'}

        convert_restriction = UserRestriction.add_restriction(self.user, UserRestriction.RESTRICTION.Convert)

        response = self.client.post(path=url, data=data)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {
            'code': 'ActionIsRestricted',
            'message': 'You can not create the trade due to the restriction.',
            'status': 'failed',
        }

        convert_restriction.delete()

        trading_restriction = UserRestriction.add_restriction(self.user, UserRestriction.RESTRICTION.Trading)

        response = self.client.post(path=url, data=data)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {
            'code': 'ActionIsRestricted',
            'message': 'You can not create the trade due to the restriction.',
            'status': 'failed',
        }

        trading_restriction.delete()

        UserRestriction.add_restriction(self.user, UserRestriction.RESTRICTION.Trading)
        UserRestriction.add_restriction(self.user, UserRestriction.RESTRICTION.Convert)

        response = self.client.post(path=url, data=data)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.json() == {
            'code': 'ActionIsRestricted',
            'message': 'You can not create the trade due to the restriction.',
            'status': 'failed',
        }

    def test_trade_when_market_limitation_exceeded_in_sell(self):
        MarketLimitation.objects.create(
            interval=24,
            max_amount=decimal.Decimal('10'),
            market=self.market,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        Estimator.set_quote(self.quote, self.user.id)
        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {
            'code': 'MarketLimitationExceeded',
            'message': 'Market limitation exceeded.',
            'status': 'failed',
        }

    def test_trade_when_market_limitation_exceeded_in_buy(self):
        user_2 = User.objects.get(id=202)
        BaseMarketLimitationTest.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=decimal.Decimal('10'),
            dst_amount=decimal.Decimal('50'),
        )
        BaseMarketLimitationTest.create_trade(
            user=user_2,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=decimal.Decimal('10'),
            dst_amount=decimal.Decimal('40'),
        )
        MarketLimitation.objects.create(
            interval=24,
            max_amount=decimal.Decimal('100'),
            market=self.market,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        self.quote.is_sell = False
        Estimator.set_quote(self.quote, self.user.id)
        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {
            'code': 'MarketLimitationExceeded',
            'message': 'Market limitation exceeded.',
            'status': 'failed',
        }

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_trade_when_market_limit_not_exceeded_in_sell(self):
        MarketLimitation.objects.create(
            interval=24,
            max_amount=decimal.Decimal('10'),
            market=self.market,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        wallet.balance = 13
        wallet.save()
        wallet = Wallet.get_user_wallet(self.xchange_user, Currencies.usdt)
        wallet.balance = 1000
        wallet.save()
        self.quote.reference_currency = Currencies.btc
        self.quote.reference_amount = decimal.Decimal('4')
        self._mock_market_maker_response()
        Estimator.set_quote(self.quote, self.user.id)
        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        ).json()
        assert response['status'] == 'ok'
        result = response['result']
        result.pop('id')
        result.pop('createdAt')
        assert result == {
            'dstAmount': '12.22',
            'dstSymbol': 'usdt',
            'isSell': True,
            'srcAmount': '4',
            'srcSymbol': 'btc',
            'status': 'succeeded',
        }

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_trade_when_market_limit_not_exceeded_in_buy(self):
        MarketLimitation.objects.create(
            interval=24,
            max_amount=decimal.Decimal('10'),
            market=self.market,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        wallet.balance = 100
        wallet.save()
        wallet = Wallet.get_user_wallet(self.xchange_user, Currencies.btc)
        wallet.balance = 10
        wallet.save()
        self.quote.reference_currency = Currencies.btc
        self.quote.is_sell = False
        self.quote.reference_amount = decimal.Decimal('1')
        self._mock_market_maker_response()
        Estimator.set_quote(self.quote, self.user.id)
        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        ).json()
        assert response['status'] == 'ok'
        result = response['result']
        result.pop('id')
        result.pop('createdAt')
        assert result == {
            'dstAmount': '12.22',
            'dstSymbol': 'usdt',
            'isSell': False,
            'srcAmount': '1',
            'srcSymbol': 'btc',
            'status': 'succeeded',
        }

    def test_trade_when_user_market_limitation_exceeded_in_sell(self):
        MarketLimitation.objects.create(
            interval=24,
            max_amount=decimal.Decimal('60'),
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
            src_amount=decimal.Decimal('10'),
            dst_amount=decimal.Decimal('50'),
        )
        Estimator.set_quote(self.quote, self.user.id)
        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == {
            'code': 'UserLimitationExceeded',
            'message': 'User limitation exceeded.',
            'status': 'failed',
        }

    def test_trade_when_user_market_limitation_exceeded_in_buy(self):
        MarketLimitation.objects.create(
            interval=24,
            max_amount=decimal.Decimal('10'),
            market=self.market,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.USER,
        )
        self.quote.is_sell = False
        Estimator.set_quote(self.quote, self.user.id)
        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        ).json()
        assert response == {
            'code': 'UserLimitationExceeded',
            'message': 'User limitation exceeded.',
            'status': 'failed',
        }

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_trade_when_user_market_limit_not_exceeded_in_sell(self):
        user_2 = User.objects.get(id=202)
        BaseMarketLimitationTest.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=decimal.Decimal('10'),
            dst_amount=decimal.Decimal('50'),
        )
        BaseMarketLimitationTest.create_trade(
            user=user_2,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            src_amount=decimal.Decimal('10'),
            dst_amount=decimal.Decimal('40'),
        )
        MarketLimitation.objects.create(
            interval=24,
            max_amount=decimal.Decimal('70'),
            market=self.market,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.USER,
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.btc)
        wallet.balance = 13
        wallet.save()
        wallet = Wallet.get_user_wallet(self.xchange_user, Currencies.usdt)
        wallet.balance = 1000
        wallet.save()
        self.quote.reference_currency = Currencies.btc
        self.quote.destination_amount = decimal.Decimal('5')
        self._mock_market_maker_response()
        Estimator.set_quote(self.quote, self.user.id)
        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        ).json()
        assert response['status'] == 'ok'
        result = response['result']
        result.pop('id')
        result.pop('createdAt')
        assert result == {
            'dstAmount': '5',
            'dstSymbol': 'usdt',
            'isSell': True,
            'srcAmount': '12.22',
            'srcSymbol': 'btc',
            'status': 'succeeded',
        }

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_trade_when_user_market_limit_not_exceeded_in_buy(self):
        MarketLimitation.objects.create(
            interval=24,
            max_amount=decimal.Decimal('10'),
            market=self.market,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.USER,
        )
        wallet = Wallet.get_user_wallet(self.user, Currencies.usdt)
        wallet.balance = 100
        wallet.save()
        wallet = Wallet.get_user_wallet(self.xchange_user, Currencies.btc)
        wallet.balance = 10
        wallet.save()
        self.quote.reference_currency = Currencies.usdt
        self.quote.is_sell = False
        self.quote.reference_amount = decimal.Decimal('5')
        self._mock_market_maker_response()
        Estimator.set_quote(self.quote, self.user.id)
        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea195'},
        ).json()
        assert response['status'] == 'ok'
        result = response['result']
        result.pop('id')
        result.pop('createdAt')
        assert result == {
            'dstAmount': '5',
            'dstSymbol': 'usdt',
            'isSell': False,
            'srcAmount': '12.22',
            'srcSymbol': 'btc',
            'status': 'succeeded',
        }

    def test_trade_in_usdtrls_market_when_reference_is_usdt_limit_exceeded_in_sell(self):
        usdt_rls_market = BaseMarketLimitationTest.create_usdt_rls_market()
        MarketLimitation.objects.create(
            interval=24,
            max_amount=decimal.Decimal('10'),
            market=usdt_rls_market,
            is_sell=True,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        BaseMarketLimitationTest.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=True,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=decimal.Decimal('5'),
            dst_amount=decimal.Decimal('2800000'),
        )
        quote = Quote(
            quote_id='dc2566913fdb4148a1357141b11ea150',
            base_currency=Currencies.usdt,
            quote_currency=Currencies.rls,
            reference_currency=Currencies.usdt,
            reference_amount=decimal.Decimal('6'),
            destination_amount=decimal.Decimal('7000000'),
            is_sell=True,
            client_order_id='cliOid',
            expires_at=ir_now() + timedelta(days=1),
            user_id=self.user.id,
        )
        Estimator.set_quote(quote, self.user.id)
        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea150'},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        # 5 previous trade + 6 new quote = 11 but limit is 10
        assert response.json() == {
            'code': 'MarketLimitationExceeded',
            'message': 'Market limitation exceeded.',
            'status': 'failed',
        }

    def test_trade_in_usdtrls_market_when_reference_is_rls_limit_exceeded_in_buy(self):
        usdt_rls_market = BaseMarketLimitationTest.create_usdt_rls_market()
        MarketLimitation.objects.create(
            interval=24,
            max_amount=decimal.Decimal('10'),
            market=usdt_rls_market,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        BaseMarketLimitationTest.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=decimal.Decimal('5'),
            dst_amount=decimal.Decimal('3500000'),
        )
        quote = Quote(
            quote_id='dc2566913fdb4148a1357141b11ea150',
            base_currency=Currencies.usdt,
            quote_currency=Currencies.rls,
            reference_currency=Currencies.rls,
            reference_amount=decimal.Decimal('4200000'),
            destination_amount=decimal.Decimal('6'),
            is_sell=False,
            client_order_id='cliOid',
            expires_at=ir_now() + timedelta(days=1),
            user_id=self.user.id,
        )
        Estimator.set_quote(quote, self.user.id)
        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea150'},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        # 5 previous trade + 6(4200000 rial) new quote = 11 but limit is 10
        assert response.json() == {
            'code': 'MarketLimitationExceeded',
            'message': 'Market limitation exceeded.',
            'status': 'failed',
        }

    def test_trade_in_usdtrls_market_when_reference_is_rls_limit_user_exceeded_in_buy(self):
        usdt_rls_market = BaseMarketLimitationTest.create_usdt_rls_market()
        MarketLimitation.objects.create(
            interval=24,
            max_amount=decimal.Decimal('10'),
            market=usdt_rls_market,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.USER,
        )
        BaseMarketLimitationTest.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=decimal.Decimal('5'),
            dst_amount=decimal.Decimal('3500000'),
        )
        quote = Quote(
            quote_id='dc2566913fdb4148a1357141b11ea150',
            base_currency=Currencies.usdt,
            quote_currency=Currencies.rls,
            reference_currency=Currencies.rls,
            reference_amount=decimal.Decimal('4200000'),
            destination_amount=decimal.Decimal('6'),
            is_sell=False,
            client_order_id='cliOid',
            expires_at=ir_now() + timedelta(days=1),
            user_id=self.user.id,
        )
        Estimator.set_quote(quote, self.user.id)
        response = self.client.post(
            path='/exchange/create-trade',
            data={'quoteId': 'dc2566913fdb4148a1357141b11ea150'},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        # 5 previous trade + 6(4200000 rial) new quote = 11 but limit is 10
        assert response.json() == {
            'code': 'UserLimitationExceeded',
            'message': 'User limitation exceeded.',
            'status': 'failed',
        }

    @responses.activate
    @override_settings(XCHANGE_MARKET_MAKER_USERNAME='system-convert')
    def test_trade_when_sum_trade_of_users_exceeded_market_limitation(self):
        user_2 = User.objects.create_user(username='user2')
        Token.objects.create(user=user_2)
        user_3 = User.objects.create_user(username='user3')
        Token.objects.create(user=user_3)
        usdtrls_market = BaseMarketLimitationTest.create_usdt_rls_market()
        MarketLimitation.objects.create(
            interval=24,
            max_amount=decimal.Decimal('9'),
            market=usdtrls_market,
            is_sell=False,
            limit_type=MarketLimitation.LIMIT_TYPE_CHOICES.ENTIRE,
        )
        MarketLimitation.objects.create(
            interval=24,
            max_amount=decimal.Decimal('7'),  # all user pass this limitation
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
            src_amount=decimal.Decimal('3'),
            dst_amount=decimal.Decimal('2100000'),
        )
        BaseMarketLimitationTest.create_trade(
            user=user_3,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=decimal.Decimal('4'),
            dst_amount=decimal.Decimal('2800000'),
        )
        BaseMarketLimitationTest.create_trade(
            user=self.user,
            status=ExchangeTrade.STATUS.succeeded,
            is_sell=False,
            src_currency=Currencies.usdt,
            dst_currency=Currencies.rls,
            src_amount=decimal.Decimal('1'),
            dst_amount=decimal.Decimal('700000'),
        )
        market_limitation_error = {
            'code': 'MarketLimitationExceeded',
            'message': 'Market limitation exceeded.',
            'status': 'failed',
        }
        url = '/exchange/create-trade'
        quote = Quote(
            quote_id='dc2566913fdb4148a1357141b12ea150',
            base_currency=Currencies.usdt,
            quote_currency=Currencies.rls,
            reference_currency=Currencies.usdt,
            reference_amount=decimal.Decimal('2'),
            destination_amount=decimal.Decimal('1400000'),
            is_sell=False,
            client_order_id='cliOid',
            expires_at=ir_now() + timedelta(days=1),
            user_id=self.user.id,
        )
        Estimator.set_quote(quote, self.user.id)
        # user 1 requested for 2 usdt, but there are 3 + 4 + 1 = 8 usdt trades and limitation is 9
        response = self.client.post(url, data={'quoteId': quote.quote_id})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == market_limitation_error
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {user_2.auth_token.key}'
        quote.user_id = user_2.id
        Estimator.set_quote(quote, user_2.id)
        # user 2 requested for 2 usdt, but there are 3 + 4 + 1 = 8 usdt trades and limitation is 9
        response = self.client.post(url, data={'quoteId': quote.quote_id})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == market_limitation_error
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {user_3.auth_token.key}'
        quote.user_id = user_3.id
        Estimator.set_quote(quote, user_3.id)
        # user 3 requested for 2 usdt, but there are 3 + 4 + 1 = 8 usdt trades and limitation is 9
        response = self.client.post(url, data={'quoteId': quote.quote_id})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == market_limitation_error
        wallet = Wallet.get_user_wallet(user_3, Currencies.rls)
        wallet.balance = decimal.Decimal('1000000')
        wallet.save()
        quote.reference_amount = decimal.Decimal('1')
        quote.destination_amount = decimal.Decimal('700000')
        Estimator.set_quote(quote, user_3.id)
        # 8 usdt are traded, limitation is 9 usdt. 9 - 8 = 1 usdt is available
        # user 3 requested 1 usdt and he can trades successfully
        self._mock_market_maker_response(is_sell=False, quote=quote)
        response = self.client.post(url, data={'quoteId': quote.quote_id})
        assert response.status_code == status.HTTP_200_OK
        output = response.json()
        assert output['status'] == 'ok'
        result = output['result']
        result.pop('id')
        result.pop('createdAt')
        assert result == {
            'dstAmount': '700000',
            'dstSymbol': 'rls',
            'isSell': False,
            'srcAmount': '1',
            'srcSymbol': 'usdt',
            'status': 'succeeded',
        }
        # total trades is 9 usdt and limitation in 9 usdt
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Token {user_2.auth_token.key}'
        quote.user_id = user_2.id
        Estimator.set_quote(quote, user_2.id)
        response = self.client.post(url, data={'quoteId': quote.quote_id})
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert response.json() == market_limitation_error
