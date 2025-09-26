from decimal import Decimal

import pytest
import requests
import responses
from django.core.cache import cache
from django.test import TestCase

from exchange.base.models import Currencies
from exchange.liquidator.broker_apis import SettlementPrices, SettlementRequest, SettlementStatus
from exchange.liquidator.errors import BrokerAPIError, DuplicatedOrderError, InvalidAPIResponse
from exchange.liquidator.models import Liquidation


class SettlementPricesAPITest(TestCase):
    def setUp(self):
        cache.clear()

    @responses.activate
    def test_error_not_respond(self):
        responses.add(
            responses.GET,
            url=SettlementPrices.get_base_url() + SettlementPrices.url,
            body=requests.ConnectionError(),
        )
        with pytest.raises(BrokerAPIError):
            SettlementPrices().request()

    @responses.activate
    def test_success(self):
        # wrong user or pass
        responses.get(
            url=SettlementPrices.get_base_url() + SettlementPrices.url,
            json={
                'result': [
                    {
                        'base': 'BTC',
                        'quote': 'USDT',
                        'symbol': 'BTC-USDT',
                        'exchange': 'Okx_futures',
                        'buy_price': '66540.2',
                        'sell_price': '66540.3',
                        'source_time': 1721477021222,
                        'update_time': 1721477021391,
                        'server_time': 1723886441627,
                    },
                    {
                        'base': 'DYDX',
                        'quote': 'USDT',
                        'symbol': 'DYDX-USDT',
                        'exchange': 'Okx_futures',
                        'buy_price': '1.443',
                        'sell_price': '1.444',
                        'source_time': 1721477021196,
                        'update_time': 1721477021366,
                        'server_time': 1723886441627,
                    },
                ],
                'message': 'success',
                'error': None,
                'hasError': False,
            },
            status=200,
        )
        data = SettlementPrices().request()
        assert data
        assert len(data) == 2


class SettlementRequestAPITest(TestCase):
    def setUp(self) -> None:
        cache.clear()

    @responses.activate
    def test_error_not_respond(self):
        responses.add(
            responses.POST,
            url=SettlementRequest.get_base_url() + SettlementRequest.url,
            body=requests.ConnectionError(),
        )
        liquidation = Liquidation(
            order_id='1',
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Liquidation.SIDES.buy,
            amount=Decimal('1'),
        )
        with pytest.raises(BrokerAPIError):
            SettlementRequest().request(liquidation)

    @responses.activate
    def test_duplicate_error(self):
        # wrong user or pass
        responses.post(
            url=SettlementRequest.get_base_url() + SettlementRequest.url,
            json={
                'result': None,
                'message': 'internal error',
                'error': 'duplicate clientId',
                'hasError': True,
            },
            status=400,
        )
        liquidation = Liquidation(
            order_id='1',
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Liquidation.SIDES.buy,
            amount=Decimal('1'),
        )
        with pytest.raises(DuplicatedOrderError):
            SettlementRequest().request(liquidation)

    @responses.activate
    def test_success(self):
        responses.post(
            url=SettlementRequest.get_base_url() + SettlementRequest.url,
            json={
                'result': {'liquidationId': 1012, 'clientId': 'clid_00000008', 'status': 'open'},
                'message': 'request accepted',
                'error': None,
                'hasError': False,
            },
            status=200,
        )
        liquidation = Liquidation(
            order_id='1',
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Liquidation.SIDES.buy,
            amount=Decimal('1'),
        )
        data = SettlementRequest().request(liquidation)
        assert data
        assert data == 1012


class SettlementStatusAPITest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.liquidation = Liquidation.objects.create(
            src_currency=Currencies.btc,
            dst_currency=Currencies.usdt,
            side=Liquidation.SIDES.buy,
            amount=Decimal('0.0000000001'),
            market_type=Liquidation.MARKET_TYPES.external,
            tracking_id='external_1',
        )

    def setUp(self) -> None:
        cache.clear()

    @responses.activate
    def test_error_not_respond(self):
        responses.add(
            responses.POST,
            url=SettlementStatus.get_base_url() + SettlementStatus.url,
            body=requests.ConnectionError(),
        )
        with pytest.raises(BrokerAPIError):
            SettlementStatus().request(self.liquidation)

    @responses.activate
    def test_error_invalid_respond(self):
        responses.get(
            url=SettlementStatus.get_base_url() + SettlementStatus.url,
            json={
                'result': {
                    'liquidationId': 1010,
                    'clientId': 'external_1',
                    'issue_time': '2024-11-04T07:36:45.38646644Z',
                },
                'message': 'success',
                'error': None,
                'hasError': False,
            },
            status=200,
        )
        with pytest.raises(InvalidAPIResponse):
            SettlementStatus().request(self.liquidation)

    @responses.activate
    def test_success(self):
        # wrong user or pass
        responses.get(
            url=SettlementStatus.get_base_url() + SettlementStatus.url,
            json={
                'result': {
                    'liquidationId': 1010,
                    'clientId': 'external_1',
                    'baseCurrency': 'btc',
                    'quoteCurrency': 'usdt',
                    'side': 'buy',
                    'amount': '0.0000000001',
                    'price': '10',
                    'filledAmount': '0',
                    'averageFillPrice': '0',
                    'status': 'open',
                    'createdAt': '2024-11-04T07:36:45.38646644Z',
                    'expiredAt': '2024-11-04T07:37:15.38646644Z',
                    'serverTime': '2024-11-04T07:36:50.38646644Z',
                },
                'message': 'success',
                'error': None,
                'hasError': False,
            },
            status=200,
        )
        assert SettlementStatus().request(self.liquidation).status == 'open'

    def test_sign_generation(self):
        params = {'timestamp': 1705776237000}
        body = {
            'quoteId': 'qid_0001',
            'clientId': 'clid_00000001',
            'baseCurrency': 'btc',
            'quoteCurrency': 'usdt',
            'referenceCurrency': 'usdt',
            'side': 'buy',
            'referenceCurrencyAmount': 10,
        }

        sign = SettlementRequest.generate_sign(params, body)
        assert sign == 'cisavRXYvHXd1SPdy9iT/Q10C8xLIzstuGbe+IrPhrk='
